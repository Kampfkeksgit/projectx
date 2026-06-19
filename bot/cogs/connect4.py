"""Connect Four cog.

Two members play Connect Four. Start with `!connect4 @opponent`. The bot posts a
6×7 board embed with a row of seven column buttons; players take turns clicking a
column to drop their disc. The bot detects horizontal / vertical / diagonal
four-in-a-rows, declares a winner (or a draw on a full board) and reports the
result to the backend's per-player game score.

Sessions live in memory keyed by a short token; button custom_ids encode that
token (`c4:<token>:<col>`) so clicks route back to the right game. Sessions do
not survive a bot restart — an old button then yields an ephemeral "expired".

Backend contract (X-Bot-Token auth):
  GET  /api/bot/guilds/{gid}/settings/games
       → { games_channel_id, connect4_enabled, ... }  (or None)
  POST /api/bot/guilds/{gid}/games/score
       body { user_id, game: "connect4", win: <bool> }

Logging prefix: "[connect4]".
"""

import time
import uuid

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_post
from utils.game_i18n import make_translator, lang_of


_STRINGS = {
    "en": {
        "not_enabled": "Connect Four is not enabled on this server.",
        "play_in_channel": "Please play in <#{channel}>.",
        "usage": "Usage: `!connect4 @opponent`",
        "no_bot": "You can't challenge a bot.",
        "no_self": "You can't play against yourself.",
        "cant_post": "I can't post in this channel.",
        "start_failed": "Couldn't start the game right now.",
        "expired": "This game has expired.",
        "not_your_game": "This isn't your game.",
        "not_your_turn": "It's not your turn yet.",
        "column_full": "That column is full — pick another.",
        "move_error": "Something went wrong with that move.",
        "embed_title": "🔴🟡 Connect Four",
        "field_players": "Players",
        "field_status": "Status",
        "status_wins": "{cell} <@{winner}> wins! 🎉",
        "status_draw": "It's a draw! 🤝",
        "status_turn": "{cell} <@{player}>'s turn",
    },
    "de": {
        "not_enabled": "Vier gewinnt ist auf diesem Server nicht aktiviert.",
        "play_in_channel": "Bitte spiele in <#{channel}>.",
        "usage": "Verwendung: `!connect4 @gegner`",
        "no_bot": "Du kannst keinen Bot herausfordern.",
        "no_self": "Du kannst nicht gegen dich selbst spielen.",
        "cant_post": "Ich kann in diesem Kanal nicht schreiben.",
        "start_failed": "Das Spiel konnte gerade nicht gestartet werden.",
        "expired": "Dieses Spiel ist abgelaufen.",
        "not_your_game": "Das ist nicht dein Spiel.",
        "not_your_turn": "Du bist noch nicht an der Reihe.",
        "column_full": "Diese Spalte ist voll — wähle eine andere.",
        "move_error": "Bei diesem Zug ist etwas schiefgelaufen.",
        "embed_title": "🔴🟡 Vier gewinnt",
        "field_players": "Spieler",
        "field_status": "Status",
        "status_wins": "{cell} <@{winner}> gewinnt! 🎉",
        "status_draw": "Unentschieden! 🤝",
        "status_turn": "{cell} <@{player}> ist am Zug",
    },
    "tr": {
        "not_enabled": "Dört Taş bu sunucuda etkin değil.",
        "play_in_channel": "Lütfen <#{channel}> kanalında oyna.",
        "usage": "Kullanım: `!connect4 @rakip`",
        "no_bot": "Bir bota meydan okuyamazsın.",
        "no_self": "Kendine karşı oynayamazsın.",
        "cant_post": "Bu kanala mesaj gönderemiyorum.",
        "start_failed": "Oyun şu anda başlatılamadı.",
        "expired": "Bu oyunun süresi doldu.",
        "not_your_game": "Bu senin oyunun değil.",
        "not_your_turn": "Henüz sıra sende değil.",
        "column_full": "Bu sütun dolu — başka bir tane seç.",
        "move_error": "Bu hamlede bir şeyler ters gitti.",
        "embed_title": "🔴🟡 Dört Taş",
        "field_players": "Oyuncular",
        "field_status": "Durum",
        "status_wins": "{cell} <@{winner}> kazandı! 🎉",
        "status_draw": "Berabere! 🤝",
        "status_turn": "Sıra {cell} <@{player}> oyuncusunda",
    },
    "ru": {
        "not_enabled": "«Четыре в ряд» не включена на этом сервере.",
        "play_in_channel": "Пожалуйста, играй в <#{channel}>.",
        "usage": "Использование: `!connect4 @соперник`",
        "no_bot": "Ты не можешь бросить вызов боту.",
        "no_self": "Ты не можешь играть сам с собой.",
        "cant_post": "Я не могу писать в этом канале.",
        "start_failed": "Сейчас не удалось начать игру.",
        "expired": "Срок этой игры истёк.",
        "not_your_game": "Это не твоя игра.",
        "not_your_turn": "Сейчас не твой ход.",
        "column_full": "Этот столбец заполнен — выбери другой.",
        "move_error": "Что-то пошло не так с этим ходом.",
        "embed_title": "🔴🟡 Четыре в ряд",
        "field_players": "Игроки",
        "field_status": "Статус",
        "status_wins": "{cell} <@{winner}> побеждает! 🎉",
        "status_draw": "Ничья! 🤝",
        "status_turn": "Ход игрока {cell} <@{player}>",
    },
    "pl": {
        "not_enabled": "Czwórki nie są włączone na tym serwerze.",
        "play_in_channel": "Graj na kanale <#{channel}>.",
        "usage": "Użycie: `!connect4 @przeciwnik`",
        "no_bot": "Nie możesz wyzwać bota.",
        "no_self": "Nie możesz grać przeciwko sobie.",
        "cant_post": "Nie mogę pisać na tym kanale.",
        "start_failed": "Nie udało się teraz rozpocząć gry.",
        "expired": "Ta gra wygasła.",
        "not_your_game": "To nie jest twoja gra.",
        "not_your_turn": "To jeszcze nie twoja kolej.",
        "column_full": "Ta kolumna jest pełna — wybierz inną.",
        "move_error": "Coś poszło nie tak z tym ruchem.",
        "embed_title": "🔴🟡 Czwórki",
        "field_players": "Gracze",
        "field_status": "Status",
        "status_wins": "{cell} <@{winner}> wygrywa! 🎉",
        "status_draw": "Remis! 🤝",
        "status_turn": "Kolej gracza {cell} <@{player}>",
    },
}

