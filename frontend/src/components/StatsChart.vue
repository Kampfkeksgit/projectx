<template>
  <div class="chart-card">
    <div class="chart-card__head">
      <h3 class="chart-card__title">{{ title }}</h3>
      <div class="chart-card__legend">
        <button
          v-for="line in lines"
          :key="line.key"
          type="button"
          class="chart-card__legend-item"
          :class="{ 'is-hidden': hidden.has(line.key) }"
          :aria-pressed="!hidden.has(line.key)"
          :title="hidden.has(line.key) ? t('chart.show') : t('chart.hide')"
          @click="toggle(line.key)"
        >
          <span class="chart-card__legend-dot" :style="{ background: line.color }"></span>
          {{ line.label }}
        </button>
      </div>
    </div>

    <div v-if="!hasData" class="chart-card__empty">{{ emptyText }}</div>

    <div v-else class="chart-card__plot" ref="plotRef">
      <svg
        ref="svgRef"
        class="chart-card__svg"
        :viewBox="`0 0 ${W} ${H}`"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        :aria-label="title"
        @mousemove="onMove"
        @mouseleave="onLeave"
        @touchmove.passive="onTouch"
        @touchend="onLeave"
      >
        <defs>
          <linearGradient
            v-for="line in geometry.lines"
            :key="'g' + line.key"
            :id="gradId(line.key)"
            x1="0" y1="0" x2="0" y2="1"
          >
            <stop offset="0%" :stop-color="line.color" stop-opacity="0.26" />
            <stop offset="100%" :stop-color="line.color" stop-opacity="0" />
          </linearGradient>
        </defs>

        <!-- horizontal grid + y labels -->
        <g>
          <template v-for="tick in geometry.yTicks" :key="'y' + tick.value">
            <line class="chart-card__grid" :x1="padL" :y1="tick.y" :x2="W - padR" :y2="tick.y" />
            <text class="chart-card__axis" :x="padL - 6" :y="tick.y + 3" text-anchor="end">{{ tick.label }}</text>
          </template>
        </g>

        <!-- x labels -->
        <g>
          <text
            v-for="tick in geometry.xTicks"
            :key="'x' + tick.x"
            class="chart-card__axis"
            :x="tick.x"
            :y="H - 6"
            text-anchor="middle"
          >{{ tick.label }}</text>
        </g>

        <!-- area fills + lines -->
        <g>
          <path
            v-for="line in geometry.lines"
            :key="'a' + line.key"
            :d="line.area"
            :fill="`url(#${gradId(line.key)})`"
            stroke="none"
          />
          <polyline
            v-for="line in geometry.lines"
            :key="'l' + line.key"
            class="chart-card__line"
            :points="line.poly"
            :stroke="line.color"
            fill="none"
          />
        </g>

        <!-- crosshair + active dots -->
        <g v-if="hover">
          <line class="chart-card__cross" :x1="hover.x" :y1="padT" :x2="hover.x" :y2="H - padB" />
          <circle
            v-for="d in hover.dots"
            :key="'d' + d.key"
            class="chart-card__dot"
            :cx="d.x"
            :cy="d.y"
            r="3.6"
            :fill="d.color"
          />
        </g>
      </svg>

      <div v-if="hover" class="chart-card__tip" :style="hover.tipStyle">
        <div class="chart-card__tip-date">{{ hover.date }}</div>
        <div v-for="r in hover.rows" :key="'r' + r.key" class="chart-card__tip-row">
          <span class="chart-card__tip-dot" :style="{ background: r.color }"></span>
          <span class="chart-card__tip-label">{{ r.label }}</span>
          <span class="chart-card__tip-val">{{ r.value }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, getCurrentInstance, ref } from 'vue'
import { useI18n } from '../i18n/index.js'

const { t, locale } = useI18n()

const props = defineProps({
  title: { type: String, default: '' },
  // Array of { ts:Number(unix sec), [key]:Number }
  points: { type: Array, default: () => [] },
  // Array of { key, label, color }
  lines: { type: Array, default: () => [] },
  emptyText: { type: String, default: 'No data yet' }
})

