<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ value: number }>()

const pct = computed(() => Math.round(Math.min(Math.max(props.value, 0), 1) * 100))
const tier = computed(() => (pct.value >= 60 ? 'high' : pct.value >= 25 ? 'mid' : 'low'))
</script>

<template>
  <div
    class="bar"
    role="meter"
    :aria-valuenow="pct"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-label="`${pct}% likely`"
  >
    <div
      class="fill"
      :class="tier"
      :style="{ width: `${pct}%` }"
    />
    <span class="label">{{ pct }}%</span>
  </div>
</template>

<style scoped>
.bar {
  position: relative;
  height: 1.25rem;
  border-radius: 999px;
  background: var(--track);
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.3s ease;
}
.fill.high { background: var(--accent); }
.fill.mid { background: var(--accent-mid); }
.fill.low { background: var(--accent-low); }
.label {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center end;
  padding-right: 0.5rem;
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
</style>
