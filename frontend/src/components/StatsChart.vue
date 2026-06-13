<template>
  <div class="chart-card">
    <div class="chart-card__head">
      <h3 class="chart-card__title">{{ title }}</h3>
      <div class="chart-card__legend">
        <span v-for="line in lines" :key="line.key" class="chart-card__legend-item">
          <span class="chart-card__legend-dot" :style="{ background: line.color }"></span>
          {{ line.label }}
        </span>
      </div>
    </div>

    <div v-if="!hasData" class="chart-card__empty">{{ emptyText }}</div>

    <svg
      v-else
      class="chart-card__svg"
      :viewBox="`0 0 ${W} ${H}`"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      :aria-label="title"
    >
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

      <!-- lines -->
      <g>
        <polyline
          v-for="line in geometry.lines"
          :key="line.key"
          class="chart-card__line"
          :points="line.points"
          :stroke="line.color"
          fill="none"
        />
      </g>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  // Array of { ts:Number(unix sec), [key]:Number }
  points: { type: Array, default: () => [] },
  // Array of { key, label, color }
  lines: { type: Array, default: () => [] },
  emptyText: { type: String, default: 'No data yet' }
})

const W = 760
const H = 240
const padL = 44
const padR = 16
const padT = 14
const padB = 26

const cleanPoints = computed(() =>
  (props.points || [])
    .filter(p => p && Number.isFinite(Number(p.ts)))
    .map(p => ({ ...p, ts: Number(p.ts) }))
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

const geometry = computed(() => {
  const pts = cleanPoints.value
  const plotW = W - padL - padR
  const plotH = H - padT - padB

  const minX = pts[0].ts
  const maxX = pts[pts.length - 1].ts
  const spanX = maxX - minX || 1

  let maxY = 1
  for (const line of props.lines) {
    for (const p of pts) {
      const v = Number(p[line.key])
      if (Number.isFinite(v) && v > maxY) maxY = v
    }
  }
  const niceMax = niceCeil(maxY)

  const scaleX = ts => padL + ((ts - minX) / spanX) * plotW
  const scaleY = v => padT + plotH - (Math.max(0, v) / niceMax) * plotH

  const lines = props.lines.map(line => ({
    key: line.key,
    color: line.color,
    points: pts.map(p => `${scaleX(p.ts).toFixed(1)},${scaleY(Number(p[line.key]) || 0).toFixed(1)}`).join(' ')
  }))

  const yTicks = []
  for (let i = 0; i <= 4; i++) {
    const value = Math.round((niceMax / 4) * i)
    yTicks.push({ value, y: scaleY(value), label: String(value) })
  }

  const xTicks = []
  const tickCount = 4
  for (let i = 0; i <= tickCount; i++) {
    const ts = minX + (spanX * i) / tickCount
    xTicks.push({ x: scaleX(ts), label: fmtDate(ts) })
  }

  return { lines, yTicks, xTicks }
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
  gap: var(--space-4);
  flex-wrap: wrap;
}

.chart-card__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.chart-card__legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}

.chart-card__empty {
  color: var(--color-text-muted);
  font-size: 0.92rem;
  text-align: center;
  padding: var(--space-6) 0;
}

.chart-card__svg {
  width: 100%;
  height: auto;
  display: block;
}

.chart-card__grid {
  stroke: var(--color-border);
  stroke-width: 1;
  opacity: 0.5;
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
</style>
