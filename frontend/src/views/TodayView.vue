<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { onMounted } from 'vue'
import FilterBar from '@/components/FilterBar.vue'
import SpeciesRow from '@/components/SpeciesRow.vue'
import { usePredictionsStore } from '@/stores/predictions'

const store = usePredictionsStore()
const { data, loading, error, filtered, search, minLikelihood } = storeToRefs(store)

onMounted(store.fetchToday)
</script>

<template>
  <section>
    <header class="head">
      <h1>Likely today</h1>
      <p
        v-if="data?.for_date"
        class="meta"
      >
        {{ data.region_code }} · {{ data.for_date }} · model {{ data.model_name }}
      </p>
    </header>

    <FilterBar
      v-model:search="search"
      v-model:min-likelihood="minLikelihood"
    />

    <p v-if="loading">
      Loading…
    </p>
    <p
      v-else-if="error"
      class="error"
    >
      Couldn't load predictions: {{ error }}
    </p>
    <p
      v-else-if="!data?.for_date"
      class="empty"
    >
      No likelihoods yet. They are calculated from historical data, which hasn't been loaded.
    </p>
    <template v-else>
      <p class="count">
        {{ filtered.length }} species
      </p>
      <ul class="list">
        <SpeciesRow
          v-for="s in filtered"
          :key="s.species_code"
          :species="s"
        />
      </ul>
    </template>
  </section>
</template>

<style scoped>
.head h1 { margin: 0; font-size: 1.75rem; }
.meta, .count { color: var(--muted); font-size: 0.9rem; margin: 0.25rem 0 0; }
.list { list-style: none; margin: 0; padding: 0; }
.error { color: var(--danger); }
</style>
