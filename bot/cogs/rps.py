"""Rock-Paper-Scissors cog.

`!rps [@opponent]` starts a game. Without an opponent the author plays against
the bot (instant resolve). With an opponent both human players must each pick a
move via the buttons; once both have chosen the result is revealed.

Moves are picked via buttons (custom_id "rps:<token>:<choice>") handled in
on_interaction so they keep working across restarts. Sessions live in memory
keyed by an 8-char token; an expired/unknown token replies ephemerally.

Settings are read from the "games" module:
  GET /api/bot/guilds/{gid}/settings/games
      → { games_channel_id, rps_enabled, games_language, ... } or None

Scoring (humans only, never the bot):
  POST /api/bot/guilds/{gid}/games/score
      body { user_id, game: "rps", win: <bool> }

User-facing text is localized via the shared games i18n table
(per-guild `games_language`). Logging prefix: "[rps]".
"""

import time
import uuid
import random

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_post
from utils.game_i18n import make_translator, lang_of


SETTINGS_TTL_SECONDS = 60
RPS_COLOR = 0x6366F1

CHOICES = ("rock", "paper", "scissors")
EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
# What each move beats.
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

_STRINGS = {
    "en": {
        "not_enabled": "Rock-Paper-Scissors is not enabled here.",
        "play_in_channel": "Please play games in {where}.",
        "configured_channel": "the configured games channel",
        "no_challenge_bot": "You can't challenge a bot. Use `!rps` to play against me.",
        "no_challenge_self": "You can't challenge yourself.",
        "title": "🪨 📄 ✂️ Rock-Paper-Scissors",
        "make_move": "{author}, make your move!",
        "pvp_intro": "{p1} vs {p2}\n\nBoth players, pick your move with the buttons below.",
        "cant_post": "I can't post in this channel.",
        "expired": "This game has expired.",
        "went_wrong": "Something went wrong with that game.",
        "not_yours": "This game isn't yours. Start your own with `!rps`.",
        "you_win": "🎉 {player} wins!",
        "bot_wins": "🤖 I win this time, {player}!",
        "tie": "🤝 It's a tie!",
        "field_me": "Me",
        "field_result": "Result",
        "not_in_match": "You're not part of this match.",
        "already_chose": "You already chose {choice}.",
        "you_chose": "You chose {choice}. Waiting for the result…",
        "choice_rock": "Rock",
        "choice_paper": "Paper",
        "choice_scissors": "Scissors",
    },
    "de": {
        "not_enabled": "Schere-Stein-Papier ist hier nicht aktiviert.",
        "play_in_channel": "Bitte spiele Spiele in {where}.",
        "configured_channel": "dem konfigurierten Spiele-Channel",
        "no_challenge_bot": "Du kannst keinen Bot herausfordern. Nutze `!rps`, um gegen mich zu spielen.",
        "no_challenge_self": "Du kannst dich nicht selbst herausfordern.",
        "title": "🪨 📄 ✂️ Schere-Stein-Papier",
        "make_move": "{author}, mach deinen Zug!",
        "pvp_intro": "{p1} gegen {p2}\n\nBeide Spieler, wählt euren Zug mit den Buttons unten.",
        "cant_post": "Ich kann in diesem Channel nicht schreiben.",
        "expired": "Dieses Spiel ist abgelaufen.",
        "went_wrong": "Bei diesem Spiel ist etwas schiefgelaufen.",
        "not_yours": "Dieses Spiel gehört nicht dir. Starte dein eigenes mit `!rps`.",
        "you_win": "🎉 {player} gewinnt!",
        "bot_wins": "🤖 Diesmal gewinne ich, {player}!",
        "tie": "🤝 Unentschieden!",
        "field_me": "Ich",
        "field_result": "Ergebnis",
        "not_in_match": "Du bist nicht Teil dieses Matches.",
        "already_chose": "Du hast bereits {choice} gewählt.",
        "you_chose": "Du hast {choice} gewählt. Warte auf das Ergebnis…",
        "choice_rock": "Stein",
        "choice_paper": "Papier",
        "choice_scissors": "Schere",
    },
    "tr": {
        "not_enabled": "Taş-Kâğıt-Makas burada etkin değil.",
        "play_in_channel": "Lütfen oyunları {where} içinde oyna.",
        "configured_channel": "ayarlanmış oyun kanalı",
        "no_challenge_bot": "Bir botu meydan okuyamazsın. Bana karşı oynamak için `!rps` kullan.",
        "no_challenge_self": "Kendine meydan okuyamazsın.",
        "title": "🪨 📄 ✂️ Taş-Kâğıt-Makas",
        "make_move": "{author}, hamleni yap!",
        "pvp_intro": "{p1} vs {p2}\n\nİki oyuncu da aşağıdaki düğmelerle hamlesini seçsin.",
        "cant_post": "Bu kanala mesaj gönderemiyorum.",
        "expired": "Bu oyunun süresi doldu.",
        "went_wrong": "Bu oyunda bir şeyler ters gitti.",
        "not_yours": "Bu oyun sana ait değil. Kendi oyununu `!rps` ile başlat.",
        "you_win": "🎉 {player} kazandı!",
        "bot_wins": "🤖 Bu sefer ben kazandım, {player}!",
        "tie": "🤝 Berabere!",
        "field_me": "Ben",
        "field_result": "Sonuç",
        "not_in_match": "Bu maçın parçası değilsin.",
        "already_chose": "Zaten {choice} seçtin.",
        "you_chose": "{choice} seçtin. Sonuç bekleniyor…",
        "choice_rock": "Taş",
        "choice_paper": "Kâğıt",
        "choice_scissors": "Makas",
    },
    "ru": {
        "not_enabled": "Камень-ножницы-бумага здесь не включены.",
        "play_in_channel": "Пожалуйста, играйте в играх в {where}.",
        "configured_channel": "настроенном игровом канале",
        "no_challenge_bot": "Ты не можешь вызвать бота. Используй `!rps`, чтобы сыграть против меня.",
        "no_challenge_self": "Ты не можешь вызвать самого себя.",
        "title": "🪨 📄 ✂️ Камень-ножницы-бумага",
        "make_move": "{author}, сделай свой ход!",
        "pvp_intro": "{p1} против {p2}\n\nОба игрока, выберите свой ход с помощью кнопок ниже.",
        "cant_post": "Я не могу писать в этом канале.",
        "expired": "Срок этой игры истёк.",
        "went_wrong": "С этой игрой что-то пошло не так.",
        "not_yours": "Эта игра не твоя. Начни свою с помощью `!rps`.",
        "you_win": "🎉 {player} побеждает!",
        "bot_wins": "🤖 На этот раз побеждаю я, {player}!",
        "tie": "🤝 Ничья!",
        "field_me": "Я",
        "field_result": "Результат",
        "not_in_match": "Ты не участвуешь в этом матче.",
        "already_chose": "Ты уже выбрал {choice}.",
        "you_chose": "Ты выбрал {choice}. Ожидание результата…",
        "choice_rock": "Камень",
        "choice_paper": "Бумага",
        "choice_scissors": "Ножницы",
    },
    "pl": {
        "not_enabled": "Kamień-papier-nożyce nie są tutaj włączone.",
        "play_in_channel": "Graj w gry na {where}.",
        "configured_channel": "skonfigurowanym kanale gier",
        "no_challenge_bot": "Nie możesz wyzwać bota. Użyj `!rps`, aby zagrać ze mną.",
        "no_challenge_self": "Nie możesz wyzwać samego siebie.",
        "title": "🪨 📄 ✂️ Kamień-papier-nożyce",
        "make_move": "{author}, wykonaj swój ruch!",
        "pvp_intro": "{p1} vs {p2}\n\nObaj gracze, wybierzcie swój ruch przyciskami poniżej.",
        "cant_post": "Nie mogę pisać na tym kanale.",
        "expired": "Ta gra wygasła.",
        "went_wrong": "Coś poszło nie tak z tą grą.",
        "not_yours": "Ta gra nie jest twoja. Rozpocznij własną za pomocą `!rps`.",
        "you_win": "🎉 {player} wygrywa!",
        "bot_wins": "🤖 Tym razem ja wygrywam, {player}!",
        "tie": "🤝 Remis!",
        "field_me": "Ja",
        "field_result": "Wynik",
        "not_in_match": "Nie bierzesz udziału w tym meczu.",
        "already_chose": "Już wybrałeś {choice}.",
        "you_chose": "Wybrałeś {choice}. Oczekiwanie na wynik…",
        "choice_rock": "Kamień",
        "choice_paper": "Papier",
        "choice_scissors": "Nożyce",
    },
}

