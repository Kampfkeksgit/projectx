"""Statistics cog — keeps "stats channels" (voice/text channels whose name shows
a live count) up to date and records periodic snapshots for the dashboard graphs.

Backend contract (all via utils.backend helpers, X-Bot-Token auth):

  GET /api/bot/stats/configs
      → { "configs": [ { guild_id, update_interval (minutes),
                         category_id (str|null), auto_category (bool),
                         category_name (str), counters: [ counter, … ] } ] }
      Each `counter`:
        { id, guild_id, type, channel_id (str|null), channel_kind ('voice'|'text'),
          name_template (str, may be '' → default), auto_create (bool),
          position (int), enabled (bool) }
      type ∈ members | humans | bots | online | offline | boosters | channels | roles

  PUT  /api/bot/guilds/{guild_id}/stats/category
       body { category_id }  → persists an auto-created category id.

  PUT  /api/bot/guilds/{guild_id}/stats/counters/{counter_id}/channel
       body { channel_id }  → persists an auto-created channel id.

  POST /api/bot/guilds/{guild_id}/stats/snapshot
       body { members, humans, bots, online, offline, boosters }

Notes / limitations:
  - online/offline require the privileged PRESENCE intent (enabled in main.py and
    in the Discord Developer Portal). Without it every member reads as offline.
  - Discord rate-limits channel renames to ~2 / 10 min per channel, so the
    per-guild `update_interval` defaults to 10 min and we only edit a channel
    when its name actually changed.
  - Every network/Discord call is guarded; a single bad counter never aborts the
    cycle and the loop never crashes. Logging prefix: "[stats]".
"""

import time

import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put, bot_post


# Fixed loop tick; the per-guild update_interval gates how often we actually act.
LOOP_INTERVAL_SECONDS = 60
CHANNEL_NAME_MAX = 100

