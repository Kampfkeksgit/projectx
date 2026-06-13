/**
 * Shared placeholder list used by EmbedEditor and the plain message
 * placeholder helper on Welcome/Leave.
 *
 * `labelKey` is a key under the `embedEditor` i18n namespace.
 */
export const PLACEHOLDERS = [
  { token: '{user}', labelKey: 'placeholderUser' },
  { token: '{user.name}', labelKey: 'placeholderUserName' },
  { token: '{user.id}', labelKey: 'placeholderUserId' },
  { token: '{user.tag}', labelKey: 'placeholderUserTag' },
  { token: '{user.avatar}', labelKey: 'placeholderUserAvatar' },
  { token: '{guild}', labelKey: 'placeholderGuild' },
  { token: '{guild.id}', labelKey: 'placeholderGuildId' },
  { token: '{guild.member_count}', labelKey: 'placeholderGuildMemberCount' }
]

/**
 * Insert `token` into `current` at the caret position of `el` (if `el` is
 * focused), or append it otherwise. Returns the new string + caret offset.
 * The caller is responsible for setting the new value, awaiting nextTick(),
 * and re-focusing `el` if desired.
 */
export function insertAtCaret(el, current, token) {
  const v = current || ''
  if (!el || (typeof document !== 'undefined' && document.activeElement !== el)) {
    return { value: v + token, caret: v.length + token.length }
  }
  const start = el.selectionStart ?? v.length
  const end = el.selectionEnd ?? v.length
  return {
    value: v.slice(0, start) + token + v.slice(end),
    caret: start + token.length
  }
}
