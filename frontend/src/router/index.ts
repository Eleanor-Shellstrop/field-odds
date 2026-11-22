import { createRouter, createWebHistory } from 'vue-router'
import RaritiesView from '@/views/RaritiesView.vue'
import TodayView from '@/views/TodayView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'today', component: TodayView },
    { path: '/rarities', name: 'rarities', component: RaritiesView },
    // Next: { path: '/species/:code', component: () => import('@/views/SpeciesView.vue') },
  ],
})
