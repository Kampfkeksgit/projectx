<template>
  <div class="form-card mc-row" :class="{ 'is-draft': isDraft }">
    <div class="mc-row__head" @click="collapsed = !collapsed">
      <div class="mc-row__title">
        <button
          type="button"
          class="mc-row__collapse"
          :class="{ 'is-collapsed': collapsed }"
          :aria-label="t('minecraft.unsavedDot')"
          :aria-expanded="!collapsed"
          @click.stop="collapsed = !collapsed"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <span v-if="dirty" class="mc-row__dot" :title="t('minecraft.unsavedDot')" aria-hidden="true"></span>
        <span class="mc-row__badge" :class="`mc-row__badge--${local.edition}`">
          {{ local.edition === 'bedrock' ? t('minecraft.editionBedrock') : t('minecraft.editionJava') }}
        </span>
        <span class="mc-row__name">{{ local.name || local.address || t('minecraft.namePlaceholder') }}</span>
        <span v-if="statusLabel" class="mc-row__status" :class="`mc-row__status--${local.status || 'unknown'}`">
          <span class="mc-row__status-dot"></span>{{ statusLabel }}
        </span>
      </div>
      <div class="mc-row__head-actions" @click.stop>
        <span class="mc-row__enabled-label">{{ t('minecraft.enabledLabel') }}</span>
        <AppToggle v-model="local.enabled" />
      </div>
    </div>

    <div v-show="!collapsed" class="mc-row__body">
      <div class="mc-row__split">
        <div class="mc-row__fields">
          <div class="mc-row__grid">
            <div class="form-row">
              <label class="form-row__label" :for="`mc-name-${rowKey}`">{{ t('minecraft.nameLabel') }}</label>
              <input
                :id="`mc-name-${rowKey}`"
                v-model="local.name"
                class="input"
                type="text"
                maxlength="100"
                :placeholder="t('minecraft.namePlaceholder')"
              />
            </div>
            <div class="form-row">
              <label class="form-row__label" :for="`mc-edition-${rowKey}`">{{ t('minecraft.editionLabel') }}</label>
              <select :id="`mc-edition-${rowKey}`" v-model="local.edition" class="input">
                <option value="java">{{ t('minecraft.editionJava') }}</option>
                <option value="bedrock">{{ t('minecraft.editionBedrock') }}</option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <label class="form-row__label" :for="`mc-address-${rowKey}`">{{ t('minecraft.addressLabel') }}</label>
            <input
              :id="`mc-address-${rowKey}`"
              v-model="local.address"
              class="input input--mono"
              type="text"
              maxlength="200"
              :placeholder="t('minecraft.addressPlaceholder')"
            />
            <div class="form-row__hint">{{ t('minecraft.addressHint') }}</div>
          </div>

          <div class="form-row">
            <label class="form-row__label">{{ t('minecraft.channelLabel') }}</label>
            <ChannelSelector
              v-model="local.channel_id"
              :guild-id="guildId"
              :types="['text', 'announcement']"
            />
            <div class="form-row__hint">{{ t('minecraft.channelHint') }}</div>
          </div>

          <div class="form-row">
            <label class="form-row__label">{{ t('minecraft.modeLabel') }}</label>
            <div class="mc-row__mode">
              <button type="button" class="mc-row__mode-btn" :class="{ 'is-active': local.notify_mode === 'plain' }" @click="local.notify_mode = 'plain'">{{ t('minecraft.modePlain') }}</button>
              <button type="button" class="mc-row__mode-btn" :class="{ 'is-active': local.notify_mode === 'embed' }" @click="local.notify_mode = 'embed'">{{ t('minecraft.modeEmbed') }}</button>
            </div>
            <div class="form-row__hint">{{ t('minecraft.modeHint') }}</div>
          </div>

          <div v-if="local.notify_mode === 'plain'" class="form-row">
            <label class="form-row__label" :for="`mc-tpl-${rowKey}`">{{ t('minecraft.messageLabel') }}</label>
            <textarea
              :id="`mc-tpl-${rowKey}`"
              ref="tplRef"
              v-model="local.message_template"
              class="input input--textarea"
              rows="3"
              maxlength="1000"
              :placeholder="t('minecraft.messagePlaceholder')"
            ></textarea>
            <div class="form-row__hint">{{ t('minecraft.messageHint') }}</div>
            <div class="placeholder-bar">
              <button
                v-for="token in MC_PLACEHOLDERS"
                :key="token"
                type="button"
                class="placeholder-bar__chip"
                @click="insertPlaceholder(token)"
              >{{ token }}</button>
            </div>
          </div>

          <div v-else class="form-row">
            <label class="form-row__label">{{ t('minecraft.embedLabel') }}</label>
            <div class="form-row__hint">{{ t('minecraft.embedHint') }}</div>
            <EmbedEditor v-model="local.embed" />
            <div class="placeholder-bar">
              <span class="placeholder-bar__chip placeholder-bar__chip--static" v-for="token in MC_PLACEHOLDERS" :key="token">{{ token }}</span>
            </div>
            <div class="form-row__hint">{{ t('minecraft.placeholdersHint') }}</div>
          </div>
        </div>

        <aside class="mc-row__preview-col">
          <div class="mc-preview__label">{{ t('minecraft.livePreview') }}</div>
          <DiscordMessagePreview
            :mode="local.notify_mode"
            :message="previewMessage"
            :embed="previewEmbed"
            :guild-name="guildName"
            channel-name="minecraft"
          >
            <template #components>
              <div class="mc-status-mock">
                <span class="mc-status-mock__dot"></span>
                <span class="mc-status-mock__text">{{ t('minecraft.statusOnline') }} 42/100</span>
                <span class="mc-status-mock__sep">•</span>
                <span class="mc-status-mock__version">1.21.4</span>
              </div>
            </template>
          </DiscordMessagePreview>
        </aside>
      </div>

      <div class="mc-row__actions">
        <AppButton v-if="!isDraft" variant="danger" :loading="deleting" @click="$emit('delete', local)">{{ t('minecraft.delete') }}</AppButton>
        <AppButton v-if="isDraft" variant="ghost" :disabled="saving" @click="$emit('cancel')">{{ t('minecraft.cancel') }}</AppButton>
        <AppButton variant="gradient" :loading="saving" :disabled="!isDraft && !dirty" @click="$emit('save', cloneLocal())">{{ t('minecraft.save') }}</AppButton>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import AppButton from './AppButton.vue'