t = make_translator(_STRINGS)


SETTINGS_TTL_SECONDS = 60
C4_COLOR = 0x3B82F6

ROWS = 6
COLS = 7

EMPTY = 0
P1 = 1
P2 = 2

CELL_EMPTY = "⚪"
CELL_P1 = "🔴"
CELL_P2 = "🟡"
HEADER = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]


class Connect4Session:
    """In-memory state for one game."""

    def __init__(self, token, guild_id, channel_id, p1_id, p2_id):
        self.token = token
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.p1_id = p1_id
        self.p2_id = p2_id
        # grid[row][col]; row 0 = top, row ROWS-1 = bottom.
        self.grid = [[EMPTY for _ in range(COLS)] for _ in range(ROWS)]
        self.turn = P1  # P1 (🔴) moves first
        self.message_id = None
        self.created_at = time.time()
        self.lang = "en"

    def current_player_id(self):
        return self.p1_id if self.turn == P1 else self.p2_id

    def is_column_full(self, col):
        return self.grid[0][col] != EMPTY

    def is_board_full(self):
        return all(self.is_column_full(c) for c in range(COLS))

    def drop(self, col):
        """Drop the current player's disc into `col`. Returns the row used, or None."""
        if col < 0 or col >= COLS or self.is_column_full(col):
            return None
        for row in range(ROWS - 1, -1, -1):
            if self.grid[row][col] == EMPTY:
                self.grid[row][col] = self.turn
                return row
        return None

    def check_win(self, row, col):
        """Return True if the disc at (row, col) completes a four-in-a-row."""
        player = self.grid[row][col]
        if player == EMPTY:
            return False
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for dr, dc in directions:
            count = 1
            # forward
            r, c = row + dr, col + dc
            while 0 <= r < ROWS and 0 <= c < COLS and self.grid[r][c] == player:
                count += 1
                r += dr
                c += dc
            # backward
            r, c = row - dr, col - dc
            while 0 <= r < ROWS and 0 <= c < COLS and self.grid[r][c] == player:
                count += 1
                r -= dr
                c -= dc
            if count >= 4:
                return True
        return False

    def render_board(self):
        symbols = {EMPTY: CELL_EMPTY, P1: CELL_P1, P2: CELL_P2}
        lines = ["".join(HEADER)]
        for row in range(ROWS):
            lines.append("".join(symbols[self.grid[row][c]] for c in range(COLS)))
        return "\n".join(lines)


def build_view(session):
    """One row of seven column buttons; full columns are disabled."""
    view = discord.ui.View(timeout=None)
    for col in range(COLS):
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label=str(col + 1),
            custom_id=f"c4:{session.token}:{col}",
            disabled=session.is_column_full(col),
        ))
    return view


