import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { TodayResponse } from '@/api/client'
import LikelihoodBar from '@/components/LikelihoodBar.vue'
import { usePredictionsStore } from '@/stores/predictions'

const sample: TodayResponse = {
  region_code: 'US-WA-033',
  for_date: '2026-11-19',
  model_name: 'frequency_v1',
  items: [
    { species_code: 'amecro', common_name: 'American Crow', sci_name: 'Corvus brachyrhynchos',
      likelihood: 0.97, last_seen: '2026-11-18', last_location: 'Discovery Park' },
    { species_code: 'baleag', common_name: 'Bald Eagle', sci_name: 'Haliaeetus leucocephalus',
      likelihood: 0.41, last_seen: '2026-11-17', last_location: null },
    { species_code: 'snoowl1', common_name: 'Snowy Owl', sci_name: 'Bubo scandiacus',
      likelihood: 0.02, last_seen: null, last_location: null },
  ],
}

describe('predictions store', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.unstubAllGlobals())

  it('fetches today and filters by likelihood and search', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(sample))))
    const store = usePredictionsStore()
    await store.fetchToday()

    expect(store.error).toBeNull()
    // The default 5% threshold hides the Snowy Owl
    expect(store.filtered.map((s) => s.species_code)).toEqual(['amecro', 'baleag'])

    store.search = 'haliaeetus'
    expect(store.filtered.map((s) => s.species_code)).toEqual(['baleag'])

    store.search = ''
    store.minLikelihood = 0
    expect(store.filtered).toHaveLength(3)
  })

  it('records API errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 500 })))
    const store = usePredictionsStore()
    await store.fetchToday()
    expect(store.error).toMatch(/500/)
    expect(store.loading).toBe(false)
  })
})

describe('LikelihoodBar', () => {
  it('shows a rounded percentage and clamps the width', () => {
    const wrapper = mount(LikelihoodBar, { props: { value: 0.666 } })
    expect(wrapper.text()).toBe('67%')
    expect(wrapper.attributes('aria-valuenow')).toBe('67')

    const over = mount(LikelihoodBar, { props: { value: 1.4 } })
    expect(over.find('.fill').attributes('style')).toContain('width: 100%')
  })
})
