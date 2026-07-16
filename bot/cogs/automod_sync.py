"""Native Discord AutoMod sync cog.

Mirrors a guild's moderation config into REAL Discord AutoMod rules via the API
(``guild.create_automod_rule`` / ``rule.edit`` / ``rule.delete``). This is what
earns an app the **"Uses AutoMod" badge** — the bot's own on_message filtering
does not count. Native AutoMod also blocks messages *before* they are sent, so it
complements the in-bot moderation rather than conflicting with it.

Mapping (all with a BLOCK_MESSAGE action):
  banned_words / anti_invite / anti_link  → one KEYWORD rule (keywords + regexes)
  anti_spam_enabled                        → one SPAM rule
  anti_mention (max_mentions)              → one MENTION_SPAM rule

The bot only manages rules it created (identified by a fixed name per type), so
it never touches a server's other AutoMod rules. `exempt_role_ids` /
`ignored_channel_ids` map to the AutoMod rule's exemptions.

Backend contract (X-Bot-Token auth):
  GET /api/bot/automod/pending             → { guilds: [{ guild_id, automod_native, banned_words,
                                               anti_invite, anti_link, anti_spam_enabled,
                                               anti_mention, max_mentions, exempt_role_ids,
                                               ignored_channel_ids }] }
  PUT /api/bot/guilds/{id}/automod/applied  body { status: 'ok'|'error', status_message }

status_message is a short CODE the dashboard translates: missing_permission,
rule_limit, not_in_guild, error.

Requires the MANAGE_GUILD permission (in the invite bitmask). Logging: "[automod]".
"""

import discord
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put


# Fixed names so the bot recognises + reconciles only its own rules.
NAME_WORDS = "ProjectX • Wortfilter"
NAME_SPAM = "ProjectX • Spam-Schutz"
NAME_MENTION = "ProjectX • Massen-Erwähnungen"
BLOCK_MSG = "Diese Nachricht wurde von ProjectX AutoMod blockiert."

# RE2-compatible patterns (Discord AutoMod uses RE2; each ≤ 260 chars, ≤ 10 total).
INVITE_PATTERNS = [r"discord\.gg/[a-zA-Z0-9-]+", r"discord(?:app)?\.com/invite/[a-zA-Z0-9-]+"]
LINK_PATTERN = r"https?://[^\s]+"


def _block_action():
    return discord.AutoModRuleAction(
        type=discord.AutoModRuleActionType.block_message, custom_message=BLOCK_MSG
    )


class AutoModSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.sync_loop.start()

    def cog_unload(self):
        self.sync_loop.cancel()

    @tasks.loop(seconds=config.AUTOMOD_POLL_INTERVAL)
    async def sync_loop(self):
        await self._sync()

    @sync_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()

    async def _sync(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/automod/pending")
        for g in (data or {}).get("guilds", []) or []:
            gid = str(g.get("guild_id") or "")
            if not gid.isdigit():
                continue
            guild = self.bot.get_guild(int(gid))
            if guild is None:
                continue  # not in guild (yet) → retry later
            status, message = await self._sync_one(guild, g)
            await bot_put(
                self.backend_url, self.api_key,
                f"/api/bot/guilds/{gid}/automod/applied",
                {"status": status, "status_message": message},
            )

    async def _sync_one(self, guild, cfg):
        me = guild.me
        if me is None or not me.guild_permissions.manage_guild:
            return "error", "missing_permission"

        try:
            existing = {r.name: r for r in await guild.fetch_automod_rules()}
        except discord.Forbidden:
            return "error", "missing_permission"
        except discord.HTTPException as exc:
            print(f"[automod] fetch rules failed in {guild.id}: {exc}")
            return "error", "error"

        native = bool(cfg.get("automod_native"))
        exempt_roles = [discord.Object(id=int(r)) for r in (cfg.get("exempt_role_ids") or []) if str(r).isdigit()][:20]
        exempt_channels = [discord.Object(id=int(c)) for c in (cfg.get("ignored_channel_ids") or []) if str(c).isdigit()][:50]

        # --- build desired triggers (None = rule should not exist) ---
        desired = {NAME_WORDS: None, NAME_SPAM: None, NAME_MENTION: None}
        if native:
            words = _clean_keywords(cfg.get("banned_words") or [])
            regexes = []
            if cfg.get("anti_invite"):
                regexes += INVITE_PATTERNS
            if cfg.get("anti_link"):
                regexes.append(LINK_PATTERN)
            regexes = regexes[:10]
            if words or regexes:
                desired[NAME_WORDS] = discord.AutoModTrigger(
                    type=discord.AutoModRuleTriggerType.keyword,
                    keyword_filter=words, regex_patterns=regexes,
                )
            if cfg.get("anti_spam_enabled"):
                desired[NAME_SPAM] = discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.spam)
            if cfg.get("anti_mention"):
                limit = max(1, min(50, int(cfg.get("max_mentions") or 5)))
                desired[NAME_MENTION] = discord.AutoModTrigger(
                    type=discord.AutoModRuleTriggerType.mention_spam, mention_limit=limit,
                )

        errors = []
        for name, trigger in desired.items():
            rule = existing.get(name)
            try:
                if trigger is not None:
                    if rule is None:
                        await guild.create_automod_rule(
                            name=name,
                            event_type=discord.AutoModRuleEventType.message_send,
                            trigger=trigger,
                            actions=[_block_action()],
                            enabled=True,
                            exempt_roles=exempt_roles,
                            exempt_channels=exempt_channels,
                            reason="ProjectX AutoMod sync",
                        )
                    else:
                        await rule.edit(
                            trigger=trigger,
                            actions=[_block_action()],
                            enabled=True,
                            exempt_roles=exempt_roles,
                            exempt_channels=exempt_channels,
                            reason="ProjectX AutoMod sync",
                        )
                elif rule is not None:
                    await rule.delete(reason="ProjectX AutoMod sync (disabled)")
            except discord.Forbidden:
                errors.append("missing_permission")
            except discord.HTTPException as exc:
                # 400 with rules-limit code, or other API errors.
                if getattr(exc, "status", None) == 400 and "maximum number" in str(exc).lower():
                    errors.append("rule_limit")
                else:
                    print(f"[automod] {name} sync failed in {guild.id}: {exc}")
                    errors.append("error")

        if errors:
            # De-dupe while keeping order.
            uniq = list(dict.fromkeys(errors))
            return "error", ",".join(uniq)[:300]
        return "ok", ""


def _clean_keywords(words):
    """Sanitize for Discord: 1–60 chars each, deduped, max 1000."""
    out = []
    seen = set()
    for w in words:
        s = str(w).strip()[:60]
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
        if len(out) >= 1000:
            break
    return out


async def setup(bot):
    await bot.add_cog(AutoModSync(bot))
