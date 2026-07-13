<template>
  <div class="dmp">
    <div class="dmp__header">
      <span class="dmp__hash">#</span>
      <span class="dmp__channel">{{ channelName || 'welcome' }}</span>
    </div>
    <div class="dmp__messages">
      <div class="dmp__msg">
        <div class="dmp__avatar">
          <span>PX</span>
        </div>
        <div class="dmp__body">
          <div class="dmp__meta">
            <span class="dmp__author">ProjectX</span>
            <span class="dmp__badge">BOT</span>
            <span class="dmp__time">{{ time }}</span>
          </div>

          <!-- Content line: plain-mode message OR ping mention in embed mode -->
          <div v-if="contentHtml" class="dmp__content" v-html="contentHtml"></div>

          <!-- Components V2 container -->
          <div v-if="isV2" class="dmp-v2" :style="{ borderLeftColor: accentColor }">
            <template v-for="(block, i) in v2Blocks" :key="i">
              <div v-if="block.type === 'text'" class="dmp-v2__text" v-html="block.html"></div>
              <hr v-else-if="block.type === 'separator' && block.divider" class="dmp-v2__sep" :class="{ 'is-large': block.large }" />
              <div v-else-if="block.type === 'separator'" class="dmp-v2__gap" :class="{ 'is-large': block.large }"></div>
              <div v-else-if="block.type === 'image' && block.url" class="dmp-v2__image">
                <img :src="block.url" alt="" @error="$event.target.closest('.dmp-v2__image').style.display='none'" />
              </div>
              <div v-else-if="block.type === 'section'" class="dmp-v2__section">
                <div class="dmp-v2__section-text dmp-v2__text" v-html="block.html"></div>
                <div v-if="block.thumb" class="dmp-v2__section-thumb">
                  <img :src="block.thumb" alt="" @error="$event.target.closest('.dmp-v2__section-thumb').style.display='none'" />
                </div>
              </div>
            </template>
            <div v-if="!v2Blocks.length" class="dmp-v2__empty">{{ '…' }}</div>
          </div>

          <!-- Embed -->
          <div v-if="mode === 'embed' && !isV2" class="dmp-embed" :style="{ borderLeftColor: embedColor }">
            <div class="dmp-embed__inner">
              <div class="dmp-embed__main">
                <div v-if="hasAuthor" class="dmp-embed__author">
                  <span class="dmp-embed__author-icon">
                    <img
                      v-if="authorIconIsUrl && !authorIconErr"
                      :src="embedResolved.author_icon_url"
                      alt=""
                      @error="authorIconErr = true"
                    />
                    <span
                      v-else-if="embedResolved.author_icon_url"
                      class="dmp-embed__avatar-fallback"
                      :style="{ background: avatarGradient }"
                    ></span>
                  </span>
                  <span class="dmp-embed__author-name">{{ embedResolved.author_name }}</span>
                </div>

                <div v-if="embedResolved.title" class="dmp-embed__title">{{ embedResolved.title }}</div>

                <div v-if="embedResolved.description" class="dmp-embed__desc" v-html="embedDescHtml"></div>

                <div v-if="imageIsUrl && !imageErr" class="dmp-embed__image">
                  <img :src="embedResolved.image" alt="" @error="imageErr = true" />
                </div>

                <div v-if="footerRow.show" class="dmp-embed__footer">
                  <span v-if="footerRow.text" class="dmp-embed__footer-text">{{ footerRow.text }}</span>
                  <span v-if="footerRow.text && footerRow.timestamp" class="dmp-embed__footer-dot">•</span>
                  <span v-if="footerRow.timestamp" class="dmp-embed__footer-time">{{ footerRow.timestamp }}</span>
                </div>
              </div>

              <div v-if="hasThumbnail" class="dmp-embed__thumb">
                <img
                  v-if="thumbIsUrl && !thumbErr"
                  :src="embedResolved.thumbnail"
                  alt=""
                  @error="thumbErr = true"
                />
                <span
                  v-else
                  class="dmp-embed__avatar-fallback dmp-embed__thumb-fallback"
                  :style="{ background: avatarGradient }"
                ></span>
              </div>
            </div>
          </div>

          <!-- Action rows (buttons / select menus) below the message -->
          <slot name="components" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useAuth } from '../stores/auth.js'

