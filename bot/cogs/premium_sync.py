"""Premium SKU sync cog.

Reads the application's Discord Premium-App-Subscription entitlements and maps
each guild's active entitlement(s) to a tier (free/basic/pro), then pushes the
result to the backend so premium modules unlock/lock per guild.

Mechanism (Polling — no public webhook needed for self-hosting):
  - GET https://discord.com/api/v10/applications/{APP_ID}/entitlements?exclude_ended=true
    with the bot token. Guild subscriptions carry `guild_id`; `sku_id` maps to a
    tier via config.SKU_BASIC_ID / SKU_PRO_ID. Highest tier per guild wins.
  - PUT /api/bot/premium  { entitlements: [{ guild_id, tier, until }] } → backend
    sets sku-sourced premium and downgrades guilds no longer entitled. Owner-set
    (manual) premium is left untouched by the backend.

Inert when no SKU IDs are configured (owner-override in the dashboard still works).

Logging prefix: "[premium]".
"""

import datetime

import aiohttp
from discord.ext import commands, tasks

import config
from utils.backend import bot_put, bot_get


DISCORD_API = "https://discord.com/api/v10"


def _iso_to_unix(value):
    """Discord ISO-8601 timestamp → unix seconds (or None)."""
    if not value:
        return None
    try:
        # e.g. "2026-07-01T00:00:00+00:00" / "...Z"
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(cleaned)
        return int(dt.timestamp())
    except Exception:
        return None


class PremiumSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.app_id = config.APPLICATION_ID
        # sku_id → tier. Highest-rank tier wins per guild.
        self.sku_tiers = {}
        if config.SKU_BASIC_ID:
            self.sku_tiers[str(config.SKU_BASIC_ID)] = "basic"
        if config.SKU_PRO_ID:
            self.sku_tiers[str(config.SKU_PRO_ID)] = "pro"
        self._tier_rank = {"free": 0, "basic": 1, "pro": 2}
        # Start the loop whenever the backend is reachable: _sync() no-ops without
        # SKU IDs, but expiry reminders run for manual/code premium regardless.
        if self.api_key and self.backend_url:
            self.sync_loop.start()
        if not self._enabled():
            print("[premium] no SKU IDs configured — SKU sync inert (manual/code premium + reminders still work)")

    def _enabled(self):
        return bool(self.api_key and self.backend_url and self.app_id and self.sku_tiers)

    def cog_unload(self):
        if self.sync_loop.is_running():
            self.sync_loop.cancel()

    @tasks.loop(seconds=max(60, config.PREMIUM_POLL_INTERVAL))
    async def sync_loop(self):
        await self._sync()
        # Expiry reminders work for ALL premium sources (manual/code/sku), so
        # they run even when SKU sync is inert.
        await self._remind_expiring()

    async def _remind_expiring(self):
        """DM the owner of each guild whose premium expires within ~3 days."""
        if not self.api_key or not self.backend_url:
            return
        try:
            data = await bot_get(self.backend_url, self.api_key, "/api/bot/premium/expiring")
        except Exception as exc:
            print(f"[premium] expiring fetch error: {exc}")
            return
        for g in (data or {}).get("guilds", []):
            gid = g.get("guild_id")
            guild = self.bot.get_guild(int(gid)) if gid and str(gid).isdigit() else None
            if guild is None:
                continue
            try:
                owner = guild.owner or await guild.fetch_member(guild.owner_id)
            except Exception:
                owner = None
            if owner is None:
                continue
            tier = str(g.get("premium_tier") or "premium").capitalize()
            until = g.get("premium_until")
            when = f"<t:{int(until)}:D>" if until else "soon"
            try:
                await owner.send(
                    f"⏳ Heads up: **{guild.name}**'s **{tier}** subscription expires {when}. "
                    f"Renew it in the dashboard to keep your premium modules active."
                )
                await bot_put(self.backend_url, self.api_key, f"/api/bot/premium/{gid}/reminded", {})
            except Exception as exc:
                print(f"[premium] reminder DM to owner of {gid} failed: {exc}")

    @sync_loop.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    async def _fetch_entitlements(self):
        """Return the application's active entitlements (paginated)."""
        headers = {"Authorization": f"Bot {config.DISCORD_TOKEN}"}
        results = []
        after = None
        try:
            async with aiohttp.ClientSession() as session:
                for _ in range(20):  # hard page cap (20 * 100 = 2000)
                    params = {"exclude_ended": "true", "limit": "100"}
                    if after:
                        params["after"] = after
                    url = f"{DISCORD_API}/applications/{self.app_id}/entitlements"
                    async with session.get(url, headers=headers, params=params,
                                           timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            print(f"[premium] entitlements HTTP {resp.status} — {body[:200]}")
                            break
                        page = await resp.json()
                    if not page:
                        break
                    results.extend(page)
                    if len(page) < 100:
                        break
                    after = page[-1].get("id")
        except Exception as exc:
            print(f"[premium] failed to fetch entitlements: {exc}")
            return None
        return results

    async def _sync(self):
        if not self._enabled():
            return
        entitlements = await self._fetch_entitlements()
        if entitlements is None:
            return

        # Reduce to the highest tier per guild (+ latest expiry for that tier).
        best = {}  # guild_id → {tier, until}
        for ent in entitlements:
            if ent.get("deleted"):
                continue
            guild_id = ent.get("guild_id")
            sku_id = str(ent.get("sku_id") or "")
            tier = self.sku_tiers.get(sku_id)
            if not guild_id or not tier:
                continue
            until = _iso_to_unix(ent.get("ends_at"))
            cur = best.get(guild_id)
            if cur is None or self._tier_rank[tier] > self._tier_rank[cur["tier"]]:
                best[guild_id] = {"tier": tier, "until": until}

        payload = [
            {"guild_id": str(gid), "tier": v["tier"], "until": v["until"]}
            for gid, v in best.items()
        ]
        # Always PUT (even when empty) so the backend can downgrade guilds whose
        # sku entitlement lapsed since the last sync.
        result = await bot_put(self.backend_url, self.api_key, "/api/bot/premium",
                               {"entitlements": payload})
        if result:
            print(f"[premium] synced {result.get('synced', 0)} entitled, "
                  f"downgraded {result.get('downgraded', 0)}")


async def setup(bot):
    await bot.add_cog(PremiumSync(bot))
