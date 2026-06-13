<template>
  <div class="embed-editor" :class="{ 'is-disabled': disabled }">
    <!-- Color + Title -->
    <div class="ee-section">
      <div class="ee-grid ee-grid--split">
        <div class="ee-field">
          <label class="ee-label" :for="titleId">{{ t('embedEditor.titleLabel') }}</label>
          <div class="ee-hint">{{ t('embedEditor.titleHint') }}</div>
          <div class="ee-input-row">
            <input
              :id="titleId"
              class="ee-input"
              type="text"
              maxlength="256"
              :disabled="disabled"
              :value="model.title"
              @input="patch({ title: $event.target.value })"
            />
            <span class="ee-counter">{{ t('embedEditor.descCounter', { used: (model.title || '').length, max: 256 }) }}</span>
          </div>
        </div>
        <div class="ee-field">
          <label class="ee-label" :for="colorId">{{ t('embedEditor.colorLabel') }}</label>
          <div class="ee-hint">{{ t('embedEditor.colorHint') }}</div>
          <div class="ee-color-row">
            <span class="ee-color-swatch" :style="{ background: validColor(model.color) }">
              <input
                :id="colorId"
                type="color"
                class="ee-color-native"
                :disabled="disabled"
                :value="validColor(model.color)"
                @input="patch({ color: $event.target.value.toUpperCase() })"
              />
            </span>
            <input
              class="ee-input ee-input--hex"
              type="text"
              :disabled="disabled"
              :value="hexDraft"
              maxlength="7"
              spellcheck="false"
              @input="onHexInput"
              @blur="onHexBlur"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="ee-divider"></div>

    <!-- Description + placeholders -->
    <div class="ee-section">
      <div class="ee-field">
        <label class="ee-label" :for="descId">{{ t('embedEditor.descLabel') }}</label>
        <div class="ee-hint">{{ t('embedEditor.descHint') }}</div>
        <textarea
          :id="descId"
          ref="descRef"
          class="ee-input ee-input--textarea"
          rows="5"
          maxlength="4096"
          :disabled="disabled"
          :value="model.description"
          @input="patch({ description: $event.target.value })"
        ></textarea>
        <div class="ee-row-between">
          <button type="button" class="ee-toggle-btn" :disabled="disabled" @click="placeholdersOpen = !placeholdersOpen">
            <span class="ee-chev" :class="{ 'is-open': placeholdersOpen }">▸</span>
            {{ t('embedEditor.placeholdersHeading') }}
          </button>
          <span class="ee-counter">{{ t('embedEditor.descCounter', { used: (model.description || '').length, max: 4096 }) }}</span>
        </div>
        <div v-if="placeholdersOpen" class="ee-placeholders">
          <p class="ee-placeholders__intro">{{ t('embedEditor.placeholdersIntro') }}</p>
          <div class="ee-placeholders__grid">
            <button
              v-for="ph in PLACEHOLDERS"
              :key="ph.token"
              type="button"
              class="ee-ph-chip"
              :disabled="disabled"
              :title="t(`embedEditor.${ph.labelKey}`)"
              @click="insertPlaceholder(ph.token)"
            >
              <code>{{ ph.token }}</code>
              <span class="ee-ph-chip__label">{{ t(`embedEditor.${ph.labelKey}`) }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="ee-divider"></div>

    <!-- Author -->
    <div class="ee-section">
      <h4 class="ee-section-title">{{ t('embedEditor.authorSection') }}</h4>
      <div class="ee-grid ee-grid--split">
        <div class="ee-field">
          <label class="ee-label" :for="authorNameId">{{ t('embedEditor.authorNameLabel') }}</label>
          <input
            :id="authorNameId"
            class="ee-input"
            type="text"
            maxlength="256"
            :disabled="disabled"
            :value="model.author_name"
            @input="patch({ author_name: $event.target.value })"
          />
        </div>
        <div class="ee-field">
          <label class="ee-label" :for="authorIconId">{{ t('embedEditor.authorIconLabel') }}</label>
          <div class="ee-input-row">
            <input
              :id="authorIconId"
              class="ee-input"
              type="text"
              :disabled="disabled"
              :value="model.author_icon_url"
              placeholder="https://…"
              @input="patch({ author_icon_url: $event.target.value })"
            />
            <button
              type="button"
              class="ee-mini-btn"
              :disabled="disabled"
              @click="patch({ author_icon_url: '{user.avatar}' })"
            >
              {{ t('embedEditor.useUserAvatar') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="ee-divider"></div>

    <!-- Thumbnail + Image -->
    <div class="ee-section">
      <div class="ee-grid ee-grid--split">
        <div class="ee-field">
          <label class="ee-label" :for="thumbId">{{ t('embedEditor.thumbnailLabel') }}</label>
          <div class="ee-hint">{{ t('embedEditor.thumbnailHint') }}</div>
          <div class="ee-input-row">
            <input
              :id="thumbId"
              class="ee-input"
              type="text"
              :disabled="disabled"
              :value="model.thumbnail"
              placeholder="https://…"
              @input="patch({ thumbnail: $event.target.value })"
            />
            <button
              type="button"
              class="ee-mini-btn"
              :disabled="disabled"
              @click="patch({ thumbnail: '{user.avatar}' })"
            >
              {{ t('embedEditor.useUserAvatar') }}
            </button>
          </div>
          <div v-if="isHttpUrl(model.thumbnail)" class="ee-mini-preview">
            <img :src="model.thumbnail" alt="thumbnail" @error="onImgErr($event)" />
          </div>
        </div>
        <div class="ee-field">
          <label class="ee-label" :for="imageId">{{ t('embedEditor.imageLabel') }}</label>
          <div class="ee-hint">{{ t('embedEditor.imageHint') }}</div>
          <input
            :id="imageId"
            class="ee-input"
            type="text"
            :disabled="disabled"
            :value="model.image"
            placeholder="https://…"
            @input="patch({ image: $event.target.value })"
          />
          <div v-if="isHttpUrl(model.image)" class="ee-mini-preview ee-mini-preview--wide">
            <img :src="model.image" alt="image" @error="onImgErr($event)" />
          </div>
        </div>
      </div>
    </div>

    <div class="ee-divider"></div>

    <!-- Footer + timestamp -->
    <div class="ee-section">
      <div class="ee-grid ee-grid--split">
        <div class="ee-field">
          <label class="ee-label" :for="footerId">{{ t('embedEditor.footerLabel') }}</label>
          <div class="ee-hint">{{ t('embedEditor.footerHint') }}</div>
          <div class="ee-input-row">
            <input
              :id="footerId"
              class="ee-input"
              type="text"
              maxlength="2048"
              :disabled="disabled"
              :value="model.footer"
              @input="patch({ footer: $event.target.value })"
            />
            <span class="ee-counter">{{ t('embedEditor.descCounter', { used: (model.footer || '').length, max: 2048 }) }}</span>
          </div>
        </div>
        <div class="ee-field ee-field--row">
          <div>
            <div class="ee-label ee-label--inline">{{ t('embedEditor.timestampLabel') }}</div>
            <div class="ee-hint">{{ t('embedEditor.timestampHint') }}</div>
          </div>
          <AppToggle
            :model-value="!!model.show_timestamp"
            :disabled="disabled"
            @update:model-value="patch({ show_timestamp: $event })"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import AppToggle from './AppToggle.vue'
import { useI18n } from '../i18n/index.js'
import { PLACEHOLDERS } from './embedPlaceholders.js'

const { t } = useI18n()

const props = defineProps({
  modelValue: { type: Object, required: true },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])

// Stable IDs so labels work
const uid = Math.random().toString(36).slice(2, 8)
const titleId = `ee-title-${uid}`
const colorId = `ee-color-${uid}`
const descId = `ee-desc-${uid}`
const authorNameId = `ee-aname-${uid}`
const authorIconId = `ee-aicon-${uid}`
const thumbId = `ee-thumb-${uid}`
const imageId = `ee-image-${uid}`
const footerId = `ee-footer-${uid}`

const model = computed(() => props.modelValue || {})

const placeholdersOpen = ref(false)
const descRef = ref(null)

// Hex draft so the user can type intermediate states like '#586' without
// the value snapping back. Reverts on blur if invalid.
const hexDraft = ref('')
let suppressDraftWatcher = false

watch(
  () => props.modelValue?.color,
  (val) => {
    if (suppressDraftWatcher) {
      suppressDraftWatcher = false
      return
    }
    hexDraft.value = (val || '#5865F2').toUpperCase()
  },
  { immediate: true }
)

const HEX_RE = /^#[0-9A-Fa-f]{6}$/

function validColor(c) {
  return HEX_RE.test(c || '') ? c : '#5865F2'
}

function patch(p) {
  emit('update:modelValue', { ...model.value, ...p })
}

function onHexInput(e) {
  const v = e.target.value
  hexDraft.value = v
  if (HEX_RE.test(v)) {
    suppressDraftWatcher = true
    patch({ color: v.toUpperCase() })
  }
}

function onHexBlur() {
  if (!HEX_RE.test(hexDraft.value)) {
    hexDraft.value = (model.value.color || '#5865F2').toUpperCase()
  } else {
    hexDraft.value = hexDraft.value.toUpperCase()
  }
}

async function insertPlaceholder(token) {
  if (props.disabled) return
  const ta = descRef.value
  const current = model.value.description || ''
  let nextVal
  let nextCaret
  if (ta && document.activeElement === ta) {
    const start = ta.selectionStart ?? current.length
    const end = ta.selectionEnd ?? current.length
    nextVal = current.slice(0, start) + token + current.slice(end)
    nextCaret = start + token.length
  } else {
    nextVal = current + token
    nextCaret = nextVal.length
  }
  patch({ description: nextVal })
  await nextTick()
  if (ta) {
    ta.focus()
    try {
      ta.setSelectionRange(nextCaret, nextCaret)
    } catch {
      // setSelectionRange can throw on some input types — safe to ignore.
    }
  }
}

function isHttpUrl(s) {
  return typeof s === 'string' && /^https?:\/\//i.test(s)
}

function onImgErr(e) {
  e.target.style.display = 'none'
}

defineExpose({ PLACEHOLDERS })
</script>

<style scoped>
.embed-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.embed-editor.is-disabled {
  opacity: 0.55;
  pointer-events: none;
}

.ee-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.ee-section-title {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--color-text-soft);
  font-weight: 600;
  font-family: var(--font-sans);
  margin: 0;
}

.ee-divider {
  height: 1px;
  background: var(--color-border);
  width: 100%;
}

.ee-grid {
  display: grid;
  gap: var(--space-4);
}

.ee-grid--split {
  grid-template-columns: 1fr 1fr;
}

@media (max-width: 640px) {
  .ee-grid--split {
    grid-template-columns: 1fr;
  }
}

.ee-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.ee-field--row {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.ee-label {
  font-weight: 600;
  font-size: 0.92rem;
  color: var(--color-text);
}

.ee-label--inline {
  margin-bottom: 2px;
}

.ee-hint {
  font-size: 0.8rem;
  color: var(--color-text-muted);
  line-height: 1.5;
}

.ee-input {
  width: 100%;
  padding: 0.62rem 0.8rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-family: var(--font-sans);
  font-size: 0.92rem;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.ee-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.ee-input--textarea {
  resize: vertical;
  min-height: 110px;
  line-height: 1.5;
  font-family: var(--font-sans);
}

.ee-input--hex {
  font-family: var(--font-mono);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  width: auto;
  flex: 1;
  min-width: 0;
}

.ee-input-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.ee-input-row .ee-input {
  flex: 1;
  min-width: 0;
}

.ee-counter {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--color-text-soft);
  white-space: nowrap;
}

.ee-row-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.ee-color-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.ee-color-swatch {
  position: relative;
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-strong);
  overflow: hidden;
  flex-shrink: 0;
  cursor: pointer;
  box-shadow: var(--shadow-inset);
}

.ee-color-native {
  position: absolute;
  inset: -4px;
  width: calc(100% + 8px);
  height: calc(100% + 8px);
  border: none;
  background: transparent;
  cursor: pointer;
  opacity: 0;
}

.ee-mini-btn {
  padding: 0.45rem 0.7rem;
  background: var(--color-surface-2);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-text);
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition), border-color var(--transition);
  white-space: nowrap;
}

