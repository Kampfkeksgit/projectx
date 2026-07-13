// SEO feature landing pages. Each key is a public URL slug (e.g. /discord-ticket-bot)
// targeting a high-intent keyword. Rendered by pages/FeatureLanding.vue and wired
// into the router + sitemap. Copy an entry to add another feature page.
//
// Kept as plain content (not i18n) on purpose: these are standalone SEO entry
// points. For multilingual SEO, duplicate with localized slugs later.

export const FEATURE_PAGES = {
  'discord-ticket-bot': {
    seoTitle: 'Discord Ticket Bot mit Dashboard – Kampfkekse',
    seoDescription: 'Support-Tickets auf Discord: Panel mit Kategorien, Claim, Transkripte und Bewertungen – komplett über ein Web-Dashboard. Kostenlos starten.',
    h1: 'Der Discord Ticket-Bot mit Dashboard',
    subtitle: 'Professioneller Support auf deinem Server – Tickets, Kategorien, Claim, Transkripte und Bewertungen, alles ohne Code.',
    features: [
      { icon: '🎫', title: 'Panel mit Kategorien', body: 'Dropdown oder Buttons, gestaltbar als Embed oder Components V2. Pro Kategorie eigene Support-Rolle und Kanal.' },
      { icon: '🙋', title: 'Claim & Verwaltung', body: 'Tickets beanspruchen, Mitglieder hinzufügen/entfernen und mit Bestätigung schließen.' },
      { icon: '⭐', title: 'Bewertung & Transkript', body: '1–5-Sterne-Bewertung nach dem Schließen und automatisches Transkript im Log-Kanal.' },
      { icon: '🖥️', title: 'Alles im Dashboard', body: 'Panel, Kategorien und Texte im Browser konfigurieren – mit Live-Vorschau.' }
    ],
    faq: [
      { q: 'Ist der Ticket-Bot kostenlos?', a: 'Das Ticket-Modul ist im Pro-Tarif enthalten; viele andere Module sind dauerhaft kostenlos.' },
      { q: 'Kann ich mehrere Ticket-Kategorien anlegen?', a: 'Ja – jede Kategorie kann eine eigene Support-Rolle, Kanal-Kategorie und einen eigenen Willkommenstext haben.' },
      { q: 'Werden Ticket-Verläufe gespeichert?', a: 'Beim Schließen erstellt der Bot optional ein Transkript und postet es in einen Log-Kanal.' }
    ]
  },
  'discord-welcome-bot': {
    seoTitle: 'Discord Welcome Bot – Willkommensnachrichten – Kampfkekse',
    seoDescription: 'Begrüße neue Mitglieder mit Nachrichten, Embeds oder Components-V2-Containern, optional per DM. In Minuten eingerichtet, ohne Code. Kostenlos.',
    h1: 'Willkommensnachrichten für deinen Discord-Server',
    subtitle: 'Heiße neue Mitglieder automatisch willkommen – als Text, gestaltetes Embed oder moderner Components-V2-Container.',
    features: [
      { icon: '👋', title: 'Nachricht, Embed oder V2', body: 'Wähle zwischen Klartext, gestaltetem Embed oder Components-V2-Container mit Blöcken.' },
      { icon: '🏷️', title: 'Platzhalter', body: 'Dynamische Werte wie {user}, {guild} und {guild.member_count}.' },
      { icon: '✉️', title: 'Willkommens-DM', body: 'Optional zusätzlich eine private Nachricht an neue Mitglieder.' },
      { icon: '👀', title: 'Live-Vorschau', body: 'Sieh im Dashboard genau, wie die Nachricht in Discord aussieht.' }
    ],
    faq: [
      { q: 'Kann ich ein Bild einbauen?', a: 'Ja – Embeds und Components-V2-Container unterstützen Bilder und Thumbnails, inklusive des Avatars des neuen Mitglieds.' },
      { q: 'Gibt es auch Verabschiedungsnachrichten?', a: 'Ja, das Leave-Modul postet eine Nachricht, wenn jemand den Server verlässt.' },
      { q: 'Ist es kostenlos?', a: 'Ja, Welcome und Leave sind dauerhaft im Free-Tarif enthalten.' }
    ]
  },
  'discord-leveling-bot': {
    seoTitle: 'Discord Leveling Bot – XP, Ränge & Rollen – Kampfkekse',
    seoDescription: 'Belohne Aktivität mit XP, Leveln, Bestenliste und Belohnungsrollen. MEE6-ähnliches Leveling, komplett über das Dashboard konfigurierbar.',
    h1: 'Der Discord Leveling-Bot mit Belohnungsrollen',
    subtitle: 'Halte deine Community aktiv – XP pro Nachricht, Level-Up-Ankündigungen, Bestenliste und automatische Rollen.',
    features: [
      { icon: '⬆️', title: 'XP & Level', body: 'Konfigurierbare XP pro Nachricht mit Cooldown und Level-Up-Ankündigung.' },
      { icon: '🎁', title: 'Belohnungsrollen', body: 'Rollen pro Level – stapelnd oder nur die jeweils höchste.' },
      { icon: '🏆', title: 'Bestenliste', body: 'Top-Mitglieder im Dashboard und per Befehl.' },
      { icon: '🚫', title: 'Ignorierte Kanäle', body: 'Schließe Kanäle vom XP-Sammeln aus.' }
    ],
    faq: [
      { q: 'Ist es wie MEE6?', a: 'Das Leveling nutzt eine ähnliche XP-Kurve, ist aber vollständig über ein Dashboard konfigurierbar.' },
      { q: 'Kann ich Rollen als Belohnung vergeben?', a: 'Ja – lege pro Level eine Belohnungsrolle fest, wahlweise stapelnd oder ersetzend.' },
      { q: 'Welcher Tarif?', a: 'Leveling ist im Basic-Tarif enthalten.' }
    ]
  },
  'discord-moderation-bot': {
    seoTitle: 'Discord Auto-Moderation Bot – Anti-Spam – Kampfkekse',
    seoDescription: 'Auto-Moderation für Discord: Anti-Spam, Wortfilter, Anti-Invite/-Link, Caps- und Mention-Filter, Warnungen, Mutes und Timeouts. Kostenlos.',
    h1: 'Der Discord Auto-Moderation-Bot',
    subtitle: 'Halte deinen Server sauber – Filter, Warnungen und Eskalation, alles im Dashboard steuerbar.',
    features: [
      { icon: '🛡️', title: 'Filter', body: 'Anti-Spam, verbotene Wörter, Anti-Invite/-Link, Anti-Caps und Massen-Erwähnungen.' },
      { icon: '⚖️', title: 'Aktionen', body: 'Löschen, verwarnen, muten, kicken oder natives Discord-Timeout.' },
      { icon: '📈', title: 'Warn-Eskalation', body: 'Ab einer Schwelle automatisch härtere Aktion.' },
      { icon: '✅', title: 'Whitelist', body: 'Ausnahme-Rollen und ignorierte Kanäle.' }
    ],
    faq: [
      { q: 'Kann der Bot timeouten statt zu kicken?', a: 'Ja – natives Discord-Timeout ist als Aktion für alle Filter verfügbar.' },
      { q: 'Gibt es Ausnahmen?', a: 'Ja, du kannst Rollen und Kanäle von der Moderation ausnehmen.' },
      { q: 'Ist Moderation kostenlos?', a: 'Ja, das Moderations-Modul ist dauerhaft im Free-Tarif enthalten.' }
    ]
  },
  'discord-music-bot': {
    seoTitle: 'Discord Music Bot – SoundCloud & Radio – Kampfkekse',
    seoDescription: 'Spiele Musik in Sprachkanälen von SoundCloud, Bandcamp, Twitch und Radio-Streams – mit Live-Player im Dashboard, Warteschlange und DJ-Rolle.',
    h1: 'Der Discord Music-Bot mit Dashboard-Player',
    subtitle: 'Musik in deinen Sprachkanälen – gesteuert per Slash-Befehl oder direkt im Dashboard.',
    features: [
      { icon: '🎵', title: 'Slash-Befehle', body: '/play, /skip, /queue, /volume, /loop, /shuffle und mehr.' },
      { icon: '🔊', title: 'Quellen', body: 'SoundCloud, Bandcamp, Twitch und HTTP-/Radio-Streams.' },
      { icon: '🎛️', title: 'Dashboard-Player', body: 'Wiedergabe und Warteschlange live im Browser steuern.' },
      { icon: '🎧', title: 'DJ-Rolle', body: 'Steuerung auf DJ/Admin beschränken, Standard-Lautstärke, Auto-Disconnect.' }
    ],
    faq: [
      { q: 'Unterstützt der Bot YouTube?', a: 'Nein – bewusst kein YouTube. Es funktionieren SoundCloud, Bandcamp, Twitch und Radio-Streams.' },
      { q: 'Kann ich die Musik im Dashboard steuern?', a: 'Ja, es gibt einen Live-Player mit Warteschlange direkt im Dashboard.' },
      { q: 'Welcher Tarif?', a: 'Musik ist im Pro-Tarif enthalten und benötigt einen Lavalink-Server.' }
    ]
  }
}
