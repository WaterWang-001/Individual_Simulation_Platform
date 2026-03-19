<template>
  <div class="graph-panel">
    <!-- Header with gradient fade -->
    <div class="panel-header">
      <span class="panel-title">Population Network</span>
      <div class="header-tools">
        <span class="tb-label">Color by</span>
        <select class="tb-select" v-model="colorBy" @change="renderGraph">
          <option value="gender">Gender</option>
          <option value="occupation">Occupation</option>
        </select>
        <div class="toolbar-sep"></div>
        <select class="tb-select" v-model="edgeFilter" @change="renderGraph">
          <option value="all">All edges</option>
          <option v-for="t in relTypes" :key="t" :value="t">{{ t }}</option>
        </select>
        <div class="toolbar-sep"></div>
        <button class="tool-btn" @click="resetZoom">⊕ Fit</button>
        <button class="tool-btn" @click="reheat">↺ Re-layout</button>
      </div>
    </div>

    <!-- SVG canvas -->
    <div ref="svgWrap" class="graph-container">
      <div v-if="loading" class="graph-state">
        <div class="loading-spinner"></div>
        <p>Loading agent profiles…</p>
      </div>
      <svg ref="svgEl" class="graph-svg"></svg>
    </div>

    <!-- Tooltip -->
    <div ref="tooltipEl" class="g-tooltip">
      <div ref="ttName" class="g-tt-name"></div>
      <div ref="ttMeta" class="g-tt-row"></div>
      <div ref="ttTags" class="g-tt-tags"></div>
    </div>

    <!-- Legend: bottom-left white panel -->
    <div v-if="!loading && agents.length && entityTypes.length" class="graph-legend">
      <span class="legend-title">Legend</span>
      <div class="legend-items">
        <div class="legend-item" v-for="t in entityTypes" :key="t.name">
          <span class="legend-dot" :style="{ background: t.color }"></span>
          <span class="legend-label">{{ t.name }}</span>
        </div>
      </div>
    </div>

    <!-- Edge labels toggle: top-right -->
    <div v-if="!loading && agents.length" class="edge-labels-toggle">
      <label class="toggle-switch">
        <input type="checkbox" v-model="showEdgeLabels" @change="onToggleLabels" />
        <span class="slider-track"></span>
      </label>
      <span class="toggle-label">Show Edge Labels</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import * as d3 from 'd3'

// ── Props ────────────────────────────────────────────────────
const props = defineProps({
  agents:        { type: Array,   default: () => [] },
  relationships: { type: Array,   default: () => [] },
  loading:       { type: Boolean, default: false },
})

// ── Constants ────────────────────────────────────────────────
const NODE_R = 10
const ENTITY_COLORS = ['#FF6B35','#004E89','#7B2D8E','#1A936F','#C5283D','#E9724C','#3498db','#9b59b6','#27ae60','#f39c12']

// ── Reactive state ───────────────────────────────────────────
const colorBy       = ref('gender')
const edgeFilter    = ref('all')
const showEdgeLabels = ref(true)

// ── Template refs ────────────────────────────────────────────
const svgWrap   = ref(null)
const svgEl     = ref(null)
const tooltipEl = ref(null)
const ttName    = ref(null)
const ttMeta    = ref(null)
const ttTags    = ref(null)

// ── D3 state (not reactive) ──────────────────────────────────
let svgRoot       = null
let gRoot         = null
let zoomBehavior  = null
let simulation    = null
let resizeObs     = null
let linkLabelsSel = null
let linkLabelBgSel = null

// ── Relationship types computed ──────────────────────────────
const relTypes = computed(() => {
  const s = new Set(props.relationships.map(r => r.type).filter(Boolean))
  return [...s]
})

// ── Entity types for legend ──────────────────────────────────
const entityTypes = computed(() => {
  if (!props.agents.length) return []
  const typeMap = {}
  props.agents.forEach(a => {
    const key = getAgentType(a)
    if (!typeMap[key]) {
      typeMap[key] = { name: key, color: ENTITY_COLORS[Object.keys(typeMap).length % ENTITY_COLORS.length] }
    }
  })
  return Object.values(typeMap)
})

