<template>
  <div class="overview">
    <header class="overview__head">
      <div class="overview__eyebrow">{{ t('overview.eyebrow') }}</div>
      <h1 class="overview__title">{{ guildName }}</h1>
      <p class="overview__sub">{{ t('overview.sub') }}</p>
    </header>

    <section v-if="!botPresent" class="invite-banner">
      <div class="invite-banner__icon" aria-hidden="true">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><path d="M12 17h.01"/><circle cx="12" cy="12" r="10"/></svg>
      </div>
      <div class="invite-banner__body">
        <h3 class="invite-banner__title">{{ t('overview.botMissingTitle') }}</h3>
        <p class="invite-banner__text">{{ t('overview.botMissingBody') }}</p>
      </div>
      <AppButton tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="gradient">
        <template #icon-left>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </template>
        {{ t('overview.inviteBot') }}
      </AppButton>
    </section>

    <div class="overview__grid" :class="{ 'is-dimmed': !botPresent }">
      <article class="config-card">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--welcome">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.welcomeTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.welcomeDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="welcomeEnabled ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ welcomeEnabled ? t('common.enabled') : t('common.disabled') }}
          </span>
          <span v-if="welcomeChannel" class="status__channel">#{{ welcomeChannel }}</span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/welcome`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--leave">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="22" y1="11" x2="16" y2="11"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.leaveTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.leaveDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="leaveEnabled ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ leaveEnabled ? t('common.enabled') : t('common.disabled') }}
          </span>
          <span v-if="leaveChannel" class="status__channel">#{{ leaveChannel }}</span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/leave`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--autorole">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.autoroleTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.autoroleDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.autorole ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.autorole ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/autorole`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--logs">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/><line x1="8" y1="9" x2="10" y2="9"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.logsTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.logsDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.logs ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.logs ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/logs`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--moderation">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><line x1="12" y1="8" x2="12" y2="13"/><line x1="12" y1="16" x2="12" y2="16"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.moderationTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.moderationDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.moderation ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.moderation ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/moderation`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--reactionroles">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.reactionRolesTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.reactionRolesDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.reactionRoles ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.reactionRoles ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/reaction-roles`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('leveling') }" :data-lock="lockLabel('leveling')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--leveling">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 9 11 13 15 21 7"/><polyline points="14 7 21 7 21 14"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.levelingTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.levelingDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.leveling ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.leveling ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/leveling`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--customcmds">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.customCommandsTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.customCommandsDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status status--on">
            <span class="status__dot"></span>
            {{ t('overview.customCommandsCount', { count: extraEnabled.customCommandsCount }) }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/custom-commands`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('social') }" :data-lock="lockLabel('social')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--social">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.socialTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.socialDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.social ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.social ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/social`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('stats') }" :data-lock="lockLabel('stats')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--stats">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.statsTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.statsDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.stats ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.stats ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/stats`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('tempvoice') }" :data-lock="lockLabel('tempvoice')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--tempvoice">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.tempvoiceTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.tempvoiceDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.tempvoice ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.tempvoice ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/tempvoice`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('starboard') }" :data-lock="lockLabel('starboard')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--starboard">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.starboardTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.starboardDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.starboard ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.starboard ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/starboard`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--suggestions">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.suggestionsTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.suggestionsDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.suggestions ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.suggestions ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/suggestions`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('birthday') }" :data-lock="lockLabel('birthday')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--birthday">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-8a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8"/><path d="M4 16s.5-1 2-1 2.5 2 4 2 2.5-2 4-2 2.5 2 4 2 2-1 2-1"/><path d="M2 21h20"/><path d="M7 8v3M12 8v3M17 8v3"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.birthdayTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.birthdayDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.birthday ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.birthday ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/birthday`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('scheduled') }" :data-lock="lockLabel('scheduled')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--scheduled">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.scheduledTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.scheduledDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status status--on">
            <span class="status__dot"></span>
            {{ t('overview.scheduledCount', { count: extraEnabled.scheduledCount }) }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/scheduled`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('antiraid') }" :data-lock="lockLabel('antiraid')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--antiraid">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.antiraidTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.antiraidDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.antiraid ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.antiraid ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/antiraid`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--verification">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="9"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.verificationTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.verificationDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.verification ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.verification ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/verification`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('rolemenus') }" :data-lock="lockLabel('rolemenus')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--rolemenus">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="4" rx="1"/><rect x="3" y="10" width="18" height="4" rx="1"/><rect x="3" y="16" width="18" height="4" rx="1"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.rolemenusTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.rolemenusDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status status--on">
            <span class="status__dot"></span>
            {{ t('overview.rolemenusCount', { count: extraEnabled.rolemenusCount }) }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/rolemenus`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('tickets') }" :data-lock="lockLabel('tickets')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--tickets">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4z"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.ticketsTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.ticketsDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.tickets ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.tickets ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/tickets`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('giveaways') }" :data-lock="lockLabel('giveaways')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--giveaways">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 12 20 22 4 22 4 12"/><rect x="2" y="7" width="20" height="5"/><line x1="12" y1="22" x2="12" y2="7"/><path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"/><path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.giveawaysTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.giveawaysDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status status--on">
            <span class="status__dot"></span>
            {{ t('overview.giveawaysCount', { count: extraEnabled.giveawaysCount }) }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/giveaways`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--counting">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.countingTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.countingDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.counting ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.counting ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/counting`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--polls">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.pollsTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.pollsDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status status--on">
            <span class="status__dot"></span>
            {{ t('overview.pollsCount', { count: extraEnabled.pollsCount }) }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/polls`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('invitetracking') }" :data-lock="lockLabel('invitetracking')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--invitetracking">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.invitetrackingTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.invitetrackingDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.invitetracking ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.invitetracking ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/invitetracking`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('applications') }" :data-lock="lockLabel('applications')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--applications">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="m9 15 2 2 4-4"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.applicationsTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.applicationsDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status status--on">
            <span class="status__dot"></span>
            {{ t('overview.applicationsCount', { count: extraEnabled.applicationsCount }) }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/applications`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card" :class="{ 'config-card--locked': isLocked('economy') }" :data-lock="lockLabel('economy')">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--economy">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M14.5 9.5a2.5 2.5 0 0 0-2.5-1.5c-1.4 0-2.5.9-2.5 2s1.1 2 2.5 2 2.5.9 2.5 2-1.1 2-2.5 2a2.5 2.5 0 0 1-2.5-1.5"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.economyTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.economyDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled.economy ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled.economy ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/economy`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article class="config-card">
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--backup">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
          </div>
          <div>
            <h3 class="config-card__title">{{ t('overview.backupTitle') }}</h3>
            <p class="config-card__desc">{{ t('overview.backupDesc') }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status status--on">
            <span class="status__dot"></span>
            {{ t('overview.backupCount', { count: extraEnabled.backupCount }) }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/backup`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>

      <article
        v-for="g in gameCards"
        :key="g.key"
        class="config-card"
        :class="{ 'config-card--locked': isLocked(g.key) }"
        :data-lock="lockLabel(g.key)"
      >
        <div class="config-card__head">
          <div class="config-card__icon config-card__icon--games" v-html="g.icon"></div>
          <div>
            <h3 class="config-card__title">{{ t(`overview.${g.key}Title`) }}</h3>
            <p class="config-card__desc">{{ t(`overview.${g.key}Desc`) }}</p>
          </div>
        </div>
        <div class="config-card__meta">
          <span class="status" :class="extraEnabled[g.key] ? 'status--on' : 'status--off'">
            <span class="status__dot"></span>
            {{ extraEnabled[g.key] ? t('common.enabled') : t('common.disabled') }}
          </span>
        </div>
        <div class="config-card__cta">
          <AppButton v-if="botPresent" tag="router-link" :to="`/dashboard/${guildId}/${g.key}`" variant="gradient">{{ t('common.configure') }}</AppButton>
          <AppButton v-else tag="a" :href="inviteUrl" target="_blank" rel="noopener noreferrer" variant="ghost">{{ t('common.invite') }}</AppButton>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import api from '../services/api.js'
import { useGuildSettings } from '../stores/guildSettings.js'
import { usePremium } from '../stores/premium.js'
import { useI18n } from '../i18n/index.js'

const { t } = useI18n()

const route = useRoute()
const store = useGuildSettings()
const premium = usePremium()

/** Is a premium module locked for the current tier? (false for free modules) */
function isLocked(moduleKey) {
  return !premium.isUnlocked(moduleKey)
}
/** Short ribbon label for a locked card: the required tier name (e.g. "PRO"). */
function lockLabel(moduleKey) {
  return t(`premium.tiers.${premium.tierOf(moduleKey)}.name`)
}

const guildId = computed(() => route.params.guild_id)
const guildName = computed(() => {
  const g = store.cache.guild
  return g?.guild_name || g?.name || 'Server'
})

const botPresent = computed(() => !!store.cache.guild?.bot_present)

// Bot invite URL for the current guild. Permissions bitmask 285223990 =
// VIEW_CHANNEL + SEND_MESSAGES + MANAGE_MESSAGES + KICK_MEMBERS + BAN_MEMBERS +
// MANAGE_ROLES + MANAGE_CHANNELS (Stats: rename/create channels) +
// MOVE_MEMBERS (Temp-Voice: move members into their created channel) +
// MANAGE_GUILD (Backup: restore the server name).
// disable_guild_select=true keeps Discord on the guild we pre-selected.
const inviteUrl = computed(() => {
  const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID || ''
  const id = guildId.value
  if (!clientId || !id) return '#'
  const params = new URLSearchParams({
    client_id: clientId,
    scope: 'bot applications.commands',
    permissions: '285223990',
    guild_id: id,
    disable_guild_select: 'true'
  })
  return `https://discord.com/oauth2/authorize?${params.toString()}`
})

const welcomeEnabled = computed(() => !!store.cache.settings?.welcome_enabled)
const leaveEnabled = computed(() => !!store.cache.settings?.leave_enabled)

const welcomeChannel = computed(() => {
  const id = store.cache.settings?.welcome_channel_id
  if (!id) return ''
  return id.length > 10 ? id.slice(-6) : id
})

const leaveChannel = computed(() => {
  const id = store.cache.settings?.leave_channel_id
  if (!id) return ''
  return id.length > 10 ? id.slice(-6) : id
})

const extraEnabled = reactive({
  autorole: false,
  logs: false,
  moderation: false,
  leveling: false,
  reactionRoles: false,
  customCommandsCount: 0,
  social: false,
  stats: false,
  tempvoice: false,
  starboard: false,
  suggestions: false,
  birthday: false,
  scheduledCount: 0,
  antiraid: false,
  verification: false,
  rolemenusCount: 0,
  tickets: false,
  giveawaysCount: 0,
  counting: false,
  pollsCount: 0,
  invitetracking: false,
  applicationsCount: 0,
  economy: false,
  tictactoe: false,
  rps: false,
  trivia: false,
  connect4: false,
  hangman: false,
  poker: false,
  backupCount: 0
})

// Games category — one shared /games settings row drives all five cards.
const gameCards = [
  { key: 'tictactoe', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/></svg>' },
  { key: 'rps', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 11V6a2 2 0 0 0-4 0"/><path d="M14 10V4a2 2 0 0 0-4 0v2"/><path d="M10 10.5V6a2 2 0 0 0-4 0v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/></svg>' },
  { key: 'trivia', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>' },
  { key: 'connect4', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><circle cx="12" cy="8" r="1.5"/><circle cx="16" cy="12" r="1.5"/><circle cx="8" cy="16" r="1.5"/></svg>' },
  { key: 'hangman', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 21h10"/><path d="M6 21V4h9"/><path d="M15 4v3"/><circle cx="15" cy="9" r="2"/></svg>' },
  { key: 'poker', icon: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="13" height="16" rx="2"/><path d="M8 9c-1.5 1-1.5 3 0 4 1.5-1 1.5-3 0-4z"/><path d="M19 7l2 .8a2 2 0 0 1 1.2 2.5l-3 8"/></svg>' }
]

async function fetchExtraStatus() {
  const id = guildId.value
  if (!id) return
  const endpoints = ['autorole', 'logs', 'moderation', 'leveling']
  const [autorole, logs, moderation, leveling, rr, cmds, social, stats, tempvoice, starboard, suggestions, birthday, scheduled, antiraid, verification, rolemenus, tickets, giveaways, counting, polls, invitetracking, applications, economy, games, backups] = await Promise.all([
    api.get(`/guilds/${id}/settings/autorole`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/settings/logs`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/settings/moderation`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/settings/leveling`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/reaction-roles`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/custom-commands`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/social`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/stats`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/tempvoice`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/starboard`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/suggestions`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/birthday`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/scheduled`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/antiraid`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/verification`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/rolemenus`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/tickets`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/giveaways`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/counting`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/polls`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/invitetracking`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/applications/forms`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/economy`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/games`).then(r => r.data).catch(() => null),
    api.get(`/guilds/${id}/backups`).then(r => r.data).catch(() => null)
  ])
  void endpoints
  extraEnabled.autorole = !!(autorole?.success && autorole.settings?.enabled)
  extraEnabled.logs = !!(logs?.success && logs.settings?.enabled)
  extraEnabled.moderation = !!(moderation?.success && moderation.settings?.enabled)
  extraEnabled.leveling = !!(leveling?.success && leveling.settings?.enabled)
  extraEnabled.reactionRoles = !!(rr?.success && Array.isArray(rr.messages) && rr.messages.length > 0)
  const commandList = (cmds?.success && Array.isArray(cmds.commands)) ? cmds.commands : []
  extraEnabled.customCommandsCount = commandList.filter(c => c?.enabled).length
  extraEnabled.social = !!(social?.success && Array.isArray(social.subscriptions) && social.subscriptions.some(s => s?.enabled))
  extraEnabled.stats = !!(stats?.success && stats.settings?.enabled)
  extraEnabled.tempvoice = !!(tempvoice?.success && tempvoice.settings?.enabled)
  extraEnabled.starboard = !!(starboard?.success && starboard.settings?.enabled)
  extraEnabled.suggestions = !!(suggestions?.success && suggestions.settings?.enabled)
  extraEnabled.birthday = !!(birthday?.success && birthday.settings?.enabled)
  const schedList = (scheduled?.success && Array.isArray(scheduled.messages)) ? scheduled.messages : []
  extraEnabled.scheduledCount = schedList.filter(m => m?.enabled).length
  extraEnabled.antiraid = !!(antiraid?.success && antiraid.settings?.enabled)
  extraEnabled.verification = !!(verification?.success && verification.settings?.enabled)
  extraEnabled.rolemenusCount = (rolemenus?.success && Array.isArray(rolemenus.menus)) ? rolemenus.menus.length : 0
  extraEnabled.tickets = !!(tickets?.success && tickets.settings?.enabled)
  const gwList = (giveaways?.success && Array.isArray(giveaways.giveaways)) ? giveaways.giveaways : []
  extraEnabled.giveawaysCount = gwList.filter(g => !g.ended).length
  extraEnabled.counting = !!(counting?.success && counting.settings?.enabled)
  const pollList = (polls?.success && Array.isArray(polls.polls)) ? polls.polls : []
  extraEnabled.pollsCount = pollList.filter(p => !p.ended).length
  extraEnabled.invitetracking = !!(invitetracking?.success && invitetracking.settings?.enabled)
  extraEnabled.applicationsCount = (applications?.success && Array.isArray(applications.forms)) ? applications.forms.filter(f => f.enabled).length : 0
  extraEnabled.economy = !!(economy?.success && economy.settings?.enabled)
  const gs = (games?.success && games.settings) ? games.settings : {}
  extraEnabled.tictactoe = !!gs.tictactoe_enabled
  extraEnabled.rps = !!gs.rps_enabled
  extraEnabled.trivia = !!gs.trivia_enabled
  extraEnabled.connect4 = !!gs.connect4_enabled
  extraEnabled.hangman = !!gs.hangman_enabled
  extraEnabled.poker = !!gs.poker_enabled
  extraEnabled.backupCount = (backups?.success && Array.isArray(backups.snapshots)) ? backups.snapshots.length : 0
}

onMounted(fetchExtraStatus)
watch(() => guildId.value, fetchExtraStatus)
</script>

<style scoped>
.overview__head {
  margin-bottom: var(--space-8);
}

.overview__eyebrow {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-soft);
  margin-bottom: var(--space-2);
}

.overview__title {
  font-size: clamp(1.7rem, 3vw, 2.2rem);
  letter-spacing: -0.025em;
  margin-bottom: var(--space-2);
}

.overview__sub {
  color: var(--color-text-muted);
}

.overview__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--space-5);
}

.overview__grid.is-dimmed {
  opacity: 0.72;
}

/* Invite banner (only shown when the bot is not in the guild) */
.invite-banner {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  margin-bottom: var(--space-6);
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(244, 114, 182, 0.10));
  border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: var(--radius-xl);
  box-shadow: 0 0 30px -10px rgba(245, 158, 11, 0.25), var(--shadow-inset);
}

.invite-banner__icon {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  background: rgba(245, 158, 11, 0.18);
  color: #fbbf24;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.invite-banner__body {
  flex: 1;
  min-width: 0;
}

.invite-banner__title {
  font-size: 1.05rem;
  margin-bottom: 4px;
  color: var(--color-text);
}

.invite-banner__text {
  color: var(--color-text-muted);
  font-size: 0.92rem;
  line-height: 1.5;
}

@media (max-width: 720px) {
  .invite-banner {
    flex-direction: column;
    align-items: flex-start;
    text-align: left;
  }
  .invite-banner > :last-child {
    width: 100%;
  }
}

.config-card {
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  box-shadow: var(--shadow-inset);
  transition: transform var(--transition), border-color var(--transition), box-shadow var(--transition);
}

.config-card:hover {
  transform: translateY(-3px);
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-lg), var(--shadow-inset);
}

/* Premium-locked modules: subtle dim + a tier ribbon in the top-right corner. */
.config-card--locked {
  position: relative;
  border-color: rgba(167, 139, 250, 0.32);
}
.config-card--locked::after {
  content: attr(data-lock);
  position: absolute;
  top: var(--space-4);
  right: var(--space-4);
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #fff;
  padding: 3px 8px;
  border-radius: var(--radius-full);
  background: linear-gradient(135deg, #a78bfa, #ec4899);
  pointer-events: none;
}
.config-card--locked .config-card__icon { opacity: 0.85; }

.config-card__head {
  display: flex;
  gap: var(--space-4);
  align-items: flex-start;
}

.config-card__icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.config-card__icon--welcome { background: linear-gradient(135deg, #5865f2, #a78bfa); }
.config-card__icon--leave { background: linear-gradient(135deg, #f472b6, #a78bfa); }
.config-card__icon--autorole { background: linear-gradient(135deg, #22d3ee, #5865f2); }
.config-card__icon--logs { background: linear-gradient(135deg, #38bdf8, #22d3ee); }
.config-card__icon--moderation { background: linear-gradient(135deg, #ef4444, #f472b6); }
.config-card__icon--reactionroles { background: linear-gradient(135deg, #f43f5e, #f472b6); }
.config-card__icon--leveling { background: linear-gradient(135deg, #facc15, #22d3ee); }
.config-card__icon--customcmds { background: linear-gradient(135deg, #10b981, #5865f2); }
.config-card__icon--social { background: linear-gradient(135deg, #6366f1, #ec4899); }
.config-card__icon--stats { background: linear-gradient(135deg, #14b8a6, #22d3ee); }
.config-card__icon--tempvoice { background: linear-gradient(135deg, #8b5cf6, #22d3ee); }
.config-card__icon--starboard { background: linear-gradient(135deg, #f59e0b, #fbbf24); }
.config-card__icon--suggestions { background: linear-gradient(135deg, #10b981, #34d399); }
.config-card__icon--birthday { background: linear-gradient(135deg, #f472b6, #fbbf24); }
.config-card__icon--scheduled { background: linear-gradient(135deg, #6366f1, #22d3ee); }
.config-card__icon--antiraid { background: linear-gradient(135deg, #ef4444, #f59e0b); }
.config-card__icon--verification { background: linear-gradient(135deg, #22c55e, #10b981); }
.config-card__icon--rolemenus { background: linear-gradient(135deg, #8b5cf6, #ec4899); }
.config-card__icon--tickets { background: linear-gradient(135deg, #5865f2, #38bdf8); }
.config-card__icon--giveaways { background: linear-gradient(135deg, #f59e0b, #f43f5e); }
.config-card__icon--counting { background: linear-gradient(135deg, #06b6d4, #6366f1); }
.config-card__icon--polls { background: linear-gradient(135deg, #8b5cf6, #06b6d4); }
.config-card__icon--invitetracking { background: linear-gradient(135deg, #10b981, #06b6d4); }
.config-card__icon--applications { background: linear-gradient(135deg, #6366f1, #8b5cf6); }
.config-card__icon--economy { background: linear-gradient(135deg, #facc15, #f59e0b); }
.config-card__icon--games { background: linear-gradient(135deg, #ec4899, #8b5cf6); }
.config-card__icon--backup { background: linear-gradient(135deg, #14b8a6, #22d3ee); }

.config-card__title {
  font-size: 1.1rem;
  margin-bottom: 4px;
}

.config-card__desc {
  color: var(--color-text-muted);
  font-size: 0.92rem;
  line-height: 1.5;
}

.config-card__meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--color-bg-elevated);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  flex-wrap: wrap;
}

.status {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 0.85rem;
  font-weight: 600;
}

.status__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status--on { color: var(--color-success); }
.status--on .status__dot {
  background: var(--color-success);
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}

.status--off { color: var(--color-text-soft); }
.status--off .status__dot {
  background: var(--color-text-soft);
}

.status__channel {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--color-text-muted);
  background: var(--color-surface-2);
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-sm);
}

.config-card__cta {
  display: flex;
  justify-content: flex-end;
  margin-top: auto;
}
</style>
