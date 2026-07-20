<template>
  <LegalLayout
    :title="t('legal.impressum.title')"
    :intro="t('legal.impressum.intro')"
    :sections="sections"
    :last-updated="lastUpdated"
  />
</template>

<script setup>
import { computed, onMounted } from 'vue'
import LegalLayout from './LegalLayout.vue'
import { useI18n } from '../../i18n/index.js'
import { useLegalInfo } from '../../composables/useLegalInfo.js'

const { t, locale } = useI18n()
const { info, load, resolve } = useLegalInfo()

const lastUpdated = '2026-06-06'

onMounted(load)

const sections = computed(() => {
  // re-read on locale change + when the operator info arrives
  void locale.value
  void info.value
  const raw = t('legal.impressum.sections')
  if (!Array.isArray(raw)) return []
  return raw.map((s) => ({ ...s, bodyHtml: resolve(s.bodyHtml) }))
})
</script>
