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


SETTINGS_TTL_SECONDS = 60
TTT_COLOR = 0x5865F2

EMPTY_LABEL = "▫️"
MARKS = {"X": "❌", "O": "⭕"}

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
            await ctx.reply("Usage: `!ttt @opponent` — challenge someone to Tic-Tac-Toe.", mention_author=False)
            return
        if opponent.bot:
            await ctx.reply("You can't challenge a bot.", mention_author=False)
            return
        if opponent.id == ctx.author.id:
            await ctx.reply("You can't play against yourself.", mention_author=False)
            return

        settings = await self._get_settings(ctx.guild.id)
        if not settings or not settings.get("tictactoe_enabled"):
            await ctx.reply("The Tic-Tac-Toe game is disabled on this server.", mention_author=False)
            return
        games_channel_id = settings.get("games_channel_id")
        if games_channel_id and str(ctx.channel.id) != str(games_channel_id):
            await ctx.reply(f"Games can only be played in <#{games_channel_id}>.", mention_author=False)
            return

        token = uuid.uuid4().hex[:8]
        board = [None] * 9
        session = {
            "board": board,
            "players": {"X": ctx.author.id, "O": opponent.id},
            "turn": "X",
            "message_id": None,
            "guild_id": ctx.guild.id,
        }
        self._sessions[token] = session

        embed = self._build_embed(session)
        try:
            msg = await ctx.send(embed=embed, view=build_board_view(token, board))
        except discord.Forbidden:
            self._sessions.pop(token, None)
            await ctx.reply("I can't post in this channel.", mention_author=False)
            return
        except Exception as exc:
            self._sessions.pop(token, None)
            print(f"[ttt] failed to start game in {ctx.guild.id}: {exc}")
            await ctx.reply("Couldn't start the game right now.", mention_author=False)
            return
        session["message_id"] = msg.id

    def _build_embed(self, session, status=None):
        players = session["players"]
        turn = session["turn"]
        embed = discord.Embed(title="⭕ Tic-Tac-Toe ❌", color=TTT_COLOR)
        embed.add_field(name="❌ Player X", value=f"<@{players['X']}>", inline=True)
        embed.add_field(name="⭕ Player O", value=f"<@{players['O']}>", inline=True)
        if status:
            embed.description = status
        else:
            embed.description = f"It's {MARKS[turn]} <@{players[turn]}>'s turn."
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
                await interaction.response.send_message("This game has expired.", ephemeral=True)
            except Exception:
                pass
            return

        players = session["players"]
        turn = session["turn"]
        clicker = interaction.user.id

        if clicker not in (players["X"], players["O"]):
            try:
                await interaction.response.send_message("You're not in this game.", ephemeral=True)
            except Exception:
                pass
            return
        if clicker != players[turn]:
            try:
                await interaction.response.send_message("It's not your turn.", ephemeral=True)
            except Exception:
                pass
            return

        board = session["board"]
        if board[pos] is not None:
            try:
                await interaction.response.send_message("That cell is already taken.", ephemeral=True)
            except Exception:
                pass
            return

        # Place the mark.
        board[pos] = turn
        winner = check_winner(board)
        is_draw = winner is None and board_full(board)

        if winner or is_draw:
            if winner:
                status = f"{MARKS[winner]} <@{players[winner]}> wins!"
            else:
                status = "It's a draw!"
            embed = self._build_embed(session, status=status)
            try:
                await interaction.response.edit_message(embed=embed, view=build_board_view(token, board, disabled=True))
            except Exception as exc:
                print(f"[ttt] failed to edit final board for {token}: {exc}")
            try:
                if winner:
                    await interaction.followup.send(f"{MARKS[winner]} <@{players[winner]}> wins!")
                else:
                    await interaction.followup.send("It's a draw!")
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
