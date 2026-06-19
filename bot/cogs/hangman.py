"""Hangman cog.

Members run `!hangman` to start a guessing game in a channel. Players then type
single letters as messages to guess the hidden word. The first solver wins; the
bot scores the solver via the backend.

This cog uses an on_message listener for letter guesses (NOT buttons). It never
calls bot.process_commands — main.py / the command framework handles that.

All user-facing strings and the word bank are localized per guild via the shared
games language setting (`games_language`); see utils/game_i18n.py.

Backend contract (X-Bot-Token auth):
  GET  /api/bot/guilds/{gid}/settings/games
      → { games_channel_id, hangman_enabled, games_language, ... }
  POST /api/bot/guilds/{gid}/games/score
      body { user_id, game, win }

Logging prefix: "[hangman]".
"""

import random

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_post
from utils.game_i18n import make_translator, lang_of


HANGMAN_COLOR = 0x5865F2
WIN_COLOR = 0x22C55E
LOSE_COLOR = 0xEF4444
MAX_ATTEMPTS = 6


# Family-friendly words, lowercase, single word (no spaces), per language.
WORDS_BY_LANG = {
    "en": [
        "apple", "banana", "orange", "grape", "lemon",
        "garden", "flower", "forest", "river", "mountain",
        "rocket", "planet", "comet", "galaxy", "meteor",
        "guitar", "violin", "piano", "drum", "trumpet",
        "castle", "bridge", "tower", "island", "harbor",
        "dragon", "wizard", "knight", "puzzle", "treasure",
        "rainbow", "thunder", "breeze", "sunset", "winter",
        "pencil", "marble", "candle", "basket", "blanket",
    ],
    "de": [
        "apfel", "banane", "orange", "traube", "zitrone",
        "garten", "blume", "wald", "fluss", "berg",
        "rakete", "planet", "komet", "galaxie", "meteor",
        "gitarre", "geige", "klavier", "trommel", "trompete",
        "schloss", "bruecke", "turm", "insel", "hafen",
        "drache", "zauberer", "ritter", "raetsel", "schatz",
        "regenbogen", "donner", "brise", "abend", "winter",
        "stift", "murmel", "kerze", "korb", "decke",
    ],
    "tr": [
        "elma", "muz", "portakal", "uzum", "limon",
        "bahce", "cicek", "orman", "nehir", "dag",
        "roket", "gezegen", "kuyruklu", "galaksi", "meteor",
        "gitar", "keman", "piyano", "davul", "trompet",
        "kale", "kopru", "kule", "ada", "liman",
        "ejderha", "buyucu", "sovalye", "bulmaca", "hazine",
        "gokkusagi", "gokgurultusu", "esinti", "gunbatimi", "kis",
        "kalem", "bilye", "mum", "sepet", "battaniye",
    ],
    "ru": [
        "яблоко", "банан", "апельсин", "виноград", "лимон",
        "сад", "цветок", "лес", "река", "гора",
        "ракета", "планета", "комета", "галактика", "метеор",
        "гитара", "скрипка", "пианино", "барабан", "труба",
        "замок", "мост", "башня", "остров", "гавань",
        "дракон", "волшебник", "рыцарь", "загадка", "сокровище",
        "радуга", "гром", "ветерок", "закат", "зима",
        "карандаш", "шарик", "свеча", "корзина", "одеяло",
    ],
    "pl": [
        "jablko", "banan", "pomarancza", "winogrono", "cytryna",
        "ogrod", "kwiat", "las", "rzeka", "gora",
        "rakieta", "planeta", "kometa", "galaktyka", "meteor",
        "gitara", "skrzypce", "fortepian", "beben", "trabka",
        "zamek", "most", "wieza", "wyspa", "przystan",
        "smok", "czarodziej", "rycerz", "zagadka", "skarb",
        "tecza", "grzmot", "wietrzyk", "zachod", "zima",
        "olowek", "kulka", "swieca", "koszyk", "koc",
    ],
}


