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

          <!-- Embed -->
          <div v-if="mode === 'embed'" class="dmp-embed" :style="{ borderLeftColor: embedColor }">
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
}

function resolvePlainText(raw) {
  return replaceFlat(raw)
    .replace(/\{guild\}/g, props.guildName || 'Your Server')
    .replace(/\{user\}/g, `@${props.username || MOCK_USER_NAME}`)
}

function renderInlineHtml(raw) {
  if (typeof raw !== 'string' || !raw) return ''
  let s = replaceFlat(raw)
  let html = escapeHtml(s)
  html = html.replace(/\{user\}/g, `<span class="mention">@${escapeHtml(props.username || MOCK_USER_NAME)}</span>`)
  html = html.replace(/\{guild\}/g, `<span class="mention mention--soft">${escapeHtml(props.guildName || 'Your Server')}</span>`)
  html = html.replace(/\n/g, '<br/>')
  return html
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
  return renderInlineHtml(raw)
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
</style>
