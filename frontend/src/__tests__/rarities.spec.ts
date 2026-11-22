import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rarity } from '@/api/client'
import RarityCard from '@/components/RarityCard.vue'
import { useRaritiesStore } from '@/stores/rarities'

const bird: Rarity = {
  species_code: 'exafly', common_name: 'Example Flycatcher', status: 'being_seen', reason: null,
  first_reported: '2026-11-01T08:00:00', last_reported: '2026-11-04T12:00:00', outings: 9,
  outings_today: 3, outings_yesterday: 4, days_reported: 4, unreviewed: false,
  hotspots: ['Example Trail'], area: null, is_current: true,
}

describe('RarityCard', () => {
  const card = () => mount(RarityCard, { props: { rarity: bird, saving: false } })

  it('logs a miss in one tap', async () => {
    const wrapper = card()
    await wrapper.findAll('button')[1].trigger('click')
    expect(wrapper.emitted('log')).toEqual([[false, undefined]])
  })

  it('requires a time once backdating, then logs it', async () => {
    const wrapper = card()
    await wrapper.find('input[type="checkbox"]').setValue(true)
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    await wrapper.find('input[type="datetime-local"]').setValue('2026-11-04T12:30')
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('log')).toEqual([[true, '2026-11-04T12:30']])
  })

  it('shows evidence, never a percentage', () => {
    const text = card().text()
    expect(text).toContain('3 outings today')
    expect(text).toContain('Example Trail')
    expect(text).not.toContain('%')
  })
})

describe('rarities store', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.unstubAllGlobals())

  it('separates current birds from past ones', () => {
    const store = useRaritiesStore()
    const gone: Rarity = { ...bird, status: 'probably_gone' }
    const old: Rarity = { ...bird, is_current: false }
    store.data = {
      region_code: 'US-WA-033', today: '2026-11-04', updated_at: null, counts_through: null,
      items: [bird, gone, old],
    }
    expect(store.active).toHaveLength(1)
    expect(store.past).toHaveLength(2)
  })

  it('sends the app header and no location', async () => {
    const fetchMock = vi.fn().mockImplementation(async () => new Response('[]'))
    vi.stubGlobal('fetch', fetchMock)
    await useRaritiesStore().log('exafly', false)
    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers['X-Field-Odds']).toBe('1')
    expect(JSON.parse(init.body)).toEqual({ species_code: 'exafly', found: false })
  })
})
