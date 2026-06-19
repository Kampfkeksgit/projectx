"""Trivia quiz cog.

Members start a trivia round with `!trivia`. The bot posts a general-knowledge
question with four labelled answer buttons (A–D). The first player to click the
correct answer wins; their win is scored via the backend. After 25 seconds the
answer auto-reveals if nobody solved it.

Clicks are handled via on_interaction (custom_id "trv:<token>:<idx>") so the
buttons keep working without persistent-view registration. Sessions live only in
memory (a round is short-lived), keyed by a short random token.

All user-facing UI strings and the question bank are localized per guild via the
shared games language setting (`games_language`); see utils/game_i18n.py.

Backend contract (X-Bot-Token auth):
  GET  /api/bot/guilds/{gid}/settings/games
       → { games_channel_id, trivia_enabled, games_language, ... } or None
  POST /api/bot/guilds/{gid}/games/score
       body { user_id, game: "trivia", win: true }

Logging prefix: "[trivia]".
"""

import time
import uuid
import random
import asyncio

import discord
from discord.ext import commands

import config
from utils.backend import fetch_bot_settings, bot_post
from utils.game_i18n import make_translator, lang_of


SETTINGS_TTL_SECONDS = 60
TRIVIA_COLOR = 0x6366F1
REVEAL_AFTER_SECONDS = 25
OPTION_LABELS = ["A", "B", "C", "D"]


_STRINGS = {
    "en": {
        "not_enabled": "Trivia is not enabled on this server.",
        "configured_channel": "the configured games channel",
        "use_here": "Please use trivia in {channel}.",
        "title_question": "🧠 Trivia Time!",
        "footer": "First correct answer wins • {seconds}s",
        "cant_post": "I can't post in this channel.",
        "start_failed": "Couldn't start trivia right now.",
        "expired": "This question has expired.",
        "already_answered": "You already answered.",
        "not_quite": "❌ Not quite!",
        "went_wrong": "Something went wrong.",
        "title_solved": "🧠 Trivia — Solved!",
        "desc_solved": "The correct answer was **{label}. {answer}**\n\n🎉 {player} got it!",
        "title_timeup": "🧠 Trivia — Time's up!",
        "desc_timeup": "Time's up! The answer was **{label}. {answer}**",
    },
    "de": {
        "not_enabled": "Trivia ist auf diesem Server nicht aktiviert.",
        "configured_channel": "den konfigurierten Spiele-Channel",
        "use_here": "Bitte nutze Trivia in {channel}.",
        "title_question": "🧠 Trivia-Zeit!",
        "footer": "Die erste richtige Antwort gewinnt • {seconds}s",
        "cant_post": "Ich kann in diesem Channel nicht schreiben.",
        "start_failed": "Trivia konnte gerade nicht gestartet werden.",
        "expired": "Diese Frage ist abgelaufen.",
        "already_answered": "Du hast bereits geantwortet.",
        "not_quite": "❌ Nicht ganz!",
        "went_wrong": "Etwas ist schiefgelaufen.",
        "title_solved": "🧠 Trivia — Gelöst!",
        "desc_solved": "Die richtige Antwort war **{label}. {answer}**\n\n🎉 {player} hat es gewusst!",
        "title_timeup": "🧠 Trivia — Zeit abgelaufen!",
        "desc_timeup": "Zeit abgelaufen! Die Antwort war **{label}. {answer}**",
    },
    "tr": {
        "not_enabled": "Bu sunucuda Trivia etkin değil.",
        "configured_channel": "ayarlanmış oyun kanalı",
        "use_here": "Lütfen Trivia'yı {channel} içinde kullan.",
        "title_question": "🧠 Trivia Zamanı!",
        "footer": "İlk doğru cevap kazanır • {seconds}s",
        "cant_post": "Bu kanala mesaj gönderemiyorum.",
        "start_failed": "Trivia şu anda başlatılamadı.",
        "expired": "Bu sorunun süresi doldu.",
        "already_answered": "Zaten cevap verdin.",
        "not_quite": "❌ Pek değil!",
        "went_wrong": "Bir şeyler ters gitti.",
        "title_solved": "🧠 Trivia — Çözüldü!",
        "desc_solved": "Doğru cevap **{label}. {answer}** idi\n\n🎉 {player} bildi!",
        "title_timeup": "🧠 Trivia — Süre doldu!",
        "desc_timeup": "Süre doldu! Cevap **{label}. {answer}** idi",
    },
    "ru": {
        "not_enabled": "Викторина не включена на этом сервере.",
        "configured_channel": "настроенный игровой канал",
        "use_here": "Пожалуйста, используй викторину в {channel}.",
        "title_question": "🧠 Время викторины!",
        "footer": "Побеждает первый правильный ответ • {seconds}с",
        "cant_post": "Я не могу писать в этом канале.",
        "start_failed": "Не удалось запустить викторину прямо сейчас.",
        "expired": "Срок действия этого вопроса истёк.",
        "already_answered": "Ты уже ответил.",
        "not_quite": "❌ Не совсем!",
        "went_wrong": "Что-то пошло не так.",
        "title_solved": "🧠 Викторина — Решено!",
        "desc_solved": "Правильный ответ был **{label}. {answer}**\n\n🎉 {player} угадал!",
        "title_timeup": "🧠 Викторина — Время вышло!",
        "desc_timeup": "Время вышло! Ответ был **{label}. {answer}**",
    },
    "pl": {
        "not_enabled": "Quiz nie jest włączony na tym serwerze.",
        "configured_channel": "skonfigurowanym kanale gier",
        "use_here": "Użyj quizu na {channel}.",
        "title_question": "🧠 Czas na quiz!",
        "footer": "Wygrywa pierwsza poprawna odpowiedź • {seconds}s",
        "cant_post": "Nie mogę pisać na tym kanale.",
        "start_failed": "Nie udało się teraz uruchomić quizu.",
        "expired": "To pytanie wygasło.",
        "already_answered": "Już odpowiedziałeś.",
        "not_quite": "❌ Niezupełnie!",
        "went_wrong": "Coś poszło nie tak.",
        "title_solved": "🧠 Quiz — Rozwiązano!",
        "desc_solved": "Poprawna odpowiedź to **{label}. {answer}**\n\n🎉 {player} zgadł!",
        "title_timeup": "🧠 Quiz — Czas minął!",
        "desc_timeup": "Czas minął! Odpowiedź to **{label}. {answer}**",
    },
}

