<template>
  <LegalLayout
    :title="t('legal.terms.title')"
    :intro="t('legal.terms.intro')"
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
  void locale.value
  const raw = t('legal.terms.sections')
  return Array.isArray(raw) ? raw : []
})
</script>
