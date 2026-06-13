<template>
  <div ref="rootEl" class="rs" :class="{ 'is-open': open, 'is-disabled': isDisabled }">
    <button
      type="button"
      class="rs__trigger"
      :class="{ 'is-empty': !selectedChannel && !hasRawValue }"
      :disabled="isDisabled"
      :aria-expanded="open ? 'true' : 'false'"
      :aria-haspopup="'listbox'"
      @click="toggle"
    >
      <span class="rs__trigger-content">
        <template v-if="selectedChannel">
          <span class="rs__icon" v-html="iconFor(selectedChannel.type)" aria-hidden="true"></span>
          <span class="rs__label">{{ selectedChannel.name }}</span>
        </template>
        <template v-else-if="hasRawValue">
          <span class="rs__icon rs__icon--unknown" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </span>
          <span class="rs__label rs__label--unknown" :title="t('resourceSelector.unknownChannel')">{{ modelValue }}</span>
          <span class="rs__badge">{{ t('resourceSelector.unknownChannel') }}</span>
        </template>
        <template v-else>
          <span class="rs__placeholder">{{ resolvedPlaceholder }}</span>
        </template>
      </span>

      <span class="rs__trigger-actions">
        <button
          v-if="allowClear && (selectedChannel || hasRawValue) && !isDisabled"
          type="button"
          class="rs__clear"
          :aria-label="t('resourceSelector.clear')"
          @click.stop="clear"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
        <svg class="rs__chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </span>
    </button>

    <transition name="rs-menu">
      <div v-if="open" class="rs__panel" role="listbox">
        <div class="rs__panel-head">
          <div class="rs__search">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              ref="searchEl"
              v-model="query"
              type="text"
              class="rs__search-input"
              :placeholder="t('resourceSelector.searchChannels')"
              @keydown="onKeydown"
            />
          </div>
          <button type="button" class="rs__refresh" :disabled="loading" @click="refresh">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10"/><path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14"/>
            </svg>
            {{ t('resourceSelector.refresh') }}
          </button>
        </div>

        <div class="rs__list" role="presentation">
          <div v-if="loading && !hasAnyData" class="rs__state">
            {{ t('resourceSelector.loading') }}
          </div>
          <div v-else-if="error && !hasAnyData" class="rs__state rs__state--error">
            {{ t('resourceSelector.error') }}
          </div>
          <div v-else-if="!hasAnyData" class="rs__state">
            <div>{{ t('resourceSelector.emptyChannels') }}</div>
            <div class="rs__state-hint">{{ t('resourceSelector.emptyChannelsHint') }}</div>
          </div>
          <div v-else-if="filteredGroups.length === 0" class="rs__state">
            {{ t('resourceSelector.noMatch') }}
          </div>
          <template v-else>
            <template v-for="(group, gi) in filteredGroups" :key="group.key">
              <div v-if="group.label" class="rs__group-header">
                <span class="rs__icon" v-html="iconFor('category')" aria-hidden="true"></span>
                <span>{{ group.label }}</span>
              </div>
              <button
                v-for="(channel, ci) in group.channels"
                :key="channel.id"
                ref="itemEls"
                type="button"
                class="rs__item"
                :class="{
                  'is-selected': channel.id === modelValue,
                  'is-focused': focusedIndex === absoluteIndex(gi, ci)
                }"
                role="option"
                :aria-selected="channel.id === modelValue ? 'true' : 'false'"
                @click="select(channel)"
                @mouseenter="focusedIndex = absoluteIndex(gi, ci)"
              >
                <span class="rs__icon" v-html="iconFor(channel.type)" aria-hidden="true"></span>
                <span class="rs__item-label">{{ channel.name }}</span>
                <svg v-if="channel.id === modelValue" class="rs__check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </button>
            </template>
          </template>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useGuildResources } from '../composables/useGuildResources.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()