function getAgentType(a) {
  if (colorBy.value === 'gender') {
    if (a.gender === 'male')   return 'Male'
    if (a.gender === 'female') return 'Female'
    return 'Unknown'
  }
  const o = (a.occupation || '').toLowerCase()
  if (o.includes('博士') || o.includes('phd'))                     return 'PhD'
  if (o.includes('研究生') || o.includes('硕士') || o.includes('grad')) return 'Graduate'
  return 'Undergraduate'
}

function getAgentColor(a) {
  const type = getAgentType(a)
  const found = entityTypes.value.find(t => t.name === type)
  return found ? found.color : '#999'
}

// ── Init SVG ─────────────────────────────────────────────────
function initSVG() {
  svgRoot = d3.select(svgEl.value)
  gRoot   = svgRoot.append('g').attr('class', 'zoom-root')

  zoomBehavior = d3.zoom()
    .scaleExtent([0.1, 4])
    .on('zoom', e => gRoot.attr('transform', e.transform))
  svgRoot.call(zoomBehavior)

  svgRoot.on('click', e => {
    if (e.target === svgEl.value) resetSelection()
  })
}

// ── Render graph ─────────────────────────────────────────────
function renderGraph() {
  if (!svgRoot || !gRoot || props.loading || !props.agents.length) return

  if (simulation) simulation.stop()
  gRoot.selectAll('*').remove()
  linkLabelsSel  = null
  linkLabelBgSel = null

  const W = svgWrap.value.clientWidth
  const H = svgWrap.value.clientHeight
  svgRoot.attr('width', W).attr('height', H)

  const nodeMap = new Map(props.agents.map(a => [a.user_id, { ...a, id: a.user_id }]))
  const selectedIds = new Set(props.agents.map(a => a.user_id))

  const activeRels = props.relationships.filter(r =>
    selectedIds.has(r.agent1) && selectedIds.has(r.agent2) &&
    (edgeFilter.value === 'all' || r.type === edgeFilter.value)
  )

  // ── Build edges with MiroFish curvature ──
  const pairCount = {}, pairIndex = {}
  activeRels.forEach(r => {
    const key = [r.agent1, r.agent2].sort().join('_')
    pairCount[key] = (pairCount[key] || 0) + 1
  })

  const edges = activeRels.map(r => {
    const key        = [r.agent1, r.agent2].sort().join('_')
    const totalCount = pairCount[key]
    const curIdx     = pairIndex[key] || 0
    pairIndex[key]   = curIdx + 1

    const isReversed = r.agent1 > r.agent2
    let curvature = 0
    if (totalCount > 1) {
      const curvatureRange = Math.min(1.2, 0.6 + totalCount * 0.15)
      curvature = ((curIdx / (totalCount - 1)) - 0.5) * curvatureRange * 2
      if (isReversed) curvature = -curvature
    }
    return {
      source: r.agent1, target: r.agent2,
      type: r.type, directed: r.directed,
      curvature, pairTotal: totalCount, pairIndex: curIdx,
    }
  })

  const nodes = Array.from(nodeMap.values())

  // ── Groups ──
  const linkGroup = gRoot.append('g').attr('class', 'links')
  const nodeGroup = gRoot.append('g').attr('class', 'nodes')

  // ── Edge paths ──
  const linkSel = linkGroup.selectAll('path.edge-path')
    .data(edges).join('path')
    .attr('class', 'edge-path')
    .attr('stroke', '#C0C0C0')
    .attr('stroke-width', 1.5)
    .attr('fill', 'none')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkSel.attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      d3.select(event.currentTarget).attr('stroke', '#3498db').attr('stroke-width', 3)
      nodeSel.select('circle').attr('stroke', '#fff').attr('stroke-width', 2.5)
    })

  // ── Edge label backgrounds ──
  const linkLabelBg = linkGroup.selectAll('rect.edge-label-bg')
    .data(edges).join('rect')
    .attr('class', 'edge-label-bg')
    .attr('fill', 'rgba(255,255,255,0.95)')
    .attr('rx', 3)
    .style('display', showEdgeLabels.value ? null : 'none')
    .style('pointer-events', 'none')

  // ── Edge labels ──
  const linkLabels = linkGroup.selectAll('text.edge-label')
    .data(edges).join('text')
    .attr('class', 'edge-label')
    .text(d => d.type || '')
    .attr('font-size', '9px')
    .attr('fill', '#666')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .attr('font-family', 'system-ui, sans-serif')
    .style('display', showEdgeLabels.value ? null : 'none')
    .style('pointer-events', 'none')

  linkLabelsSel  = linkLabels
  linkLabelBgSel = linkLabelBg

  // ── Node groups ──
  const nodeSel = nodeGroup.selectAll('g.node')
    .data(nodes, d => d.id)
    .join('g').attr('class', 'node')
    .style('cursor', 'pointer')
    .call(d3.drag()
      .on('start', dragStart)
      .on('drag',  dragged)
      .on('end',   dragEnd))
    .on('click', (event, d) => {
      event.stopPropagation()
      nodeSel.select('circle').attr('stroke', '#fff').attr('stroke-width', 2.5)
      linkSel.attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      d3.select(event.currentTarget).select('circle')
        .attr('stroke', '#E91E63').attr('stroke-width', 4)
      linkSel.filter(l => {
        const s = l.source.id || l.source, t = l.target.id || l.target
        return s === d.id || t === d.id
      }).attr('stroke', '#E91E63').attr('stroke-width', 2.5)
      showTooltip(event, d)
    })
    .on('mouseenter', (event, d) => {
      const circle = d3.select(event.currentTarget).select('circle')
      if (circle.attr('stroke') !== '#E91E63')
        circle.attr('stroke', '#333').attr('stroke-width', 3)
      showTooltip(event, d)
    })
    .on('mousemove', e => moveTooltip(e))
    .on('mouseleave', (event, d) => {
      const circle = d3.select(event.currentTarget).select('circle')
      if (circle.attr('stroke') !== '#E91E63')
        circle.attr('stroke', '#fff').attr('stroke-width', 2.5)
      hideTooltip()
    })

  nodeSel.append('circle')
    .attr('r', NODE_R)
    .attr('fill', d => getAgentColor(d))
    .attr('stroke', '#fff')
    .attr('stroke-width', 2.5)

  nodeSel.append('text')
    .text(d => d.name.length > 8 ? d.name.substring(0, 8) + '…' : d.name)
    .attr('dx', 14)
    .attr('dy', 4)
    .attr('font-size', '11px')
    .attr('fill', '#333')
    .attr('font-weight', '500')
    .attr('font-family', 'system-ui, sans-serif')
    .style('pointer-events', 'none')
    .style('user-select', 'none')

  // ── Force simulation ──
  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id)
      .distance(d => 150 + ((d.pairTotal || 1) - 1) * 50))
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collide', d3.forceCollide(50))
    .force('x', d3.forceX(W / 2).strength(0.04))
    .force('y', d3.forceY(H / 2).strength(0.04))
    .alphaDecay(0.006)     // very slow cool-down so the graph stays alive
    .velocityDecay(0.35)
    .on('tick', () => {
      linkSel.attr('d', getLinkPath)
      linkLabels.each(function(d) {
        const mid = getLinkMidpoint(d)
        d3.select(this).attr('x', mid.x).attr('y', mid.y)
      })
      linkLabelBg.each(function(d, i) {
        const mid   = getLinkMidpoint(d)
        const textEl = linkLabels.nodes()[i]
        if (!textEl) return
        const bbox  = textEl.getBBox()
        d3.select(this)
          .attr('x', mid.x - bbox.width / 2 - 4)
          .attr('y', mid.y - bbox.height / 2 - 2)
          .attr('width',  bbox.width + 8)
          .attr('height', bbox.height + 4)
      })
      nodeSel.attr('transform', d => `translate(${d.x ?? W/2},${d.y ?? H/2})`)
    })
}