const auth = useAuth()

// The logged-in user's own Discord avatar — used so the preview renders the
// real avatar wherever the {user.avatar} token appears (instead of a generic
// placeholder). Empty for guests → falls back to the gradient placeholder.
const myAvatarUrl = computed(() => auth.state.user?.avatar_url || '')

const AVATAR_TOKEN = '{user.avatar}'

/** Resolve an image-field value: substitute {user.avatar} with the viewer's own
 * avatar URL when available; otherwise return the raw value unchanged. */
function resolveImageField(value) {
  if (value === AVATAR_TOKEN) return myAvatarUrl.value || value
  return value || ''
}

const props = defineProps({
  message: { type: String, default: '' },
  channelName: { type: String, default: '' },
  username: { type: String, default: 'Alex' },
  guildName: { type: String, default: 'Your Server' },
  mode: { type: String, default: 'plain' }, // 'plain' | 'embed'
  embed: { type: Object, default: () => ({}) },
  pingUser: { type: Boolean, default: false }
})

const MOCK_USER_NAME = 'Alex'
const MOCK_USER_ID = '123456789012345678'
const MOCK_USER_TAG = 'Alex#0001'
const MOCK_GUILD_ID = '987654321098765432'
const MOCK_MEMBER_COUNT = '42'
const MOCK_TICKET_NUMBER = '42'
const MOCK_TICKET_CATEGORY = 'Support'

const authorIconErr = ref(false)
const imageErr = ref(false)
const thumbErr = ref(false)

watch(() => props.embed?.author_icon_url, () => { authorIconErr.value = false })
watch(() => props.embed?.image, () => { imageErr.value = false })
watch(() => props.embed?.thumbnail, () => { thumbErr.value = false })

