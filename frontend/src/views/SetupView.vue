<template>
  <div class="setup-layout">
    <NavBar>
      <template #right>
        <div class="step-indicator">
          <div class="step-pip active">1</div>
          <div class="step-line"></div>
          <div class="step-pip">2</div>
          <div class="step-line"></div>
          <div class="step-pip">3</div>
          <span class="step-label">Configure</span>
        </div>
      </template>
    </NavBar>

    <div class="workspace">
      <!-- Left: relationship graph -->
      <GraphPanel
        :agents="selectedAgents"
        :relationships="relationships"
        :loading="loading"
      />

      <!-- Right: config panel -->
      <div class="config-pane">
        <div class="config-scroll">

          <!-- Agent count -->
          <div class="cfg-section">
            <div class="cfg-section-title">Agent Selection</div>
            <div class="agent-slider-wrap">
              <div class="slider-header">
                <div>
                  <div class="slider-label">Number of Agents</div>
                  <div class="slider-sub">Selected from {{ allProfiles.length }} profiles</div>
                </div>
                <div class="slider-val">{{ agentCount }}</div>
              </div>
              <input type="range" min="2" :max="allProfiles.length || 37" step="1"
                     v-model.number="agentCount" :style="sliderStyle(agentCount, 2, allProfiles.length || 37)">
            </div>

            <!-- Distribution -->
            <div class="dist-grid">
              <div class="dist-item">
                <div class="dist-item-val">{{ dist.male }}</div>
                <div class="dist-item-label">Male</div>
                <div class="dist-bar-wrap"><div class="dist-bar-fill" :style="`background:#3b82f6;width:${dist.male / agentCount * 100}%`"></div></div>
              </div>
              <div class="dist-item">
                <div class="dist-item-val">{{ dist.female }}</div>
                <div class="dist-item-label">Female</div>
                <div class="dist-bar-wrap"><div class="dist-bar-fill" :style="`background:#ec4899;width:${dist.female / agentCount * 100}%`"></div></div>
              </div>
              <div class="dist-item">
                <div class="dist-item-val">{{ dist.ugrad }}</div>
                <div class="dist-item-label">Undergrad</div>
                <div class="dist-bar-wrap"><div class="dist-bar-fill" :style="`background:#7c3aed;width:${dist.ugrad / agentCount * 100}%`"></div></div>
              </div>
              <div class="dist-item">
                <div class="dist-item-val">{{ dist.grad }}</div>
                <div class="dist-item-label">Grad / PhD</div>
                <div class="dist-bar-wrap"><div class="dist-bar-fill" :style="`background:#2563eb;width:${dist.grad / agentCount * 100}%`"></div></div>
              </div>
            </div>
          </div>

          <!-- Network stats -->
          <div class="cfg-section">
            <div class="cfg-section-title">Network Stats</div>
            <div class="stats-row">
              <div class="stat-box"><div class="stat-box-val">{{ agentCount }}</div><div class="stat-box-label">Agents</div></div>
              <div class="stat-box"><div class="stat-box-val">{{ activeEdgeCount }}</div><div class="stat-box-label">Connections</div></div>
              <div class="stat-box"><div class="stat-box-val">{{ avgDegree }}</div><div class="stat-box-label">Avg Degree</div></div>
            </div>
          </div>

          <!-- Log -->
          <div class="cfg-section">
            <div class="cfg-section-title">System Log</div>
            <div class="log-box" ref="logBox">
              <div v-for="(entry, i) in logs" :key="i" v-html="entry"></div>
            </div>
          </div>

        </div>

        <div class="config-footer">
          <button class="btn-start-sim" :disabled="loading || !allProfiles.length" @click="nextStep">
            Next Step
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 8h10M9 4l4 4-4 4"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '../components/NavBar.vue'
import GraphPanel from '../components/GraphPanel.vue'
import { getProfiles, getRelationships } from '../api/index.js'

const router = useRouter()

