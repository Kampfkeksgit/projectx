<template>
  <LegalLayout
    :title="t('legal.impressum.title')"
    :intro="t('legal.impressum.intro')"
    :sections="sections"
    :last-updated="lastUpdated"
  />
</template>

<script setup>
import { computed } from 'vue'
import LegalLayout from './LegalLayout.vue'
import { useI18n } from '../../i18n/index.js'

const { t, locale } = useI18n()

const lastUpdated = '2026-06-06'

const sections = computed(() => {
  // re-read on locale change
  void locale.value
  const raw = t('legal.impressum.sections')
  return Array.isArray(raw) ? raw : []
})
</script>
