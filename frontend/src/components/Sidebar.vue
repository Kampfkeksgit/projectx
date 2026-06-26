<template>
  <aside class="sidebar" :class="{ 'is-open': isMobileOpen }">
    <div class="sidebar__head">
      <GuildAvatar :name="guildName" :icon-url="guildIconUrl" size="md" />
      <div class="sidebar__head-text">
        <div class="sidebar__guild-name" :title="guildName">{{ guildName }}</div>
        <router-link to="/dashboard" class="sidebar__switch">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
          {{ t('sidebar.switchServer') }}
        </router-link>
      </div>
    </div>

    <router-link
      :to="`/dashboard/${guildId}/premium`"
      class="sidebar__premium"
      :class="`sidebar__premium--${premium.cache.tier || 'free'}`"
      @click="$emit('navigate')"
    >
      <span class="sidebar__premium-icon">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15 8.5 22 9.3 17 14 18.2 21 12 17.5 5.8 21 7 14 2 9.3 9 8.5 12 2"/></svg>
      </span>
      <span class="sidebar__premium-text">
        <span class="sidebar__premium-label">{{ t('sidebar.linkPremium') }}</span>
        <span class="sidebar__premium-tier">{{ t(`premium.tiers.${premium.cache.tier || 'free'}.name`) }}</span>
      </span>
    </router-link>

    <nav class="sidebar__nav">
      <div v-for="group in groups" :key="group.key" class="sidebar__group">
        <button
          type="button"
          class="sidebar__section"
          :class="{ 'is-collapsed': isCollapsed(group.key) }"
          :aria-expanded="!isCollapsed(group.key)"
          @click="toggleGroup(group.key)"
        >
          <svg class="sidebar__section-caret" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
          <span class="sidebar__section-title">{{ group.title }}</span>
        </button>
        <div v-show="!isCollapsed(group.key)" class="sidebar__group-links">
          <router-link
            v-for="link in group.links"
            :key="link.to"
            :to="link.to"
            class="sidebar__link"
            :class="{ 'is-active': isActive(link), 'is-locked': isLocked(link) }"
            @click="$emit('navigate')"
          >
            <span class="sidebar__icon" v-html="link.icon"></span>
            <span class="sidebar__link-label">{{ link.label }}</span>
            <span v-if="isLocked(link)" class="sidebar__lock" :title="t('premiumLock.tooltip')">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            </span>
          </router-link>
        </div>
      </div>
    </nav>

    <div class="sidebar__foot">
      <div class="sidebar__hint">
        <span class="sidebar__hint-dot"></span>
        {{ t('common.online') }}
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'
import { useRoute } from 'vue-router'
import GuildAvatar from './GuildAvatar.vue'
import { usePremium } from '../stores/premium.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()
const premium = usePremium()

const props = defineProps({
  guildId: { type: String, required: true },
  guildName: { type: String, default: 'Server' },
  guildIconUrl: { type: String, default: '' },
  isMobileOpen: { type: Boolean, default: false }
})

defineEmits(['navigate'])

const route = useRoute()

