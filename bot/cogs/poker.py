"""Poker cog — multiplayer Texas Hold'em tables (Games category, Basic).

A table lives in a channel. Members open one with `!poker`, join via a button,
and play hand-by-hand: blinds, hole cards (revealed ephemerally via a button),
flop/turn/river, betting (fold/check/call/raise/all-in), proper layered side pots
and a showdown with a 7-card hand evaluator. The chip leader when the table ends
is recorded as a win via the shared /games/score endpoint.

The host can fill empty seats with AI bots (Add/Remove bot in the lobby). Bots
play automatically on their turn using a rough hand-strength + pot-odds heuristic;
they are never recorded to the leaderboard (only real participants are).

Hole cards and the community board are rendered as card-face PNGs via Pillow when
available; without Pillow the cog degrades gracefully to text card symbols.

Interactions use on_interaction with custom_id prefix "pk:<action>:<tid>" so they
survive across handlers; the Raise button opens a Modal. All state is in-memory
(one table per channel) — a bot restart drops active tables.

Backend contract (X-Bot-Token auth, shared Games module):
  GET  /api/bot/guilds/{gid}/settings/games  → { games_channel_id, poker_enabled, ... }
  POST /api/bot/guilds/{gid}/games/score      body { user_id, game:"poker", win }

Logging prefix: "[poker]".
"""

import asyncio
import io
import itertools
import math
import random
import time
import uuid
from collections import Counter

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_post

# Card images are rendered with Pillow when available; otherwise the cog falls
# back to text card symbols so it keeps working without the dependency.
try:
    from PIL import Image, ImageDraw, ImageFont
    IMAGES_AVAILABLE = True
except Exception:  # pragma: no cover
    IMAGES_AVAILABLE = False


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

# Table render themes (felt design) — keys mirror backend POKER_THEMES and the
# dashboard picker. Each: bg gradient, felt fill/edge, rail (wooden rim), accent
# (highlight/dealer), embed accent color.
THEMES = {
    "classic":  {"label": "Classic Green", "bg": ((16, 20, 18), (26, 34, 28)), "felt": (34, 110, 66), "felt2": (24, 84, 50), "rail": (60, 40, 24), "rail2": (104, 72, 40), "accent": (245, 205, 90), "embed": 0x2ECC71},
    "midnight": {"label": "Midnight Blue", "bg": ((12, 15, 24), (22, 28, 46), ), "felt": (32, 52, 96), "felt2": (22, 38, 74), "rail": (24, 30, 52), "rail2": (62, 78, 130), "accent": (122, 176, 255), "embed": 0x5B8DEF},
    "crimson":  {"label": "Crimson Red", "bg": ((22, 12, 14), (38, 18, 22)), "felt": (132, 36, 44), "felt2": (102, 24, 32), "rail": (46, 18, 20), "rail2": (96, 44, 48), "accent": (255, 206, 130), "embed": 0xD9495B},
    "charcoal": {"label": "Charcoal", "bg": ((14, 15, 18), (26, 28, 32)), "felt": (52, 58, 66), "felt2": (38, 42, 50), "rail": (22, 24, 28), "rail2": (70, 76, 86), "accent": (120, 224, 200), "embed": 0x4EC8B0},
    "royal":    {"label": "Royal Purple", "bg": ((18, 14, 26), (32, 22, 46)), "felt": (78, 46, 122), "felt2": (58, 34, 96), "rail": (36, 24, 56), "rail2": (98, 70, 150), "accent": (244, 206, 128), "embed": 0x9B6BE3},
}
DEFAULT_THEME = "classic"


def theme_of(table):
    return THEMES.get(getattr(table, "theme", DEFAULT_THEME), THEMES[DEFAULT_THEME])
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


# ----- Card image rendering (Pillow) -----

BOT_NAMES = ["Ada", "Björn", "Cleo", "Dex", "Echo", "Fritz", "Gína", "Hiro", "Iris", "Juno"]
_RED = (208, 0, 0)
_BLACK = (24, 24, 28)
CARD_W, CARD_H, GAP, PAD = 90, 126, 14, 16


