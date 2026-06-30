"""Music cog (Pro) — Lavalink-backed voice playback via wavelink.

Slash commands: /play /skip /stop /pause /resume /queue /nowplaying /volume
/loop /shuffle. Sources are SoundCloud / Bandcamp / Twitch / direct HTTP+radio
URLs — **YouTube is intentionally not used** (disabled on the Lavalink side and
blocked here defensively).

The bot pushes a live snapshot of the player (current track + queue + paused +
volume) to the backend so the dashboard can show "now playing", and polls a
control-command queue so the dashboard can pause/skip/stop/set volume/etc.

Safety: if wavelink is not installed or LAVALINK_HOST is unset, the cog loads but
stays inert (no node, no loops) — the rest of the bot is unaffected.

Backend contract (X-Bot-Token auth):
  GET    /api/bot/guilds/{gid}/settings/music   → raw settings (or disabled shape)
  PUT    /api/bot/guilds/{gid}/music/state      body { voice_channel_id, ... }
  GET    /api/bot/music/commands                → { commands: [{ id, guild_id, action, payload }] }
  DELETE /api/bot/music/commands/{id}

Logging prefix: "[music]".
"""

import asyncio

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils.backend import bot_get, bot_put, bot_delete, fetch_bot_settings
from utils.bot_i18n import t, lang_for

try:
    import wavelink
    WAVELINK_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    wavelink = None
    WAVELINK_AVAILABLE = False


MUSIC_COLOR = 0x1DB954  # spotify-ish green
MAX_QUEUE_DISPLAY = 10

# Hosts we always refuse, even if a URL is pasted directly.
BLOCKED_HOSTS = ("youtube.com", "youtu.be", "music.youtube.com")
# Map an allow_* setting flag to substrings that identify the source host.
SOURCE_HOSTS = {
    "allow_soundcloud": ("soundcloud.com",),
    "allow_bandcamp": ("bandcamp.com",),
    "allow_twitch": ("twitch.tv",),
}


def _loop_to_str(mode):
    if wavelink is None:
        return "off"
    if mode == wavelink.QueueMode.loop:
        return "track"
    if mode == wavelink.QueueMode.loop_all:
        return "queue"
    return "off"


def _str_to_loop(value):
    if value == "track":
        return wavelink.QueueMode.loop
    if value == "queue":
        return wavelink.QueueMode.loop_all
    return wavelink.QueueMode.normal


def _track_dict(track):
    if track is None:
        return None
    return {
        "title": getattr(track, "title", "?"),
        "author": getattr(track, "author", None),
        "uri": getattr(track, "uri", None),
        "length_ms": getattr(track, "length", 0),
        "artwork": getattr(track, "artwork", None),
        "source": getattr(track, "source", None),
    }


