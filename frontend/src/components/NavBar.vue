<template>
  <nav :class="['navbar', { 'navbar--home': centered }]">
    <RouterLink to="/" class="nav-logo">
      <div class="nav-logo-icon">🧠</div>
      <span class="nav-logo-text">LifeNetSim</span>
    </RouterLink>

    <div :class="centered ? 'nav-links-center' : 'nav-links-inline'">
      <RouterLink to="/" class="nav-link" :class="{ active: route.path === '/' }">About</RouterLink>
      <a href="#" class="nav-link">Paper</a>
      <a href="#" class="nav-link">GitHub</a>
      <a href="#" class="nav-link">Contact Us</a>
    </div>

    <div v-if="!centered" class="nav-spacer"></div>
    <slot name="right" />
  </nav>
</template>

<script setup>
import { useRoute } from 'vue-router'

defineProps({
  centered: { type: Boolean, default: false },
})

const route = useRoute()
</script>

<style scoped>
.navbar {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 32px;
  flex-shrink: 0;
  z-index: 50;
  background: rgba(248, 249, 252, 0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
}

/* Home variant: fixed, full-width, taller */
.navbar--home {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 60px;
  padding: 0 48px;
  background: rgba(248, 249, 252, 0.85);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(228, 231, 239, 0.8);
  z-index: 100;
}

.nav-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  flex-shrink: 0;
}
.nav-logo-icon {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: var(--grad);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
}
.nav-logo-text {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.3px;
  background: var(--grad);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.navbar--home .nav-logo-icon { width: 28px; height: 28px; border-radius: 7px; font-size: 14px; }
.navbar--home .nav-logo-text { font-size: 15px; }

/* Centered links (home page) */
.nav-links-center {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 0 auto;
}

/* Inline links (app pages) */
.nav-links-inline {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: 16px;
}

.nav-link {
  color: var(--text-dim);
  text-decoration: none;
  font-size: 13.5px;
  font-weight: 500;
  padding: 6px 14px;
  border-radius: 6px;
  transition: color 0.15s, background 0.15s;
}
.nav-link:hover { color: var(--text); background: rgba(0, 0, 0, 0.04); }
.nav-link.active { color: var(--text); }
.navbar:not(.navbar--home) .nav-link { font-size: 13px; padding: 6px 13px; }

.nav-spacer { flex: 1; }
</style>
