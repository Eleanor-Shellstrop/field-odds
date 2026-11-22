import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, type TodayResponse } from '@/api/client'

export const usePredictionsStore = defineStore('predictions', () => {
  const data = ref<TodayResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Filters live in the store so other views (a map, say) can share them later.
  const minLikelihood = ref(0.05)
  const search = ref('')
  const recentOnly = ref(false)

  const filtered = computed(() => {
    const q = search.value.trim().toLowerCase()
    return (data.value?.items ?? []).filter(
      (s) =>
        // Most recent sightings are of uncommon birds, so this view ignores the threshold
        (recentOnly.value ? s.reported_days_ago !== null : s.likelihood >= minLikelihood.value) &&
        (!q ||
          s.common_name.toLowerCase().includes(q) ||
          (s.sci_name ?? '').toLowerCase().includes(q)),
    )
  })

  async function fetchToday() {
    loading.value = true
    error.value = null
    try {
      data.value = await api.today()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  return { data, loading, error, minLikelihood, search, recentOnly, filtered, fetchToday }
})