import AppToggle from './AppToggle.vue'
import ChannelSelector from './ChannelSelector.vue'
import EmbedEditor from './EmbedEditor.vue'
import DiscordMessagePreview from './DiscordMessagePreview.vue'
import { insertAtCaret } from './embedPlaceholders.js'
import { useI18n } from '../i18n/index.js'
import { useGuildSettings } from '../stores/guildSettings.js'

const { t } = useI18n()
const store = useGuildSettings()
const guildName = computed(() => {
  const g = store.cache.guild
  return g?.guild_name || g?.name || 'Your Server'
})

// Minecraft-specific placeholders — distinct from the welcome/social sets.
const MC_PLACEHOLDERS = ['{status}', '{players}', '{max}', '{motd}', '{version}', '{address}', '{name}']

// Example values used to render the live preview so the admin sees a realistic
// message rather than raw {placeholder} tokens.
const SAMPLE = {
  status: 'Online',
  players: '42',
  max: '100',
  motd: 'A Minecraft Server',
  version: '1.21.4'
}

function defaultEmbed() {
  return {
    title: '',
    description: '',
    color: '#5865F2',
    thumbnail: '',
    image: '',
    footer: '',
    show_timestamp: false,
    author_name: '',
    author_icon_url: ''
  }
}

const props = defineProps({
  modelValue: { type: Object, required: true },
  saving: { type: Boolean, default: false },
  deleting: { type: Boolean, default: false },
  isDraft: { type: Boolean, default: false },
  guildId: { type: String, default: '' }
})

defineEmits(['save', 'delete', 'cancel'])