// ── Data ────────────────────────────────────────────────────
const loading       = ref(true)
const allProfiles   = ref([])
const relationships = ref([])
const logs          = ref([])
const logBox        = ref(null)

// ── Agent count ──────────────────────────────────────────────
const agentCount = ref(10)

// ── Selected agents (deterministic spread) ───────────────────
const selectedAgents = computed(() => {
  const sorted = [...allProfiles.value].sort((a, b) => a.user_id.localeCompare(b.user_id))
  const n = agentCount.value
  if (!sorted.length || !n) return []
  const step = sorted.length / n
  return Array.from({ length: n }, (_, i) =>
    sorted[Math.min(Math.floor(i * step), sorted.length - 1)]
  )
})

// ── Distribution stats ────────────────────────────────────────
const dist = computed(() => {
  const a = selectedAgents.value
  const n = a.length || 1
  const male   = a.filter(x => x.gender === 'male').length
  const female = a.filter(x => x.gender === 'female').length
  const occ    = (p) => { const o = (p.occupation||'').toLowerCase(); return o.includes('博士') || o.includes('研究生') || o.includes('硕士') }
  const grad   = a.filter(occ).length
  return { male, female, ugrad: n - grad, grad }
})

// ── Active edge count (between selected agents) ───────────────
const activeEdgeCount = computed(() => {
  const ids = new Set(selectedAgents.value.map(a => a.user_id))
  return relationships.value.filter(r => ids.has(r.agent1) && ids.has(r.agent2)).length
})

const avgDegree = computed(() => {
  const n = agentCount.value
  return n > 0 ? (activeEdgeCount.value * 2 / n).toFixed(1) : '—'
})

// ── Slider style helper ───────────────────────────────────────
function sliderStyle(val, min, max) {
  const pct = ((val - min) / (max - min) * 100).toFixed(1) + '%'
  return `background: linear-gradient(to right, var(--purple) ${pct}, var(--border) ${pct})`
}

// ── Logging ──────────────────────────────────────────────────
function log(html) {
  const t = new Date().toTimeString().slice(0, 8)
  logs.value.push(`<span class="log-time">[${t}]</span> ${html}`)
  nextTick(() => { if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight })
}

// ── Next Step ─────────────────────────────────────────────────
function nextStep() {
  localStorage.setItem('agentParams', JSON.stringify({
    num_agents: agentCount.value,
    agent_ids:  selectedAgents.value.map(a => a.user_id),
  }))
  log(`Selected <span class="log-info">${agentCount.value}</span> agents — proceeding to simulation`)
  setTimeout(() => router.push('/simulation'), 300)
}

// ── Log when agent count changes ──────────────────────────────
watch(agentCount, (v) => {
  log(`Selected <span class="log-info">${v}</span> agents — rebuilding network…`)
})

