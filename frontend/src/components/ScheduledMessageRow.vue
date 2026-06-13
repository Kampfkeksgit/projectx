<template>
  <div class="form-card sch-row" :class="{ 'is-draft': isDraft }">
    <div class="sch-row__head">
      <div class="sch-row__title">
        <span v-if="dirty" class="sch-row__dot" :title="t('scheduled.unsavedDot')" aria-hidden="true"></span>
        <span class="sch-row__badge">{{ local.schedule_type === 'interval' ? t('scheduled.typeInterval') : t('scheduled.typeOnce') }}</span>
        <span class="sch-row__preview">{{ (local.content || t('scheduled.contentPlaceholder')).slice(0, 48) }}</span>
      </div>
      <div class="sch-row__head-actions">
        <span class="sch-row__enabled-label">{{ t('scheduled.enabledLabel') }}</span>
        <AppToggle v-model="local.enabled" />
      </div>
    </div>

    <div class="form-row">
      <label class="form-row__label">{{ t('scheduled.channelLabel') }}</label>
      <ChannelSelector v-model="local.channel_id" :guild-id="guildId" :types="['text', 'announcement']" />
    </div>

    <div class="form-row">
      <label class="form-row__label" :for="`sch-content-${rowKey}`">{{ t('scheduled.contentLabel') }}</label>
      <textarea :id="`sch-content-${rowKey}`" v-model="local.content" class="input input--textarea" rows="3" maxlength="2000" :placeholder="t('scheduled.contentPlaceholder')"></textarea>
    </div>

    <div class="form-row">
      <label class="form-row__label">{{ t('scheduled.typeLabel') }}</label>
      <div class="sch-row__mode">
        <button type="button" class="sch-row__mode-btn" :class="{ 'is-active': local.schedule_type === 'once' }" @click="local.schedule_type = 'once'">{{ t('scheduled.typeOnce') }}</button>
        <button type="button" class="sch-row__mode-btn" :class="{ 'is-active': local.schedule_type === 'interval' }" @click="local.schedule_type = 'interval'">{{ t('scheduled.typeInterval') }}</button>
      </div>
    </div>

    <div v-if="local.schedule_type === 'once'" class="form-row">
      <label class="form-row__label" :for="`sch-once-${rowKey}`">{{ t('scheduled.whenLabel') }}</label>
      <input :id="`sch-once-${rowKey}`" v-model="local.onceLocal" class="input input--narrow" type="datetime-local" />
    </div>
    <div v-else class="form-row">
      <label class="form-row__label" :for="`sch-int-${rowKey}`">{{ t('scheduled.everyLabel') }}</label>
      <input :id="`sch-int-${rowKey}`" v-model.number="local.intervalMinutes" class="input input--narrow" type="number" min="1" max="525600" />
      <div class="form-row__hint">{{ t('scheduled.everyHint') }}</div>
    </div>

    <div class="sch-row__actions">
      <AppButton v-if="!isDraft" variant="danger" :loading="deleting" @click="$emit('delete', local)">{{ t('scheduled.delete') }}</AppButton>
      <AppButton v-if="isDraft" variant="ghost" :disabled="saving" @click="$emit('cancel')">{{ t('scheduled.cancel') }}</AppButton>
      <AppButton variant="gradient" :loading="saving" :disabled="!isDraft && !dirty" @click="emitSave">{{ t('scheduled.save') }}</AppButton>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import AppButton from './AppButton.vue'
import AppToggle from './AppToggle.vue'
import ChannelSelector from './ChannelSelector.vue'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()

const props = defineProps({
  modelValue: { type: Object, required: true },
  saving: { type: Boolean, default: false },
  deleting: { type: Boolean, default: false },
  isDraft: { type: Boolean, default: false },
  guildId: { type: String, default: '' }
})
const emit = defineEmits(['save', 'delete', 'cancel'])

function toLocalInput(unix) {
  if (!unix) return ''
  const d = new Date(unix * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function hydrate(src) {
  const type = src.schedule_type === 'interval' ? 'interval' : 'once'
  return {
    id: src.id ?? null,
    channel_id: src.channel_id || '',
    content: src.content || '',
    schedule_type: type,
    enabled: src.enabled !== undefined ? !!src.enabled : true,
    onceLocal: type === 'once' ? toLocalInput(src.run_at) : '',
    intervalMinutes: type === 'interval' && src.interval_seconds ? Math.round(src.interval_seconds / 60) : 60
  }
}

const local = reactive(hydrate(props.modelValue))
let initial = JSON.stringify(local)
const rowKey = computed(() => local.id || 'draft')
const dirty = computed(() => JSON.stringify(local) !== initial)

watch(() => props.modelValue, (next) => {
  if (!next) return
  Object.assign(local, hydrate(next))
  initial = JSON.stringify(local)
}, { deep: true })

function emitSave() {
  const nowSec = Math.floor(Date.now() / 1000)
  let run_at = 0
  let interval_seconds = 0
  if (local.schedule_type === 'interval') {
    interval_seconds = Math.max(60, (local.intervalMinutes || 1) * 60)
    run_at = nowSec + interval_seconds
  } else {
    run_at = local.onceLocal ? Math.floor(new Date(local.onceLocal).getTime() / 1000) : 0
  }
  emit('save', {
    id: local.id,
    channel_id: local.channel_id,
    content: local.content,
    schedule_type: local.schedule_type,
    enabled: local.enabled,
    run_at,
    interval_seconds
  })
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
.sch-row.is-draft { border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft), var(--shadow-inset); }
.sch-row__head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; }
.sch-row__title { display: inline-flex; align-items: center; gap: var(--space-2); min-width: 0; flex-wrap: wrap; }
.sch-row__dot { width: 8px; height: 8px; border-radius: 50%; background: var(--color-warning); box-shadow: 0 0 0 3px rgba(245,158,11,0.18); }
.sch-row__badge { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; color: #fff; padding: 2px 8px; border-radius: var(--radius-sm); background: linear-gradient(135deg, #6366f1, #22d3ee); }
.sch-row__preview { font-size: 0.9rem; color: var(--color-text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 30ch; }
.sch-row__head-actions { display: inline-flex; align-items: center; gap: var(--space-3); }
.sch-row__enabled-label { font-size: 0.82rem; color: var(--color-text-muted); }

.form-row { display: flex; flex-direction: column; gap: var(--space-2); }
.form-row__label { font-weight: 600; font-size: 0.95rem; color: var(--color-text); }
.form-row__hint { font-size: 0.82rem; color: var(--color-text-muted); }

.input {
  width: 100%; padding: 0.7rem 0.85rem; background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-strong); border-radius: var(--radius-md);
  color: var(--color-text); font-family: var(--font-sans); font-size: 0.95rem;
}
.input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-soft); }
.input--textarea { resize: vertical; min-height: 70px; line-height: 1.5; }
.input--narrow { max-width: 260px; }

.sch-row__mode { display: inline-flex; gap: 4px; background: var(--color-bg-elevated); border: 1px solid var(--color-border-strong); border-radius: var(--radius-md); padding: 3px; width: fit-content; }
.sch-row__mode-btn { padding: 0.45rem 0.9rem; border-radius: var(--radius-sm); font-size: 0.88rem; font-weight: 600; color: var(--color-text-muted); }
.sch-row__mode-btn.is-active { background: var(--gradient-brand); color: #fff; }

.sch-row__actions { display: flex; justify-content: flex-end; gap: var(--space-3); }
</style>