const uid = getCurrentInstance()?.uid ?? 0
const gradId = (key) => `chart-${uid}-${String(key).replace(/[^a-zA-Z0-9_-]/g, '')}`

const W = 760
const H = 240
const padL = 46
const padR = 16
const padT = 14
const padB = 26

// Series the user toggled off via the legend.
const hidden = ref(new Set())
function toggle(key) {
  const s = new Set(hidden.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  hidden.value = s
}
const visibleLines = computed(() => props.lines.filter((l) => !hidden.value.has(l.key)))

const cleanPoints = computed(() =>
  (props.points || [])
    .filter((p) => p && Number.isFinite(Number(p.ts)))
    .map((p) => ({ ...p, ts: Number(p.ts) }))
    .sort((a, b) => a.ts - b.ts)
)
const hasData = computed(() => cleanPoints.value.length >= 2)

function niceCeil(v) {
  if (v <= 5) return 5
  const p = Math.pow(10, Math.floor(Math.log10(v)))
  const n = v / p
  let m
  if (n <= 1) m = 1
  else if (n <= 2) m = 2
  else if (n <= 5) m = 5
  else m = 10
  return m * p
}

function fmtDate(ts) {
  const d = new Date(ts * 1000)
  return `${d.getDate()}.${d.getMonth() + 1}.`
}
function fmtDateFull(ts) {
  try { return new Date(ts * 1000).toLocaleDateString(locale.value) }
  catch { return fmtDate(ts) }
}
function fmtCompact(v) {
  const n = Math.round(v)
  if (Math.abs(n) >= 1000) {
    const k = n / 1000
    return `${k % 1 === 0 ? k : k.toFixed(1)}k`
  }
  return String(n)
}
function fmtFull(v) {
  try { return Number(v).toLocaleString(locale.value) }
  catch { return String(v) }
}

const geometry = computed(() => {
  const pts = cleanPoints.value
  const plotW = W - padL - padR
  const plotH = H - padT - padB
  const baseY = padT + plotH

  const minX = pts.length ? pts[0].ts : 0
  const maxX = pts.length ? pts[pts.length - 1].ts : 1
  const spanX = maxX - minX || 1

  let maxY = 1
  for (const line of visibleLines.value) {
    for (const p of pts) {
      const v = Number(p[line.key])
      if (Number.isFinite(v) && v > maxY) maxY = v
    }
  }
  const niceMax = niceCeil(maxY)

  const scaleX = (ts) => padL + ((ts - minX) / spanX) * plotW
  const scaleY = (v) => padT + plotH - (Math.max(0, v) / niceMax) * plotH

  const lines = visibleLines.value.map((line) => {
    const coords = pts.map((p) => ({ x: scaleX(p.ts), y: scaleY(Number(p[line.key]) || 0) }))
    const poly = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ')
    let area = ''
    if (coords.length) {
      area = `M ${coords[0].x.toFixed(1)},${baseY.toFixed(1)} `
        + coords.map((c) => `L ${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ')
        + ` L ${coords[coords.length - 1].x.toFixed(1)},${baseY.toFixed(1)} Z`
    }
    return { key: line.key, color: line.color, label: line.label, poly, area, coords }
  })

  const yTicks = []
  for (let i = 0; i <= 4; i++) {
    const value = Math.round((niceMax / 4) * i)
    yTicks.push({ value, y: scaleY(value), label: fmtCompact(value) })
  }

  const xTicks = []
  const tickCount = 4
  for (let i = 0; i <= tickCount; i++) {
    const ts = minX + (spanX * i) / tickCount
    xTicks.push({ x: scaleX(ts), label: fmtDate(ts) })
  }

  return { lines, yTicks, xTicks, scaleX }
})

// ---- hover / crosshair / tooltip ----
const svgRef = ref(null)
const plotRef = ref(null)
const hoverIndex = ref(null)

function locate(clientX) {
  const svg = svgRef.value
  const pts = cleanPoints.value
  if (!svg || pts.length < 2) return
  const rect = svg.getBoundingClientRect()
  if (!rect.width) return
  const vx = ((clientX - rect.left) / rect.width) * W // → viewBox x
  const sx = geometry.value.scaleX
  let best = 0
  let bestD = Infinity
  for (let i = 0; i < pts.length; i++) {
    const d = Math.abs(sx(pts[i].ts) - vx)
    if (d < bestD) { bestD = d; best = i }
  }
  hoverIndex.value = best
}
function onMove(e) { locate(e.clientX) }
function onTouch(e) { if (e.touches && e.touches[0]) locate(e.touches[0].clientX) }
function onLeave() { hoverIndex.value = null }

const hover = computed(() => {
  const idx = hoverIndex.value
  const pts = cleanPoints.value
  if (idx == null || idx < 0 || idx >= pts.length || !geometry.value.lines.length) return null
  const x = geometry.value.scaleX(pts[idx].ts)
  const dots = geometry.value.lines.map((l) => ({ key: l.key, color: l.color, x, y: l.coords[idx]?.y ?? 0 }))
  const rows = geometry.value.lines.map((l) => ({
    key: l.key, color: l.color, label: l.label, value: fmtFull(Number(pts[idx][l.key]) || 0)
  }))
  // Tooltip position (pixels relative to the plot wrapper).
  const rect = svgRef.value?.getBoundingClientRect()
  const w = rect?.width || W
  const pxX = (x / W) * w
  const flip = pxX > w * 0.55
  const tipStyle = {
    left: pxX + 'px',
    top: '8px',
    transform: flip ? 'translateX(calc(-100% - 14px))' : 'translateX(14px)'
  }
  return { x, dots, rows, date: fmtDateFull(pts[idx].ts), tipStyle }
})
</script>

<style scoped>
.chart-card {
  background: var(--color-surface);
  background-image: var(--gradient-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-5) var(--space-6);
  box-shadow: var(--shadow-inset);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.chart-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.chart-card__title {
  font-size: 1.02rem;
  font-weight: 600;
}

.chart-card__legend {
  display: inline-flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.chart-card__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
  color: var(--color-text-muted);
  padding: 3px 8px;
  border-radius: var(--radius-full);
  border: 1px solid transparent;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast), opacity var(--transition-fast);
}
.chart-card__legend-item:hover { background: var(--color-surface-2); color: var(--color-text); }
.chart-card__legend-item.is-hidden { opacity: 0.4; }
.chart-card__legend-item.is-hidden .chart-card__legend-dot { background: var(--color-text-soft) !important; }
.chart-card__legend-item.is-hidden { text-decoration: line-through; }

.chart-card__legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  flex-shrink: 0;
}

.chart-card__empty {
  color: var(--color-text-muted);
  font-size: 0.92rem;
  text-align: center;
  padding: var(--space-6) 0;
}

.chart-card__plot { position: relative; }

.chart-card__svg {
  width: 100%;
  height: auto;
  display: block;
}

.chart-card__grid {
  stroke: var(--color-border);
  stroke-width: 1;
  opacity: 0.45;
}

.chart-card__axis {
  fill: var(--color-text-soft);
  font-size: 11px;
  font-family: var(--font-mono);
}

.chart-card__line {
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.chart-card__cross {
  stroke: var(--color-text-soft);
  stroke-width: 1;
  stroke-dasharray: 3 3;
  opacity: 0.7;
}
.chart-card__dot {
  stroke: var(--color-surface);
  stroke-width: 2;
}

.chart-card__tip {
  position: absolute;
  z-index: 5;
  pointer-events: none;
  min-width: 120px;
  background: rgba(13, 16, 23, 0.94);
  backdrop-filter: blur(6px);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  padding: 8px 10px;
  box-shadow: var(--shadow-lg);
}
.chart-card__tip-date {
  font-size: 0.72rem;
  color: var(--color-text-soft);
  font-family: var(--font-mono);
  margin-bottom: 5px;
}
.chart-card__tip-row {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 0.8rem;
  line-height: 1.5;
}
.chart-card__tip-dot { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }
.chart-card__tip-label { color: var(--color-text-muted); margin-right: auto; }
.chart-card__tip-val { color: var(--color-text); font-weight: 700; font-variant-numeric: tabular-nums; }
</style>
