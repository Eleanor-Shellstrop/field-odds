import { createRouter, createWebHistory } from 'vue-router'
import TodayView from '@/views/TodayView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'today', component: TodayView },
    // Next: { path: '/species/:code', component: () => import('@/views/SpeciesView.vue') },
  ],
})