// ── MiroFish getLinkPath ─────────────────────────────────────
function getLinkPath(d) {
  const sx = d.source.x ?? 0, sy = d.source.y ?? 0
  const tx = d.target.x ?? 0, ty = d.target.y ?? 0

  if (d.curvature === 0) {
    return `M${sx},${sy} L${tx},${ty}`
  }

  const dx   = tx - sx, dy = ty - sy
  const dist = Math.sqrt(dx * dx + dy * dy) || 1
  const pairTotal   = d.pairTotal || 1
  const offsetRatio = 0.25 + pairTotal * 0.05
  const baseOffset  = Math.max(35, dist * offsetRatio)
  const offsetX = -dy / dist * d.curvature * baseOffset
  const offsetY =  dx / dist * d.curvature * baseOffset
  const cx = (sx + tx) / 2 + offsetX
  const cy = (sy + ty) / 2 + offsetY

  return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
}

// ── MiroFish getLinkMidpoint ──────────────────────────────────
function getLinkMidpoint(d) {
  const sx = d.source.x ?? 0, sy = d.source.y ?? 0
  const tx = d.target.x ?? 0, ty = d.target.y ?? 0

  if (d.curvature === 0) {
    return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
  }

  const dx   = tx - sx, dy = ty - sy
  const dist = Math.sqrt(dx * dx + dy * dy) || 1
  const pairTotal   = d.pairTotal || 1
  const offsetRatio = 0.25 + pairTotal * 0.05
  const baseOffset  = Math.max(35, dist * offsetRatio)
  const offsetX = -dy / dist * d.curvature * baseOffset
  const offsetY =  dx / dist * d.curvature * baseOffset
  const cx = (sx + tx) / 2 + offsetX
  const cy = (sy + ty) / 2 + offsetY

  return {
    x: 0.25 * sx + 0.5 * cx + 0.25 * tx,
    y: 0.25 * sy + 0.5 * cy + 0.25 * ty,
  }
}