def _load_font(size):
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "arialbd.ttf", "arial.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_suit(d, cx, cy, s, suit, color):
    if suit == "d":
        d.polygon([(cx, cy - s), (cx + s * 0.78, cy), (cx, cy + s), (cx - s * 0.78, cy)], fill=color)
    elif suit == "h":
        top = cy - s * 0.7
        d.ellipse([cx - s, top, cx, top + s], fill=color)
        d.ellipse([cx, top, cx + s, top + s], fill=color)
        d.polygon([(cx - s + 1, top + s * 0.45), (cx + s - 1, top + s * 0.45), (cx, cy + s)], fill=color)
    elif suit == "s":
        bot = cy + s * 0.7
        d.ellipse([cx - s, bot - s, cx, bot], fill=color)
        d.ellipse([cx, bot - s, cx + s, bot], fill=color)
        d.polygon([(cx - s + 1, bot - s * 0.45), (cx + s - 1, bot - s * 0.45), (cx, cy - s)], fill=color)
        d.polygon([(cx - s * 0.42, cy + s), (cx + s * 0.42, cy + s), (cx + s * 0.14, cy + s * 0.35), (cx - s * 0.14, cy + s * 0.35)], fill=color)
    elif suit == "c":
        r = s * 0.62
        d.ellipse([cx - r, cy - s, cx + r, cy - s + 2 * r], fill=color)
        d.ellipse([cx - s, cy - r * 0.4, cx - s + 2 * r, cy - r * 0.4 + 2 * r], fill=color)
        d.ellipse([cx + s - 2 * r, cy - r * 0.4, cx + s, cy - r * 0.4 + 2 * r], fill=color)
        d.polygon([(cx - s * 0.42, cy + s), (cx + s * 0.42, cy + s), (cx + s * 0.14, cy + s * 0.2), (cx - s * 0.14, cy + s * 0.2)], fill=color)


def _draw_card(d, x, y, card, fonts):
    rank, suit = card
    color = _RED if suit in "hd" else _BLACK
    d.rounded_rectangle([x, y, x + CARD_W, y + CARD_H], radius=11, fill=(252, 252, 250), outline=(40, 40, 50), width=2)
    label = rank_label(rank)
    d.text((x + 8, y + 4), label, font=fonts["rank"], fill=color)
    _draw_suit(d, x + 16, y + 46, 8, suit, color)
    _draw_suit(d, x + CARD_W / 2, y + CARD_H / 2 + 12, 22, suit, color)
    d.text((x + CARD_W - 8, y + CARD_H - 6), label, font=fonts["rank"], fill=color, anchor="rs")


def _draw_back(d, x, y):
    d.rounded_rectangle([x, y, x + CARD_W, y + CARD_H], radius=11, fill=(34, 53, 122), outline=(20, 30, 70), width=2)
    d.rounded_rectangle([x + 8, y + 8, x + CARD_W - 8, y + CARD_H - 8], radius=8, outline=(120, 150, 230), width=2)
    for i in range(-CARD_H, CARD_W, 14):
        d.line([(x + 10 + i, y + CARD_H - 10), (x + 10 + i + CARD_H, y + 10)], fill=(70, 95, 180), width=2)


def render_cards_png(cards, hidden_count=0):
    """Render a row of cards (+ optional face-down backs) to a PNG BytesIO."""
    if not IMAGES_AVAILABLE:
        return None
    try:
        n = len(cards) + hidden_count
        if n <= 0:
            return None
        width = PAD * 2 + n * CARD_W + (n - 1) * GAP
        height = PAD * 2 + CARD_H
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        fonts = {"rank": _load_font(30)}
        x = PAD
        for c in cards:
            _draw_card(d, x, PAD, c, fonts)
            x += CARD_W + GAP
        for _ in range(hidden_count):
            _draw_back(d, x, PAD)
            x += CARD_W + GAP
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf
    except Exception as exc:  # never let rendering break the game
        print(f"[poker] card render failed: {exc}")
        return None


def _draw_card_g(d, x, y, w, h, card, font, face_down=False):
    """Generic scaled card (used by the full-table renderer)."""
    if face_down:
        d.rounded_rectangle([x, y, x + w, y + h], radius=max(4, int(w * 0.13)), fill=(34, 53, 122), outline=(18, 26, 60), width=2)
        d.rounded_rectangle([x + 4, y + 4, x + w - 4, y + h - 4], radius=4, outline=(110, 140, 220), width=1)
        return
    rank, suit = card
    color = _RED if suit in "hd" else _BLACK
    d.rounded_rectangle([x, y, x + w, y + h], radius=max(4, int(w * 0.13)), fill=(252, 252, 250), outline=(40, 40, 50), width=2)
    label = rank_label(rank)
    d.text((x + w * 0.10, y + h * 0.04), label, font=font, fill=color)
    _draw_suit(d, x + w / 2, y + h * 0.60, w * 0.24, suit, color)


def _fit(s, n):
    return s if len(s) <= n else s[: n - 1] + "…"