t = make_translator(_STRINGS)


QUESTIONS_BY_LANG = {
    "en": [
        {"q": "What is the largest planet in our solar system?",
         "options": ["Earth", "Jupiter", "Saturn", "Neptune"], "answer": 1},
        {"q": "Which gas do plants primarily absorb from the atmosphere?",
         "options": ["Oxygen", "Nitrogen", "Carbon dioxide", "Hydrogen"], "answer": 2},
        {"q": "How many continents are there on Earth?",
         "options": ["5", "6", "7", "8"], "answer": 2},
        {"q": "What is the capital city of Japan?",
         "options": ["Seoul", "Beijing", "Bangkok", "Tokyo"], "answer": 3},
        {"q": "Which animal is known as the 'King of the Jungle'?",
         "options": ["Tiger", "Lion", "Elephant", "Bear"], "answer": 1},
        {"q": "What is the chemical symbol for water?",
         "options": ["H2O", "CO2", "O2", "NaCl"], "answer": 0},
        {"q": "How many sides does a hexagon have?",
         "options": ["5", "6", "7", "8"], "answer": 1},
        {"q": "Which planet is known as the Red Planet?",
         "options": ["Venus", "Mars", "Mercury", "Jupiter"], "answer": 1},
        {"q": "What is the tallest mountain in the world?",
         "options": ["K2", "Mount Kilimanjaro", "Mount Everest", "Denali"], "answer": 2},
        {"q": "Which ocean is the largest?",
         "options": ["Atlantic", "Indian", "Arctic", "Pacific"], "answer": 3},
        {"q": "How many colors are there in a rainbow?",
         "options": ["5", "6", "7", "9"], "answer": 2},
        {"q": "What is the fastest land animal?",
         "options": ["Cheetah", "Lion", "Horse", "Greyhound"], "answer": 0},
        {"q": "Which language has the most native speakers worldwide?",
         "options": ["English", "Hindi", "Mandarin Chinese", "Spanish"], "answer": 2},
        {"q": "What is the smallest prime number?",
         "options": ["0", "1", "2", "3"], "answer": 2},
        {"q": "Which instrument has 88 keys?",
         "options": ["Guitar", "Piano", "Violin", "Flute"], "answer": 1},
        {"q": "What is the freezing point of water in degrees Celsius?",
         "options": ["0", "32", "100", "-10"], "answer": 0},
        {"q": "Which country is home to the kangaroo?",
         "options": ["South Africa", "Brazil", "Australia", "India"], "answer": 2},
        {"q": "How many legs does a spider have?",
         "options": ["6", "8", "10", "12"], "answer": 1},
        {"q": "What is the main ingredient in guacamole?",
         "options": ["Tomato", "Avocado", "Pepper", "Onion"], "answer": 1},
        {"q": "Which planet is closest to the Sun?",
         "options": ["Venus", "Earth", "Mercury", "Mars"], "answer": 2},
    ],
    "de": [
        {"q": "Was ist der größte Planet in unserem Sonnensystem?",
         "options": ["Erde", "Jupiter", "Saturn", "Neptun"], "answer": 1},
        {"q": "Welches Gas nehmen Pflanzen hauptsächlich aus der Atmosphäre auf?",
         "options": ["Sauerstoff", "Stickstoff", "Kohlendioxid", "Wasserstoff"], "answer": 2},
        {"q": "Wie viele Kontinente gibt es auf der Erde?",
         "options": ["5", "6", "7", "8"], "answer": 2},
        {"q": "Was ist die Hauptstadt von Japan?",
         "options": ["Seoul", "Peking", "Bangkok", "Tokio"], "answer": 3},
        {"q": "Welches Tier ist als 'König des Dschungels' bekannt?",
         "options": ["Tiger", "Löwe", "Elefant", "Bär"], "answer": 1},
        {"q": "Was ist das chemische Symbol für Wasser?",
         "options": ["H2O", "CO2", "O2", "NaCl"], "answer": 0},
        {"q": "Wie viele Seiten hat ein Sechseck?",
         "options": ["5", "6", "7", "8"], "answer": 1},
        {"q": "Welcher Planet ist als der Rote Planet bekannt?",
         "options": ["Venus", "Mars", "Merkur", "Jupiter"], "answer": 1},
        {"q": "Was ist der höchste Berg der Welt?",
         "options": ["K2", "Kilimandscharo", "Mount Everest", "Denali"], "answer": 2},
        {"q": "Welcher Ozean ist der größte?",
         "options": ["Atlantik", "Indischer Ozean", "Arktischer Ozean", "Pazifik"], "answer": 3},
        {"q": "Wie viele Farben hat ein Regenbogen?",
         "options": ["5", "6", "7", "9"], "answer": 2},
        {"q": "Was ist das schnellste Landtier?",
         "options": ["Gepard", "Löwe", "Pferd", "Windhund"], "answer": 0},
        {"q": "Welche Sprache hat weltweit die meisten Muttersprachler?",
         "options": ["Englisch", "Hindi", "Mandarin-Chinesisch", "Spanisch"], "answer": 2},
        {"q": "Was ist die kleinste Primzahl?",
         "options": ["0", "1", "2", "3"], "answer": 2},
        {"q": "Welches Instrument hat 88 Tasten?",
         "options": ["Gitarre", "Klavier", "Geige", "Flöte"], "answer": 1},
        {"q": "Was ist der Gefrierpunkt von Wasser in Grad Celsius?",
         "options": ["0", "32", "100", "-10"], "answer": 0},
        {"q": "In welchem Land ist das Känguru zu Hause?",
         "options": ["Südafrika", "Brasilien", "Australien", "Indien"], "answer": 2},
        {"q": "Wie viele Beine hat eine Spinne?",
         "options": ["6", "8", "10", "12"], "answer": 1},
        {"q": "Was ist die Hauptzutat in Guacamole?",
         "options": ["Tomate", "Avocado", "Paprika", "Zwiebel"], "answer": 1},
        {"q": "Welcher Planet ist der Sonne am nächsten?",
         "options": ["Venus", "Erde", "Merkur", "Mars"], "answer": 2},
    ],
    "tr": [
        {"q": "Güneş sistemimizdeki en büyük gezegen hangisidir?",
         "options": ["Dünya", "Jüpiter", "Satürn", "Neptün"], "answer": 1},
        {"q": "Bitkiler atmosferden başlıca hangi gazı emer?",
         "options": ["Oksijen", "Azot", "Karbondioksit", "Hidrojen"], "answer": 2},
        {"q": "Dünya'da kaç kıta vardır?",
         "options": ["5", "6", "7", "8"], "answer": 2},
        {"q": "Japonya'nın başkenti neresidir?",
         "options": ["Seul", "Pekin", "Bangkok", "Tokyo"], "answer": 3},
        {"q": "Hangi hayvan 'Ormanlar Kralı' olarak bilinir?",
         "options": ["Kaplan", "Aslan", "Fil", "Ayı"], "answer": 1},
        {"q": "Suyun kimyasal sembolü nedir?",
         "options": ["H2O", "CO2", "O2", "NaCl"], "answer": 0},
        {"q": "Bir altıgenin kaç kenarı vardır?",
         "options": ["5", "6", "7", "8"], "answer": 1},
        {"q": "Hangi gezegen Kızıl Gezegen olarak bilinir?",
         "options": ["Venüs", "Mars", "Merkür", "Jüpiter"], "answer": 1},
        {"q": "Dünyanın en yüksek dağı hangisidir?",
         "options": ["K2", "Kilimanjaro Dağı", "Everest Dağı", "Denali"], "answer": 2},
        {"q": "En büyük okyanus hangisidir?",
         "options": ["Atlas", "Hint", "Arktik", "Pasifik"], "answer": 3},
        {"q": "Gökkuşağında kaç renk vardır?",
         "options": ["5", "6", "7", "9"], "answer": 2},
        {"q": "En hızlı kara hayvanı hangisidir?",
         "options": ["Çita", "Aslan", "At", "Tazı"], "answer": 0},
        {"q": "Dünya genelinde en çok ana dili konuşanı olan dil hangisidir?",
         "options": ["İngilizce", "Hintçe", "Mandarin Çincesi", "İspanyolca"], "answer": 2},
        {"q": "En küçük asal sayı nedir?",
         "options": ["0", "1", "2", "3"], "answer": 2},
        {"q": "Hangi enstrümanın 88 tuşu vardır?",
         "options": ["Gitar", "Piyano", "Keman", "Flüt"], "answer": 1},
        {"q": "Suyun donma noktası Santigrat derece olarak kaçtır?",
         "options": ["0", "32", "100", "-10"], "answer": 0},
        {"q": "Kanguru hangi ülkenin yerlisidir?",
         "options": ["Güney Afrika", "Brezilya", "Avustralya", "Hindistan"], "answer": 2},
        {"q": "Bir örümceğin kaç bacağı vardır?",
         "options": ["6", "8", "10", "12"], "answer": 1},
        {"q": "Guacamole'nin ana malzemesi nedir?",
         "options": ["Domates", "Avokado", "Biber", "Soğan"], "answer": 1},
        {"q": "Güneş'e en yakın gezegen hangisidir?",
         "options": ["Venüs", "Dünya", "Merkür", "Mars"], "answer": 2},
    ],
    "ru": [
        {"q": "Какая планета самая большая в нашей Солнечной системе?",
         "options": ["Земля", "Юпитер", "Сатурн", "Нептун"], "answer": 1},
        {"q": "Какой газ растения в основном поглощают из атмосферы?",
         "options": ["Кислород", "Азот", "Углекислый газ", "Водород"], "answer": 2},
        {"q": "Сколько континентов на Земле?",
         "options": ["5", "6", "7", "8"], "answer": 2},
        {"q": "Какой город является столицей Японии?",
         "options": ["Сеул", "Пекин", "Бангкок", "Токио"], "answer": 3},
        {"q": "Какое животное известно как «Царь зверей»?",
         "options": ["Тигр", "Лев", "Слон", "Медведь"], "answer": 1},
        {"q": "Каков химический символ воды?",
         "options": ["H2O", "CO2", "O2", "NaCl"], "answer": 0},
        {"q": "Сколько сторон у шестиугольника?",
         "options": ["5", "6", "7", "8"], "answer": 1},
        {"q": "Какую планету называют Красной планетой?",
         "options": ["Венера", "Марс", "Меркурий", "Юпитер"], "answer": 1},
        {"q": "Какая самая высокая гора в мире?",
         "options": ["К2", "Килиманджаро", "Эверест", "Денали"], "answer": 2},
        {"q": "Какой океан самый большой?",
         "options": ["Атлантический", "Индийский", "Северный Ледовитый", "Тихий"], "answer": 3},
        {"q": "Сколько цветов в радуге?",
         "options": ["5", "6", "7", "9"], "answer": 2},
        {"q": "Какое самое быстрое наземное животное?",
         "options": ["Гепард", "Лев", "Лошадь", "Борзая"], "answer": 0},
        {"q": "Какой язык имеет больше всего носителей в мире?",
         "options": ["Английский", "Хинди", "Китайский (мандаринский)", "Испанский"], "answer": 2},
        {"q": "Какое наименьшее простое число?",
         "options": ["0", "1", "2", "3"], "answer": 2},
        {"q": "У какого инструмента 88 клавиш?",
         "options": ["Гитара", "Пианино", "Скрипка", "Флейта"], "answer": 1},
        {"q": "Какова температура замерзания воды в градусах Цельсия?",
         "options": ["0", "32", "100", "-10"], "answer": 0},
        {"q": "В какой стране обитает кенгуру?",
         "options": ["Южная Африка", "Бразилия", "Австралия", "Индия"], "answer": 2},
        {"q": "Сколько ног у паука?",
         "options": ["6", "8", "10", "12"], "answer": 1},
        {"q": "Какой основной ингредиент в гуакамоле?",
         "options": ["Помидор", "Авокадо", "Перец", "Лук"], "answer": 1},
        {"q": "Какая планета ближе всего к Солнцу?",
         "options": ["Венера", "Земля", "Меркурий", "Марс"], "answer": 2},
    ],
    "pl": [
        {"q": "Która planeta jest największa w naszym Układzie Słonecznym?",
         "options": ["Ziemia", "Jowisz", "Saturn", "Neptun"], "answer": 1},
        {"q": "Który gaz rośliny głównie pobierają z atmosfery?",
         "options": ["Tlen", "Azot", "Dwutlenek węgla", "Wodór"], "answer": 2},
        {"q": "Ile kontynentów jest na Ziemi?",
         "options": ["5", "6", "7", "8"], "answer": 2},
        {"q": "Jakie jest stolica Japonii?",
         "options": ["Seul", "Pekin", "Bangkok", "Tokio"], "answer": 3},
        {"q": "Które zwierzę jest znane jako 'Król dżungli'?",
         "options": ["Tygrys", "Lew", "Słoń", "Niedźwiedź"], "answer": 1},
        {"q": "Jaki jest symbol chemiczny wody?",
         "options": ["H2O", "CO2", "O2", "NaCl"], "answer": 0},
        {"q": "Ile boków ma sześciokąt?",
         "options": ["5", "6", "7", "8"], "answer": 1},
        {"q": "Która planeta jest znana jako Czerwona Planeta?",
         "options": ["Wenus", "Mars", "Merkury", "Jowisz"], "answer": 1},
        {"q": "Jaka jest najwyższa góra na świecie?",
         "options": ["K2", "Kilimandżaro", "Mount Everest", "Denali"], "answer": 2},
        {"q": "Który ocean jest największy?",
         "options": ["Atlantycki", "Indyjski", "Arktyczny", "Spokojny"], "answer": 3},
        {"q": "Ile kolorów ma tęcza?",
         "options": ["5", "6", "7", "9"], "answer": 2},
        {"q": "Jakie jest najszybsze zwierzę lądowe?",
         "options": ["Gepard", "Lew", "Koń", "Chart"], "answer": 0},
        {"q": "Który język ma najwięcej rodzimych użytkowników na świecie?",
         "options": ["Angielski", "Hindi", "Chiński mandaryński", "Hiszpański"], "answer": 2},
        {"q": "Jaka jest najmniejsza liczba pierwsza?",
         "options": ["0", "1", "2", "3"], "answer": 2},
        {"q": "Który instrument ma 88 klawiszy?",
         "options": ["Gitara", "Fortepian", "Skrzypce", "Flet"], "answer": 1},
        {"q": "Jaka jest temperatura zamarzania wody w stopniach Celsjusza?",
         "options": ["0", "32", "100", "-10"], "answer": 0},
        {"q": "W którym kraju żyje kangur?",
         "options": ["Republika Południowej Afryki", "Brazylia", "Australia", "Indie"], "answer": 2},
        {"q": "Ile nóg ma pająk?",
         "options": ["6", "8", "10", "12"], "answer": 1},
        {"q": "Jaki jest główny składnik guacamole?",
         "options": ["Pomidor", "Awokado", "Papryka", "Cebula"], "answer": 1},
        {"q": "Która planeta jest najbliżej Słońca?",
         "options": ["Wenus", "Ziemia", "Merkury", "Mars"], "answer": 2},
    ],
}


