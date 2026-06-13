import { reactive } from 'vue'
import api from '../services/api.js'

/**
 * Lightweight per-guild settings cache so Welcome/Leave pages can merge
 * with each other (and only PUT a fully-formed body).
 */
const cache = reactive({
  guildId: null,
  guild: null,
  settings: null,
  loading: false,
  error: null
})

function defaultEmbed() {
  return {
    title: '',
    description: '',
    color: '#5865F2',
    thumbnail: '',
    image: '',
    footer: '',
    show_timestamp: false,
    author_name: '',
    author_icon_url: ''
  }
}

function defaults() {
  return {
    // EXISTING
    welcome_enabled: false,
    welcome_channel_id: '',
    welcome_message: 'Welcome to {guild}, {user}!',
    leave_enabled: false,
    leave_channel_id: '',
    leave_message: '{user} has left the server.',

    // NEW — welcome
    welcome_use_embed: false,
    welcome_embed: defaultEmbed(),
    welcome_ping_user: false,
    welcome_dm_enabled: false,
    welcome_dm_message: '',
    welcome_delete_after: 0,

    // NEW — leave
    leave_use_embed: false,
    leave_embed: defaultEmbed(),
    leave_delete_after: 0
  }
}

/**
 * Deep-merge an embed: take the defaults and overlay any present keys from
 * `provided`. We do this field-by-field so unknown extra keys are stripped
 * and known keys never come back undefined.
 */
function mergeEmbed(provided) {
  const base = defaultEmbed()
  if (!provided || typeof provided !== 'object') return base
  return {
    title: typeof provided.title === 'string' ? provided.title : base.title,
    description: typeof provided.description === 'string' ? provided.description : base.description,
    color: typeof provided.color === 'string' && provided.color ? provided.color : base.color,
    thumbnail: typeof provided.thumbnail === 'string' ? provided.thumbnail : base.thumbnail,
    image: typeof provided.image === 'string' ? provided.image : base.image,
    footer: typeof provided.footer === 'string' ? provided.footer : base.footer,
    show_timestamp: !!provided.show_timestamp,
    author_name: typeof provided.author_name === 'string' ? provided.author_name : base.author_name,
    author_icon_url: typeof provided.author_icon_url === 'string' ? provided.author_icon_url : base.author_icon_url
  }
}

/** Normalize any settings blob we receive from the API into our shape. */
function normalizeSettings(raw) {
  const d = defaults()
  const r = raw || {}
  return {
    welcome_enabled: !!r.welcome_enabled,
    welcome_channel_id: r.welcome_channel_id || '',
    welcome_message: typeof r.welcome_message === 'string' ? r.welcome_message : d.welcome_message,
    leave_enabled: !!r.leave_enabled,
    leave_channel_id: r.leave_channel_id || '',
    leave_message: typeof r.leave_message === 'string' ? r.leave_message : d.leave_message,

    welcome_use_embed: !!r.welcome_use_embed,
    welcome_embed: mergeEmbed(r.welcome_embed),
    welcome_ping_user: !!r.welcome_ping_user,
    welcome_dm_enabled: !!r.welcome_dm_enabled,
    welcome_dm_message: typeof r.welcome_dm_message === 'string' ? r.welcome_dm_message : '',
    welcome_delete_after: clampSeconds(r.welcome_delete_after),

    leave_use_embed: !!r.leave_use_embed,
    leave_embed: mergeEmbed(r.leave_embed),
    leave_delete_after: clampSeconds(r.leave_delete_after)
  }
}

function clampSeconds(v) {
  const n = Number.parseInt(v, 10)
  if (!Number.isFinite(n) || n < 0) return 0
  if (n > 600) return 600
  return n
}

async function loadFull(guildId, { force = false } = {}) {
  if (!force && cache.guildId === guildId && cache.settings) {
    return cache
  }
  cache.loading = true
  cache.error = null
  cache.guildId = guildId
  try {
    const { data } = await api.get(`/guilds/${guildId}/full`)
    if (data?.success) {
      cache.guild = data.guild || null
      cache.settings = normalizeSettings(data.settings)
    } else {
      throw new Error(data?.error || 'Failed to load')
    }
  } catch (err) {
    cache.error = err.response?.data?.error || err.message || 'Failed to load'
    if (!cache.settings) cache.settings = defaults()
    throw err
  } finally {
    cache.loading = false
  }
  return cache
}

async function saveSettings(guildId, patch) {
  const current = cache.settings ? cache.settings : defaults()
  // Shallow-merge top-level, then deep-merge the embed sub-objects so a page
  // editing only its own embed doesn't wipe the other one.
  const merged = { ...current, ...patch }
  if (patch && Object.prototype.hasOwnProperty.call(patch, 'welcome_embed')) {
    merged.welcome_embed = mergeEmbed({ ...(current.welcome_embed || {}), ...(patch.welcome_embed || {}) })
  } else {
    merged.welcome_embed = mergeEmbed(current.welcome_embed)
  }
  if (patch && Object.prototype.hasOwnProperty.call(patch, 'leave_embed')) {
    merged.leave_embed = mergeEmbed({ ...(current.leave_embed || {}), ...(patch.leave_embed || {}) })
  } else {
    merged.leave_embed = mergeEmbed(current.leave_embed)
  }

  const body = {
    welcome_enabled: !!merged.welcome_enabled,
    welcome_channel_id: merged.welcome_channel_id || '',
    welcome_message: typeof merged.welcome_message === 'string' ? merged.welcome_message : '',
    leave_enabled: !!merged.leave_enabled,
    leave_channel_id: merged.leave_channel_id || '',
    leave_message: typeof merged.leave_message === 'string' ? merged.leave_message : '',

    welcome_use_embed: !!merged.welcome_use_embed,
    welcome_embed: merged.welcome_embed,
    welcome_ping_user: !!merged.welcome_ping_user,
    welcome_dm_enabled: !!merged.welcome_dm_enabled,
    welcome_dm_message: typeof merged.welcome_dm_message === 'string' ? merged.welcome_dm_message : '',
    welcome_delete_after: clampSeconds(merged.welcome_delete_after),

    leave_use_embed: !!merged.leave_use_embed,
    leave_embed: merged.leave_embed,
    leave_delete_after: clampSeconds(merged.leave_delete_after)
  }
  const { data } = await api.put(`/guilds/${guildId}/settings`, body)
  if (data?.success && data.settings) {
    cache.settings = normalizeSettings(data.settings)
  } else {
    cache.settings = normalizeSettings(body)
  }
  return cache.settings
}

export function useGuildSettings() {
  return {
    cache,
    loadFull,
    saveSettings,
    defaults,
    defaultEmbed
  }
}

export default useGuildSettings