function hydrate(src) {
  return {
    id: src.id ?? null,
    name: src.name || '',
    address: src.address || '',
    edition: src.edition === 'bedrock' ? 'bedrock' : 'java',
    channel_id: src.channel_id || '',
    notify_mode: src.notify_mode === 'embed' ? 'embed' : 'plain',
    message_template: src.message_template || '',
    embed: { ...defaultEmbed(), ...(src.embed && typeof src.embed === 'object' ? src.embed : {}) },
    enabled: src.enabled !== undefined ? !!src.enabled : true,
    // Bot-maintained, read-only fields kept around for the header status pill.
    status: src.status || 'unknown'
  }
}

const local = reactive(hydrate(props.modelValue))

// Saved servers start collapsed for a tidy list; new drafts open for editing.
const collapsed = ref(!props.isDraft)

const tplRef = ref(null)
let initial = JSON.stringify(local)

const rowKey = computed(() => local.id || 'draft')
const dirty = computed(() => JSON.stringify(local) !== initial)

const statusLabel = computed(() => {
  if (props.isDraft) return ''
  const s = local.status || 'unknown'
  if (s === 'online') return t('minecraft.statusOnline')
  if (s === 'offline') return t('minecraft.statusOffline')
  return t('minecraft.statusUnknown')
})

function fillSample(raw) {
  if (typeof raw !== 'string' || !raw) return raw
  return raw
    .replace(/\{status\}/g, SAMPLE.status)
    .replace(/\{players\}/g, SAMPLE.players)
    .replace(/\{max\}/g, SAMPLE.max)
    .replace(/\{motd\}/g, SAMPLE.motd)
    .replace(/\{version\}/g, SAMPLE.version)
    .replace(/\{address\}/g, local.address || 'mc.example.net')
    .replace(/\{name\}/g, local.name || local.address || 'My Server')
}

const previewMessage = computed(() => {
  const raw = local.message_template || `**${local.name || local.address || 'My Server'}** is {status} — {players}/{max} players on {version}.`
  return fillSample(raw)
})

const previewEmbed = computed(() => {
  const e = local.embed || defaultEmbed()
  return {
    ...e,
    title: fillSample(e.title || `${local.name || local.address || 'My Server'}`),
    description: fillSample(e.description || 'Status: {status}\nPlayers: {players}/{max}\nVersion: {version}\nMOTD: {motd}'),
    footer: fillSample(e.footer || ''),
    author_name: fillSample(e.author_name || '')
  }
})

function cloneLocal() {
  return { ...local, embed: { ...local.embed } }
}

// Re-baseline when the parent swaps the row in (e.g. after a save).
watch(() => props.modelValue, (next) => {
  if (!next) return
  Object.assign(local, hydrate(next))
  initial = JSON.stringify(local)
}, { deep: true })

async function insertPlaceholder(token) {
  const el = tplRef.value
  const { value, caret } = insertAtCaret(el, local.message_template, token)
  local.message_template = value
  await nextTick()
  if (el) {
    el.focus()
    try { el.setSelectionRange(caret, caret) } catch { /* ignore */ }
  }
}
</script>

<style scoped>
.form-card {
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  box-shadow: var(--shadow-inset);
}

.mc-row.is-draft {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-inset);
}

.mc-row__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  cursor: pointer;
}

.mc-row__title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  flex-wrap: wrap;
}

.mc-row__collapse {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  color: var(--color-text-soft);
  border-radius: var(--radius-sm);
  transition: color var(--transition), background var(--transition), transform var(--transition);
}
.mc-row__collapse:hover { color: var(--color-primary); background: var(--color-surface-2); }
.mc-row__collapse.is-collapsed { transform: rotate(-90deg); }

.mc-row__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-warning);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18);
}