const props = defineProps({
  modelValue: { type: [String, null], default: '' },
  guildId: { type: String, default: '' },
  types: { type: Array, default: () => ['text'] },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  allowClear: { type: Boolean, default: true }
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const query = ref('')
const focusedIndex = ref(-1)
const rootEl = ref(null)
const searchEl = ref(null)
const itemEls = ref([])

const resources = computed(() => useGuildResources(props.guildId))

const channels = computed(() => resources.value.state.channels || [])
const loading = computed(() => !!resources.value.state.channelsLoading)
const error = computed(() => resources.value.state.channelsError)

const isDisabled = computed(() => props.disabled || !props.guildId)
const hasRawValue = computed(() => !!props.modelValue && !selectedChannel.value)

const resolvedPlaceholder = computed(() => props.placeholder || t('resourceSelector.channelPlaceholder'))

const selectedChannel = computed(() => {
  if (!props.modelValue) return null
  return channels.value.find(c => c.id === props.modelValue) || null
})

const acceptedTypes = computed(() => {
  const arr = Array.isArray(props.types) ? props.types : ['text']
  return new Set(arr)
})

const showAll = computed(() => acceptedTypes.value.has('all'))

function passesType(channel) {
  if (showAll.value) return true
  return acceptedTypes.value.has(channel.type)
}

// Build category groupings. The API already returns categories first and the
// children sorted underneath, so we honour that order.
const filteredGroups = computed(() => {
  const q = query.value.trim().toLowerCase()
  const list = channels.value
  if (!list.length) return []

  // Map of categoryId -> {label, channels: []}
  const categoryNames = new Map()
  for (const ch of list) {
    if (ch.type === 'category') categoryNames.set(ch.id, ch.name)
  }

  const groups = new Map()
  const ungrouped = { key: '__ungrouped__', label: '', channels: [] }

  function getGroup(parentId) {
    const label = parentId && categoryNames.get(parentId)
    if (!label) return ungrouped
    if (!groups.has(parentId)) {
      groups.set(parentId, { key: parentId, label, channels: [] })
    }
    return groups.get(parentId)
  }

  for (const ch of list) {
    // Categories themselves only render as group headers, unless
    // 'category' was explicitly requested as a selectable type.
    if (ch.type === 'category' && !acceptedTypes.value.has('category') && !showAll.value) {
      continue
    }
    if (!passesType(ch)) continue
    if (q && !ch.name.toLowerCase().includes(q)) continue

    if (ch.type === 'category' && (acceptedTypes.value.has('category') || showAll.value)) {
      // A selectable category goes in the ungrouped bucket so it's still
      // listed, but the panel header is still rendered above its children.
      ungrouped.channels.push(ch)
      continue
    }

    const group = getGroup(ch.parent_id)
    group.channels.push(ch)
  }

  const out = []
  if (ungrouped.channels.length) out.push(ungrouped)
  for (const g of groups.values()) {
    if (g.channels.length) out.push(g)
  }
  return out
})

const flatItems = computed(() => {
  const out = []
  for (const g of filteredGroups.value) {
    for (const c of g.channels) out.push(c)
  }
  return out
})

const hasAnyData = computed(() => channels.value.length > 0)

function absoluteIndex(gi, ci) {
  let idx = 0
  for (let i = 0; i < gi; i++) idx += filteredGroups.value[i].channels.length
  return idx + ci
}

function iconFor(type) {
  // Discord-style outline glyphs. 14px stroke icons that mirror the look of
  // the navigation/sidebar SVGs.
  switch (type) {
    case 'text':
      return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>'
    case 'voice':
      return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>'
    case 'category':
      return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>'
    case 'announcement':
      return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l18-7v16l-18-7v-2z"/><path d="M9 13v6"/></svg>'
    case 'thread':
      return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16"/><path d="M7 12h13"/><path d="M10 18h10"/></svg>'
    case 'stage':
      return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="3"/><path d="M4 20a8 8 0 0 1 16 0"/></svg>'
    case 'forum':
      return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-9 8.5 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.2A8.5 8.5 0 1 1 21 11.5z"/></svg>'
    default:
      return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>'
  }
}

async function openPanel() {
  if (isDisabled.value) return
  open.value = true
  // Kick off a (possibly background) load.
  resources.value.loadChannels()
  await nextTick()
  searchEl.value?.focus()
  // Move focus index onto current selection if visible
  const idx = flatItems.value.findIndex(c => c.id === props.modelValue)
  focusedIndex.value = idx >= 0 ? idx : (flatItems.value.length ? 0 : -1)
}

function closePanel() {
  open.value = false
  query.value = ''
  focusedIndex.value = -1
}

function toggle() {
  if (open.value) closePanel()
  else openPanel()
}

function select(channel) {
  emit('update:modelValue', channel.id)
  closePanel()
}

function clear() {
  emit('update:modelValue', '')
}

function refresh() {
  resources.value.loadChannels(true)
}

function onKeydown(e) {
  if (e.key === 'Escape') {
    e.preventDefault()
    closePanel()
    return
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    if (!flatItems.value.length) return
    focusedIndex.value = (focusedIndex.value + 1) % flatItems.value.length
    return
  }
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (!flatItems.value.length) return
    focusedIndex.value = (focusedIndex.value - 1 + flatItems.value.length) % flatItems.value.length
    return
  }
  if (e.key === 'Enter') {
    e.preventDefault()
    const item = flatItems.value[focusedIndex.value]
    if (item) select(item)
  }
}

function onDocClick(e) {
  if (!open.value) return
  if (rootEl.value && !rootEl.value.contains(e.target)) closePanel()
}

function onDocKeydown(e) {
  if (open.value && e.key === 'Escape') closePanel()
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onDocKeydown)
  // Pre-load channels in the background so the trigger shows the resolved
  // name immediately when the page hydrates a saved value.
  if (props.guildId) resources.value.loadChannels()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onDocKeydown)
})

