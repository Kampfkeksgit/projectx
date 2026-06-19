"""Shared i18n helper for the Games category cogs.

The whole Games category shares one per-guild language setting
(`games_language` on the games settings, one of GAME_LANGUAGES). Each game cog
defines its own flat string table per language and builds a translator with
`make_translator(...)`:

    from utils.game_i18n import make_translator, lang_of

    _STRINGS = {
        "en": {"usage": "Usage: `!ttt @opponent`", "wins": "{player} wins!"},
        "de": {"usage": "Verwendung: `!ttt @gegner`", "wins": "{player} gewinnt!"},
        # tr / ru / pl ...
    }
    t = make_translator(_STRINGS)

    lang = lang_of(settings)
    await ctx.reply(t(lang, "usage"))
    await ctx.send(t(lang, "wins", player=member.mention))

Lookup falls back to English for an unknown language or a missing key, and to
the raw key as a last resort, so a partial table never crashes a cog. `.format`
is applied only when kwargs are passed and silently degrades to the unformatted
string on a bad placeholder.
"""

# Source of truth mirrored in backend db.js (GAME_LANGUAGES) + the dashboard picker.
GAME_LANGUAGES = ["en", "de", "tr", "ru", "pl"]
DEFAULT_LANG = "en"


def normalize_lang(lang):
    """Coerce an arbitrary value to a supported language key (fallback: English)."""
    return lang if lang in GAME_LANGUAGES else DEFAULT_LANG


def lang_of(settings):
    """Read the games language from a settings dict (None-safe, fallback: English)."""
    if not settings:
        return DEFAULT_LANG
    return normalize_lang(settings.get("games_language"))


def make_translator(strings):
    """Return a `t(lang, key, **kwargs)` function bound to a per-cog string table."""
    en = strings.get(DEFAULT_LANG, {})

    def t(lang, key, **kwargs):
        table = strings.get(normalize_lang(lang), en)
        text = table.get(key)
        if text is None:
            text = en.get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return text

    return t