.ee-mini-btn:hover:not(:disabled) {
  background: var(--color-surface-3);
  border-color: var(--color-primary);
}

.ee-mini-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.ee-mini-preview {
  margin-top: var(--space-2);
  width: 80px;
  height: 80px;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--color-border);
  background: var(--color-bg-elevated);
}

.ee-mini-preview--wide {
  width: 100%;
  max-width: 240px;
  height: auto;
  aspect-ratio: 16 / 9;
}

.ee-mini-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.ee-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  background: transparent;
  color: var(--color-text-muted);
  font-size: 0.82rem;
  font-weight: 500;
  padding: 0;
}

.ee-toggle-btn:hover:not(:disabled) {
  color: var(--color-text);
}

.ee-chev {
  display: inline-block;
  transition: transform var(--transition);
  color: var(--color-text-soft);
  font-size: 0.75rem;
}

.ee-chev.is-open {
  transform: rotate(90deg);
}

.ee-placeholders {
  margin-top: var(--space-2);
  padding: var(--space-3);
  background: var(--color-surface-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.ee-placeholders__intro {
  font-size: 0.78rem;
  color: var(--color-text-muted);
  margin-bottom: var(--space-3);
}

.ee-placeholders__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--space-2);
}

.ee-ph-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 0.5rem 0.65rem;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  cursor: pointer;
  text-align: left;
  transition: border-color var(--transition), background var(--transition);
}

.ee-ph-chip:hover:not(:disabled) {
  border-color: var(--color-primary);
  background: var(--color-surface-3);
}

.ee-ph-chip:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.ee-ph-chip code {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--color-accent);
}

.ee-ph-chip__label {
  font-size: 0.72rem;
  color: var(--color-text-soft);
}
</style>