// Stable per-group keys (independent of the translated title) drive collapse state.
const groups = computed(() => [
  {
    key: 'config',
    title: t('sidebar.section'),
    links: [
      {
        to: `/dashboard/${props.guildId}`,
        label: t('sidebar.linkOverview'),
        exact: true,
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/general`,
        label: t('sidebar.linkGeneral'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/welcome`,
        label: t('sidebar.linkWelcome'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/leave`,
        label: t('sidebar.linkLeave'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="22" y1="11" x2="16" y2="11"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/autorole`,
        label: t('sidebar.linkAutoRole'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/verification`,
        label: t('sidebar.linkVerification'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="9"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/custom-commands`,
        label: t('sidebar.linkCustomCommands'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>'
      }
    ]
  },
  {
    key: 'moderation',
    title: t('sidebar.sectionModeration'),
    links: [
      {
        to: `/dashboard/${props.guildId}/logs`,
        label: t('sidebar.linkLogs'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/><line x1="8" y1="9" x2="10" y2="9"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/moderation`,
        label: t('sidebar.linkModeration'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><line x1="12" y1="8" x2="12" y2="13"/><line x1="12" y1="16" x2="12" y2="16"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/antiraid`,
        label: t('sidebar.linkAntiRaid'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>'
      }
    ]
  },
  {
    key: 'engagement',
    title: t('sidebar.sectionEngagement'),
    links: [
      {
        to: `/dashboard/${props.guildId}/leveling`,
        label: t('sidebar.linkLeveling'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 9 11 13 15 21 7"/><polyline points="14 7 21 7 21 14"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/reaction-roles`,
        label: t('sidebar.linkReactionRoles'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/rolemenus`,
        label: t('sidebar.linkRoleMenus'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="4" rx="1"/><rect x="3" y="10" width="18" height="4" rx="1"/><rect x="3" y="16" width="18" height="4" rx="1"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/starboard`,
        label: t('sidebar.linkStarboard'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/suggestions`,
        label: t('sidebar.linkSuggestions'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/birthday`,
        label: t('sidebar.linkBirthday'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-8a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8"/><path d="M4 16s.5-1 2-1 2.5 2 4 2 2.5-2 4-2 2.5 2 4 2 2-1 2-1"/><path d="M2 21h20"/><path d="M7 8v3M12 8v3M17 8v3M7 4h.01M12 4h.01M17 4h.01"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/counting`,
        label: t('sidebar.linkCounting'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/polls`,
        label: t('sidebar.linkPolls'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/giveaways`,
        label: t('sidebar.linkGiveaways'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 12 20 22 4 22 4 12"/><rect x="2" y="7" width="20" height="5"/><line x1="12" y1="22" x2="12" y2="7"/><path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"/><path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/economy`,
        label: t('sidebar.linkEconomy'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M14.5 9.5a2.5 2.5 0 0 0-2.5-1.5c-1.4 0-2.5.9-2.5 2s1.1 2 2.5 2 2.5.9 2.5 2-1.1 2-2.5 2a2.5 2.5 0 0 1-2.5-1.5"/><line x1="12" y1="6" x2="12" y2="8"/><line x1="12" y1="16" x2="12" y2="18"/></svg>'
      }
    ]
  },
  {
    key: 'community',
    title: t('sidebar.sectionCommunity'),
    links: [
      {
        to: `/dashboard/${props.guildId}/tempvoice`,
        label: t('sidebar.linkTempVoice'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/tickets`,
        label: t('sidebar.linkTickets'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4z"/><line x1="12" y1="7" x2="12" y2="17" stroke-dasharray="2 2"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/applications`,
        label: t('sidebar.linkApplications'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="m9 15 2 2 4-4"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/invitetracking`,
        label: t('sidebar.linkInviteTracking'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/social`,
        label: t('sidebar.linkSocial'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/scheduled`,
        label: t('sidebar.linkScheduled'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/></svg>'
      }
    ]
  },
  {
    key: 'games',
    title: t('sidebar.sectionGames'),
    links: [
      {
        to: `/dashboard/${props.guildId}/tictactoe`,
        label: t('sidebar.linkTicTacToe'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/rps`,
        label: t('sidebar.linkRps'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 11V6a2 2 0 0 0-2-2 2 2 0 0 0-2 2"/><path d="M14 10V4a2 2 0 0 0-2-2 2 2 0 0 0-2 2v2"/><path d="M10 10.5V6a2 2 0 0 0-2-2 2 2 0 0 0-2 2v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/trivia`,
        label: t('sidebar.linkTrivia'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/connect4`,
        label: t('sidebar.linkConnect4'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><circle cx="12" cy="8" r="1.5"/><circle cx="16" cy="8" r="1.5"/><circle cx="8" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="16" cy="16" r="1.5"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/hangman`,
        label: t('sidebar.linkHangman'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 21h10"/><path d="M6 21V4h9"/><path d="M15 4v3"/><circle cx="15" cy="9" r="2"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/poker`,
        label: t('sidebar.linkPoker'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="13" height="16" rx="2"/><path d="M8 9c-1.5 1-1.5 3 0 4 1.5-1 1.5-3 0-4z"/><path d="M19 7l2 .8a2 2 0 0 1 1.2 2.5l-3 8"/></svg>'
      }
    ]
  },
  {
    key: 'server',
    title: t('sidebar.sectionServer'),
    links: [
      {
        to: `/dashboard/${props.guildId}/stats`,
        label: t('sidebar.linkStats'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>'
      },
      {
        to: `/dashboard/${props.guildId}/backup`,
        label: t('sidebar.linkBackup'),
        icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>'
      }
    ]
  }
])

// --- Collapsible category state (persisted across navigations) ---
const STORAGE_KEY = 'projectx_sidebar_collapsed'
function loadCollapsed() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') || {} } catch { return {} }
}
const collapsed = reactive(loadCollapsed())
function isCollapsed(key) { return !!collapsed[key] }
function toggleGroup(key) {
  collapsed[key] = !collapsed[key]
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(collapsed)) } catch { /* ignore */ }
}
onMounted(() => {
  // Auto-expand the group that holds the current route so the active page stays visible.
  for (const g of groups.value) {
    if (collapsed[g.key] && g.links.some((l) => isActive(l))) collapsed[g.key] = false
  }
})

function isActive(link) {
  if (link.exact) return route.path === link.to
  return route.path.startsWith(link.to)
}

/** Module route segment for a link (last path part), used for premium locks. */
function moduleKeyOf(link) {
  const parts = link.to.split('/')
  return parts[parts.length - 1]
}

function isLocked(link) {
  if (link.exact) return false // overview is never locked
  return !premium.isUnlocked(moduleKeyOf(link))
}
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  position: sticky;
  top: calc(var(--nav-height) + var(--space-6));
  align-self: flex-start;
  max-height: calc(100vh - var(--nav-height) - var(--space-12));
  overflow: hidden;
  box-shadow: var(--shadow-md), var(--shadow-inset);
}

.sidebar__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.sidebar__head-text {
  min-width: 0;
  flex: 1;
}

.sidebar__guild-name {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 0.98rem;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar__switch {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  color: var(--color-text-soft);
  margin-top: 2px;
  transition: color var(--transition-fast);
}
.sidebar__switch:hover {
  color: var(--color-primary);
}

.sidebar__premium {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0.6rem var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: linear-gradient(135deg, rgba(167, 139, 250, 0.1), rgba(88, 101, 242, 0.06));
  transition: border-color var(--transition-fast), transform var(--transition-fast);
}
.sidebar__premium:hover { border-color: var(--color-border-strong); transform: translateY(-1px); }
.sidebar__premium--basic { border-color: rgba(99, 102, 241, 0.4); }
.sidebar__premium--pro { border-color: rgba(167, 139, 250, 0.5); background: linear-gradient(135deg, rgba(167, 139, 250, 0.18), rgba(236, 72, 153, 0.1)); }
.sidebar__premium-icon { width: 28px; height: 28px; flex-shrink: 0; border-radius: var(--radius-sm); display: inline-flex; align-items: center; justify-content: center; color: #fff; background: linear-gradient(135deg, #a78bfa, #ec4899); }
.sidebar__premium-text { display: flex; flex-direction: column; min-width: 0; line-height: 1.2; }
.sidebar__premium-label { font-size: 0.9rem; font-weight: 600; color: var(--color-text); }
.sidebar__premium-tier { font-size: 0.72rem; color: var(--color-text-soft); }

.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  /* Bleed the scroll area slightly into the padding so the scrollbar sits at the edge. */
  margin: 0 calc(-1 * var(--space-2));
  padding: 0 var(--space-2);
  scrollbar-width: thin;
  scrollbar-color: var(--color-border-strong) transparent;
}

.sidebar__nav::-webkit-scrollbar {
  width: 6px;
}
.sidebar__nav::-webkit-scrollbar-thumb {
  background: var(--color-border-strong);
  border-radius: 3px;
}
.sidebar__nav::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar__group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar__group + .sidebar__group {
  margin-top: var(--space-3);
}

.sidebar__section {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  font-size: 0.7rem;
  color: var(--color-text-soft);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  transition: color var(--transition-fast), background var(--transition-fast);
}

.sidebar__section:hover {
  color: var(--color-text);
  background: var(--color-surface-2);
}

.sidebar__section-caret {
  flex-shrink: 0;
  transition: transform var(--transition-fast);
}

.sidebar__section.is-collapsed .sidebar__section-caret {
  transform: rotate(-90deg);
}

.sidebar__section-title {
  flex: 1;
  min-width: 0;
  text-align: left;
}

.sidebar__group-links {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar__link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0.65rem var(--space-3);
  border-radius: var(--radius-md);
  color: var(--color-text-muted);
  font-size: 0.92rem;
  font-weight: 500;
  transition: background var(--transition-fast), color var(--transition-fast);
  position: relative;
}

.sidebar__link:hover {
  background: var(--color-surface-2);
  color: var(--color-text);
}

.sidebar__link.is-active {
  background: var(--color-primary-soft);
  color: #fff;
}

.sidebar__link.is-active::before {
  content: '';
  position: absolute;
  left: -1px;
  top: 25%;
  bottom: 25%;
  width: 3px;
  border-radius: 2px;
  background: var(--gradient-brand);
}

.sidebar__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: currentColor;
}

.sidebar__link-label { flex: 1; min-width: 0; }

.sidebar__link.is-locked { color: var(--color-text-soft); }
.sidebar__link.is-locked .sidebar__icon { opacity: 0.6; }
.sidebar__lock {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #c4b5fd;
  flex-shrink: 0;
}

.sidebar__foot {
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.sidebar__hint {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text-soft);
  font-size: 0.78rem;
}

.sidebar__hint-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-success);
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}

@media (max-width: 900px) {
  .sidebar {
    position: static;
    width: 100%;
    max-height: none;
  }
}
</style>