def build_question_view(token, count):
    view = discord.ui.View(timeout=None)
    for idx in range(min(count, 4)):
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label=OPTION_LABELS[idx],
            custom_id=f"trv:{token}:{idx}",
        ))
    return view


class Trivia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backend_url = (config.BACKEND_URL or "").rstrip("/")
        self.api_key = config.BOT_API_KEY
        self._settings_cache = {}
        # token -> { "answer": int, "answered": set(), "solved": bool, "message": Message,
        #            "guild_id": int, "options": list, "lang": str }
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

    @commands.command(name="trivia")
    @commands.guild_only()
    async def trivia(self, ctx):
        lang = "en"
        try:
            settings = await self._get_settings(ctx.guild.id, force=True)
            lang = lang_of(settings)
            if not settings or not settings.get("trivia_enabled"):
                await ctx.reply(t(lang, "not_enabled"), mention_author=False)
                return

            games_channel_id = settings.get("games_channel_id")
            if games_channel_id and str(games_channel_id) != str(ctx.channel.id):
                channel = ctx.guild.get_channel(int(games_channel_id))
                where = channel.mention if channel else t(lang, "configured_channel")
                await ctx.reply(t(lang, "use_here", channel=where), mention_author=False)
                return

            bank = QUESTIONS_BY_LANG.get(lang) or QUESTIONS_BY_LANG["en"]
            question = random.choice(bank)
            options = question["options"]
            answer = int(question["answer"])

            token = uuid.uuid4().hex[:8]
            embed = discord.Embed(
                title=t(lang, "title_question"),
                description=question["q"],
                color=TRIVIA_COLOR,
            )
            for i, opt in enumerate(options[:4]):
                embed.add_field(name=f"{OPTION_LABELS[i]}", value=str(opt), inline=False)
            embed.set_footer(text=t(lang, "footer", seconds=REVEAL_AFTER_SECONDS))

            try:
                msg = await ctx.send(embed=embed, view=build_question_view(token, len(options)))
            except discord.Forbidden:
                await ctx.reply(t(lang, "cant_post"), mention_author=False)
                return

            self._sessions[token] = {
                "answer": answer,
                "answered": set(),
                "solved": False,
                "message": msg,
                "guild_id": ctx.guild.id,
                "options": list(options[:4]),
                "lang": lang,
            }
            asyncio.create_task(self._auto_reveal(token))
        except Exception as exc:
            print(f"[trivia] start failed in {getattr(ctx.guild, 'id', '?')}: {exc}")
            try:
                await ctx.reply(t(lang, "start_failed"), mention_author=False)
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        try:
            if interaction.type != discord.InteractionType.component or interaction.guild is None:
                return
            custom_id = (interaction.data or {}).get("custom_id") or ""
            if not custom_id.startswith("trv:"):
                return

            parts = custom_id.split(":")
            if len(parts) != 3:
                return
            token = parts[1]
            try:
                idx = int(parts[2])
            except ValueError:
                return

            session = self._sessions.get(token)
            if not session:
                await interaction.response.send_message(t("en", "expired"), ephemeral=True)
                return

            lang = session.get("lang", "en")

            uid = interaction.user.id
            if uid in session["answered"]:
                await interaction.response.send_message(t(lang, "already_answered"), ephemeral=True)
                return
            session["answered"].add(uid)

            if idx == session["answer"]:
                await self._handle_win(interaction, token, session)
            else:
                await interaction.response.send_message(t(lang, "not_quite"), ephemeral=True)
        except Exception as exc:
            print(f"[trivia] interaction error: {exc}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(t("en", "went_wrong"), ephemeral=True)
            except Exception:
                pass

    async def _handle_win(self, interaction, token, session):
        # Mark solved + remove the session up front so the auto-reveal can't fire.
        session["solved"] = True
        self._sessions.pop(token, None)

        await interaction.response.defer()

        lang = session.get("lang", "en")
        message = session.get("message")
        answer = session["answer"]
        options = session.get("options") or []
        correct_text = options[answer] if answer < len(options) else "?"

        embed = discord.Embed(
            title=t(lang, "title_solved"),
            description=t(lang, "desc_solved",
                         label=OPTION_LABELS[answer], answer=correct_text,
                         player=interaction.user.mention),
            color=TRIVIA_COLOR,
        )
        try:
            if message is not None:
                await message.edit(embed=embed, view=self._disabled_view(message))
        except Exception as exc:
            print(f"[trivia] win edit failed: {exc}")

        try:
            await bot_post(
                self.backend_url, self.api_key,
                f"/api/bot/guilds/{session['guild_id']}/games/score",
                {"user_id": str(interaction.user.id), "game": "trivia", "win": True},
            )
        except Exception as exc:
            print(f"[trivia] score failed: {exc}")

    async def _auto_reveal(self, token):
        try:
            await asyncio.sleep(REVEAL_AFTER_SECONDS)
            session = self._sessions.get(token)
            if not session or session.get("solved"):
                return
            # Claim the session so a late click can't double-fire.
            self._sessions.pop(token, None)

            lang = session.get("lang", "en")
            message = session.get("message")
            answer = session["answer"]
            options = session.get("options") or []
            correct_text = options[answer] if answer < len(options) else "?"

            embed = discord.Embed(
                title=t(lang, "title_timeup"),
                description=t(lang, "desc_timeup",
                             label=OPTION_LABELS[answer], answer=correct_text),
                color=TRIVIA_COLOR,
            )
            if message is not None:
                await message.edit(embed=embed, view=self._disabled_view(message))
        except Exception as exc:
            print(f"[trivia] auto-reveal failed: {exc}")

    @staticmethod
    def _disabled_view(message):
        view = discord.ui.View(timeout=None)
        try:
            existing = discord.ui.View.from_message(message)
            for child in existing.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
                    view.add_item(child)
        except Exception:
            pass
        return view


async def setup(bot):
    await bot.add_cog(Trivia(bot))
