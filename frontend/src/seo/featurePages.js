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
  },
  'discord-stats-bot': {
    seoTitle: 'Discord Server-Statistik Bot – Counter – Kampfkekse',
    seoDescription: 'Zeige Live-Serverzahlen als Kanalnamen (Mitglieder, Online, Booster) plus Verlaufs-Graphen. Der klassische Server-Stats-Bot, online konfigurierbar.',
    h1: 'Der Discord Server-Statistik-Bot',
    subtitle: 'Live-Zahlen deines Servers als Kanalnamen – plus Verlaufs-Graphen im Dashboard.',
    features: [
      { icon: '📊', title: 'Counter-Kanäle', body: 'Mitglieder, Menschen, Bots, Online, Booster, Kanäle und Rollen als Voice-/Text-Kanäle.' },
      { icon: '🧩', title: 'Auto-Anlage', body: 'Der Bot legt die Kanäle in einer Kategorie an und hält die Reihenfolge.' },
      { icon: '📈', title: 'Verlaufs-Graphen', body: '7- und 30-Tage-Verlauf im Dashboard.' },
      { icon: '⚙️', title: 'Vorlagen', body: 'Kanalnamen frei per Vorlage mit {count}.' }
    ],
    faq: [
      { q: 'Wie zählt der Bot online/offline?', a: 'Über das privilegierte Presence-Intent, das im Discord-Developer-Portal aktiviert werden muss.' },
      { q: 'Werden echte Kanäle erstellt?', a: 'Ja – wahlweise nutzt du bestehende Kanäle oder der Bot erstellt sie automatisch.' },
      { q: 'Welcher Tarif?', a: 'Statistiken sind im Pro-Tarif enthalten.' }
    ]
  },
  'discord-giveaway-bot': {
    seoTitle: 'Discord Giveaway Bot – Voraussetzungen & Reroll – Kampfkekse',
    seoDescription: 'Gewinnspiele mit Teilnahme-Voraussetzungen (Rollen, Kontoalter, Level), automatischer Ziehung und Reroll – auch direkt im Dashboard erstellbar.',
    h1: 'Der Discord Giveaway-Bot',
    subtitle: 'Faire Verlosungen mit Voraussetzungen, automatischer Ziehung und Reroll.',
    features: [
      { icon: '🎉', title: 'Slash-Befehle', body: '/giveaway start, reroll und end – schnell erstellt.' },
      { icon: '✅', title: 'Voraussetzungen', body: 'Benötigte Rollen, Mindest-Kontoalter, Serverzugehörigkeit und Level.' },
      { icon: '🎲', title: 'Auto-Ziehung', body: 'Gewinner werden automatisch gezogen, Reroll jederzeit möglich.' },
      { icon: '🖥️', title: 'Im Dashboard', body: 'Giveaways auch komplett im Browser erstellen.' }
    ],
    faq: [
      { q: 'Kann ich Voraussetzungen festlegen?', a: 'Ja – Rollen, Kontoalter, Serverzugehörigkeit und Mindest-Level werden beim Klick geprüft.' },
      { q: 'Gibt es einen Reroll?', a: 'Ja, ein neuer Gewinner kann jederzeit aus den Teilnehmern gezogen werden.' },
      { q: 'Welcher Tarif?', a: 'Gewinnspiele sind im Pro-Tarif enthalten.' }
    ]
  },
  'discord-economy-bot': {
    seoTitle: 'Discord Economy Bot – Währung & Shop – Kampfkekse',
    seoDescription: 'Server-Wirtschaft mit Kontostand, Daily/Work, Bezahlen, Bestenliste und Rollen-Shop. Shop und Einstellungen bequem im Dashboard.',
    h1: 'Der Discord Economy-Bot',
    subtitle: 'Eine eigene Server-Währung mit Daily, Work, Shop und Bestenliste.',
    features: [
      { icon: '💰', title: 'Währung & Belohnungen', body: 'Kontostand, Daily und Work mit konfigurierbaren Beträgen und Cooldowns.' },
      { icon: '🛒', title: 'Rollen-Shop', body: 'Artikel kaufen – optional mit Rollenvergabe.' },
      { icon: '🤝', title: 'Bezahlen', body: 'Mitglieder überweisen sich gegenseitig Guthaben.' },
      { icon: '🏆', title: 'Bestenliste', body: 'Wer hat am meisten? Guthaben-Ranking.' }
    ],
    faq: [
      { q: 'Kann ich Rollen im Shop verkaufen?', a: 'Ja – ein Shop-Artikel kann beim Kauf automatisch eine Rolle vergeben.' },
      { q: 'Sind die Beträge einstellbar?', a: 'Ja, Start-Guthaben, Daily/Work-Beträge und Cooldowns sind konfigurierbar.' },
      { q: 'Welcher Tarif?', a: 'Wirtschaft ist im Pro-Tarif enthalten.' }
    ]
  },
  'discord-server-backup-bot': {
    seoTitle: 'Discord Server-Backup Bot – Wiederherstellen – Kampfkekse',
    seoDescription: 'Erstelle Snapshots deiner Server-Struktur (Kanäle & Rollen inkl. Rechte) und stelle sie jederzeit wieder her. Mit Server-Vorlagen und Marktplatz.',
    h1: 'Der Discord Server-Backup-Bot',
    subtitle: 'Sichere deine komplette Server-Struktur und stelle sie mit einem Klick wieder her.',
    features: [
      { icon: '💾', title: 'Snapshots', body: 'Rollen, Kanäle, Rechte und Server-Style sichern.' },
      { icon: '♻️', title: 'Wiederherstellen', body: 'Modus „missing" (nur Fehlendes) oder „mirror" (angleichen).' },
      { icon: '📋', title: 'Server-Vorlagen', body: 'Struktur von einem Server auf einen anderen anwenden.' },
      { icon: '🛍️', title: 'Marktplatz', body: 'Veröffentlichte Vorlagen anwenden.' }
    ],
    faq: [
      { q: 'Werden Nachrichten mitgesichert?', a: 'Nein – gesichert wird die Struktur (Rollen, Kanäle, Rechte), nicht Nachrichten oder Mitglieder.' },
      { q: 'Kann ich einen Server als Vorlage nutzen?', a: 'Ja, Snapshots lassen sich als Vorlage auf andere eigene Server anwenden.' },
      { q: 'Welcher Tarif?', a: 'Server-Backup ist im Pro-Tarif enthalten.' }
    ]
  },
  'discord-minecraft-bot': {
    seoTitle: 'Minecraft Server-Status Bot für Discord – Kampfkekse',
    seoDescription: 'Zeige den Live-Status deiner Minecraft-Server (Java & Bedrock) in Discord – Spielerzahl, MOTD und Version – als automatisch aktualisierte Nachricht.',
    h1: 'Minecraft Server-Status in Discord',
    subtitle: 'Zeige live, ob deine Minecraft-Server online sind – Java und Bedrock, ganz ohne Plugin.',
    features: [
      { icon: '🟢', title: 'Live-Status', body: 'Online/Offline mit Spielerzahl, MOTD und Version.' },
      { icon: '🧱', title: 'Java & Bedrock', body: 'Beide Editionen per IP unterstützt.' },
      { icon: '🔄', title: 'Auto-Update', body: 'Die Statusnachricht aktualisiert sich selbst.' },
      { icon: '🎨', title: 'Klartext oder Embed', body: 'Darstellung frei wählbar mit Platzhaltern.' }
    ],
    faq: [
      { q: 'Brauche ich ein Plugin auf dem Server?', a: 'Nein – der Status wird extern abgefragt, es genügt die Server-IP.' },
      { q: 'Werden Java und Bedrock unterstützt?', a: 'Ja, beide Editionen werden unterstützt.' },
      { q: 'Ist das kostenlos?', a: 'Ja, das Minecraft-Status-Modul ist dauerhaft im Free-Tarif enthalten.' }
    ]
  }
}