def render_table_png(table):
    """Render the whole poker table (felt, seats, community cards, pot) to PNG."""
    if not IMAGES_AVAILABLE:
        return None
    try:
        th = theme_of(table)
        W, H = 940, 660
        img = Image.new("RGB", (W, H), th["bg"][0])
        d = ImageDraw.Draw(img)
        # vertical background gradient
        c0, c1 = th["bg"]
        for y in range(H):
            f = y / H
            d.line([(0, y), (W, y)], fill=tuple(int(c0[k] + (c1[k] - c0[k]) * f) for k in range(3)))

        # felt table: wooden rail + felt ellipse + inner ring
        rail = [54, 92, W - 54, H - 92]
        felt = [86, 124, W - 86, H - 124]
        d.ellipse(rail, fill=th["rail"], outline=th["rail2"], width=10)
        d.ellipse(felt, fill=th["felt"], outline=th["felt2"], width=6)
        d.ellipse([felt[0] + 34, felt[1] + 26, felt[2] - 34, felt[3] - 26], outline=th["felt2"], width=2)

        cx, cy = W // 2, H // 2
        f_rank = _load_font(26)
        f_pot = _load_font(30)
        f_street = _load_font(18)
        f_name = _load_font(20)
        f_sub = _load_font(17)
        f_tag = _load_font(16)
        f_hole = _load_font(16)

        # -- community cards (center) --
        cw, ch = 60, 84
        gap = 12
        board = table.board or []
        slots = 5 if table.state in ("betting", "hand_over") else 0
        if slots:
            total = slots * cw + (slots - 1) * gap
            bx = cx - total // 2
            by = cy - ch // 2 + 8
            for i in range(slots):
                x = bx + i * (cw + gap)
                if i < len(board):
                    _draw_card_g(d, x, by, cw, ch, board[i], f_rank)
                else:
                    # empty slot placeholder
                    d.rounded_rectangle([x, by, x + cw, by + ch], radius=8, outline=th["felt2"], width=2)

        # -- pot + street label (above community) --
        pot = table.pot()
        pot_txt = f"POT  {pot}"
        d.text((cx, cy - ch // 2 - 30), pot_txt, font=f_pot, fill=(252, 248, 235), anchor="mm")
        if table.state == "betting":
            d.text((cx, cy + ch // 2 + 26), table.street.upper(), font=f_street, fill=th["accent"], anchor="mm")
        elif table.state == "hand_over":
            d.text((cx, cy + ch // 2 + 26), "SHOWDOWN", font=f_street, fill=th["accent"], anchor="mm")

        # -- seats around the ellipse (seat 0 = bottom) --
        n = len(table.players)
        arx = (felt[2] - felt[0]) / 2 + 30
        ary = (felt[3] - felt[1]) / 2 + 26
        bw, bh = 174, 66
        for idx, p in enumerate(table.players):
            ang = math.radians(90 + 360 * idx / n)
            sx = cx + arx * math.cos(ang)
            sy = cy + ary * math.sin(ang)
            x = int(min(max(sx - bw / 2, 6), W - bw - 6))
            y = int(min(max(sy - bh / 2, 6), H - bh - 6))

            in_hand = p.in_hand if table.state in ("betting", "hand_over") else True
            active = table.state == "betting" and table.to_act == idx
            folded = p.folded and table.state in ("betting", "hand_over")
            fill = (30, 33, 40) if not folded else (26, 27, 31)
            border = th["accent"] if active else (74, 80, 92)
            if active:
                d.rounded_rectangle([x - 3, y - 3, x + bw + 3, y + bh + 3], radius=15, outline=th["accent"], width=2)
            d.rounded_rectangle([x, y, x + bw, y + bh], radius=12, fill=fill, outline=border, width=3 if active else 2)

            name_col = (236, 239, 246) if not folded else (120, 122, 130)
            label = _fit(p.name, 14)
            d.text((x + 12, y + 8), label, font=f_name, fill=name_col)
            if p.is_bot:
                d.text((x + bw - 12, y + 9), "BOT", font=f_tag, fill=(150, 156, 168), anchor="ra")

            # chip stack line
            d.ellipse([x + 12, y + 38, x + 24, y + 50], fill=th["accent"], outline=(0, 0, 0))
            d.text((x + 30, y + 36), f"{p.stack}", font=f_sub, fill=(206, 211, 220) if not folded else (110, 112, 120))

            # right side: dealer/blind tag (top) + status (bottom)
            tags = _dealer_marks(table, idx).replace("`", "").strip()
            if tags and not folded:
                d.text((x + bw - 12, y + 30), tags, font=f_tag, fill=th["accent"], anchor="ra")
            status = ""
            scol = (180, 186, 196)
            if folded:
                status, scol = "FOLD", (150, 90, 90)
            elif p.all_in:
                status, scol = "ALL-IN", th["accent"]
            elif table.state == "betting" and p.bet > 0:
                status, scol = f"bet {p.bet}", (206, 211, 220)
            if status:
                d.text((x + bw - 12, y + 46), status, font=f_tag, fill=scol, anchor="ra")

            # showdown: reveal live players' hole cards just inside the felt
            if table.state == "hand_over" and p.in_hand and not p.folded and p.hole:
                hw, hh, hg = 34, 48, 6
                tot = 2 * hw + hg
                hx = int(min(max(x + bw / 2 - tot / 2, 6), W - tot - 6))
                hy = y + bh + 4 if sy < cy else y - hh - 4
                for j, c in enumerate(p.hole[:2]):
                    _draw_card_g(d, hx + j * (hw + hg), hy, hw, hh, c, f_hole)

        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf
    except Exception as exc:
        print(f"[poker] table render failed: {exc}")
        return None


# ----- Player + Table -----

class PokerPlayer:
    __slots__ = ("id", "name", "stack", "hole", "folded", "all_in", "bet", "total", "acted", "in_hand", "is_bot")

    def __init__(self, uid, name, stack, is_bot=False):
        self.id = uid
        self.name = name
        self.stack = stack
        self.is_bot = is_bot
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
        self.theme = DEFAULT_THEME  # felt design (set from guild games settings)
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
        theme = settings.get("poker_table_theme")
        if theme in THEMES:
            table.theme = theme
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
            content = f"🃏 Your hand: **{cards_str(p.hole)}**{extra}"
            buf = render_cards_png(p.hole)
            if buf is not None:
                await interaction.response.send_message(content, file=discord.File(buf, filename="hand.png"), ephemeral=True)
            else:
                await interaction.response.send_message(content, ephemeral=True)
            return

        # all other actions mutate state under the lock
        async with table.lock:
            if action in ("join", "leave", "start", "cancel", "addbot", "rmbot"):
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
        elif action == "addbot":
            if uid != table.host_id:
                await interaction.response.send_message("Only the host can add bots.", ephemeral=True)
                return
            if len(table.players) >= MAX_PLAYERS:
                await interaction.response.send_message("The table is full.", ephemeral=True)
                return
            used = {p.name for p in table.players if p.is_bot}
            pick = next((f"🤖 {n}" for n in BOT_NAMES if f"🤖 {n}" not in used), None)
            if pick is None:
                await interaction.response.send_message("No more bot seats available.", ephemeral=True)
                return
            table.players.append(PokerPlayer(f"bot:{uuid.uuid4().hex[:8]}", pick, STARTING_STACK, is_bot=True))
            await interaction.response.edit_message(embed=self._lobby_embed(table), view=self._lobby_view(table))
        elif action == "rmbot":
            if uid != table.host_id:
                await interaction.response.send_message("Only the host can remove bots.", ephemeral=True)
                return
            bot_player = next((p for p in reversed(table.players) if p.is_bot), None)
            if not bot_player:
                await interaction.response.send_message("There are no bots to remove.", ephemeral=True)
                return
            table.players.remove(bot_player)
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
            await interaction.response.defer()
            await self._render(table)
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
        await interaction.response.defer()
        await self._render(table)
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
                await table.message.edit(content=None, embed=embed, view=None, attachments=[])
        except discord.HTTPException:
            pass

    # -- timeout + bot turns --
    def _arm_timeout(self, table):
        table.turn_token += 1
        token = table.turn_token
        # If it's a bot's turn, let the AI act after a short think; otherwise arm the
        # idle-timeout for the human to act.
        if table.state == "betting" and table.to_act is not None and table.players[table.to_act].is_bot:
            asyncio.create_task(self._bot_act(table, token))
        else:
            asyncio.create_task(self._timeout_watch(table, token))

    def _bot_strength(self, table, p):
        """Rough 0..1 hand-strength estimate for the AI."""
        if table.board:
            cat = best_hand(p.hole + table.board)[0]
            return min(1.0, 0.18 + cat * 0.11)
        r1, r2 = sorted((p.hole[0][0], p.hole[1][0]), reverse=True)
        suited = p.hole[0][1] == p.hole[1][1]
        if r1 == r2:
            return min(1.0, 0.55 + (r1 - 2) / 26)
        s = (r1 + r2) / 40.0
        if suited:
            s += 0.08
        if 0 < r1 - r2 <= 2:
            s += 0.05
        return min(0.95, s)

    def _bot_decide(self, table, p):
        """Return (action, raise_to|None) for the AI player p."""
        strength = self._bot_strength(table, p)
        jitter = random.uniform(-0.08, 0.08)
        strength = max(0.0, min(1.0, strength + jitter))
        to_call = table.current_bet - p.bet
        pot = table.pot()
        min_to = table.current_bet + table.last_raise
        max_to = p.bet + p.stack

        def raise_amount():
            target = table.current_bet + max(BIG_BLIND, int(pot * 0.6))
            target = max(target, min_to)
            return min(target, max_to)

        if to_call <= 0:
            if strength > 0.62 and max_to > table.current_bet:
                return ("raise", raise_amount())
            if strength > 0.4 and random.random() < 0.35 and max_to > table.current_bet:
                return ("raise", raise_amount())
            return ("check", None)
        # facing a bet
        odds = to_call / (pot + to_call) if (pot + to_call) else 1
        if strength > 0.78 and max_to > table.current_bet:
            return ("raise", raise_amount()) if random.random() < 0.7 else ("call", None)
        if strength >= odds + 0.06:
            return ("call", None)
        if random.random() < 0.05 and strength > 0.3:
            return ("call", None)  # occasional float/bluff-catch
        return ("fold", None)

    async def _bot_act(self, table, token):
        await asyncio.sleep(random.uniform(1.2, 2.4))
        async with table.lock:
            if table.turn_token != token or table.state != "betting" or table.to_act is None:
                return
            p = table.players[table.to_act]
            if not p.is_bot:
                return
            action, raise_to = self._bot_decide(table, p)
            ok, _ = table.apply_action(p, action, raise_to=raise_to)
            if not ok:  # fall back to a always-legal action
                if table.current_bet - p.bet > 0:
                    ok, _ = table.apply_action(p, "call")
                if not ok:
                    table.apply_action(p, "check")
            await self._after_action(table)

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
        if table.state == "betting":
            view = self._betting_view(table)
        elif table.state == "hand_over":
            view = None if final else self._over_view(table)
        else:
            view = None
        # Preferred path: send the rendered table as a PLAIN attachment (not inside
        # an embed) so Discord shows it large/inline — the caption goes in the
        # message content above it. Fall back to a text embed if rendering fails.
        buf = render_table_png(table)
        try:
            if buf is not None:
                await table.message.edit(
                    content=self._caption_text(table), embed=None, view=view,
                    attachments=[discord.File(buf, filename="table.png")],
                )
            else:
                await table.message.edit(content=None, embed=self._table_embed(table), view=view, attachments=[])
        except discord.HTTPException as exc:
            print(f"[poker] render failed: {exc}")

    def _caption_text(self, table):
        """Plain-text caption shown above the rendered table image."""
        head = f"♠ **Poker — Hand #{table.hand_no}**"
        if table.state == "betting" and table.to_act is not None:
            actor = table.players[table.to_act]
            to_call = max(0, table.current_bet - actor.bet)
            call_txt = f"to call **{to_call}**" if to_call else "can **check**"
            return f"{head}\n➤ **{actor.name}** to act · {call_txt} · 🃏 shows your cards"
        if table.state == "hand_over" and table.last_result:
            return f"{head}\n{table.last_result[:1800]}"
        return head

    def _lobby_embed(self, table):
        host = table.find(table.host_id)
        lines = []
        for p in table.players:
            tag = " 👑" if p.id == table.host_id else ""
            if p.is_bot:
                tag += " 🤖"
            lines.append(f"• {p.name}{tag} — {p.stack} chips")
        embed = discord.Embed(
            title="♠ Poker table — Lobby",
            color=LOBBY_COLOR,
            description="\n".join(lines) or "No players yet.",
        )
        embed.add_field(name="Players", value=f"{len(table.players)}/{MAX_PLAYERS}", inline=True)
        embed.add_field(name="Blinds", value=f"{SMALL_BLIND}/{BIG_BLIND}", inline=True)
        embed.add_field(name="Start stack", value=str(STARTING_STACK), inline=True)
        embed.set_footer(text=f"Host: {host.name if host else '—'} • Design: {theme_of(table)['label']} • Press Join to take a seat")
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
        v.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label="Add bot", emoji="🤖", custom_id=f"pk:addbot:{table.tid}"))
        v.add_item(discord.ui.Button(style=discord.ButtonStyle.secondary, label="Remove bot", emoji="🗑️", custom_id=f"pk:rmbot:{table.tid}"))
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