// Re-fetch when guildId changes.
watch(() => props.guildId, (id) => {
  if (id) resources.value.loadChannels()
})

// Reset query when closing.
watch(open, (v) => {
  if (!v) query.value = ''
})
</script>

<style scoped>
.rs {
  position: relative;
  width: 100%;
}

.rs__trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  width: 100%;
  padding: 0.7rem 0.85rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 0.95rem;
  text-align: left;
  cursor: pointer;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.rs__trigger:hover:not(:disabled) {
  border-color: var(--color-border-strong);
}

.rs.is-open .rs__trigger,
.rs__trigger:focus-visible {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.rs__trigger:disabled {
  background: var(--color-surface);
  cursor: not-allowed;
  opacity: 0.7;
}

.rs__trigger-content {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  flex: 1;
}

.rs__trigger-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.rs__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-soft);
  flex-shrink: 0;
  line-height: 0;
}

.rs__icon--unknown {
  color: var(--color-warning);
}

.rs__label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rs__label--unknown {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: var(--color-text-soft);
}

.rs__badge {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  background: var(--color-warning-soft);
  color: var(--color-warning);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}

.rs__placeholder {
  color: var(--color-text-soft);
}

.rs__chev {
  color: var(--color-text-soft);
  transition: transform var(--transition);
}

.rs.is-open .rs__chev {
  transform: rotate(180deg);
}

.rs__clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: var(--radius-full);
  color: var(--color-text-muted);
  background: transparent;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.rs__clear:hover {
  background: rgba(239, 68, 68, 0.18);
  color: var(--color-danger);
}

.rs__panel {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: 60;
  background: rgba(22, 26, 35, 0.98);
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: var(--space-2);
  max-height: 320px;
  display: flex;
  flex-direction: column;
}

.rs__panel-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-bottom: 1px solid var(--color-border);
  margin-bottom: var(--space-2);
}

.rs__search {
  flex: 1;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0.4rem 0.5rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-soft);
}

.rs__search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 0.88rem;
  padding: 0;
}

.rs__search-input::placeholder {
  color: var(--color-text-soft);
}

.rs__refresh {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0.35rem 0.55rem;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  color: var(--color-text-soft);
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.rs__refresh:hover:not(:disabled) {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.rs__refresh:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.rs__list {
  overflow-y: auto;
  flex: 1;
  padding-right: 2px;
}

.rs__group-header {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3) 4px;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-soft);
  font-weight: 600;
  width: 100%;
}

.rs__item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: 0.5rem var(--space-3);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-size: 0.9rem;
  cursor: pointer;
  text-align: left;
  transition: background var(--transition-fast);
}

.rs__item:hover,
.rs__item.is-focused {
  background: var(--color-surface-2);
}

.rs__item.is-selected {
  background: var(--color-primary-soft);
  color: #fff;
}

.rs__item-label {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rs__check {
  color: #fff;
  flex-shrink: 0;
}

.rs__state {
  padding: var(--space-4) var(--space-3);
  color: var(--color-text-muted);
  font-size: 0.86rem;
  text-align: center;
}

.rs__state-hint {
  margin-top: var(--space-1);
  font-size: 0.78rem;
  color: var(--color-text-soft);
}

.rs__state--error {
  color: var(--color-danger);
}

.rs-menu-enter-active,
.rs-menu-leave-active {
  transition: opacity 140ms ease, transform 140ms ease;
}

.rs-menu-enter-from,
.rs-menu-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