DEFAULT_TEMPLATES = {
    "members": "Members: {count}",
    "humans": "Humans: {count}",
    "bots": "Bots: {count}",
    "online": "Online: {count}",
    "offline": "Offline: {count}",
    "boosters": "Boosters: {count}",
    "channels": "Channels: {count}",
    "roles": "Roles: {count}",
}


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        # guild_id (str) → unix ts of the last successful update.
        self._last_run = {}
        self.update_loop.start()

    def cog_unload(self):
        self.update_loop.cancel()

    @tasks.loop(seconds=LOOP_INTERVAL_SECONDS)
    async def update_loop(self):
        await self._run_cycle()

    @update_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _run_cycle(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/stats/configs")
        if not data:
            return
        configs = data.get("configs") or []
        now = int(time.time())
        for cfg in configs:
            try:
                await self._process_guild(cfg, now)
            except Exception as exc:  # never let one guild abort the cycle
                print(f"[stats] guild {cfg.get('guild_id')} cycle error: {exc}")

    async def _process_guild(self, cfg, now):
        guild_id = str(cfg.get("guild_id"))
        interval_min = cfg.get("update_interval") or 10
        counters = cfg.get("counters") or []
        if not counters:
            return

        # Gate on the per-guild interval (with a small slack so a 10-min interval
        # isn't pushed to 11 by the 60s tick alignment).
        last = self._last_run.get(guild_id, 0)
        if now - last < interval_min * 60 - 5:
            return

        guild = self.bot.get_guild(int(guild_id))
        if guild is None:
            return

        counts = self._compute_counts(guild)

        # Resolve (or auto-create) the target category for the stats channels.
        category = await self._resolve_category(guild, cfg)

        # Process counters in their configured order (position ASC).
        ordered = sorted(counters, key=lambda c: c.get("position") or 0)
        managed = []  # bot-managed (auto_create) channels inside the category, in order
        for counter in ordered:
            try:
                channel = await self._apply_counter(guild, counter, counts, category)
                if channel is not None and counter.get("auto_create"):
                    managed.append(channel)
            except Exception as exc:
                print(f"[stats] counter {counter.get('id')} error in {guild_id}: {exc}")

        # Enforce the configured 1-2-3-4 ordering for the bot-managed channels.
        if category is not None and len(managed) > 1:
            await self._enforce_order(managed)

        # Record a snapshot for the dashboard graphs (best-effort).
        await bot_post(
            self.backend_url, self.api_key,
            f"/api/bot/guilds/{guild_id}/stats/snapshot",
            {
                "members": counts["members"],
                "humans": counts["humans"],
                "bots": counts["bots"],
                "online": counts["online"],
                "offline": counts["offline"],
                "boosters": counts["boosters"],
            },
        )

        self._last_run[guild_id] = now

    def _compute_counts(self, guild):
        members = guild.members
        humans = sum(1 for m in members if not m.bot)
        bots = sum(1 for m in members if m.bot)
        # status is only meaningful with the presence intent; without it every
        # member is 'offline' and online stays 0.
        online = sum(1 for m in members if str(m.status) != "offline")
        total = guild.member_count if guild.member_count is not None else len(members)
        offline = max(0, total - online)
        return {
            "members": total,
            "humans": humans,
            "bots": bots,
            "online": online,
            "offline": offline,
            "boosters": guild.premium_subscription_count or 0,
            "channels": len(guild.channels),
            "roles": len(guild.roles),
        }

    def _render_name(self, template, ctype, value):
        tmpl = template or DEFAULT_TEMPLATES.get(ctype, "{count}")
        if "{count}" in tmpl:
            name = tmpl.replace("{count}", str(value))
        else:
            name = f"{tmpl} {value}"
        return name[:CHANNEL_NAME_MAX]

    async def _resolve_category(self, guild, cfg):
        """Return the CategoryChannel stats channels should live in, or None.

        Uses the configured existing category if present; otherwise, when
        auto_category is on, creates one and writes its id back to the backend.
        """
        category_id = cfg.get("category_id")
        if category_id:
            existing = guild.get_channel(int(category_id))
            if isinstance(existing, discord.CategoryChannel):
                return existing

        if cfg.get("auto_category"):
            name = (cfg.get("category_name") or "📊 Statistics")[:100]
            try:
                category = await guild.create_category(name, reason="Stats category")
                await bot_put(
                    self.backend_url, self.api_key,
                    f"/api/bot/guilds/{guild.id}/stats/category",
                    {"category_id": str(category.id)},
                )
                return category
            except discord.Forbidden:
                print(f"[stats] missing Manage Channels permission in {guild.id} — cannot create category")
            except Exception as exc:
                print(f"[stats] create category failed in {guild.id}: {exc}")
        return None

    async def _apply_counter(self, guild, counter, counts, category):
        ctype = counter.get("type")
        if ctype not in counts:
            return None
        value = counts[ctype]
        name = self._render_name(counter.get("name_template"), ctype, value)

        channel = None
        channel_id = counter.get("channel_id")
        if channel_id:
            channel = guild.get_channel(int(channel_id))

        # Auto-create the channel on first run (or if it was deleted) inside the
        # resolved category.
        if channel is None and counter.get("auto_create"):
            channel = await self._create_channel(guild, counter.get("channel_kind"), name, category)
            if channel is not None:
                await bot_put(
                    self.backend_url, self.api_key,
                    f"/api/bot/guilds/{guild.id}/stats/counters/{counter.get('id')}/channel",
                    {"channel_id": str(channel.id)},
                )

        if channel is None:
            return None

        # Keep bot-managed channels inside the configured category. This also
        # self-heals channels that were auto-created in an earlier cycle before
        # the category existed (only moves when not already in it → no spam).
        if category is not None and counter.get("auto_create") and channel.category_id != category.id:
            try:
                await channel.edit(category=category, reason="Stats category")
            except discord.Forbidden:
                print(f"[stats] missing Manage Channels permission in {guild.id} — cannot move channel into category")
            except Exception as exc:
                print(f"[stats] move channel into category failed in {guild.id}: {exc}")

        # Only rename when the name actually changed (channel-rename rate limit).
        if channel.name != name:
            await channel.edit(name=name, reason="Stats counter update")

        return channel

    async def _create_channel(self, guild, kind, name, category):
        try:
            if kind == "text":
                return await guild.create_text_channel(name, category=category, reason="Stats counter")
            # Voice info-channel: lock it so members can't join/clutter it.
            overwrites = {guild.default_role: discord.PermissionOverwrite(connect=False)}
            return await guild.create_voice_channel(name, overwrites=overwrites, category=category, reason="Stats counter")
        except discord.Forbidden:
            print(f"[stats] missing Manage Channels permission in {guild.id} — cannot create channel")
        except Exception as exc:
            print(f"[stats] create channel failed in {guild.id}: {exc}")
        return None

    async def _enforce_order(self, channels):
        """Reorder the bot-managed channels so they match the configured order.

        `channels` is already in the desired order (counter position). We reassign
        the set of positions they currently occupy, so they end up 1-2-3-4 in that
        order without disturbing unrelated channels. Edits only on mismatch, so the
        steady state issues no requests (rate-limit friendly).
        """
        try:
            slots = sorted(ch.position for ch in channels)
        except Exception:
            return
        for idx, channel in enumerate(channels):
            target = slots[idx]
            if channel.position != target:
                try:
                    await channel.edit(position=target, reason="Stats channel order")
                except Exception as exc:
                    print(f"[stats] reorder failed for {channel.id}: {exc}")


async def setup(bot):
    await bot.add_cog(Stats(bot))
