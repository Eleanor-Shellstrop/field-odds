<script setup lang="ts">
const search = defineModel<string>('search', { required: true })
const minLikelihood = defineModel<number>('minLikelihood', { required: true })
</script>

<template>
  <div class="filters">
    <input
      v-model="search"
      type="search"
      placeholder="Filter species…"
      aria-label="Filter species"
    >
    <label>
      At least {{ Math.round(minLikelihood * 100) }}%
      <input
        v-model.number="minLikelihood"
        type="range"
        min="0"
        max="1"
        step="0.05"
      >
    </label>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: center;
  margin: 1rem 0;
}
input[type='search'] {
  flex: 1 1 14rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--surface);
  color: var(--text);
  font: inherit;
}
label {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  font-size: 0.9rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}
input[type='range'] { accent-color: var(--accent); }
</style>
