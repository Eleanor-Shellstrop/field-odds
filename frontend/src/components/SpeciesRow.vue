<script setup lang="ts">
import type { PredictionItem } from '@/api/client'
import LikelihoodBar from './LikelihoodBar.vue'

defineProps<{ species: PredictionItem }>()

function formatDate(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}
</script>

<template>
  <li class="row">
    <div class="names">
      <a
        class="common"
        :href="`https://ebird.org/species/${species.species_code}`"
        target="_blank"
        rel="noopener"
      >{{ species.common_name }}</a>
      <span
        v-if="species.sci_name"
        class="sci"
      >{{ species.sci_name }}</span>
    </div>
    <LikelihoodBar :value="species.likelihood" />
    <div
      v-if="species.last_seen"
      class="last"
    >
      Last reported {{ formatDate(species.last_seen) }}
      <template v-if="species.last_location">
        · {{ species.last_location }}
      </template>
    </div>
  </li>
</template>

<style scoped>
.row {
  display: grid;
  grid-template-columns: minmax(12rem, 1fr) minmax(8rem, 14rem);
  gap: 0.25rem 1rem;
  align-items: center;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--border);
}
.names { display: flex; flex-direction: column; }
.common { font-weight: 600; color: var(--text); text-decoration: none; }
.common:hover { text-decoration: underline; }
.sci { font-style: italic; font-size: 0.85rem; color: var(--muted); }
.last { grid-column: 1 / -1; font-size: 0.8rem; color: var(--muted); }
@media (max-width: 520px) {
  .row { grid-template-columns: 1fr; }
}
</style>