class ConnectFour(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self._settings_cache = {}
        self._sessions = {}  # token -> Connect4Session

    async def _get_settings(self, guild_id, force=False):
        key = str(guild_id)
        now = time.time()
        cached = self._settings_cache.get(key)
        if not force and cached and now - cached[1] < SETTINGS_TTL_SECONDS:
            return cached[0]
        settings = await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "games")
        if settings is not None:
            self._settings_cache[key] = (settings, now)
        return settings

    async def _score(self, guild_id, user_id, win):
        try:
            await bot_post(
                self.backend_url, self.api_key,
                f"/api/bot/guilds/{guild_id}/games/score",
                {"user_id": str(user_id), "game": "connect4", "win": bool(win)},
            )
        except Exception as exc:
            print(f"[connect4] score post failed in {guild_id} for {user_id}: {exc}")

    def _build_embed(self, session, status_line):
        lang = session.lang
        embed = discord.Embed(
            title=t(lang, "embed_title"),
            description=session.render_board(),
            color=C4_COLOR,
        )
        embed.add_field(
            name=t(lang, "field_players"),
            value=f"{CELL_P1} <@{session.p1_id}>  vs  {CELL_P2} <@{session.p2_id}>",
            inline=False,
        )
        embed.add_field(name=t(lang, "field_status"), value=status_line, inline=False)
        return embed

    def _turn_status(self, session):
        cell = CELL_P1 if session.turn == P1 else CELL_P2
        return t(session.lang, "status_turn", cell=cell, player=session.current_player_id())

    @commands.command(name="connect4")
    @commands.guild_only()
    async def connect4(self, ctx, opponent: discord.Member = None):
        try:
            settings = await self._get_settings(ctx.guild.id)
            lang = lang_of(settings)
            if not settings or not settings.get("connect4_enabled"):
                await ctx.reply(t(lang, "not_enabled"), mention_author=False)
                return

            games_channel_id = settings.get("games_channel_id")
            if games_channel_id and str(games_channel_id) != str(ctx.channel.id):
                await ctx.reply(
                    t(lang, "play_in_channel", channel=games_channel_id),
                    mention_author=False,
                )
                return

            if opponent is None:
                await ctx.reply(t("en", "usage"), mention_author=False)
                return
            if opponent.bot:
                await ctx.reply(t("en", "no_bot"), mention_author=False)
                return
            if opponent.id == ctx.author.id:
                await ctx.reply(t("en", "no_self"), mention_author=False)
                return

            token = uuid.uuid4().hex[:8]
            session = Connect4Session(
                token=token,
                guild_id=ctx.guild.id,
                channel_id=ctx.channel.id,
                p1_id=ctx.author.id,
                p2_id=opponent.id,
            )
            session.lang = lang

            embed = self._build_embed(session, self._turn_status(session))
            try:
                msg = await ctx.send(embed=embed, view=build_view(session))
            except discord.Forbidden:
                await ctx.reply(t(lang, "cant_post"), mention_author=False)
                return

            session.message_id = msg.id
            self._sessions[token] = session
        except Exception as exc:
            print(f"[connect4] start failed in {getattr(ctx.guild, 'id', '?')}: {exc}")
            try:
                await ctx.reply(t("en", "start_failed"), mention_author=False)
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        try:
            if interaction.type != discord.InteractionType.component or interaction.guild is None:
                return
            custom_id = (interaction.data or {}).get("custom_id") or ""
            if not custom_id.startswith("c4:"):
                return

            parts = custom_id.split(":")
            if len(parts) != 3:
                return
            _, token, col_raw = parts
            try:
                col = int(col_raw)
            except ValueError:
                return

            session = self._sessions.get(token)
            if session is None:
                await interaction.response.send_message(t("en", "expired"), ephemeral=True)
                return

            lang = session.lang

            # Turn enforcement — only the player whose turn it is may click.
            if interaction.user.id != session.current_player_id():
                if interaction.user.id not in (session.p1_id, session.p2_id):
                    await interaction.response.send_message(
                        t(lang, "not_your_game"), ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        t(lang, "not_your_turn"), ephemeral=True
                    )
                return

            if col < 0 or col >= COLS or session.is_column_full(col):
                await interaction.response.send_message(
                    t(lang, "column_full"), ephemeral=True
                )
                return

            mover = session.turn  # remember who just moved before we flip
            row = session.drop(col)
            if row is None:
                await interaction.response.send_message(
                    t(lang, "column_full"), ephemeral=True
                )
                return

            # --- Win check ---
            if session.check_win(row, col):
                winner_id = session.p1_id if mover == P1 else session.p2_id
                loser_id = session.p2_id if mover == P1 else session.p1_id
                cell = CELL_P1 if mover == P1 else CELL_P2
                status = t(lang, "status_wins", cell=cell, winner=winner_id)
                embed = self._build_embed(session, status)
                await interaction.response.edit_message(embed=embed, view=None)
                await self._score(session.guild_id, winner_id, True)
                await self._score(session.guild_id, loser_id, False)
                self._sessions.pop(token, None)
                return

            # --- Draw check (full board) ---
            if session.is_board_full():
                embed = self._build_embed(session, t(lang, "status_draw"))
                await interaction.response.edit_message(embed=embed, view=None)
                await self._score(session.guild_id, session.p1_id, False)
                await self._score(session.guild_id, session.p2_id, False)
                self._sessions.pop(token, None)
                return

            # --- Continue: flip turn and refresh ---
            session.turn = P2 if mover == P1 else P1
            embed = self._build_embed(session, self._turn_status(session))
            await interaction.response.edit_message(embed=embed, view=build_view(session))
        except discord.NotFound:
            # Interaction token expired — nothing we can do.
            pass
        except Exception as exc:
            print(f"[connect4] interaction error: {exc}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        t("en", "move_error"), ephemeral=True
                    )
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(ConnectFour(bot))
