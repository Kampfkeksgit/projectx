import { reactive } from 'vue'

const state = reactive({
  toasts: []
})

let nextId = 1

function push(message, options = {}) {
  const id = nextId++
  const toast = {
    id,
    message,
    type: options.type || 'info',
    duration: options.duration ?? 3200
  }
  state.toasts.push(toast)
  if (toast.duration > 0) {
    setTimeout(() => dismiss(id), toast.duration)
  }
  return id
}

function dismiss(id) {
  const idx = state.toasts.findIndex(t => t.id === id)
  if (idx !== -1) state.toasts.splice(idx, 1)
}

export function useToast() {
  return {
    state,
    push,
    dismiss,
    success: (msg, opts = {}) => push(msg, { ...opts, type: 'success' }),
    error: (msg, opts = {}) => push(msg, { ...opts, type: 'error' }),
    info: (msg, opts = {}) => push(msg, { ...opts, type: 'info' })
  }
}

export default useToast