t = make_translator(_STRINGS)


def label_of(lang, choice):
    return t(lang, f"choice_{choice}")


def pretty(lang, choice):
    return f"{EMOJI.get(choice, '')} {label_of(lang, choice)}".strip()


def resolve(a, b):
    """Return 1 if `a` beats `b`, -1 if `b` beats `a`, 0 on a tie."""
    if a == b:
        return 0
    return 1 if BEATS.get(a) == b else -1


def build_view(lang, token, disabled=False):
    view = discord.ui.View(timeout=None)
    for choice in CHOICES:
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label=label_of(lang, choice),
            emoji=EMOJI[choice],
            custom_id=f"rps:{token}:{choice}",
            disabled=disabled,
        ))
    return view


class RPS(commands.Cog):
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

    async def _score(self, guild_id, user_id, win):
        """Record a result for a single human player. Never call for the bot."""
        try:
            await bot_post(
                self.backend_url, self.api_key,
                f"/api/bot/guilds/{guild_id}/games/score",
                {"user_id": str(user_id), "game": "rps", "win": bool(win)},
            )
        except Exception as exc:
            print(f"[rps] score failed in {guild_id} for {user_id}: {exc}")

    @commands.command(name="rps")
    @commands.guild_only()
    async def rps(self, ctx, opponent: discord.Member = None):
        settings = await self._get_settings(ctx.guild.id, force=True)
        lang = lang_of(settings)
        if not settings or not settings.get("rps_enabled"):
            await ctx.reply(t(lang, "not_enabled"), mention_author=False)
            return

        games_channel_id = settings.get("games_channel_id")
        if games_channel_id and str(games_channel_id) != str(ctx.channel.id):
            channel = ctx.guild.get_channel(int(games_channel_id)) if str(games_channel_id).isdigit() else None
            where = channel.mention if channel else t(lang, "configured_channel")
            await ctx.reply(t(lang, "play_in_channel", where=where), mention_author=False)
            return

        # vs opponent
        if opponent is not None:
            if opponent.bot:
                await ctx.reply(t(lang, "no_challenge_bot"), mention_author=False)
                return
            if opponent.id == ctx.author.id:
                await ctx.reply(t(lang, "no_challenge_self"), mention_author=False)
                return
            await self._start_pvp(ctx, opponent, lang)
            return

        # vs bot
        await self._start_vs_bot(ctx, lang)

    async def _start_vs_bot(self, ctx, lang):
        token = uuid.uuid4().hex[:8]
        self._sessions[token] = {
            "mode": "bot",
            "guild_id": ctx.guild.id,
            "author_id": ctx.author.id,
            "lang": lang,
            "created": time.time(),
        }
        embed = discord.Embed(
            title=t(lang, "title"),
            description=t(lang, "make_move", author=ctx.author.mention),
            color=RPS_COLOR,
        )
        try:
            await ctx.send(embed=embed, view=build_view(lang, token))
        except discord.Forbidden:
            self._sessions.pop(token, None)
            await ctx.reply(t(lang, "cant_post"), mention_author=False)

    async def _start_pvp(self, ctx, opponent, lang):
        token = uuid.uuid4().hex[:8]
        self._sessions[token] = {
            "mode": "pvp",
            "guild_id": ctx.guild.id,
            "p1_id": ctx.author.id,
            "p2_id": opponent.id,
            "p1_choice": None,
            "p2_choice": None,
            "lang": lang,
            "created": time.time(),
        }
        embed = discord.Embed(
            title=t(lang, "title"),
            description=t(lang, "pvp_intro", p1=ctx.author.mention, p2=opponent.mention),
            color=RPS_COLOR,
        )
        try:
            await ctx.send(embed=embed, view=build_view(lang, token))
        except discord.Forbidden:
            self._sessions.pop(token, None)
            await ctx.reply(t(lang, "cant_post"), mention_author=False)

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type != discord.InteractionType.component or interaction.guild is None:
            return
        custom_id = (interaction.data or {}).get("custom_id") or ""
        if not custom_id.startswith("rps:"):
            return

        parts = custom_id.split(":")
        if len(parts) != 3:
            return
        _, token, choice = parts
        if choice not in CHOICES:
            return

        session = self._sessions.get(token)
        if session is None:
            try:
                await interaction.response.send_message(t("en", "expired"), ephemeral=True)
            except Exception:
                pass
            return

        lang = session.get("lang", "en")
        try:
            if session.get("mode") == "bot":
                await self._handle_vs_bot(interaction, token, session, choice)
            else:
                await self._handle_pvp(interaction, token, session, choice)
        except Exception as exc:
            print(f"[rps] interaction error in {interaction.guild.id}: {exc}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(t(lang, "went_wrong"), ephemeral=True)
                else:
                    await interaction.response.send_message(t(lang, "went_wrong"), ephemeral=True)
            except Exception:
                pass

    async def _handle_vs_bot(self, interaction, token, session, choice):
        lang = session.get("lang", "en")
        if interaction.user.id != session["author_id"]:
            await interaction.response.send_message(t(lang, "not_yours"), ephemeral=True)
            return

        # Consume the session up front so a double-click can't resolve twice.
        self._sessions.pop(token, None)

        bot_choice = random.choice(CHOICES)
        outcome = resolve(choice, bot_choice)  # 1 player wins, -1 bot wins, 0 tie

        if outcome == 1:
            result = t(lang, "you_win", player=interaction.user.mention)
            win = True
        elif outcome == -1:
            result = t(lang, "bot_wins", player=interaction.user.mention)
            win = False
        else:
            result = t(lang, "tie")
            win = False

        embed = discord.Embed(title=t(lang, "title"), color=RPS_COLOR)
        embed.add_field(name=str(interaction.user.display_name), value=pretty(lang, choice), inline=True)
        embed.add_field(name=t(lang, "field_me"), value=pretty(lang, bot_choice), inline=True)
        embed.add_field(name=t(lang, "field_result"), value=result, inline=False)

        await interaction.response.edit_message(embed=embed, view=build_view(lang, token, disabled=True))
        await self._score(session["guild_id"], session["author_id"], win)

    async def _handle_pvp(self, interaction, token, session, choice):
        lang = session.get("lang", "en")
        uid = interaction.user.id
        if uid == session["p1_id"]:
            slot = "p1_choice"
        elif uid == session["p2_id"]:
            slot = "p2_choice"
        else:
            await interaction.response.send_message(t(lang, "not_in_match"), ephemeral=True)
            return

        if session.get(slot) is not None:
            await interaction.response.send_message(
                t(lang, "already_chose", choice=pretty(lang, session[slot])), ephemeral=True
            )
            return

        session[slot] = choice
        await interaction.response.send_message(
            t(lang, "you_chose", choice=pretty(lang, choice)), ephemeral=True
        )

        # Resolve only once both players have picked.
        if session.get("p1_choice") is None or session.get("p2_choice") is None:
            return

        # Consume the session so a race can't resolve twice.
        if self._sessions.pop(token, None) is None:
            return

        p1_id = session["p1_id"]
        p2_id = session["p2_id"]
        p1_choice = session["p1_choice"]
        p2_choice = session["p2_choice"]
        guild = interaction.guild
        guild_id = session["guild_id"]

        outcome = resolve(p1_choice, p2_choice)  # 1 p1 wins, -1 p2 wins, 0 tie

        m1 = guild.get_member(p1_id)
        m2 = guild.get_member(p2_id)
        name1 = m1.display_name if m1 else f"User {p1_id}"
        name2 = m2.display_name if m2 else f"User {p2_id}"
        mention1 = m1.mention if m1 else f"<@{p1_id}>"
        mention2 = m2.mention if m2 else f"<@{p2_id}>"

        if outcome == 1:
            result = t(lang, "you_win", player=mention1)
        elif outcome == -1:
            result = t(lang, "you_win", player=mention2)
        else:
            result = t(lang, "tie")

        embed = discord.Embed(title=t(lang, "title"), color=RPS_COLOR)
        embed.add_field(name=name1, value=pretty(lang, p1_choice), inline=True)
        embed.add_field(name=name2, value=pretty(lang, p2_choice), inline=True)
        embed.add_field(name=t(lang, "field_result"), value=result, inline=False)

        try:
            await interaction.message.edit(embed=embed, view=build_view(lang, token, disabled=True))
        except Exception as exc:
            print(f"[rps] could not edit pvp message in {guild_id}: {exc}")

        # Score both humans: winner True, loser False, tie both False.
        await self._score(guild_id, p1_id, outcome == 1)
        await self._score(guild_id, p2_id, outcome == -1)


async def setup(bot):
    await bot.add_cog(RPS(bot))
