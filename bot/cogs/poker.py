"""Poker cog — multiplayer Texas Hold'em tables (Games category, Basic).

A table lives in a channel. Members open one with `!poker`, join via a button,
and play hand-by-hand: blinds, hole cards (revealed ephemerally via a button),
flop/turn/river, betting (fold/check/call/raise/all-in), proper layered side pots
and a showdown with a 7-card hand evaluator. The chip leader when the table ends
is recorded as a win via the shared /games/score endpoint.

Interactions use on_interaction with custom_id prefix "pk:<action>:<tid>" so they
survive across handlers; the Raise button opens a Modal. All state is in-memory
(one table per channel) — a bot restart drops active tables.

Backend contract (X-Bot-Token auth, shared Games module):
  GET  /api/bot/guilds/{gid}/settings/games  → { games_channel_id, poker_enabled, ... }
  POST /api/bot/guilds/{gid}/games/score      body { user_id, game:"poker", win }

Logging prefix: "[poker]".
"""

import asyncio
import itertools
import random
import time
import uuid
from collections import Counter

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_post


# ----- Tunables -----
STARTING_STACK = 1000
SMALL_BLIND = 10
BIG_BLIND = 20
MAX_PLAYERS = 8
MIN_PLAYERS = 2
TURN_TIMEOUT = 90
SETTINGS_TTL_SECONDS = 60
LOBBY_COLOR = 0x5865F2
TABLE_COLOR = 0x2ECC71
SHOWDOWN_COLOR = 0xF1C40F

SUIT_SYMBOL = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
RANK_LABEL = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "10"}
HAND_NAMES = {
    8: "Straight Flush", 7: "Four of a Kind", 6: "Full House", 5: "Flush",
    4: "Straight", 3: "Three of a Kind", 2: "Two Pair", 1: "Pair", 0: "High Card",
}


def rank_label(r):
    return RANK_LABEL.get(r, str(r))


def card_str(card):
    return f"{rank_label(card[0])}{SUIT_SYMBOL[card[1]]}"


def cards_str(cards):
    return "  ".join(card_str(c) for c in cards) if cards else "—"


def build_deck():
    deck = [(r, s) for s in "shdc" for r in range(2, 15)]
    random.shuffle(deck)
    return deck


# ----- Hand evaluation -----

