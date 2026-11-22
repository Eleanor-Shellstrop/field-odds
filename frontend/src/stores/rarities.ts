import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, type RaritiesResponse, type RaritySearch } from '@/api/client'

export const useRaritiesStore = defineStore('rarities', () => {
  const data = ref<RaritiesResponse | null>(null)
  const searches = ref<RaritySearch[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  const saveError = ref<string | null>(null)

  const items = computed(() => data.value?.items ?? [])
  const active = computed(() =>
    items.value.filter((r) => r.is_current && r.status !== 'probably_gone'),
  )
  // Still listed, so a search from a few days ago can be logged
  const past = computed(() =>
    items.value.filter((r) => !r.is_current || r.status === 'probably_gone'),
  )

  async function load() {
    loading.value = true
    error.value = null
    try {
      ;[data.value, searches.value] = await Promise.all([api.rarities(), api.searches()])
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  async function save(action: () => Promise<unknown>) {
    saving.value = true
    saveError.value = null
    try {
      await action()
      searches.value = await api.searches()
    } catch (e) {
      saveError.value = e instanceof Error ? e.message : String(e)
    } finally {
      saving.value = false
    }
  }

  const log = (speciesCode: string, found: boolean, searchedAt?: string) =>
    save(() => api.logSearch(speciesCode, found, searchedAt))
  const remove = (id: number) => save(() => api.removeSearch(id))

  return { data, searches, loading, saving, error, saveError, active, past, load, log, remove }
})
