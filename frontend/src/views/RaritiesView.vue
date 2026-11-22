<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { onMounted } from 'vue'
import RarityCard from '@/components/RarityCard.vue'
import SearchLog from '@/components/SearchLog.vue'
import { STATUS } from '@/rarityText'
import { useRaritiesStore } from '@/stores/rarities'

const store = useRaritiesStore()
const { data, searches, loading, saving, error, saveError, active, past } = storeToRefs(store)

onMounted(store.load)

const updated = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })
</script>

<template>
  <section>
    <h1>Rarities now</h1>
    <p class="meta">
      Rare or unusual reports from eBird. These show the evidence, not your chance of finding the
      bird: people who miss a bird often don't submit a checklist.
    </p>
    <p class="meta">
      Please respect private property. Only public hotspots are named, and they may be some
      distance from the bird.
    </p>
    <p
      v-if="data?.updated_at"
      class="meta"
    >
      Reports updated {{ updated(data.updated_at) }}<template v-if="data.counts_through">
        · checklist counts through {{ data.counts_through }}
      </template>
    </p>
    <details class="meta">
      <summary>What the statuses mean</summary>
      <p
        v-for="(text, key) in STATUS"
        :key="key"
      >
        <strong>{{ text.label }}:</strong> {{ text.meaning }}
      </p>
    </details>

    <p v-if="loading">
      Loading…
    </p>
    <p
      v-else-if="error"
      class="error"
    >
      Couldn't load rarities: {{ error }}
    </p>
    <template v-else>
      <p
        v-if="saveError"
        class="error"
      >
        Couldn't save that: {{ saveError }}
      </p>
      <p v-if="data && !data.updated_at">
        No rarity pull yet. The worker runs it at 6 and 11 AM, or at the next chance after.
      </p>
      <p v-else-if="!active.length">
        No current rarities.
      </p>
      <ul>
        <RarityCard
          v-for="(r, i) in active"
          :key="`${r.species_code}-${r.first_reported}-${i}`"
          :rarity="r"
          :saving="saving"
          @log="(found, at) => store.log(r.species_code, found, at)"
        />
      </ul>
      <details
        v-if="past.length"
        class="past"
      >
        <summary>Earlier in the last 30 days ({{ past.length }})</summary>
        <ul>
          <RarityCard
            v-for="(r, i) in past"
            :key="`${r.species_code}-${r.first_reported}-${i}`"
            :rarity="r"
            :saving="saving"
            @log="(found, at) => store.log(r.species_code, found, at)"
          />
        </ul>
      </details>
      <SearchLog
        :searches="searches"
        :saving="saving"
        @remove="store.remove"
      />
    </template>
  </section>
</template>

<style scoped>
h1 { margin: 0; font-size: 1.75rem; }
.meta { color: var(--muted); font-size: 0.85rem; margin: 0.4rem 0 0; }
.meta p { margin: 0.3rem 0; }
ul { margin: 0.5rem 0 0; padding: 0; list-style: none; }
.past { margin-top: 1.25rem; }
summary { cursor: pointer; }
.error { color: var(--danger); }
</style>