// ── Drag ─────────────────────────────────────────────────────
function dragStart(e, d) {
  if (!e.active) simulation.alphaTarget(0.3).restart()
  d.fx = d.x; d.fy = d.y
}
function dragged(e, d) {
  d.fx = e.x; d.fy = e.y
}
function dragEnd(e, d) {
  if (!e.active) simulation.alphaTarget(0)
  d.fx = null; d.fy = null
}

// ── Selection reset ──────────────────────────────────────────
function resetSelection() {
  if (!gRoot) return
  gRoot.selectAll('circle').attr('stroke', '#fff').attr('stroke-width', 2.5)
  gRoot.selectAll('path.edge-path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
  hideTooltip()
}

// ── Edge labels toggle ───────────────────────────────────────
function onToggleLabels() {
  const show = showEdgeLabels.value
  if (linkLabelsSel)  linkLabelsSel.style('display', show ? null : 'none')
  if (linkLabelBgSel) linkLabelBgSel.style('display', show ? null : 'none')
}

// ── Tooltip ──────────────────────────────────────────────────
function showTooltip(e, d) {
  ttName.value.textContent = d.name
  ttMeta.value.innerHTML = `${d.gender === 'male' ? '♂' : '♀'} ${d.age ?? '?'} · ${d.occupation || ''}<br>${d.major || '—'}`
  ttTags.value.innerHTML = (d.interests || []).slice(0, 3)
    .map(t => `<span class="g-tt-tag">${t}</span>`).join('')
  tooltipEl.value.style.display = 'block'
  moveTooltip(e)
}
function moveTooltip(e) {
  const rect = svgWrap.value.getBoundingClientRect()
  const tt   = tooltipEl.value
  tt.style.left = Math.min(e.clientX - rect.left + 14, rect.width  - 245) + 'px'
  tt.style.top  = Math.max(e.clientY - rect.top  - 40, 4) + 'px'
}
function hideTooltip() {
  if (tooltipEl.value) tooltipEl.value.style.display = 'none'
}

// ── Zoom helpers ─────────────────────────────────────────────
function resetZoom() {
  if (!svgRoot || !zoomBehavior) return
  const W = svgWrap.value.clientWidth, H = svgWrap.value.clientHeight
  svgRoot.transition().duration(500)
    .call(zoomBehavior.transform, d3.zoomIdentity.translate(W / 2, H / 2).scale(1).translate(-W / 2, -H / 2))
}
function reheat() { if (simulation) simulation.alpha(0.6).restart() }

// ── Lifecycle ────────────────────────────────────────────────
onMounted(() => {
  initSVG()
  if (props.agents.length && !props.loading) renderGraph()

  resizeObs = new ResizeObserver(() => {
    if (!simulation || !svgWrap.value) return
    const W = svgWrap.value.clientWidth, H = svgWrap.value.clientHeight
    svgRoot.attr('width', W).attr('height', H)
    simulation
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('x', d3.forceX(W / 2).strength(0.04))
      .force('y', d3.forceY(H / 2).strength(0.04))
      .alpha(0.1).restart()
  })
  resizeObs.observe(svgWrap.value)
})

onBeforeUnmount(() => {
  if (simulation) simulation.stop()
  if (resizeObs)  resizeObs.disconnect()
})

watch(() => props.agents,       () => { if (!props.loading) renderGraph() }, { deep: false })
watch(() => props.relationships, () => { if (!props.loading) renderGraph() }, { deep: false })
watch(() => props.loading, v => { if (!v && props.agents.length) renderGraph() })
</script>

<style scoped>
/* ── Main panel with MiroFish dot-grid background ── */
.graph-panel {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #FAFAFA;
  background-image: radial-gradient(#D0D0D0 1.5px, transparent 1.5px);
  background-size: 24px 24px;
  overflow: hidden;
}

/* ── Header: gradient fade from white ── */
.panel-header {
  position: absolute;
  top: 0; left: 0; right: 0;
  padding: 12px 20px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  background: linear-gradient(to bottom, rgba(255,255,255,0.97) 60%, rgba(255,255,255,0));
  pointer-events: none;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-right: 4px;
  pointer-events: auto;
}

.header-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  pointer-events: auto;
}

.toolbar-sep { width: 1px; height: 16px; background: #E0E0E0; }

.tb-label { font-size: 11px; color: #888; font-weight: 500; }

.tb-select {
  background: #FFF;
  border: 1px solid #E0E0E0;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  color: #333;
  outline: none;
  cursor: pointer;
  font-family: inherit;
}
.tb-select:focus { border-color: #7B2D8E; }

.tool-btn {
  height: 28px;
  padding: 0 10px;
  background: #FFF;
  border: 1px solid #E0E0E0;
  border-radius: 6px;
  font-size: 12px;
  color: #666;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
  display: flex;
  align-items: center;
  gap: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.tool-btn:hover { background: #F5F5F5; color: #333; border-color: #CCC; }

/* ── SVG container fills full panel ── */
.graph-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.graph-svg {
  width: 100%;
  height: 100%;
  display: block;
}

/* ── Loading state ── */
.graph-state {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #999;
  z-index: 5;
}

.loading-spinner {
  width: 36px; height: 36px;
  border: 3px solid #E0E0E0;
  border-top-color: #7B2D8E;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 14px;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Tooltip ── */
.g-tooltip {
  position: absolute;
  pointer-events: none;
  z-index: 30;
  background: #FFF;
  border: 1px solid #EAEAEA;
  border-radius: 10px;
  padding: 12px 14px;
  min-width: 190px; max-width: 230px;
  box-shadow: 0 8px 28px rgba(0,0,0,0.12);
  display: none;
}
.g-tt-name { font-size: 13px; font-weight: 600; color: #333; margin-bottom: 5px; }
.g-tt-row  { font-size: 11px; color: #666; line-height: 1.7; }
.g-tt-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }

/* ── Legend: bottom-left white panel ── */
.graph-legend {
  position: absolute;
  bottom: 24px; left: 24px;
  background: rgba(255,255,255,0.95);
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid #EAEAEA;
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  z-index: 10;
}

.legend-title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #E91E63;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.legend-items { display: flex; flex-wrap: wrap; gap: 8px 14px; max-width: 300px; }
.legend-item  { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #555; }
.legend-dot   { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.legend-label { white-space: nowrap; }

/* ── Edge labels toggle: top-right ── */
.edge-labels-toggle {
  position: absolute;
  top: 60px; right: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: #FFF;
  padding: 8px 14px;
  border-radius: 20px;
  border: 1px solid #E0E0E0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  z-index: 10;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px; height: 22px;
}
.toggle-switch input { opacity: 0; width: 0; height: 0; }

.slider-track {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background: #E0E0E0;
  border-radius: 22px;
  transition: 0.3s;
}
.slider-track::before {
  content: '';
  position: absolute;
  width: 16px; height: 16px;
  left: 3px; bottom: 3px;
  background: #FFF;
  border-radius: 50%;
  transition: 0.3s;
}
input:checked + .slider-track { background: #7B2D8E; }
input:checked + .slider-track::before { transform: translateX(18px); }

.toggle-label { font-size: 12px; color: #666; }
</style>

<!-- Global: tooltip tags rendered via innerHTML -->
<style>
.g-tt-tag {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 8px;
  background: rgba(123, 45, 142, 0.10);
  color: #7B2D8E;
  font-weight: 500;
}
</style>
