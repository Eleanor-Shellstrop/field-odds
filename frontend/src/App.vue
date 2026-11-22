<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="shell">
    <nav class="nav">
      <span class="brand">Field Odds</span>
      <RouterLink to="/">
        Today
      </RouterLink>
      <RouterLink to="/rarities">
        Rarities now
      </RouterLink>
    </nav>
    <main>
      <RouterView />
    </main>
    <footer>Data from <a href="https://ebird.org">eBird</a>, Cornell Lab of Ornithology.</footer>
  </div>
</template>

<style>
:root {
  --bg: #f6f5ef;
  --surface: #ffffff;
  --text: #1f2a24;
  --muted: #5c6b62;
  --border: #e2e0d6;
  --track: #e9e7de;
  --accent: #2f7d55;
  --accent-mid: #7fb08a;
  --accent-low: #c7d9c5;
  --danger: #b3261e;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #141815;
    --surface: #1d221e;
    --text: #e8ece8;
    --muted: #9aa69e;
    --border: #2c332e;
    --track: #2a302b;
    --accent: #4fb07e;
    --accent-mid: #3c7a58;
    --accent-low: #2e4a39;
    --danger: #f2b8b5;
    color-scheme: dark;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
  line-height: 1.45;
}
a { color: var(--accent); }
</style>

<style scoped>
.shell { max-width: 48rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
.nav { display: flex; flex-wrap: wrap; align-items: baseline; gap: 1rem; margin-bottom: 1.5rem; }
.brand { font-weight: 700; letter-spacing: 0.02em; color: var(--accent); margin-right: auto; }
.nav a { color: var(--muted); font-size: 0.9rem; text-decoration: none; }
.nav a.router-link-active { color: var(--accent); font-weight: 600; }
footer { margin-top: 3rem; font-size: 0.8rem; color: var(--muted); }
</style>