def evaluate_5(cards):
    """Comparable tuple for a 5-card hand (higher = better)."""
    ranks = sorted((c[0] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    cnt = Counter(ranks)
    by = sorted(cnt.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    counts = [c for _, c in by]
    ordered = [r for r, _ in by]
    is_flush = len(set(suits)) == 1

    distinct = sorted(set(ranks), reverse=True)
    straight_high = None
    if len(distinct) >= 5:
        for i in range(len(distinct) - 4):
            window = distinct[i:i + 5]
            if window[0] - window[4] == 4:
                straight_high = window[0]
                break
        if straight_high is None and {14, 5, 4, 3, 2}.issubset(set(ranks)):
            straight_high = 5  # wheel A-2-3-4-5
    is_straight = straight_high is not None

    if is_straight and is_flush:
        return (8, straight_high)
    if counts[0] == 4:
        quad = ordered[0]
        return (7, quad, max(r for r in ranks if r != quad))
    if counts[0] == 3 and counts[1] >= 2:
        return (6, ordered[0], ordered[1])
    if is_flush:
        return (5, *ranks[:5])
    if is_straight:
        return (4, straight_high)
    if counts[0] == 3:
        trips = ordered[0]
        return (3, trips, *[r for r in ranks if r != trips][:2])
    if counts[0] == 2 and counts[1] == 2:
        hp, lp = ordered[0], ordered[1]
        return (2, hp, lp, max(r for r in ranks if r not in (hp, lp)))
    if counts[0] == 2:
        pair = ordered[0]
        return (1, pair, *[r for r in ranks if r != pair][:3])
    return (0, *ranks[:5])


def best_hand(seven):
    return max(evaluate_5(list(c)) for c in itertools.combinations(seven, 5))


def hand_name(score):
    return HAND_NAMES.get(score[0], "High Card")


# ----- Player + Table -----

class PokerPlayer:
    __slots__ = ("id", "name", "stack", "hole", "folded", "all_in", "bet", "total", "acted", "in_hand")

    def __init__(self, uid, name, stack):
        self.id = uid
        self.name = name
        self.stack = stack
        self.hole = []
        self.folded = False
        self.all_in = False
        self.bet = 0      # committed this betting round
        self.total = 0    # committed this hand (for side pots)
        self.acted = False
        self.in_hand = False


class PokerTable:
    def __init__(self, guild_id, channel_id, host_id):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.host_id = host_id
        self.tid = uuid.uuid4().hex[:8]
        self.players = []
        self.state = "lobby"        # lobby | betting | hand_over | ended
        self.message = None
        self.deck = []
        self.board = []
        self.dealer_pos = -1
        self.current_bet = 0
        self.last_raise = BIG_BLIND
        self.to_act = None
        self.street = "preflop"
        self.turn_token = 0
        self.lock = asyncio.Lock()
        self.last_result = ""
        self.hand_no = 0
        self.participants = {}      # uid -> name (everyone who ever joined)

    # -- helpers --
    def find(self, uid):
        return next((p for p in self.players if p.id == uid), None)

    def seated_with_chips(self):
        return [p for p in self.players if p.stack > 0]

    def pot(self):
        return sum(p.total for p in self.players)

    def in_hand_players(self):
        return [p for p in self.players if p.in_hand]

    def live_players(self):
        return [p for p in self.players if p.in_hand and not p.folded]

    def contenders(self):
        return [p for p in self.players if p.in_hand and not p.folded and not p.all_in]

    def _next_active_index(self, start):
        n = len(self.players)
        for off in range(n):
            i = (start + off) % n
            p = self.players[i]
            if p.in_hand and not p.folded and not p.all_in:
                return i
        return None

    def _next_to_act(self, start):
        n = len(self.players)
        for off in range(n):
            i = (start + off) % n
            p = self.players[i]
            if p.in_hand and not p.folded and not p.all_in and (not p.acted or p.bet < self.current_bet):
                return i
        return None

    # -- hand lifecycle --
    def begin_hand(self):
        if len(self.seated_with_chips()) < MIN_PLAYERS:
            return False
        self.hand_no += 1
        self.deck = build_deck()
        self.board = []
        self.current_bet = 0
        self.last_raise = BIG_BLIND
        self.street = "preflop"
        self.last_result = ""
        for p in self.players:
            p.hole = []
            p.folded = False
            p.all_in = False
            p.bet = 0
            p.total = 0
            p.acted = False
            p.in_hand = p.stack > 0

        self.dealer_pos = self._next_active_index((self.dealer_pos + 1) % len(self.players))
        for _ in range(2):
            for p in self.in_hand_players():
                p.hole.append(self.deck.pop())

        active = [i for i, p in enumerate(self.players) if p.in_hand]
        if len(active) == 2:
            sb_i = self.dealer_pos
            bb_i = self._next_active_index((self.dealer_pos + 1) % len(self.players))
        else:
            sb_i = self._next_active_index((self.dealer_pos + 1) % len(self.players))
            bb_i = self._next_active_index((sb_i + 1) % len(self.players))
        self._post_blind(sb_i, SMALL_BLIND)
        self._post_blind(bb_i, BIG_BLIND)
        self.current_bet = BIG_BLIND
        self.last_raise = BIG_BLIND
        self.to_act = self._next_to_act((bb_i + 1) % len(self.players))
        self.state = "betting"
        return True

    def _post_blind(self, i, amount):
        p = self.players[i]
        pay = min(amount, p.stack)
        p.stack -= pay
        p.bet = pay
        p.total += pay
        if p.stack == 0:
            p.all_in = True

    def betting_complete(self):
        for p in self.contenders():
            if not p.acted or p.bet < self.current_bet:
                return False
        return True

    def apply_action(self, p, action, raise_to=None):
        """Validate + mutate. Returns (ok, error_or_None)."""
        if action == "fold":
            p.folded = True
            p.acted = True
        elif action == "check":
            if p.bet != self.current_bet:
                return False, "You can't check — there's a bet to call."
            p.acted = True
        elif action == "call":
            pay = min(self.current_bet - p.bet, p.stack)
            p.stack -= pay
            p.bet += pay
            p.total += pay
            if p.stack == 0:
                p.all_in = True
            p.acted = True
        elif action == "allin":
            pay = p.stack
            if pay <= 0:
                return False, "You have no chips left."
            p.stack = 0
            p.bet += pay
            p.total += pay
            p.all_in = True
            p.acted = True
            if p.bet > self.current_bet:
                self.last_raise = max(self.last_raise, p.bet - self.current_bet)
                self.current_bet = p.bet
                for o in self.contenders():
                    if o is not p:
                        o.acted = False
        elif action == "raise":
            try:
                target = int(raise_to)
            except (TypeError, ValueError):
                return False, "Enter a whole number."
            max_to = p.bet + p.stack
            if target <= self.current_bet:
                return False, f"A raise must exceed the current bet of {self.current_bet}."
            if target > max_to:
                return False, f"You can bet at most {max_to}."
            min_to = self.current_bet + self.last_raise
            if target < min_to and target != max_to:
                return False, f"Minimum raise is to {min_to} (or all-in for {max_to})."
            pay = target - p.bet
            p.stack -= pay
            p.total += pay
            p.bet = target
            self.last_raise = max(self.last_raise, target - self.current_bet)
            self.current_bet = target
            if p.stack == 0:
                p.all_in = True
            for o in self.contenders():
                if o is not p:
                    o.acted = False
            p.acted = True
        else:
            return False, "Unknown action."
        return True, None

    def advance_street(self):
        """Reveal next street(s), set up betting, or return 'showdown'."""
        while True:
            if self.street == "preflop":
                self.board += [self.deck.pop() for _ in range(3)]
                self.street = "flop"
            elif self.street == "flop":
                self.board.append(self.deck.pop())
                self.street = "turn"
            elif self.street == "turn":
                self.board.append(self.deck.pop())
                self.street = "river"
            else:
                return "showdown"
            for p in self.live_players():
                p.bet = 0
                p.acted = False
            self.current_bet = 0
            self.last_raise = BIG_BLIND
            self.to_act = self._next_to_act((self.dealer_pos + 1) % len(self.players))
            if len(self.contenders()) >= 2 and self.to_act is not None:
                return "betting"

    def compute_side_pots(self):
        """Layered side pots: list of (amount, [eligible non-folded players])."""
        contributors = [p for p in self.players if p.total > 0]
        if not contributors:
            return []
        levels = sorted(set(p.total for p in contributors))
        pots = []
        prev = 0
        for lvl in levels:
            layer = lvl - prev
            payers = [p for p in contributors if p.total >= lvl]
            amount = layer * len(payers)
            eligible = [p for p in payers if not p.folded]
            if amount <= 0:
                prev = lvl
                continue
            if eligible:
                pots.append([amount, eligible])
            elif pots:
                pots[-1][0] += amount      # dead (all-folded) layer rolls into previous pot
            prev = lvl
        return pots


def _dealer_marks(table, idx):
    """D / SB / BB tags for a seat index, if in hand."""
    if not table.in_hand_players():
        return ""
    active = [i for i, p in enumerate(table.players) if p.in_hand]
    if idx not in active:
        return ""
    tags = []
    if idx == table.dealer_pos:
        tags.append("D")
    if len(active) == 2:
        sb = table.dealer_pos
        bb = next(i for i in active if i != sb)
    else:
        sb = table._next_active_index((table.dealer_pos + 1) % len(table.players))
        bb = table._next_active_index((sb + 1) % len(table.players))
    if idx == sb:
        tags.append("SB")
    if idx == bb:
        tags.append("BB")
    return " ".join(f"`{t}`" for t in tags)


# ----- Modal for raising -----

class RaiseModal(discord.ui.Modal, title="Raise"):
    amount = discord.ui.TextInput(label="Raise to (total bet this round)", required=True, max_length=12)

    def __init__(self, cog, channel_id, tid, hint):
        super().__init__()
        self.cog = cog
        self.channel_id = channel_id
        self.tid = tid
        self.amount.placeholder = hint

    async def on_submit(self, interaction):
        await self.cog.on_raise_submit(interaction, self.channel_id, self.tid, str(self.amount.value))


# ----- Cog -----

class Poker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self.tables = {}            # channel_id -> PokerTable
        self._settings_cache = {}

    # -- settings --
    async def _settings(self, guild_id):
        key = str(guild_id)
        now = time.time()
        cached = self._settings_cache.get(key)
        if cached and now - cached[1] < SETTINGS_TTL_SECONDS:
            return cached[0]
        s = await fetch_bot_settings(self.backend_url, self.api_key, guild_id, "games")
        if s is not None:
            self._settings_cache[key] = (s, now)
        return s

    # -- command --
    @commands.command(name="poker")
    @commands.guild_only()
    async def poker(self, ctx):
        settings = await self._settings(ctx.guild.id)
        if not settings or not settings.get("poker_enabled"):
            await ctx.reply("Poker is not enabled on this server.", mention_author=False)
            return
        ch = settings.get("games_channel_id")
        if ch and str(ctx.channel.id) != str(ch):
            await ctx.reply(f"Poker can only be played in <#{ch}>.", mention_author=False)
            return
        if ctx.channel.id in self.tables:
            await ctx.reply("A poker table is already open in this channel.", mention_author=False)
            return

        table = PokerTable(ctx.guild.id, ctx.channel.id, ctx.author.id)
        table.players.append(PokerPlayer(ctx.author.id, ctx.author.display_name, STARTING_STACK))
        table.participants[ctx.author.id] = ctx.author.display_name
        self.tables[ctx.channel.id] = table
        try:
            table.message = await ctx.send(embed=self._lobby_embed(table), view=self._lobby_view(table))
        except discord.Forbidden:
            del self.tables[ctx.channel.id]
            await ctx.reply("I can't post in this channel.", mention_author=False)

    # -- interaction routing --
    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component or interaction.guild is None:
            return
        cid = (interaction.data or {}).get("custom_id") or ""
        if not cid.startswith("pk:"):
            return
        parts = cid.split(":")
        if len(parts) != 3:
            return
        _, action, tid = parts
        table = self.tables.get(interaction.channel_id)
        if not table or table.tid != tid:
            try:
                await interaction.response.send_message("This poker table has closed.", ephemeral=True)
            except discord.HTTPException:
                pass
            return

        if action == "raise":
            # opens a modal — must respond directly, no defer
            p = table.find(interaction.user.id)
            if table.state != "betting" or table.to_act is None or table.players[table.to_act].id != interaction.user.id:
                await interaction.response.send_message("It's not your turn.", ephemeral=True)
                return
            min_to = table.current_bet + table.last_raise
            max_to = p.bet + p.stack
            await interaction.response.send_modal(RaiseModal(self, table.channel_id, tid, f"{min_to}–{max_to}"))
            return

        if action == "cards":
            p = table.find(interaction.user.id)
            if not p or not p.hole:
                await interaction.response.send_message("You have no cards in this hand.", ephemeral=True)
                return
            score = best_hand(p.hole + table.board) if table.board else None
            extra = f"\nBest so far: **{hand_name(score)}**" if score else ""
            await interaction.response.send_message(f"🃏 Your hand: **{cards_str(p.hole)}**{extra}", ephemeral=True)
            return

        # all other actions mutate state under the lock
        async with table.lock:
            if action in ("join", "leave", "start", "cancel"):
                await self._handle_lobby(interaction, table, action)
            elif action in ("fold", "check", "call", "allin"):
                await self._handle_bet(interaction, table, action)
            elif action == "nexthand":
                await self._handle_nexthand(interaction, table)
            elif action == "end":
                await self._handle_end(interaction, table)

    # -- lobby --
    async def _handle_lobby(self, interaction, table, action):
        if table.state != "lobby":
            await interaction.response.send_message("The game has already started.", ephemeral=True)
            return
        uid = interaction.user.id
        if action == "join":
            if table.find(uid):
                await interaction.response.send_message("You're already at the table.", ephemeral=True)
                return
            if len(table.players) >= MAX_PLAYERS:
                await interaction.response.send_message("The table is full.", ephemeral=True)
                return
            table.players.append(PokerPlayer(uid, interaction.user.display_name, STARTING_STACK))
            table.participants[uid] = interaction.user.display_name
            await interaction.response.edit_message(embed=self._lobby_embed(table), view=self._lobby_view(table))
        elif action == "leave":
            p = table.find(uid)
            if not p:
                await interaction.response.send_message("You're not at the table.", ephemeral=True)
                return
            table.players.remove(p)
            if not table.players:
                self.tables.pop(table.channel_id, None)
                await interaction.response.edit_message(content="Table closed.", embed=None, view=None)
                return
            if uid == table.host_id:
                table.host_id = table.players[0].id
            await interaction.response.edit_message(embed=self._lobby_embed(table), view=self._lobby_view(table))
        elif action == "cancel":
            if uid != table.host_id:
                await interaction.response.send_message("Only the host can cancel the table.", ephemeral=True)
                return
            self.tables.pop(table.channel_id, None)
            await interaction.response.edit_message(content="Table cancelled by the host.", embed=None, view=None)
        elif action == "start":
            if uid != table.host_id:
                await interaction.response.send_message("Only the host can start the game.", ephemeral=True)
                return
            if len(table.players) < MIN_PLAYERS:
                await interaction.response.send_message(f"Need at least {MIN_PLAYERS} players.", ephemeral=True)
                return
            table.begin_hand()
            await interaction.response.edit_message(embed=self._table_embed(table), view=self._betting_view(table))
            self._arm_timeout(table)

    # -- betting --
    async def _handle_bet(self, interaction, table, action):
        if table.state != "betting":
            await interaction.response.send_message("No betting is in progress.", ephemeral=True)
            return
        if table.to_act is None or table.players[table.to_act].id != interaction.user.id:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return
        p = table.players[table.to_act]
        ok, err = table.apply_action(p, action)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.defer()
        await self._after_action(table)

    async def on_raise_submit(self, interaction, channel_id, tid, raw):
        table = self.tables.get(channel_id)
        if not table or table.tid != tid:
            await interaction.response.send_message("This table has closed.", ephemeral=True)
            return
        async with table.lock:
            if table.state != "betting" or table.to_act is None or table.players[table.to_act].id != interaction.user.id:
                await interaction.response.send_message("It's not your turn anymore.", ephemeral=True)
                return
            p = table.players[table.to_act]
            ok, err = table.apply_action(p, "raise", raise_to=raw.strip())
            if not ok:
                await interaction.response.send_message(err, ephemeral=True)
                return
            await interaction.response.defer()
            await self._after_action(table)

    async def _after_action(self, table):
        """Resolve state after a validated action and refresh the table message."""
        if len(table.live_players()) <= 1:
            await self._finish_no_showdown(table)
            return
        if table.betting_complete():
            result = table.advance_street()
            if result == "showdown":
                await self._showdown(table)
                return
            # new street begins
        table.to_act = table._next_to_act(table.to_act) if table.to_act is not None else None
        if table.to_act is None:
            # safety: nobody to act — settle
            if table.betting_complete():
                result = table.advance_street()
                if result == "showdown":
                    await self._showdown(table)
                    return
        await self._render(table)
        self._arm_timeout(table)

    async def _finish_no_showdown(self, table):
        winner = table.live_players()[0]
        amount = table.pot()
        winner.stack += amount
        table.last_result = f"🏆 **{winner.name}** wins **{amount}** chips (everyone else folded)."
        await self._end_hand(table)

    async def _showdown(self, table):
        pots = table.compute_side_pots()
        lines = []
        for p in sorted(table.live_players(), key=lambda x: best_hand(x.hole + table.board), reverse=True):
            sc = best_hand(p.hole + table.board)
            lines.append(f"**{p.name}** — {cards_str(p.hole)}  ·  *{hand_name(sc)}*")
        payouts = Counter()
        for amount, eligible in pots:
            scored = [(p, best_hand(p.hole + table.board)) for p in eligible]
            best = max(s for _, s in scored)
            winners = [p for p, s in scored if s == best]
            share = amount // len(winners)
            rem = amount % len(winners)
            for i, w in enumerate(winners):
                payouts[w] += share + (1 if i < rem else 0)
        for p, amt in payouts.items():
            p.stack += amt
        win_txt = ", ".join(f"**{p.name}** (+{amt})" for p, amt in sorted(payouts.items(), key=lambda kv: -kv[1]))
        table.last_result = "🃏 **Showdown**\n" + "\n".join(lines) + f"\n\n💰 Pot **{table.pot()}** → {win_txt}"
        await self._end_hand(table)

    async def _end_hand(self, table):
        table.state = "hand_over"
        table.to_act = None
        table.turn_token += 1
        # drop busted players from the lobby seating after the hand
        survivors = [p for p in table.players if p.stack > 0]
        if len(survivors) < MIN_PLAYERS:
            if survivors:
                table.last_result += f"\n\n👑 **{survivors[0].name}** is the last player standing — table over!"
            await self._render(table, final=True)
            await self._score_and_close(table)
            return
        await self._render(table)

    # -- next hand / end --
    async def _handle_nexthand(self, interaction, table):
        if table.state != "hand_over":
            await interaction.response.send_message("No hand to continue.", ephemeral=True)
            return
        if interaction.user.id != table.host_id and table.find(interaction.user.id) is None:
            await interaction.response.send_message("Only players at the table can deal.", ephemeral=True)
            return
        if not table.begin_hand():
            await interaction.response.send_message("Not enough players with chips.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self._table_embed(table), view=self._betting_view(table))
        self._arm_timeout(table)

    async def _handle_end(self, interaction, table):
        if interaction.user.id != table.host_id:
            await interaction.response.send_message("Only the host can end the table.", ephemeral=True)
            return
        await interaction.response.defer()
        await self._score_and_close(table)

    async def _score_and_close(self, table):
        if table.state == "ended":
            return
        table.state = "ended"
        table.turn_token += 1
        ranking = sorted(table.players, key=lambda p: p.stack, reverse=True)
        winner = ranking[0] if ranking else None
        # record scores: chip leader = win, everyone else who joined = a play
        for uid, name in table.participants.items():
            try:
                await bot_post(
                    self.backend_url, self.api_key,
                    f"/api/bot/guilds/{table.guild_id}/games/score",
                    {"user_id": str(uid), "game": "poker", "win": bool(winner and uid == winner.id)},
                )
            except Exception as exc:
                print(f"[poker] score post failed for {uid}: {exc}")
        self.tables.pop(table.channel_id, None)
        embed = discord.Embed(
            title="♠ Poker — Table closed",
            color=SHOWDOWN_COLOR,
            description="\n".join(f"**{i+1}.** {p.name} — {p.stack} chips" for i, p in enumerate(ranking)) or "No players.",
        )
        if winner:
            embed.set_footer(text=f"Winner: {winner.name}")
        try:
            if table.message:
                await table.message.edit(embed=embed, view=None)
        except discord.HTTPException:
            pass

    # -- timeout --
    def _arm_timeout(self, table):
        table.turn_token += 1
        token = table.turn_token
        asyncio.create_task(self._timeout_watch(table, token))

    async def _timeout_watch(self, table, token):
        await asyncio.sleep(TURN_TIMEOUT)
        async with table.lock:
            if table.turn_token != token or table.state != "betting" or table.to_act is None:
                return
            p = table.players[table.to_act]
            action = "check" if p.bet == table.current_bet else "fold"
            ok, _ = table.apply_action(p, action)
            if not ok:
                table.apply_action(p, "fold")
            try:
                ch = self.bot.get_channel(table.channel_id)
                if ch:
                    await ch.send(f"⏰ {p.name} took too long — auto **{action}**.", delete_after=10)
            except discord.HTTPException:
                pass
            await self._after_action(table)

    # -- rendering --
    async def _render(self, table, final=False):
        if not table.message:
            return
        try:
            if table.state == "betting":
                await table.message.edit(embed=self._table_embed(table), view=self._betting_view(table))
            elif table.state == "hand_over":
                await table.message.edit(embed=self._table_embed(table), view=None if final else self._over_view(table))
        except discord.HTTPException as exc:
            print(f"[poker] render failed: {exc}")

    def _lobby_embed(self, table):
        host = table.find(table.host_id)
        lines = []
        for p in table.players:
            tag = " 👑" if p.id == table.host_id else ""
            lines.append(f"• {p.name}{tag} — {p.stack} chips")
        embed = discord.Embed(
            title="♠ Poker table — Lobby",
            color=LOBBY_COLOR,
            description="\n".join(lines) or "No players yet.",
        )
        embed.add_field(name="Players", value=f"{len(table.players)}/{MAX_PLAYERS}", inline=True)
        embed.add_field(name="Blinds", value=f"{SMALL_BLIND}/{BIG_BLIND}", inline=True)
        embed.add_field(name="Start stack", value=str(STARTING_STACK), inline=True)
        embed.set_footer(text=f"Host: {host.name if host else '—'} • Press Join to take a seat")
        return embed

    def _table_embed(self, table):
        color = SHOWDOWN_COLOR if table.state == "hand_over" else TABLE_COLOR
        embed = discord.Embed(title=f"♠ Poker — Hand #{table.hand_no}", color=color)
        embed.add_field(
            name=f"Community  ·  {table.street.title() if table.state == 'betting' else 'Board'}",
            value=cards_str(table.board),
            inline=False,
        )
        rows = []
        for idx, p in enumerate(table.players):
            if not p.in_hand and table.state == "betting":
                continue
            marks = _dealer_marks(table, idx)
            cursor = "➤ " if (table.state == "betting" and table.to_act == idx) else ""
            status = ""
            if p.folded:
                status = " — 🚫 folded"
            elif p.all_in:
                status = " — 🅰️ all-in"
            elif table.state == "betting" and p.bet > 0:
                status = f" — bet {p.bet}"
            rows.append(f"{cursor}**{p.name}** {marks}\n`{p.stack}` chips{status}")
        embed.add_field(name="Players", value="\n".join(rows) or "—", inline=False)
        embed.add_field(name="Pot", value=str(table.pot()), inline=True)
        if table.state == "betting":
            to_call = max(0, table.current_bet - table.players[table.to_act].bet) if table.to_act is not None else 0
            embed.add_field(name="To call", value=str(to_call), inline=True)
            actor = table.players[table.to_act].name if table.to_act is not None else "—"
            embed.set_footer(text=f"{actor} to act • use the buttons • 🃏 shows your cards")
        if table.state == "hand_over" and table.last_result:
            embed.add_field(name="Result", value=table.last_result[:1024], inline=False)
        return embed

    # -- views (buttons handled in on_interaction) --
    def _lobby_view(self, table):
        v = discord.ui.View(timeout=None)
        v.add_item(discord.ui.Button(style=discord.ButtonStyle.success, label="Join", emoji="➕", custom_id=f"pk:join:{table.tid}"))
        v.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label="Leave", emoji="➖", custom_id=f"pk:leave:{table.tid}"))
        v.add_item(discord.ui.Button(style=discord.ButtonStyle.primary, label="Start", emoji="▶️", custom_id=f"pk:start:{table.tid}"))
        v.add_item(discord.ui.Button(style=discord.ButtonStyle.danger, label="Cancel", emoji="✖️", custom_id=f"pk:cancel:{table.tid}"))
        return v

    def _betting_view(self, table):
        v = discord.ui.View(timeout=None)
        facing = table.to_act is not None and table.current_bet > table.players[table.to_act].bet
        v.add_item(discord.ui.Button(style=discord.ButtonStyle.danger, label="Fold", emoji="❌", custom_id=f"pk:fold:{table.tid}"))
        if facing:
            to_call = table.current_bet - table.players[table.to_act].bet
            v.add_item(discord.ui.Button(style=discord.ButtonStyle.primary, label=f"Call {to_call}", emoji="📞", custom_id=f"pk:call:{table.tid}"))
        else:
            v.add_item(discord.ui.Button(style=discord.ButtonStyle.success, label="Check", emoji="✅", custom_id=f"pk:check:{table.tid}"))
        v.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label="Raise", emoji="⬆️", custom_id=f"pk:raise:{table.tid}"))
        v.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label="All-in", emoji="🅰️", custom_id=f"pk:allin:{table.tid}"))
        v.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label="My cards", emoji="🃏", custom_id=f"pk:cards:{table.tid}"))
        return v

    def _over_view(self, table):
        v = discord.ui.View(timeout=None)
        v.add_item(discord.ui.Button(style=discord.ButtonStyle.success, label="Next hand", emoji="🔁", custom_id=f"pk:nexthand:{table.tid}"))
        v.add_item(discord.ui.Button(style=discord.ButtonStyle.danger, label="End table", emoji="⏹️", custom_id=f"pk:end:{table.tid}"))
        return v


