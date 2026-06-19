"""Tic-Tac-Toe cog.

Two members play a 3x3 game of Tic-Tac-Toe via an interactive button grid.
Start with `!ttt @opponent`. Clicks are handled via on_interaction (custom_id
`ttt:<token>:<pos>`) against an in-memory session keyed by a short token, so the
board keeps working without persistent-view registration. Sessions are dropped
once the game ends (win/draw).

Per-human result is reported to the backend score endpoint.

Backend contract (X-Bot-Token auth):
  GET  /api/bot/guilds/{gid}/settings/games
       → { games_channel_id, tictactoe_enabled, rps_enabled, ... } | None
  POST /api/bot/guilds/{gid}/games/score
       body { user_id, game: "tictactoe", win: <bool> }

Logging prefix: "[ttt]".
"""

import time
import uuid

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_post
from utils.game_i18n import make_translator, lang_of


SETTINGS_TTL_SECONDS = 60
TTT_COLOR = 0x5865F2

EMPTY_LABEL = "▫️"
MARKS = {"X": "❌", "O": "⭕"}

# User-visible strings per language. English values are word-for-word the
# original literals so the default behaviour is unchanged.
_STRINGS = {
    "en": {
        "usage": "Usage: `!ttt @opponent` — challenge someone to Tic-Tac-Toe.",
        "no_bot": "You can't challenge a bot.",
        "no_self": "You can't play against yourself.",
        "disabled": "The Tic-Tac-Toe game is disabled on this server.",
        "channel_only": "Games can only be played in <#{channel}>.",
        "cant_post": "I can't post in this channel.",
        "start_failed": "Couldn't start the game right now.",
        "embed_title": "⭕ Tic-Tac-Toe ❌",
        "player_x": "❌ Player X",
        "player_o": "⭕ Player O",
        "turn": "It's {mark} <@{player}>'s turn.",
        "expired": "This game has expired.",
        "not_in_game": "You're not in this game.",
        "not_your_turn": "It's not your turn.",
        "cell_taken": "That cell is already taken.",
        "wins": "{mark} <@{player}> wins!",
        "draw": "It's a draw!",
    },
    "de": {
        "usage": "Verwendung: `!ttt @gegner` — fordere jemanden zu Tic-Tac-Toe heraus.",
        "no_bot": "Du kannst keinen Bot herausfordern.",
        "no_self": "Du kannst nicht gegen dich selbst spielen.",
        "disabled": "Das Tic-Tac-Toe-Spiel ist auf diesem Server deaktiviert.",
        "channel_only": "Spiele können nur in <#{channel}> gespielt werden.",
        "cant_post": "Ich kann in diesem Kanal nicht schreiben.",
        "start_failed": "Das Spiel konnte gerade nicht gestartet werden.",
        "embed_title": "⭕ Tic-Tac-Toe ❌",
        "player_x": "❌ Spieler X",
        "player_o": "⭕ Spieler O",
        "turn": "{mark} <@{player}> ist am Zug.",
        "expired": "Dieses Spiel ist abgelaufen.",
        "not_in_game": "Du nimmst an diesem Spiel nicht teil.",
        "not_your_turn": "Du bist nicht am Zug.",
        "cell_taken": "Dieses Feld ist bereits belegt.",
        "wins": "{mark} <@{player}> gewinnt!",
        "draw": "Unentschieden!",
    },
    "tr": {
        "usage": "Kullanım: `!ttt @rakip` — birini Tic-Tac-Toe'ye davet et.",
        "no_bot": "Bir botu davet edemezsin.",
        "no_self": "Kendine karşı oynayamazsın.",
        "disabled": "Tic-Tac-Toe oyunu bu sunucuda devre dışı.",
        "channel_only": "Oyunlar yalnızca <#{channel}> kanalında oynanabilir.",
        "cant_post": "Bu kanala mesaj gönderemiyorum.",
        "start_failed": "Oyun şu anda başlatılamadı.",
        "embed_title": "⭕ Tic-Tac-Toe ❌",
        "player_x": "❌ Oyuncu X",
        "player_o": "⭕ Oyuncu O",
        "turn": "Sıra {mark} <@{player}> oyuncusunda.",
        "expired": "Bu oyunun süresi doldu.",
        "not_in_game": "Bu oyunda değilsin.",
        "not_your_turn": "Sıra sende değil.",
        "cell_taken": "Bu hücre zaten dolu.",
        "wins": "{mark} <@{player}> kazandı!",
        "draw": "Berabere!",
    },
    "ru": {
        "usage": "Использование: `!ttt @соперник` — вызовите кого-нибудь на игру в крестики-нолики.",
        "no_bot": "Нельзя бросить вызов боту.",
        "no_self": "Нельзя играть против самого себя.",
        "disabled": "Игра «крестики-нолики» отключена на этом сервере.",
        "channel_only": "Играть можно только в <#{channel}>.",
        "cant_post": "Я не могу писать в этом канале.",
        "start_failed": "Не удалось начать игру прямо сейчас.",
        "embed_title": "⭕ Крестики-нолики ❌",
        "player_x": "❌ Игрок X",
        "player_o": "⭕ Игрок O",
        "turn": "Ход {mark} <@{player}>.",
        "expired": "Срок этой игры истёк.",
        "not_in_game": "Ты не участвуешь в этой игре.",
        "not_your_turn": "Сейчас не твой ход.",
        "cell_taken": "Эта клетка уже занята.",
        "wins": "{mark} <@{player}> побеждает!",
        "draw": "Ничья!",
    },
    "pl": {
        "usage": "Użycie: `!ttt @przeciwnik` — wyzwij kogoś do gry w kółko i krzyżyk.",
        "no_bot": "Nie możesz wyzwać bota.",
        "no_self": "Nie możesz grać przeciwko samemu sobie.",
        "disabled": "Gra w kółko i krzyżyk jest wyłączona na tym serwerze.",
        "channel_only": "W gry można grać tylko na <#{channel}>.",
        "cant_post": "Nie mogę pisać na tym kanale.",
        "start_failed": "Nie udało się teraz rozpocząć gry.",
        "embed_title": "⭕ Kółko i krzyżyk ❌",
        "player_x": "❌ Gracz X",
        "player_o": "⭕ Gracz O",
        "turn": "Tura gracza {mark} <@{player}>.",
        "expired": "Ta gra wygasła.",
        "not_in_game": "Nie bierzesz udziału w tej grze.",
        "not_your_turn": "To nie twoja tura.",
        "cell_taken": "To pole jest już zajęte.",
        "wins": "{mark} <@{player}> wygrywa!",
        "draw": "Remis!",
    },
}
t = make_translator(_STRINGS)