def _fmt_ms(ms):
    s = int((ms or 0) / 1000)
    return f"{s // 60}:{s % 60:02d}"


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self._idle = {}  # guild_id -> seconds idle (auto-disconnect tracking)
        self.enabled = WAVELINK_AVAILABLE and bool(config.LAVALINK_HOST)
        if self.enabled:
            self.control_loop.start()

    def cog_unload(self):
        if self.enabled:
            self.control_loop.cancel()

    async def cog_load(self):
        if self.enabled:
            self.bot.loop.create_task(self._connect_nodes())

    async def _connect_nodes(self):
        await self.bot.wait_until_ready()
        scheme = "https" if config.LAVALINK_SECURE else "http"
        uri = f"{scheme}://{config.LAVALINK_HOST}:{config.LAVALINK_PORT}"
        try:
            node = wavelink.Node(uri=uri, password=config.LAVALINK_PASSWORD)
            await wavelink.Pool.connect(nodes=[node], client=self.bot, cache_capacity=100)
            print(f"[music] connecting to Lavalink at {uri}")
        except Exception as exc:
            print(f"[music] Lavalink connection failed: {exc}")

    # ---- helpers -----------------------------------------------------------

    async def _settings(self, guild_id):
        return await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "music")

    def _player(self, guild) -> "wavelink.Player | None":
        return guild.voice_client if guild and isinstance(guild.voice_client, wavelink.Player) else None

    def _is_dj(self, member, settings):
        perms = getattr(member, "guild_permissions", None)
        if perms and (perms.manage_guild or perms.administrator):
            return True
        dj = settings.get("dj_role_id")
        if not dj:
            return True  # no DJ role configured → everyone may control
        return any(str(r.id) == str(dj) for r in getattr(member, "roles", []))

    def _source_allowed(self, query, settings):
        q = (query or "").lower()
        if not q.startswith("http"):
            return True  # plain search → goes to SoundCloud
        if any(h in q for h in BLOCKED_HOSTS):
            return False
        for flag, hosts in SOURCE_HOSTS.items():
            if any(h in q for h in hosts):
                return bool(settings.get(flag, True))
        # generic http/radio stream
        return bool(settings.get("allow_http", True))

    async def _push_state(self, guild):
        player = self._player(guild)
        if player is None:
            await bot_put(self.backend_url, self.api_key,
                          f"/api/bot/guilds/{guild.id}/music/state", {"voice_channel_id": None})
            return
        snapshot = {
            "voice_channel_id": str(player.channel.id) if player.channel else None,
            "text_channel_id": str(player.home.id) if getattr(player, "home", None) else None,
            "current": _track_dict(player.current),
            "queue": [_track_dict(t) for t in list(player.queue)[:50]],
            "paused": bool(player.paused),
            "volume": int(player.volume),
            "loop_mode": _loop_to_str(player.queue.mode),
            "position_ms": int(player.position),
        }
        await bot_put(self.backend_url, self.api_key, f"/api/bot/guilds/{guild.id}/music/state", snapshot)

    # ---- slash commands ----------------------------------------------------

    @app_commands.command(name="play", description="Play or queue a track (SoundCloud / Bandcamp / URL).")
    @app_commands.describe(query="Search text or a SoundCloud/Bandcamp/stream URL.")
    @app_commands.guild_only()
    async def play(self, interaction: discord.Interaction, query: str):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not self.enabled:
            await interaction.response.send_message(t(lang, "music.noNode"), ephemeral=True)
            return
        settings = await self._settings(interaction.guild.id)
        if not settings or not settings.get("enabled"):
            await interaction.response.send_message(t(lang, "music.notEnabled"), ephemeral=True)
            return
        voice = getattr(interaction.user, "voice", None)
        if not voice or not voice.channel:
            await interaction.response.send_message(t(lang, "music.notInVoice"), ephemeral=True)
            return
        if not self._source_allowed(query, settings):
            await interaction.response.send_message(t(lang, "music.sourceBlocked"), ephemeral=True)
            return

        await interaction.response.defer()
        player = self._player(interaction.guild)
        if player is None:
            try:
                player = await voice.channel.connect(cls=wavelink.Player)
            except Exception as exc:
                print(f"[music] connect failed in {interaction.guild.id}: {exc}")
                await interaction.followup.send(t(lang, "music.noNode"), ephemeral=True)
                return
            player.autoplay = wavelink.AutoPlayMode.partial  # play queue, no YouTube recommendations
            player.home = interaction.channel
            try:
                await player.set_volume(int(settings.get("default_volume", 100)))
            except Exception:
                pass

        # URL → search resolves it; plain text → SoundCloud search.
        try:
            if query.lower().startswith("http"):
                results = await wavelink.Playable.search(query)
            else:
                results = await wavelink.Playable.search(query, source=wavelink.TrackSource.SoundCloud)
        except Exception as exc:
            print(f"[music] search failed: {exc}")
            results = None
        if not results:
            await interaction.followup.send(t(lang, "music.notFound"), ephemeral=True)
            return

        max_queue = int(settings.get("max_queue", 100))
        if isinstance(results, wavelink.Playlist):
            added = 0
            for tr in results.tracks:
                if len(player.queue) >= max_queue:
                    break
                player.queue.put(tr)
                added += 1
            msg = t(lang, "music.addedPlaylist", count=added, name=results.name)
        else:
            track = results[0]
            if len(player.queue) >= max_queue:
                await interaction.followup.send(t(lang, "music.queueFull", max=max_queue), ephemeral=True)
                return
            player.queue.put(track)
            msg = t(lang, "music.added", title=track.title)

        if not player.playing:
            await player.play(player.queue.get())
        await interaction.followup.send(msg)
        self._idle.pop(interaction.guild.id, None)
        await self._push_state(interaction.guild)

    @app_commands.command(name="skip", description="Skip the current track.")
    @app_commands.guild_only()
    async def skip(self, interaction: discord.Interaction):
        await self._simple(interaction, "skip")

    @app_commands.command(name="stop", description="Stop playback, clear the queue and leave.")
    @app_commands.guild_only()
    async def stop(self, interaction: discord.Interaction):
        await self._simple(interaction, "stop")

    @app_commands.command(name="pause", description="Pause playback.")
    @app_commands.guild_only()
    async def pause(self, interaction: discord.Interaction):
        await self._simple(interaction, "pause")

    @app_commands.command(name="resume", description="Resume playback.")
    @app_commands.guild_only()
    async def resume(self, interaction: discord.Interaction):
        await self._simple(interaction, "resume")

    @app_commands.command(name="shuffle", description="Shuffle the queue.")
    @app_commands.guild_only()
    async def shuffle(self, interaction: discord.Interaction):
        await self._simple(interaction, "shuffle")

    async def _simple(self, interaction, action):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not self.enabled:
            await interaction.response.send_message(t(lang, "music.noNode"), ephemeral=True)
            return
        settings = await self._settings(interaction.guild.id)
        player = self._player(interaction.guild)
        if player is None:
            await interaction.response.send_message(t(lang, "music.nothingPlaying"), ephemeral=True)
            return
        if not self._is_dj(interaction.user, settings or {}):
            await interaction.response.send_message(t(lang, "music.djOnly"), ephemeral=True)
            return
        key = await self._apply(player, interaction.guild, action, None)
        await interaction.response.send_message(t(lang, key))
        await self._push_state(interaction.guild)

    @app_commands.command(name="volume", description="Set playback volume (0-150).")
    @app_commands.describe(level="Volume from 0 to 150.")
    @app_commands.guild_only()
    async def volume(self, interaction: discord.Interaction, level: int):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not self.enabled:
            await interaction.response.send_message(t(lang, "music.noNode"), ephemeral=True)
            return
        settings = await self._settings(interaction.guild.id)
        player = self._player(interaction.guild)
        if player is None:
            await interaction.response.send_message(t(lang, "music.nothingPlaying"), ephemeral=True)
            return
        if not self._is_dj(interaction.user, settings or {}):
            await interaction.response.send_message(t(lang, "music.djOnly"), ephemeral=True)
            return
        if level < 0 or level > 150:
            await interaction.response.send_message(t(lang, "music.volumeRange"), ephemeral=True)
            return
        await player.set_volume(level)
        await interaction.response.send_message(t(lang, "music.volumeSet", level=level))
        await self._push_state(interaction.guild)

    @app_commands.command(name="loop", description="Set loop mode.")
    @app_commands.describe(mode="What to loop.")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Off", value="off"),
        app_commands.Choice(name="Track", value="track"),
        app_commands.Choice(name="Queue", value="queue"),
    ])
    @app_commands.guild_only()
    async def loop(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        if not self.enabled:
            await interaction.response.send_message(t(lang, "music.noNode"), ephemeral=True)
            return
        settings = await self._settings(interaction.guild.id)
        player = self._player(interaction.guild)
        if player is None:
            await interaction.response.send_message(t(lang, "music.nothingPlaying"), ephemeral=True)
            return
        if not self._is_dj(interaction.user, settings or {}):
            await interaction.response.send_message(t(lang, "music.djOnly"), ephemeral=True)
            return
        player.queue.mode = _str_to_loop(mode.value)
        await interaction.response.send_message(t(lang, "music.loopSet", mode=mode.value))
        await self._push_state(interaction.guild)

    @app_commands.command(name="nowplaying", description="Show the current track.")
    @app_commands.guild_only()
    async def nowplaying(self, interaction: discord.Interaction):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        player = self._player(interaction.guild)
        if not self.enabled or player is None or player.current is None:
            await interaction.response.send_message(t(lang, "music.nothingPlaying"), ephemeral=True)
            return
        await interaction.response.send_message(embed=self._np_embed(player, lang))

    @app_commands.command(name="queue", description="Show the current queue.")
    @app_commands.guild_only()
    async def queue(self, interaction: discord.Interaction):
        lang = await lang_for(self.backend_url, self.api_key, interaction.guild.id)
        player = self._player(interaction.guild)
        if not self.enabled or player is None or (player.current is None and not player.queue):
            await interaction.response.send_message(t(lang, "music.queueEmpty"), ephemeral=True)
            return
        embed = discord.Embed(title=t(lang, "music.queueHeader"), color=MUSIC_COLOR)
        if player.current:
            embed.add_field(name=t(lang, "music.nowPlaying"),
                            value=f"[{player.current.title}]({player.current.uri or 'https://discord.com'})", inline=False)
        lines = []
        for i, tr in enumerate(list(player.queue)[:MAX_QUEUE_DISPLAY], start=1):
            lines.append(f"`{i}.` {tr.title} · `{_fmt_ms(tr.length)}`")
        more = len(player.queue) - MAX_QUEUE_DISPLAY
        if more > 0:
            lines.append(t(lang, "music.queueMore", count=more))
        if lines:
            embed.add_field(name=t(lang, "music.upNext"), value="\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed)

    def _np_embed(self, player, lang):
        cur = player.current
        embed = discord.Embed(title=t(lang, "music.nowPlaying"),
                              description=f"[{cur.title}]({cur.uri or 'https://discord.com'})", color=MUSIC_COLOR)
        if getattr(cur, "author", None):
            embed.add_field(name=t(lang, "music.artist"), value=str(cur.author), inline=True)
        embed.add_field(name=t(lang, "music.duration"), value=_fmt_ms(cur.length), inline=True)
        embed.add_field(name=t(lang, "music.volumeLabel"), value=f"{player.volume}%", inline=True)
        if getattr(cur, "artwork", None):
            embed.set_thumbnail(url=cur.artwork)
        return embed

    # ---- control actions (shared by slash + dashboard) ---------------------

    async def _apply(self, player, guild, action, payload):
        """Run a control action on a player. Returns an i18n key for the reply."""
        if action == "skip":
            await player.skip(force=True)
            return "music.skipped"
        if action == "stop":
            player.queue.clear()
            await player.disconnect()
            self._idle.pop(guild.id, None)
            return "music.stopped"
        if action == "pause":
            await player.pause(True)
            return "music.paused"
        if action == "resume":
            await player.pause(False)
            return "music.resumed"
        if action == "shuffle":
            player.queue.shuffle()
            return "music.shuffled"
        if action == "clear":
            player.queue.clear()
            return "music.cleared"
        if action == "volume":
            try:
                await player.set_volume(max(0, min(150, int(payload))))
            except Exception:
                pass
            return "music.volumeSet"
        if action == "loop":
            player.queue.mode = _str_to_loop(str(payload))
            return "music.loopSet"
        if action == "remove":
            try:
                idx = int(payload)
                if 0 <= idx < len(player.queue):
                    del player.queue[idx]
            except Exception:
                pass
            return "music.removed"
        return "music.nothingPlaying"

    # ---- dashboard control poll --------------------------------------------

    @tasks.loop(seconds=max(2, config.MUSIC_POLL_INTERVAL))
    async def control_loop(self):
        if not self.api_key or not self.backend_url:
            return
        data = await bot_get(self.backend_url, self.api_key, "/api/bot/music/commands")
        for cmd in (data or {}).get("commands", []) or []:
            try:
                guild = self.bot.get_guild(int(cmd["guild_id"]))
                player = self._player(guild) if guild else None
                if player is not None:
                    await self._apply(player, guild, cmd.get("action"), cmd.get("payload"))
                    await self._push_state(guild)
            except Exception as exc:
                print(f"[music] control cmd {cmd.get('id')} failed: {exc}")
            finally:
                await bot_delete(self.backend_url, self.api_key, f"/api/bot/music/commands/{cmd.get('id')}")

    @control_loop.before_loop
    async def _before_control(self):
        await self.bot.wait_until_ready()

    # ---- wavelink events ---------------------------------------------------

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload):
        print(f"[music] Lavalink node ready: {getattr(payload.node, 'identifier', '?')}")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload):
        player = payload.player
        if player is None:
            return
        self._idle.pop(player.guild.id, None)
        home = getattr(player, "home", None)
        if home is not None:
            try:
                lang = await lang_for(self.backend_url, self.api_key, player.guild.id)
                await home.send(embed=self._np_embed(player, lang))
            except Exception:
                pass
        await self._push_state(player.guild)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload):
        player = payload.player
        if player is None:
            return
        # Nothing left → start idle countdown handled by the inactivity check.
        await self._push_state(player.guild)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Auto-leave when the bot is left alone in the voice channel.
        if not self.enabled or member.guild is None:
            return
        player = self._player(member.guild)
        if player is None or player.channel is None:
            return
        humans = [m for m in player.channel.members if not m.bot]
        if not humans:
            await asyncio.sleep(2)
            player = self._player(member.guild)
            if player and player.channel and not [m for m in player.channel.members if not m.bot]:
                await player.disconnect()
                await self._push_state(member.guild)


async def setup(bot):
    await bot.add_cog(Music(bot))