// ── Fetch data ────────────────────────────────────────────────
onMounted(async () => {
  log('Connecting to backend…')
  try {
    const [profiles, relData] = await Promise.all([getProfiles(), getRelationships()])
    allProfiles.value   = profiles
    relationships.value = relData.relationships || []
    log(`<span class="log-ok">✓</span> <span class="log-info">${profiles.length}</span> profiles loaded`)
    log(`<span class="log-ok">✓</span> <span class="log-info">${relationships.value.length}</span> relationships loaded`)
    log('Network ready')
  } catch (err) {
    log(`<span class="log-err">Error: ${err.message} — start the Flask server first</span>`)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.setup-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: var(--bg);
}

/* Step indicator */
.step-indicator { display: flex; align-items: center; gap: 6px; }
.step-pip {
  display: flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%;
  font-size: 11px; font-weight: 600;
  background: var(--border); color: var(--text-muted);
}
.step-pip.active { background: var(--grad); color: #fff; }
.step-line { width: 24px; height: 1px; background: var(--border); }
.step-label { font-size: 11px; color: var(--text-dim); margin-left: 6px; }

/* Workspace */
.workspace { display: flex; flex: 1; overflow: hidden; }

/* Config pane */
.config-pane {
  width: 340px; flex-shrink: 0;
  display: flex; flex-direction: column; overflow: hidden;
  background: var(--surface); border-left: 1px solid var(--border);
}
.config-scroll { flex: 1; overflow-y: auto; padding: 20px 20px 0; }
.config-scroll::-webkit-scrollbar { width: 4px; }
.config-scroll::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 2px; }

.cfg-section { margin-bottom: 24px; }
.cfg-section-title {
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .8px; color: var(--text-muted); margin-bottom: 14px;
  display: flex; align-items: center; gap: 8px;
}
.cfg-section-title::after { content: ''; flex: 1; height: 1px; background: var(--border); }

.agent-slider-wrap {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px; margin-bottom: 12px;
}
.slider-header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 12px; }
.slider-label { font-size: 13px; font-weight: 500; }
.slider-sub   { font-size: 11px; color: var(--text-muted); }
.slider-val {
  font-size: 26px; font-weight: 800;
  background: var(--grad);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}

input[type=range] {
  -webkit-appearance: none; appearance: none;
  width: 100%; height: 4px; border-radius: 2px; outline: none; cursor: pointer;
}
input[type=range]::-webkit-slider-thumb {
  -webkit-appearance: none; width: 16px; height: 16px; border-radius: 50%;
  background: var(--purple); box-shadow: 0 0 0 3px rgba(124,58,237,.15);
}

.slider-ticks {
  display: flex; justify-content: space-between; margin-top: 4px;
  font-size: 11px; color: var(--text-muted);
}
.tick-val { font-size: 12px; font-weight: 600; color: var(--purple); }

.dist-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 4px; }
.dist-item { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; }
.dist-item-val   { font-size: 18px; font-weight: 700; color: var(--text); }
.dist-item-label { font-size: 11px; color: var(--text-dim); margin-top: 2px; }
.dist-bar-wrap   { height: 3px; background: var(--border); border-radius: 2px; margin-top: 8px; }
.dist-bar-fill   { height: 100%; border-radius: 2px; transition: width .3s; }

.stats-row { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; margin-bottom: 16px; }
.stat-box { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 10px; text-align: center; }
.stat-box-val   { font-size: 18px; font-weight: 700; color: var(--text); }
.stat-box-label { font-size: 10px; color: var(--text-muted); margin-top: 2px; font-weight: 500; }

.form-row { margin-bottom: 12px; }
.form-label { display: block; font-size: 12px; font-weight: 500; color: var(--text-dim); margin-bottom: 5px; }
.form-control {
  width: 100%; background: var(--bg); border: 1px solid var(--border);
  border-radius: 7px; padding: 8px 11px; font-size: 13px;
  color: var(--text); outline: none; transition: border-color .15s; font-family: inherit;
}
.form-control:focus { border-color: var(--purple); }
select.form-control { cursor: pointer; }

.log-box {
  background: #f1f3f8; border: 1px solid var(--border);
  border-radius: 8px; padding: 10px 12px;
  font-family: 'SF Mono','Fira Code',monospace; font-size: 11px;
  color: var(--text-dim); line-height: 1.9; max-height: 100px; overflow-y: auto;
}

.config-footer { padding: 16px 20px; border-top: 1px solid var(--border); flex-shrink: 0; }
.btn-start-sim {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  background: var(--grad); color: #fff; font-weight: 600; font-size: 14px;
  padding: 13px; border-radius: 10px; border: none; cursor: pointer;
  width: 100%; transition: opacity .2s, transform .15s, box-shadow .2s;
  font-family: inherit;
}
.btn-start-sim:hover { opacity: .9; transform: translateY(-1px); box-shadow: 0 6px 24px rgba(124,58,237,.3); }
.btn-start-sim:disabled { opacity: .4; cursor: not-allowed; transform: none; box-shadow: none; }
</style>

<style>
/* Log colors (used in v-html) */
.log-time { color: var(--text-muted); }
.log-ok   { color: #16a34a; }
.log-info { color: var(--purple); }
.log-err  { color: #dc2626; }
</style>
