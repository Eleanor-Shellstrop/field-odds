<script setup lang="ts">
import { computed } from 'vue'
import type { RaritySearch, RarityStatus } from '@/api/client'
import { STATUS, when } from '@/rarityText'

const props = defineProps<{ searches: RaritySearch[]; saving: boolean }>()
defineEmits<{ remove: [id: number] }>()

// The test of whether the statuses are honest
const tally = computed(() =>
  (Object.keys(STATUS) as RarityStatus[])
    .map((status) => {
      const matching = props.searches.filter((s) => s.status_then === status)
      return { status, total: matching.length, found: matching.filter((s) => s.found).length }
    })
    .filter((t) => t.total > 0),
)
</script>

<template>
  <section class="searches">
    <h2>My searches</h2>
    <p class="note">
      Kept only in your database: the bird, the time and whether you found it. No location.
    </p>
    <p
      v-for="t in tally"
      :key="t.status"
      class="note"
    >
      When the app said "{{ STATUS[t.status].label }}", you found it {{ t.found }} of {{ t.total }}
    </p>
    <p
      v-if="!searches.length"
      class="note"
    >
      Nothing logged yet.
    </p>
    <ul>
      <li
        v-for="s in searches"
        :key="s.id"
      >
        <span>
          <strong>{{ s.common_name }}</strong>: {{ s.found ? 'found it' : "didn't find it" }},
          {{ when(s.searched_at) }}
          <span class="note">
            ({{ s.status_then ? `app said ${STATUS[s.status_then].label}` : 'app was not tracking it yet' }})
          </span>
        </span>
        <button
          type="button"
          :disabled="saving"
          @click="$emit('remove', s.id)"
        >
          Remove
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.searches { margin-top: 2rem; }
h2 { margin: 0; font-size: 1.15rem; }
.note { color: var(--muted); font-size: 0.8rem; margin: 0.25rem 0 0; }
ul { margin: 0.5rem 0 0; padding: 0; list-style: none; }
li {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
}
button { border: 0; background: none; color: var(--accent); cursor: pointer; font: inherit; }
</style>