# All 8 winning lines (3 rows, 3 columns, 2 diagonals).
WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),   # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),   # columns
    (0, 4, 8), (2, 4, 6),              # diagonals
]


def check_winner(board):
    """Return 'X' / 'O' if a player has a winning line, else None."""
    for a, b, c in WIN_LINES:
        if board[a] is not None and board[a] == board[b] == board[c]:
            return board[a]
    return None


def board_full(board):
    return all(cell is not None for cell in board)


def build_board_view(token, board, disabled=False):
    """Build the 3x3 button grid as a timeout-less View."""
    view = discord.ui.View(timeout=None)
    for pos in range(9):
        mark = board[pos]
        if mark is None:
            label = EMPTY_LABEL
            style = discord.ButtonStyle.secondary
            btn_disabled = disabled
        else:
            label = MARKS[mark]
            style = discord.ButtonStyle.primary if mark == "X" else discord.ButtonStyle.danger
            btn_disabled = True
        view.add_item(discord.ui.Button(
            style=style,
            label=label,
            custom_id=f"ttt:{token}:{pos}",
            row=pos // 3,
            disabled=btn_disabled,
        ))
    return view


class TicTacToe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self._settings_cache = {}
        # token -> session dict
        self._sessions = {}

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

    @commands.command(name="ttt")
    @commands.guild_only()
    async def ttt(self, ctx, opponent: discord.Member = None):
        if opponent is None:
            await ctx.reply(t("en", "usage"), mention_author=False)
            return
        if opponent.bot:
            await ctx.reply(t("en", "no_bot"), mention_author=False)
            return
        if opponent.id == ctx.author.id:
            await ctx.reply(t("en", "no_self"), mention_author=False)
            return

        settings = await self._get_settings(ctx.guild.id)
        lang = lang_of(settings)
        if not settings or not settings.get("tictactoe_enabled"):
            await ctx.reply(t(lang, "disabled"), mention_author=False)
            return
        games_channel_id = settings.get("games_channel_id")
        if games_channel_id and str(ctx.channel.id) != str(games_channel_id):
            await ctx.reply(t(lang, "channel_only", channel=games_channel_id), mention_author=False)
            return

        token = uuid.uuid4().hex[:8]
        board = [None] * 9
        session = {
            "board": board,
            "players": {"X": ctx.author.id, "O": opponent.id},
            "turn": "X",
            "message_id": None,
            "guild_id": ctx.guild.id,
            "lang": lang,
        }
        self._sessions[token] = session

        embed = self._build_embed(session)
        try:
            msg = await ctx.send(embed=embed, view=build_board_view(token, board))
        except discord.Forbidden:
            self._sessions.pop(token, None)
            await ctx.reply(t(lang, "cant_post"), mention_author=False)
            return
        except Exception as exc:
            self._sessions.pop(token, None)
            print(f"[ttt] failed to start game in {ctx.guild.id}: {exc}")
            await ctx.reply(t(lang, "start_failed"), mention_author=False)
            return
        session["message_id"] = msg.id

    def _build_embed(self, session, status=None):
        players = session["players"]
        turn = session["turn"]
        lang = session.get("lang", "en")
        embed = discord.Embed(title=t(lang, "embed_title"), color=TTT_COLOR)
        embed.add_field(name=t(lang, "player_x"), value=f"<@{players['X']}>", inline=True)
        embed.add_field(name=t(lang, "player_o"), value=f"<@{players['O']}>", inline=True)
        if status:
            embed.description = status
        else:
            embed.description = t(lang, "turn", mark=MARKS[turn], player=players[turn])
        return embed

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = (interaction.data or {}).get("custom_id") or ""
        if not custom_id.startswith("ttt:"):
            return
        if interaction.guild is None:
            return

        parts = custom_id.split(":")
        if len(parts) != 3:
            return
        token, pos_raw = parts[1], parts[2]
        try:
            pos = int(pos_raw)
        except ValueError:
            return
        if pos < 0 or pos > 8:
            return

        session = self._sessions.get(token)
        if session is None:
            try:
                await interaction.response.send_message(t("en", "expired"), ephemeral=True)
            except Exception:
                pass
            return

        lang = session.get("lang", "en")
        players = session["players"]
        turn = session["turn"]
        clicker = interaction.user.id

        if clicker not in (players["X"], players["O"]):
            try:
                await interaction.response.send_message(t(lang, "not_in_game"), ephemeral=True)
            except Exception:
                pass
            return
        if clicker != players[turn]:
            try:
                await interaction.response.send_message(t(lang, "not_your_turn"), ephemeral=True)
            except Exception:
                pass
            return

        board = session["board"]
        if board[pos] is not None:
            try:
                await interaction.response.send_message(t(lang, "cell_taken"), ephemeral=True)
            except Exception:
                pass
            return

        # Place the mark.
        board[pos] = turn
        winner = check_winner(board)
        is_draw = winner is None and board_full(board)

        if winner or is_draw:
            if winner:
                status = t(lang, "wins", mark=MARKS[winner], player=players[winner])
            else:
                status = t(lang, "draw")
            embed = self._build_embed(session, status=status)
            try:
                await interaction.response.edit_message(embed=embed, view=build_board_view(token, board, disabled=True))
            except Exception as exc:
                print(f"[ttt] failed to edit final board for {token}: {exc}")
            try:
                if winner:
                    await interaction.followup.send(t(lang, "wins", mark=MARKS[winner], player=players[winner]))
                else:
                    await interaction.followup.send(t(lang, "draw"))
            except Exception:
                pass
            self._sessions.pop(token, None)
            await self._record_results(interaction.guild, session, winner)
            return

        # No end yet: flip turn, rebuild board.
        session["turn"] = "O" if turn == "X" else "X"
        embed = self._build_embed(session)
        try:
            await interaction.response.edit_message(embed=embed, view=build_board_view(token, board))
        except Exception as exc:
            print(f"[ttt] failed to edit board for {token}: {exc}")

    async def _record_results(self, guild, session, winner):
        """Report the game result for each human player to the backend."""
        if not self.api_key or not self.backend_url:
            return
        players = session["players"]
        guild_id = session.get("guild_id")
        winner_uid = players[winner] if winner else None
        for mark in ("X", "O"):
            uid = players[mark]
            member = guild.get_member(uid) if guild else None
            # Never score a bot.
            if member is not None and member.bot:
                continue
            win = (winner_uid is not None and uid == winner_uid)
            try:
                await bot_post(
                    self.backend_url, self.api_key,
                    f"/api/bot/guilds/{guild_id}/games/score",
                    {"user_id": str(uid), "game": "tictactoe", "win": bool(win)},
                )
            except Exception as exc:
                print(f"[ttt] failed to record score for {uid} in {guild_id}: {exc}")


async def setup(bot):
    await bot.add_cog(TicTacToe(bot))
