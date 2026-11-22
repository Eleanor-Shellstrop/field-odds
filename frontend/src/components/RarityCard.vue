<script setup lang="ts">
import { ref } from 'vue'
import type { Rarity } from '@/api/client'
import { evidence, STATUS } from '@/rarityText'

defineProps<{ rarity: Rarity; saving: boolean }>()
const emit = defineEmits<{ log: [found: boolean, searchedAt?: string] }>()

const backdating = ref(false)
const searchedAt = ref('')

function log(found: boolean) {
  emit('log', found, backdating.value && searchedAt.value ? searchedAt.value : undefined)
  backdating.value = false
  searchedAt.value = ''
}
</script>

<template>
  <li class="card">
    <div class="top">
      <a
        class="name"
        :href="`https://ebird.org/map/${rarity.species_code}`"
        target="_blank"
        rel="noopener noreferrer"
      >{{ rarity.common_name }}</a>
      <span
        class="status"
        :class="rarity.status"
        :title="STATUS[rarity.status].meaning"
      >{{ STATUS[rarity.status].label }}</span>
      <span
        v-if="rarity.unreviewed"
        class="status"
      >Unreviewed</span>
    </div>
    <p class="detail">
      {{ evidence(rarity) }}
    </p>
    <p
      v-if="rarity.hotspots.length"
      class="detail"
    >
      Reported from {{ rarity.hotspots.join('; ') }}
    </p>
    <p
      v-else-if="rarity.area"
      class="detail"
    >
      {{ rarity.area }}
    </p>
    <p
      v-if="rarity.reason"
      class="detail"
    >
      {{ rarity.reason }}
    </p>
    <div class="log">
      <span>I looked:</span>
      <button
        type="button"
        :disabled="saving || (backdating && !searchedAt)"
        @click="log(true)"
      >
        Found it
      </button>
      <button
        type="button"
        :disabled="saving || (backdating && !searchedAt)"
        @click="log(false)"
      >
        Didn't find it
      </button>
      <label>
        <input
          v-model="backdating"
          type="checkbox"
        >
        Earlier
      </label>
      <input
        v-if="backdating"
        v-model="searchedAt"
        type="datetime-local"
        aria-label="When you looked"
      >
    </div>
  </li>
</template>

<style scoped>
.card { padding: 0.85rem 0; border-bottom: 1px solid var(--border); }
.top { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem 0.6rem; }
.name { color: var(--text); font-weight: 600; text-decoration: none; }
.name:hover { text-decoration: underline; }
.status {
  padding: 0.05rem 0.5rem;
  border: 1px solid var(--muted);
  border-radius: 999px;
  color: var(--muted);
  font-size: 0.75rem;
}
.status.being_seen { background: var(--accent); border-color: var(--accent); color: var(--bg); }
.status.single_report { border-color: var(--accent); color: var(--accent); }
.status.probably_gone { opacity: 0.7; }
.detail { margin: 0.2rem 0 0; color: var(--muted); font-size: 0.8rem; }
.log {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.6rem;
  color: var(--muted);
  font-size: 0.8rem;
}
button,
input[type='datetime-local'] {
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 0.4rem;
  background: var(--surface);
  color: var(--text);
  font: inherit;
}
button { cursor: pointer; }
button:disabled { opacity: 0.5; cursor: default; }
input[type='checkbox'] { accent-color: var(--accent); }
</style>
