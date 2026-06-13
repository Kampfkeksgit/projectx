<template>
  <div ref="rootEl" class="rs" :class="{ 'is-open': open, 'is-disabled': isDisabled, 'is-multi': multiple }">
    <button
      type="button"
      class="rs__trigger"
      :class="{ 'is-empty': isEmpty }"
      :disabled="isDisabled"
      :aria-expanded="open ? 'true' : 'false'"
      :aria-haspopup="'listbox'"
      @click="toggle"
    >
      <span class="rs__trigger-content">
        <template v-if="!multiple">
          <template v-if="selectedRole">
            <span class="rs__dot" :style="{ background: dotColor(selectedRole) }" aria-hidden="true"></span>
            <span class="rs__label">{{ selectedRole.name }}</span>
          </template>
          <template v-else-if="hasRawSingle">
            <span class="rs__icon rs__icon--unknown" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            </span>
            <span class="rs__label rs__label--unknown" :title="t('resourceSelector.unknownRole')">{{ modelValue }}</span>
            <span class="rs__badge">{{ t('resourceSelector.unknownRole') }}</span>
          </template>
          <template v-else>
            <span class="rs__placeholder">{{ resolvedPlaceholder }}</span>
          </template>
        </template>

        <template v-else>
          <template v-if="multiSelectedItems.length === 0">
            <span class="rs__placeholder">{{ resolvedPlaceholder }}</span>
          </template>
          <template v-else>
            <span
              v-for="item in multiSelectedItems"
              :key="item.id"
              class="rs__chip"
              :class="{ 'rs__chip--unknown': !item.role }"
            >
              <span class="rs__dot" :style="{ background: item.role ? dotColor(item.role) : 'var(--color-warning)' }" aria-hidden="true"></span>
              <span class="rs__chip-label" :class="{ 'rs__chip-label--mono': !item.role }">
                {{ item.role ? item.role.name : item.id }}
              </span>
              <button
                v-if="!isDisabled"
                type="button"
                class="rs__chip-remove"
                :aria-label="t('resourceSelector.removeRole')"
                @click.stop="removeOne(item.id)"
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </span>
          </template>
        </template>
      </span>

      <span class="rs__trigger-actions">
        <button
          v-if="allowClear && !isEmpty && !isDisabled"
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
              :placeholder="t('resourceSelector.searchRoles')"
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
            <div>{{ t('resourceSelector.emptyRoles') }}</div>
            <div class="rs__state-hint">{{ t('resourceSelector.emptyRolesHint') }}</div>
          </div>
          <div v-else-if="filteredRoles.length === 0" class="rs__state">
            {{ t('resourceSelector.noMatch') }}
          </div>
          <template v-else>
            <button
              v-for="(role, i) in filteredRoles"
              :key="role.id"
              type="button"
              class="rs__item"
              :class="{ 'is-selected': isSelected(role.id), 'is-focused': focusedIndex === i }"
              role="option"
              :aria-selected="isSelected(role.id) ? 'true' : 'false'"
              @click="toggleOne(role)"
              @mouseenter="focusedIndex = i"
            >
              <span v-if="multiple" class="rs__check-box" :class="{ 'is-checked': isSelected(role.id) }" aria-hidden="true">
                <svg v-if="isSelected(role.id)" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              </span>
              <span class="rs__dot" :style="{ background: dotColor(role) }" aria-hidden="true"></span>
              <span class="rs__item-label">{{ role.name }}</span>
              <span v-if="role.managed" class="rs__role-badge">{{ t('resourceSelector.managedRole') }}</span>
              <span v-if="role.is_default" class="rs__role-badge">{{ t('resourceSelector.defaultRole') }}</span>
              <svg v-if="!multiple && isSelected(role.id)" class="rs__check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            </button>
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
  modelValue: { type: [String, Array, null], default: '' },
  guildId: { type: String, default: '' },
  multiple: { type: Boolean, default: false },
  excludeManaged: { type: Boolean, default: true },
  excludeDefault: { type: Boolean, default: true },
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

const resources = computed(() => useGuildResources(props.guildId))
const roles = computed(() => resources.value.state.roles || [])
const loading = computed(() => !!resources.value.state.rolesLoading)
const error = computed(() => resources.value.state.rolesError)

const isDisabled = computed(() => props.disabled || !props.guildId)

const resolvedPlaceholder = computed(() => {
  if (props.placeholder) return props.placeholder
  return props.multiple
    ? t('resourceSelector.rolesPlaceholder')
    : t('resourceSelector.rolePlaceholder')
})

// Normalised multi value (always an array when multiple is true).
const multiValue = computed(() => {
  if (!props.multiple) return []
  if (Array.isArray(props.modelValue)) return props.modelValue.filter(Boolean)
  if (typeof props.modelValue === 'string' && props.modelValue) return [props.modelValue]
  return []
})