.mc-row__badge {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 700;
  color: #fff;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  background: var(--color-text-soft);
}
.mc-row__badge--java { background: linear-gradient(135deg, #8b6f4e, #b08d57); }
.mc-row__badge--bedrock { background: linear-gradient(135deg, #10b981, #34d399); color: #06210a; }

.mc-row__name {
  font-weight: 600;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 24ch;
}

.mc-row__status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  color: var(--color-text-soft);
  background: var(--color-surface-2);
}
.mc-row__status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--color-text-soft); }
.mc-row__status--online { color: var(--color-success); background: rgba(34, 197, 94, 0.12); }
.mc-row__status--online .mc-row__status-dot { background: var(--color-success); }
.mc-row__status--offline { color: var(--color-danger); background: rgba(239, 68, 68, 0.12); }
.mc-row__status--offline .mc-row__status-dot { background: var(--color-danger); }

.mc-row__head-actions { display: inline-flex; align-items: center; gap: var(--space-3); }
.mc-row__enabled-label { font-size: 0.82rem; color: var(--color-text-muted); }

.mc-row__body { display: flex; flex-direction: column; gap: var(--space-4); }

/* Fields left, live preview right (sticky) — like the welcome/leave pages. */
.mc-row__split {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: var(--space-5);
  align-items: flex-start;
}
.mc-row__fields { display: flex; flex-direction: column; gap: var(--space-4); min-width: 0; }
.mc-row__preview-col { position: sticky; top: calc(var(--nav-height) + var(--space-6)); min-width: 0; }
@media (max-width: 900px) {
  .mc-row__split { grid-template-columns: 1fr; }
  .mc-row__preview-col { position: static; }
}

.mc-row__grid { display: grid; grid-template-columns: 1.4fr 0.8fr; gap: var(--space-4); }

.mc-row__mode {
  display: inline-flex;
  gap: 4px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  padding: 3px;
  width: fit-content;
}
.mc-row__mode-btn { padding: 0.45rem 0.9rem; border-radius: var(--radius-sm); font-size: 0.88rem; font-weight: 600; color: var(--color-text-muted); }
.mc-row__mode-btn.is-active { background: var(--gradient-brand); color: #fff; }

.form-row { display: flex; flex-direction: column; gap: var(--space-2); }
.form-row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.form-row__hint { font-size: 0.82rem; color: var(--color-text-muted); line-height: 1.55; }

.input {
  width: 100%;
  padding: 0.7rem 0.85rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 0.95rem;
  transition: border-color var(--transition), box-shadow var(--transition);
}
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.input--mono { font-family: var(--font-mono); letter-spacing: 0.02em; }
.input--textarea { resize: vertical; min-height: 80px; line-height: 1.55; }

select.input {
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6' fill='none' stroke='%2399a' stroke-width='2'%3E%3Cpolyline points='1 1 5 5 9 1'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.9rem center;
  padding-right: 2rem;
}

.placeholder-bar { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
.placeholder-bar__chip {
  padding: 0.3rem 0.55rem;
  background: var(--color-surface-2);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 0.74rem;
  color: var(--color-accent);
  cursor: pointer;
  transition: border-color var(--transition), background var(--transition);
}
.placeholder-bar__chip:hover { border-color: var(--color-primary); background: var(--color-surface-3); }
.placeholder-bar__chip--static { cursor: default; }
.placeholder-bar__chip--static:hover { border-color: var(--color-border-strong); background: var(--color-surface-2); }

.mc-row__actions { display: flex; justify-content: flex-end; gap: var(--space-3); }

.mc-preview__label { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-text-soft); margin-bottom: var(--space-2); }

/* Status badge mock rendered inside the preview bubble. */
.mc-status-mock {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 4px 10px;
  border-radius: 4px;
  background: #1e1f22;
  border: 1px solid #2b2d31;
  color: #b5bac1;
  font-size: 0.8rem;
}
.mc-status-mock__dot { width: 8px; height: 8px; border-radius: 50%; background: #23a55a; box-shadow: 0 0 0 3px rgba(35, 165, 90, 0.2); }
.mc-status-mock__text { font-weight: 600; color: #dbdee1; }
.mc-status-mock__sep { color: #5a5e69; }
.mc-status-mock__version { color: #949ba4; }

@media (max-width: 640px) {
  .mc-row__grid { grid-template-columns: 1fr; }
}
</style>