_STRINGS = {
    "en": {
        "already_running": "A game is already running here.",
        "not_enabled": "Hangman is not enabled on this server.",
        "wrong_channel": "Hangman can only be played in {where}.",
        "configured_channel": "the configured games channel",
        "embed_title": "Hangman",
        "field_word": "Word",
        "field_wrong": "Wrong letters",
        "field_attempts": "Attempts left",
        "footer_default": "Type a single letter to guess.",
        "footer_correct": "Correct! Keep going.",
        "footer_wrong": "Wrong letter!",
        "solved_title": "🎉 Solved!",
        "solved_footer": "{player} guessed it.",
        "win_announce": "🎉 {player} solved it: **{word}**",
        "lose_announce": "💀 Out of attempts! The word was **{word}**",
    },
    "de": {
        "already_running": "Hier läuft bereits ein Spiel.",
        "not_enabled": "Galgenmännchen ist auf diesem Server nicht aktiviert.",
        "wrong_channel": "Galgenmännchen kann nur in {where} gespielt werden.",
        "configured_channel": "dem konfigurierten Spiele-Channel",
        "embed_title": "Galgenmännchen",
        "field_word": "Wort",
        "field_wrong": "Falsche Buchstaben",
        "field_attempts": "Verbleibende Versuche",
        "footer_default": "Schreibe einen einzelnen Buchstaben zum Raten.",
        "footer_correct": "Richtig! Weiter so.",
        "footer_wrong": "Falscher Buchstabe!",
        "solved_title": "🎉 Gelöst!",
        "solved_footer": "{player} hat es erraten.",
        "win_announce": "🎉 {player} hat es gelöst: **{word}**",
        "lose_announce": "💀 Keine Versuche mehr! Das Wort war **{word}**",
    },
    "tr": {
        "already_running": "Burada zaten bir oyun devam ediyor.",
        "not_enabled": "Adam Asmaca bu sunucuda etkin değil.",
        "wrong_channel": "Adam Asmaca yalnızca {where} içinde oynanabilir.",
        "configured_channel": "ayarlanan oyun kanalı",
        "embed_title": "Adam Asmaca",
        "field_word": "Kelime",
        "field_wrong": "Yanlış harfler",
        "field_attempts": "Kalan deneme",
        "footer_default": "Tahmin etmek için tek bir harf yaz.",
        "footer_correct": "Doğru! Devam et.",
        "footer_wrong": "Yanlış harf!",
        "solved_title": "🎉 Çözüldü!",
        "solved_footer": "{player} bildi.",
        "win_announce": "🎉 {player} çözdü: **{word}**",
        "lose_announce": "💀 Deneme hakkın bitti! Kelime **{word}** idi",
    },
    "ru": {
        "already_running": "Здесь уже идёт игра.",
        "not_enabled": "Виселица не включена на этом сервере.",
        "wrong_channel": "В Виселицу можно играть только в {where}.",
        "configured_channel": "настроенном игровом канале",
        "embed_title": "Виселица",
        "field_word": "Слово",
        "field_wrong": "Неверные буквы",
        "field_attempts": "Осталось попыток",
        "footer_default": "Напиши одну букву, чтобы угадать.",
        "footer_correct": "Верно! Продолжай.",
        "footer_wrong": "Неверная буква!",
        "solved_title": "🎉 Разгадано!",
        "solved_footer": "{player} угадал.",
        "win_announce": "🎉 {player} разгадал: **{word}**",
        "lose_announce": "💀 Попытки закончились! Слово было **{word}**",
    },
    "pl": {
        "already_running": "Gra już tu trwa.",
        "not_enabled": "Wisielec nie jest włączony na tym serwerze.",
        "wrong_channel": "W Wisielca można grać tylko na {where}.",
        "configured_channel": "skonfigurowanym kanale gier",
        "embed_title": "Wisielec",
        "field_word": "Słowo",
        "field_wrong": "Błędne litery",
        "field_attempts": "Pozostałe próby",
        "footer_default": "Napisz jedną literę, aby zgadnąć.",
        "footer_correct": "Dobrze! Tak trzymaj.",
        "footer_wrong": "Zła litera!",
        "solved_title": "🎉 Rozwiązane!",
        "solved_footer": "{player} zgadł.",
        "win_announce": "🎉 {player} rozwiązał: **{word}**",
        "lose_announce": "💀 Brak prób! Słowo to **{word}**",
    },
}

t = make_translator(_STRINGS)


def mask_word(word, guessed):
    """Return the word with un-guessed letters shown as underscores, e.g. '_ a _ _'."""
    return " ".join(letter if letter in guessed else "_" for letter in word)


def is_solved(word, guessed):
    return all(letter in guessed for letter in word)