const time = computed(() => {
  const d = new Date()
  return `Today at ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
})

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/** Replace placeholders that have a flat text mapping. {user.avatar} is
 * deliberately left alone — it's an image URL token that only makes sense
 * in image fields, and we render a gradient placeholder for it. */
function replaceFlat(raw) {
  if (typeof raw !== 'string') return ''
  return raw
    .replace(/\{user\.name\}/g, MOCK_USER_NAME)
    .replace(/\{user\.id\}/g, MOCK_USER_ID)
    .replace(/\{user\.tag\}/g, MOCK_USER_TAG)
    .replace(/\{guild\.id\}/g, MOCK_GUILD_ID)
    .replace(/\{guild\.member_count\}/g, MOCK_MEMBER_COUNT)
    // Ticket-specific tokens — mocked so ticket panel/welcome previews look live.
    .replace(/\{number\}/g, MOCK_TICKET_NUMBER)
    .replace(/\{category\}/g, MOCK_TICKET_CATEGORY)
}

function resolvePlainText(raw) {
  return replaceFlat(raw)
    .replace(/\{guild\}/g, props.guildName || 'Your Server')
    .replace(/\{user\}/g, `@${props.username || MOCK_USER_NAME}`)
}

// --- Discord-flavoured markdown → HTML (preview approximation) -------------
// Input is HTML-escaped FIRST, so user text can never inject tags; every tag
// below is our own. Masked links are restricted to http(s) (no javascript:).

/** Inline formatting: bold/italic/underline/strike/code/spoiler/links/mentions.
 * `text` must already be HTML-escaped. */
function inlineMd(text) {
  let h = text
  // masked link [label](https://…)
  h = h.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (m, label, url) => `<a class="md-link" href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`)
  // inline code `code`
  h = h.replace(/`([^`\n]+)`/g, '<code class="md-code">$1</code>')
  // bold **text**  (before single-* italic)
  h = h.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
  // underline __text__  (before single-_ italic)
  h = h.replace(/__([^_\n]+)__/g, '<u>$1</u>')
  // strikethrough ~~text~~
  h = h.replace(/~~([^~\n]+)~~/g, '<s>$1</s>')
  // spoiler ||text||
  h = h.replace(/\|\|([^|\n]+)\|\|/g, '<span class="md-spoiler">$1</span>')
  // italic *text* / _text_
  h = h.replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
  h = h.replace(/_([^_\n]+)_/g, '<em>$1</em>')
  // placeholder mentions
  h = h.replace(/\{user\}/g, `<span class="mention">@${escapeHtml(props.username || MOCK_USER_NAME)}</span>`)
  h = h.replace(/\{guild\}/g, `<span class="mention mention--soft">${escapeHtml(props.guildName || 'Your Server')}</span>`)
  return h
}

/** Full renderer: block-level (headers/quote/list) line by line, then inline.
 * `allowHeaders` matches Discord: headers render in message content + V2 text
 * displays, but NOT inside classic embed descriptions. */
function renderMarkdown(raw, allowHeaders = false) {
  if (typeof raw !== 'string' || !raw) return ''
  const lines = replaceFlat(raw).split('\n')
  const pieces = [] // { block: bool, html }
  for (const rawLine of lines) {
    const line = escapeHtml(rawLine)
    let m
    if (allowHeaders && (m = line.match(/^###\s+(.+)$/))) { pieces.push({ block: true, html: `<div class="md-h md-h3">${inlineMd(m[1])}</div>` }); continue }
    if (allowHeaders && (m = line.match(/^##\s+(.+)$/)))  { pieces.push({ block: true, html: `<div class="md-h md-h2">${inlineMd(m[1])}</div>` }); continue }
    if (allowHeaders && (m = line.match(/^#\s+(.+)$/)))   { pieces.push({ block: true, html: `<div class="md-h md-h1">${inlineMd(m[1])}</div>` }); continue }
    if ((m = line.match(/^-#\s+(.+)$/)))                  { pieces.push({ block: true, html: `<div class="md-subtext">${inlineMd(m[1])}</div>` }); continue }
    if ((m = line.match(/^&gt;\s?(.*)$/)))                { pieces.push({ block: true, html: `<div class="md-quote">${inlineMd(m[1])}</div>` }); continue }
    if ((m = line.match(/^[-*]\s+(.+)$/)))                { pieces.push({ block: true, html: `<div class="md-li">${inlineMd(m[1])}</div>` }); continue }
    pieces.push({ block: false, html: inlineMd(line) })
  }
  let out = ''
  for (let i = 0; i < pieces.length; i++) {
    if (i > 0 && !pieces[i - 1].block && !pieces[i].block) out += '<br/>'
    out += pieces[i].html
  }
  return out
}

function renderInlineHtml(raw) {
  return renderMarkdown(raw, false)
}

// --- Content row above the embed (or for plain mode) ----------------------
const contentHtml = computed(() => {
  if (props.mode === 'embed') {
    if (props.pingUser) {
      return `<span class="mention">@${escapeHtml(props.username || MOCK_USER_NAME)}</span>`
    }
    return ''
  }
  const raw = (props.message || '').trim() || '(empty message)'
  return renderMarkdown(raw, true)
})

// --- Embed resolution -----------------------------------------------------
const embedResolved = computed(() => {
  const e = props.embed || {}
  return {
    title: resolvePlainText(e.title || ''),
    description: e.description || '',
    color: typeof e.color === 'string' ? e.color : '#5865F2',
    thumbnail: resolveImageField(e.thumbnail),
    image: resolveImageField(e.image),
    footer: resolvePlainText(e.footer || ''),
    show_timestamp: !!e.show_timestamp,
    author_name: resolvePlainText(e.author_name || ''),
    author_icon_url: resolveImageField(e.author_icon_url)
  }
})

const embedColor = computed(() => {
  const c = embedResolved.value.color
  return /^#[0-9A-Fa-f]{6}$/.test(c) ? c : '#5865F2'
})

// --- Components V2 container preview ---------------------------------------
const isV2 = computed(() => props.mode === 'embed' && (props.embed || {}).format === 'components_v2')

const accentColor = computed(() => {
  const c = (props.embed || {}).accent_color
  return typeof c === 'string' && /^#[0-9A-Fa-f]{6}$/.test(c) ? c : embedColor.value
})

const v2Blocks = computed(() => {
  const blocks = (props.embed || {}).blocks
  if (!Array.isArray(blocks)) return []
  return blocks.map((b) => {
    if (b.type === 'text') return { type: 'text', html: renderMarkdown(b.content || '', true) }
    if (b.type === 'separator') return { type: 'separator', divider: b.divider !== false, large: b.spacing === 2 }
    if (b.type === 'image') return { type: 'image', url: resolveImageField(b.url) }
    if (b.type === 'section') {
      const thumb = resolveImageField(b.thumbnail)
      return { type: 'section', html: renderMarkdown(b.content || '', true), thumb: /^https?:\/\//i.test(thumb) ? thumb : '' }
    }
    return { type: 'unknown' }
  })
})

const embedDescHtml = computed(() => renderInlineHtml(embedResolved.value.description))

const hasAuthor = computed(() => {
  return !!(embedResolved.value.author_name || embedResolved.value.author_icon_url)
})

const authorIconIsUrl = computed(() => /^https?:\/\//i.test(embedResolved.value.author_icon_url))
const imageIsUrl = computed(() => /^https?:\/\//i.test(embedResolved.value.image))
const thumbIsUrl = computed(() => /^https?:\/\//i.test(embedResolved.value.thumbnail))

const hasThumbnail = computed(() => !!embedResolved.value.thumbnail)

const footerRow = computed(() => {
  const text = embedResolved.value.footer
  const ts = embedResolved.value.show_timestamp ? formattedTimestamp() : ''
  return {
    show: !!(text || ts),
    text,
    timestamp: ts
  }
})

function formattedTimestamp() {
  const d = new Date()
  return `Today at ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

// Deterministic gradient matching GuildAvatar's behavior for the mock user.
const avatarGradient = computed(() => {
  const palette = [
    ['#5865f2', '#a78bfa'],
    ['#a78bfa', '#22d3ee'],
    ['#22d3ee', '#5865f2'],
    ['#f472b6', '#a78bfa'],
    ['#10b981', '#22d3ee'],
    ['#f59e0b', '#f472b6'],
    ['#6366f1', '#06b6d4'],
    ['#8b5cf6', '#ec4899']
  ]
  const n = props.username || MOCK_USER_NAME
  let hash = 0
  for (let i = 0; i < n.length; i++) hash = (hash * 31 + n.charCodeAt(i)) | 0
  const [a, b] = palette[Math.abs(hash) % palette.length]
  return `linear-gradient(135deg, ${a} 0%, ${b} 100%)`
})
</script>

<style scoped>
.dmp {
  background: #2b2d31;
  border: 1px solid #1f2024;
  border-radius: var(--radius-lg);
  overflow: hidden;
  font-family: var(--font-sans);
  color: #dbdee1;
  box-shadow: var(--shadow-md);
}

.dmp__header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0.75rem 1rem;
  background: #2b2d31;
  border-bottom: 1px solid #1f2024;
  font-weight: 600;
  color: #f2f3f5;
  font-size: 0.95rem;
}

.dmp__hash {
  color: #80848e;
  font-weight: 700;
  font-size: 1.1rem;
  line-height: 1;
}

.dmp__messages {
  padding: 1rem 1rem 1.25rem;
}

.dmp__msg {
  display: flex;
  gap: 0.85rem;
  align-items: flex-start;
}

.dmp__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--gradient-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
  font-weight: 700;
  font-family: var(--font-display);
  font-size: 0.85rem;
  letter-spacing: -0.01em;
}

.dmp__body {
  flex: 1;
  min-width: 0;
}

.dmp__meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.2rem;
}

.dmp__author {
  color: #fff;
  font-weight: 600;
  font-size: 0.98rem;
}

.dmp__badge {
  background: var(--color-primary);
  color: #fff;
  font-size: 0.62rem;
  padding: 0.08rem 0.35rem;
  border-radius: 4px;
  font-weight: 700;
  letter-spacing: 0.03em;
  margin-top: 1px;
}

.dmp__time {
  color: #949ba4;
  font-size: 0.75rem;
}

.dmp__content {
  color: #dbdee1;
  font-size: 0.97rem;
  line-height: 1.45;
  word-wrap: break-word;
  white-space: pre-wrap;
}

.dmp__content :deep(.mention) {
  background: rgba(88, 101, 242, 0.3);
  color: #c9cdfb;
  padding: 0 2px;
  border-radius: 3px;
  font-weight: 500;
}

.dmp__content :deep(.mention--soft) {
  background: rgba(167, 139, 250, 0.18);
  color: #d4c5fc;
}

/* ---------- Embed ---------- */
.dmp-embed {
  margin-top: 0.4rem;
  background: #2b2d31;
  border: 1px solid #1f2024;
  border-left: 4px solid #5865F2;
  border-radius: 4px;
  max-width: 520px;
  overflow: hidden;
}

.dmp-embed__inner {
  display: flex;
  gap: 0.6rem;
  padding: 0.6rem 0.9rem 0.7rem;
}

.dmp-embed__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.dmp-embed__author {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.85rem;
  color: #f2f3f5;
  font-weight: 600;
}

.dmp-embed__author-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  overflow: hidden;
  display: inline-flex;
  flex-shrink: 0;
}

.dmp-embed__author-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dmp-embed__avatar-fallback {
  width: 100%;
  height: 100%;
  display: inline-block;
  background: linear-gradient(135deg, #5865f2, #a78bfa);
}

.dmp-embed__thumb-fallback {
  border-radius: 4px;
}

.dmp-embed__author-name {
  word-break: break-word;
}

.dmp-embed__title {
  color: #f2f3f5;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.3;
  word-break: break-word;
}

.dmp-embed__desc {
  color: #dbdee1;
  font-size: 0.88rem;
  line-height: 1.45;
  word-break: break-word;
  white-space: pre-wrap;
}

.dmp-embed__desc :deep(.mention) {
  background: rgba(88, 101, 242, 0.3);
  color: #c9cdfb;
  padding: 0 2px;
  border-radius: 3px;
  font-weight: 500;
}

.dmp-embed__desc :deep(.mention--soft) {
  background: rgba(167, 139, 250, 0.18);
  color: #d4c5fc;
}

.dmp-embed__image {
  margin-top: 0.4rem;
  max-width: 100%;
  border-radius: 4px;
  overflow: hidden;
  background: #1e1f22;
}

.dmp-embed__image img {
  display: block;
  width: 100%;
  height: auto;
  max-height: 320px;
  object-fit: cover;
}

.dmp-embed__footer {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.74rem;
  color: #949ba4;
  margin-top: 0.3rem;
  flex-wrap: wrap;
}

.dmp-embed__footer-dot {
  color: #5a5e69;
}

.dmp-embed__thumb {
  width: 80px;
  height: 80px;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
  background: #1e1f22;
}

.dmp-embed__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* ---------- Components V2 container ---------- */
.dmp-v2 {
  margin-top: 0.4rem;
  background: #2b2d31;
  border: 1px solid #1f2024;
  border-left: 4px solid #5865F2;
  border-radius: 4px;
  max-width: 520px;
  padding: 0.7rem 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.dmp-v2__text {
  color: #dbdee1;
  font-size: 0.9rem;
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-wrap;
}

.dmp-v2__text :deep(.mention) {
  background: rgba(88, 101, 242, 0.3);
  color: #c9cdfb;
  padding: 0 2px;
  border-radius: 3px;
  font-weight: 500;
}

.dmp-v2__text :deep(.mention--soft) {
  background: rgba(167, 139, 250, 0.18);
  color: #d4c5fc;
}

.dmp-v2__sep {
  border: none;
  border-top: 1px solid #3f4147;
  margin: 0.15rem 0;
}

.dmp-v2__sep.is-large {
  margin: 0.5rem 0;
}

.dmp-v2__gap {
  height: 0.3rem;
}

.dmp-v2__gap.is-large {
  height: 0.8rem;
}

.dmp-v2__image {
  border-radius: 4px;
  overflow: hidden;
  background: #1e1f22;
}

.dmp-v2__image img {
  display: block;
  width: 100%;
  height: auto;
  max-height: 320px;
  object-fit: cover;
}

.dmp-v2__empty {
  color: #949ba4;
  font-size: 0.85rem;
}

.dmp-v2__section {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.dmp-v2__section-text {
  flex: 1;
  min-width: 0;
  color: #dbdee1;
  font-size: 0.9rem;
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-wrap;
}

.dmp-v2__section-thumb {
  flex-shrink: 0;
  width: 72px;
  height: 72px;
  border-radius: 6px;
  overflow: hidden;
  background: #1e1f22;
}

.dmp-v2__section-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* ---------- Rendered markdown (shared across content / embed desc / V2 text) ---------- */
.dmp__content :deep(.md-h),
.dmp-embed__desc :deep(.md-h),
.dmp-v2__text :deep(.md-h) {
  font-weight: 700;
  line-height: 1.3;
  color: #f2f3f5;
  margin: 0.25rem 0 0.1rem;
}
.dmp__content :deep(.md-h1),
.dmp-embed__desc :deep(.md-h1),
.dmp-v2__text :deep(.md-h1) { font-size: 1.4rem; }
.dmp__content :deep(.md-h2),
.dmp-embed__desc :deep(.md-h2),
.dmp-v2__text :deep(.md-h2) { font-size: 1.15rem; }
.dmp__content :deep(.md-h3),
.dmp-embed__desc :deep(.md-h3),
.dmp-v2__text :deep(.md-h3) { font-size: 1rem; }

.dmp__content :deep(.md-code),
.dmp-embed__desc :deep(.md-code),
.dmp-v2__text :deep(.md-code) {
  font-family: var(--font-mono, monospace);
  font-size: 0.85em;
  background: #1e1f22;
  border: 1px solid #111214;
  border-radius: 4px;
  padding: 0.05rem 0.3rem;
}

.dmp__content :deep(.md-link),
.dmp-embed__desc :deep(.md-link),
.dmp-v2__text :deep(.md-link) {
  color: #00a8fc;
  text-decoration: none;
}
.dmp__content :deep(.md-link:hover),
.dmp-embed__desc :deep(.md-link:hover),
.dmp-v2__text :deep(.md-link:hover) { text-decoration: underline; }

.dmp__content :deep(.md-spoiler),
.dmp-embed__desc :deep(.md-spoiler),
.dmp-v2__text :deep(.md-spoiler) {
  background: #111214;
  color: transparent;
  border-radius: 4px;
  padding: 0 2px;
}

.dmp__content :deep(.md-quote),
.dmp-embed__desc :deep(.md-quote),
.dmp-v2__text :deep(.md-quote) {
  border-left: 3px solid #4e5058;
  padding-left: 0.6rem;
  margin: 0.1rem 0;
}

.dmp__content :deep(.md-subtext),
.dmp-embed__desc :deep(.md-subtext),
.dmp-v2__text :deep(.md-subtext) {
  font-size: 0.8em;
  color: #949ba4;
  line-height: 1.3;
}

.dmp__content :deep(.md-li),
.dmp-embed__desc :deep(.md-li),
.dmp-v2__text :deep(.md-li) {
  padding-left: 1.1rem;
  position: relative;
}
.dmp__content :deep(.md-li)::before,
.dmp-embed__desc :deep(.md-li)::before,
.dmp-v2__text :deep(.md-li)::before {
  content: '•';
  position: absolute;
  left: 0.35rem;
  color: #b5bac1;
}
</style>
