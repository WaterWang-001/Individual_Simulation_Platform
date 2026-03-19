<template>
  <RouterView />
</template>

<script setup>
import { RouterView } from 'vue-router'
</script>

<style>
/* ── Global reset & design tokens ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:         #f8f9fc;
  --surface:    #ffffff;
  --border:     #e4e7ef;
  --border-2:   #d0d5e0;
  --text:       #0f172a;
  --text-dim:   #64748b;
  --text-muted: #94a3b8;
  --purple:     #7c3aed;
  --blue:       #2563eb;
  --grad:       linear-gradient(135deg, #7c3aed, #2563eb);
  --grad-soft:  linear-gradient(135deg, rgba(124,58,237,.07), rgba(37,99,235,.07));
  --radius:     10px;
}

html, body {
  height: 100%;
  font-family: 'Inter', system-ui, sans-serif;
  line-height: 1.6;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