const selectedRole = computed(() => {
  if (props.multiple) return null
  if (!props.modelValue) return null
  return roles.value.find(r => r.id === props.modelValue) || null
})

const hasRawSingle = computed(() => {
  return !props.multiple && !!props.modelValue && !selectedRole.value
})

const isEmpty = computed(() => {
  if (props.multiple) return multiValue.value.length === 0
  return !props.modelValue
})

const multiSelectedItems = computed(() => {
  return multiValue.value.map(id => ({
    id,
    role: roles.value.find(r => r.id === id) || null
  }))
})

const filteredRoles = computed(() => {
  const q = query.value.trim().toLowerCase()
  return roles.value.filter(r => {
    if (props.excludeManaged && r.managed) return false
    if (props.excludeDefault && r.is_default) return false
    if (q && !r.name.toLowerCase().includes(q)) return false
    return true
  })
})

const hasAnyData = computed(() => roles.value.length > 0)

function dotColor(role) {
  if (!role) return 'var(--color-text-soft)'
  if (!role.color || role.color === 0) return 'var(--color-text-soft)'
  const hex = role.color.toString(16).padStart(6, '0')
  return `#${hex}`
}

function isSelected(id) {
  if (props.multiple) return multiValue.value.includes(id)
  return props.modelValue === id
}

async function openPanel() {
  if (isDisabled.value) return
  open.value = true
  resources.value.loadRoles()
  await nextTick()
  searchEl.value?.focus()
  if (props.multiple) {
    focusedIndex.value = filteredRoles.value.length ? 0 : -1
  } else {
    const idx = filteredRoles.value.findIndex(r => r.id === props.modelValue)
    focusedIndex.value = idx >= 0 ? idx : (filteredRoles.value.length ? 0 : -1)
  }
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

function toggleOne(role) {
  if (props.multiple) {
    const arr = multiValue.value.slice()
    const idx = arr.indexOf(role.id)
    if (idx >= 0) arr.splice(idx, 1)
    else arr.push(role.id)
    emit('update:modelValue', arr)
  } else {
    emit('update:modelValue', role.id)
    closePanel()
  }
}

function removeOne(id) {
  if (!props.multiple) return
  const arr = multiValue.value.filter(v => v !== id)
  emit('update:modelValue', arr)
}

function clear() {
  if (props.multiple) emit('update:modelValue', [])
  else emit('update:modelValue', '')
}

function refresh() {
  resources.value.loadRoles(true)
}

function onKeydown(e) {
  if (e.key === 'Escape') {
    e.preventDefault()
    closePanel()
    return
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    if (!filteredRoles.value.length) return
    focusedIndex.value = (focusedIndex.value + 1) % filteredRoles.value.length
    return
  }
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (!filteredRoles.value.length) return
    focusedIndex.value = (focusedIndex.value - 1 + filteredRoles.value.length) % filteredRoles.value.length
    return
  }
  if (e.key === 'Enter') {
    e.preventDefault()
    const item = filteredRoles.value[focusedIndex.value]
    if (item) toggleOne(item)
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
  if (props.guildId) resources.value.loadRoles()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onDocKeydown)
})

watch(() => props.guildId, (id) => {
  if (id) resources.value.loadRoles()
})

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
  min-height: 44px;
  padding: 0.55rem 0.75rem;
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
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  flex: 1;
  flex-wrap: wrap;
}

.rs__trigger-actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.rs__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.25) inset;
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

.rs__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0.2rem 0.4rem 0.2rem 0.55rem;
  background: var(--color-primary-soft);
  border: 1px solid rgba(88, 101, 242, 0.35);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  font-size: 0.85rem;
  line-height: 1.2;
  max-width: 100%;
}

.rs__chip--unknown {
  background: var(--color-warning-soft);
  border-color: rgba(245, 158, 11, 0.35);
}

.rs__chip-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 22ch;
}

.rs__chip-label--mono {
  font-family: var(--font-mono);
  font-size: 0.78rem;
}

.rs__chip-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: var(--radius-full);
  color: var(--color-text-muted);
  background: transparent;
  transition: background var(--transition-fast), color var(--transition-fast);
  flex-shrink: 0;
}

.rs__chip-remove:hover {
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

.rs__check-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border: 1.5px solid var(--color-border-strong);
  border-radius: 4px;
  background: var(--color-bg-elevated);
  color: #fff;
  flex-shrink: 0;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.rs__check-box.is-checked {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.rs__role-badge {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  background: var(--color-surface-3);
  color: var(--color-text-soft);
  padding: 1px 5px;
  border-radius: var(--radius-sm);
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