class Hangman(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        # channel.id -> { word, guessed:set, wrong:set, attempts_left:int, message, lang }
        self._games = {}

    def _build_embed(self, game, title=None, color=HANGMAN_COLOR, footer=None):
        lang = game.get("lang", "en")
        embed = discord.Embed(title=title or t(lang, "embed_title"), color=color)
        embed.add_field(
            name=t(lang, "field_word"),
            value=f"`{mask_word(game['word'], game['guessed'])}`",
            inline=False,
        )
        wrong = game["wrong"]
        embed.add_field(
            name=t(lang, "field_wrong"),
            value=", ".join(sorted(wrong)) if wrong else "—",
            inline=True,
        )
        embed.add_field(
            name=t(lang, "field_attempts"),
            value=str(game["attempts_left"]),
            inline=True,
        )
        embed.set_footer(text=footer or t(lang, "footer_default"))
        return embed

    @commands.command(name="hangman")
    @commands.guild_only()
    async def hangman(self, ctx):
        if ctx.channel.id in self._games:
            await ctx.reply(t("en", "already_running"), mention_author=False)
            return

        settings = await fetch_bot_settings(self.backend_url, self.api_key, ctx.guild.id, "games")
        lang = lang_of(settings)
        if not settings or not settings.get("hangman_enabled"):
            await ctx.reply(t(lang, "not_enabled"), mention_author=False)
            return

        games_channel_id = settings.get("games_channel_id")
        if games_channel_id and str(ctx.channel.id) != str(games_channel_id):
            channel = ctx.guild.get_channel(int(games_channel_id)) if str(games_channel_id).isdigit() else None
            where = channel.mention if channel else t(lang, "configured_channel")
            await ctx.reply(t(lang, "wrong_channel", where=where), mention_author=False)
            return

        bank = WORDS_BY_LANG.get(lang) or WORDS_BY_LANG["en"]
        word = random.choice(bank)
        game = {
            "word": word,
            "guessed": set(),
            "wrong": set(),
            "attempts_left": MAX_ATTEMPTS,
            "message": None,
            "lang": lang,
        }
        self._games[ctx.channel.id] = game

        try:
            game["message"] = await ctx.send(embed=self._build_embed(game))
        except Exception as exc:
            print(f"[hangman] failed to post game in {ctx.channel.id}: {exc}")
            self._games.pop(ctx.channel.id, None)

    async def _refresh_embed(self, channel, game, **kwargs):
        """Edit the stored message if possible; fall back to posting a new one."""
        embed = self._build_embed(game, **kwargs)
        msg = game.get("message")
        if msg is not None:
            try:
                await msg.edit(embed=embed)
                return
            except Exception:
                pass
        try:
            game["message"] = await channel.send(embed=embed)
        except Exception as exc:
            print(f"[hangman] failed to refresh embed in {getattr(channel, 'id', '?')}: {exc}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.guild is None:
            return

        game = self._games.get(message.channel.id)
        if game is None:
            return

        lang = game.get("lang", "en")
        content = message.content.strip()
        if len(content) != 1 or not content.isalpha() or not content.isascii():
            return

        letter = content.lower()

        if letter in game["guessed"] or letter in game["wrong"]:
            try:
                await message.add_reaction("♻️")
            except Exception:
                pass
            return

        if letter in game["word"]:
            game["guessed"].add(letter)
            if is_solved(game["word"], game["guessed"]):
                word = game["word"]
                # Win: clean up first so a re-trigger can't double-score.
                self._games.pop(message.channel.id, None)
                await self._refresh_embed(
                    message.channel, game,
                    title=t(lang, "solved_title"), color=WIN_COLOR,
                    footer=t(lang, "solved_footer", player=str(message.author)),
                )
                try:
                    await message.channel.send(
                        t(lang, "win_announce", player=message.author.mention, word=word.upper())
                    )
                except Exception as exc:
                    print(f"[hangman] win announce failed: {exc}")
                await self._score_solver(message.guild.id, message.author.id)
            else:
                await self._refresh_embed(message.channel, game, footer=t(lang, "footer_correct"))
            return

        # Wrong letter.
        game["wrong"].add(letter)
        game["attempts_left"] -= 1
        if game["attempts_left"] <= 0:
            word = game["word"]
            self._games.pop(message.channel.id, None)
            try:
                await message.channel.send(
                    t(lang, "lose_announce", word=word.upper())
                )
            except Exception as exc:
                print(f"[hangman] lose announce failed: {exc}")
            return

        await self._refresh_embed(message.channel, game, footer=t(lang, "footer_wrong"))

    async def _score_solver(self, guild_id, uid):
        try:
            await bot_post(
                self.backend_url, self.api_key,
                f"/api/bot/guilds/{guild_id}/games/score",
                {"user_id": str(uid), "game": "hangman", "win": True},
            )
        except Exception as exc:
            print(f"[hangman] score failed for {uid} in {guild_id}: {exc}")


async def setup(bot):
    await bot.add_cog(Hangman(bot))
