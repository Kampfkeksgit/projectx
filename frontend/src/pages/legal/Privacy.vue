<template>
  <LegalLayout
    :title="t('legal.privacy.title')"
    :intro="t('legal.privacy.intro')"
    :sections="sections"
    :last-updated="lastUpdated"
    :show-toc="true"
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
  void locale.value
  void info.value
  const raw = t('legal.privacy.sections')
  if (!Array.isArray(raw)) return []
  return raw.map((s) => ({ ...s, bodyHtml: resolve(s.bodyHtml) }))
})
</script>