# ----- self-test for the evaluator (run: python cogs/poker.py) -----
def _self_test():
    C = lambda r, s: (r, s)
    sf = [C(10, "s"), C(11, "s"), C(12, "s"), C(13, "s"), C(14, "s")]
    quad = [C(9, "s"), C(9, "h"), C(9, "d"), C(9, "c"), C(2, "s")]
    fh = [C(8, "s"), C(8, "h"), C(8, "d"), C(3, "c"), C(3, "s")]
    flush = [C(2, "h"), C(5, "h"), C(9, "h"), C(11, "h"), C(13, "h")]
    straight = [C(5, "s"), C(6, "h"), C(7, "d"), C(8, "c"), C(9, "s")]
    wheel = [C(14, "s"), C(2, "h"), C(3, "d"), C(4, "c"), C(5, "s")]
    trips = [C(7, "s"), C(7, "h"), C(7, "d"), C(13, "c"), C(2, "s")]
    twop = [C(6, "s"), C(6, "h"), C(9, "d"), C(9, "c"), C(2, "s")]
    pair = [C(4, "s"), C(4, "h"), C(9, "d"), C(11, "c"), C(2, "s")]
    high = [C(2, "s"), C(5, "h"), C(9, "d"), C(11, "c"), C(13, "s")]
    assert evaluate_5(sf) > evaluate_5(quad) > evaluate_5(fh) > evaluate_5(flush)
    assert evaluate_5(flush) > evaluate_5(straight) > evaluate_5(trips) > evaluate_5(twop)
    assert evaluate_5(twop) > evaluate_5(pair) > evaluate_5(high)
    assert evaluate_5(wheel) == (4, 5)            # wheel straight, 5-high
    assert evaluate_5(sf)[0] == 8 and evaluate_5(quad)[0] == 7
    # best_of_7 picks the flush out of 7 cards
    seven = flush + [C(14, "d"), C(14, "c")]
    assert best_hand(seven)[0] == 5
    # full house is the best 5 out of a 7-card mix (no quads present)
    seven2 = fh + [C(13, "c"), C(2, "d")]
    assert best_hand(seven2)[0] == 6
    print("poker self-test OK")


async def setup(bot):
    await bot.add_cog(Poker(bot))


if __name__ == "__main__":
    _self_test()
