<template>
  <div class="home">
    <!-- Decorative background -->
    <div class="bg-grid"></div>
    <div class="bg-glow bg-glow-1"></div>
    <div class="bg-glow bg-glow-2"></div>

    <NavBar :centered="true" />

    <main>
      <!-- Hero -->
      <section class="hero">
        <h1 class="hero-title">
          Simulate<br>
          <span class="grad">Human Behavior</span>
        </h1>
        <p class="hero-sub">
          A long-horizon individual simulation engine powered by
          memory, beliefs, and intentions — grounded in real urban environments.
        </p>
        <div class="hero-cta">
          <RouterLink to="/setup" class="btn-primary">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="5,3 13,8 5,13"/>
            </svg>
            Start Simulation
          </RouterLink>
          <RouterLink to="/setup" class="btn-secondary">
            🧪 Try Example Scenario
          </RouterLink>
        </div>
        <p class="hero-hint">
          From <span>beliefs</span> to <span>intentions</span>,
          simulate how humans think and act over time.
        </p>
      </section>

      <!-- Feature Cards -->
      <section class="features" id="scenarios">
        <div class="features-label reveal">Core Capabilities</div>
        <div class="cards-grid">
          <div class="card reveal reveal-delay-1">
            <div class="card-icon card-icon-1">🧬</div>
            <div class="card-title">Persona Simulation</div>
            <div class="card-desc">
              Generate realistic behavior trajectories based on structured user profiles —
              personality, needs, memory, and social relationships.
            </div>
            <span class="card-tag card-tag-1">Profile-driven</span>
          </div>
          <div class="card reveal reveal-delay-2">
            <div class="card-icon card-icon-2">🏙️</div>
            <div class="card-title">Scenario-based Planning</div>
            <div class="card-desc">
              Simulate decisions and spatial movement under dynamic urban environments,
              from campus life to city-scale daily routines.
            </div>
            <span class="card-tag card-tag-2">Environment-aware</span>
          </div>
          <div class="card reveal reveal-delay-3">
            <div class="card-icon card-icon-3">📈</div>
            <div class="card-title">Long-term Evolution</div>
            <div class="card-desc">
              Observe how needs shift, social bonds evolve, and behavioral patterns
              emerge across hours, days, or weeks of simulation time.
            </div>
            <span class="card-tag card-tag-3">Temporal modeling</span>
          </div>
        </div>
      </section>

      <!-- Demo CTA -->
      <section class="demo-section" id="method">
        <div class="demo-inner reveal">
          <h2 class="demo-title">Explore the Simulation</h2>
          <p class="demo-desc">
            Configure your agents, inspect their social network,
            then watch them navigate a real city map in real time.
          </p>
          <div class="demo-steps">
            <div class="demo-step">
              <div class="step-num">1</div>
              <div class="step-lbl">Configure</div>
            </div>
            <div class="demo-step">
              <div class="step-num">2</div>
              <div class="step-lbl">Relationships</div>
            </div>
            <div class="demo-step">
              <div class="step-num">3</div>
              <div class="step-lbl">Simulate</div>
            </div>
            <div class="demo-step">
              <div class="step-num">4</div>
              <div class="step-lbl">Analyze</div>
            </div>
          </div>
          <RouterLink to="/setup" class="btn-primary" style="font-size:15px;padding:14px 36px">
            Launch Interactive Demo
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 8h10M9 4l4 4-4 4"/>
            </svg>
          </RouterLink>
        </div>
      </section>
    </main>

    <footer class="site-footer">
      <span>© 2025 LifeNetSim · Fudan DISC Lab</span>
      <span>Built with BDI cognitive modeling · Shanghai urban map</span>
      <a href="#">Back to top ↑</a>
    </footer>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import NavBar from '../components/NavBar.vue'

onMounted(() => {
  const obs = new IntersectionObserver(
    entries => entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible') }),
    { threshold: 0.15 }
  )
  document.querySelectorAll('.reveal').forEach(el => obs.observe(el))
})
</script>

<style scoped>
.home { background: var(--bg); color: var(--text); overflow-x: hidden; }

/* Background */
.bg-grid {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image:
    linear-gradient(rgba(124,58,237,.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(124,58,237,.06) 1px, transparent 1px);
  background-size: 48px 48px;
}
.bg-glow {
  position: fixed; width: 700px; height: 700px; border-radius: 50%;
  filter: blur(160px); pointer-events: none; z-index: 0;
}
.bg-glow-1 {
  background: rgba(124,58,237,.06); top: -200px; left: -200px;
  animation: drift1 18s ease-in-out infinite alternate;
}
.bg-glow-2 {
  background: rgba(37,99,235,.05); bottom: -200px; right: -200px;
  animation: drift2 22s ease-in-out infinite alternate;
}
@keyframes drift1 { to { transform: translate(80px,60px); } }
@keyframes drift2 { to { transform: translate(-60px,-80px); } }

main { position: relative; z-index: 1; }

/* Hero */
.hero {
  min-height: 100vh;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; padding: 120px 24px 80px;
}
.hero-title {
  font-size: clamp(48px, 7vw, 88px); font-weight: 800;
  letter-spacing: -2.5px; line-height: 1.05; margin-bottom: 28px;
  animation: fadeUp .6s .1s ease both;
}
.hero-title .grad {
  background: var(--grad);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.hero-sub {
  max-width: 560px; font-size: 17px; font-weight: 400;
  color: var(--text-dim); line-height: 1.7; margin-bottom: 44px;
  animation: fadeUp .6s .2s ease both;
}
.hero-cta {
  display: flex; gap: 14px; flex-wrap: wrap; justify-content: center;
  margin-bottom: 52px; animation: fadeUp .6s .3s ease both;
}
.btn-primary {
  display: inline-flex; align-items: center; gap: 8px;
  background: var(--grad); color: #fff; font-weight: 600; font-size: 14px;
  padding: 13px 28px; border-radius: 10px; text-decoration: none; border: none; cursor: pointer;
  transition: opacity .2s, transform .15s, box-shadow .2s;
}
.btn-primary:hover { opacity: .9; transform: translateY(-2px); box-shadow: 0 8px 32px rgba(167,139,250,.3); }
.btn-secondary {
  display: inline-flex; align-items: center; gap: 8px;
  background: transparent; color: var(--text); font-weight: 500; font-size: 14px;
  padding: 12px 28px; border-radius: 10px; text-decoration: none;
  border: 1px solid var(--border); cursor: pointer; transition: background .15s, border-color .15s, transform .15s;
}
.btn-secondary:hover { background: rgba(0,0,0,.03); border-color: rgba(167,139,250,.4); transform: translateY(-2px); }
.hero-hint { font-size: 13px; color: var(--text-muted); animation: fadeUp .6s .4s ease both; }
.hero-hint span { color: var(--purple); font-style: italic; }

/* Feature cards */
.features { padding: 60px 24px 100px; max-width: 1080px; margin: 0 auto; }
.features-label {
  text-align: center; font-size: 11px; font-weight: 600;
  letter-spacing: 2px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 48px;
}
.cards-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 20px; }
.card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 28px 26px; transition: border-color .2s, transform .2s, box-shadow .2s;
  position: relative; overflow: hidden;
}
.card::before {
  content: ''; position: absolute; inset: 0;
  background: var(--grad-soft); opacity: 0; transition: opacity .2s; border-radius: inherit;
}
.card:hover { border-color: rgba(167,139,250,.35); transform: translateY(-4px); box-shadow: 0 12px 40px rgba(0,0,0,.08); }
.card:hover::before { opacity: 1; }
.card-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; margin-bottom: 18px; position: relative; z-index: 1; }
.card-icon-1 { background: rgba(167,139,250,.15); }
.card-icon-2 { background: rgba(96,165,250,.15); }
.card-icon-3 { background: rgba(52,211,153,.15); }
.card-title { font-size: 15px; font-weight: 600; color: var(--text); margin-bottom: 8px; position: relative; z-index: 1; }
.card-desc  { font-size: 13px; color: var(--text-dim); line-height: 1.65; position: relative; z-index: 1; }
.card-tag { display: inline-block; margin-top: 14px; font-size: 11px; font-weight: 500; padding: 3px 9px; border-radius: 10px; position: relative; z-index: 1; }
.card-tag-1 { background: rgba(167,139,250,.12); color: var(--purple); }
.card-tag-2 { background: rgba(96,165,250,.12);  color: var(--blue); }
.card-tag-3 { background: rgba(52,211,153,.12);  color: #34d399; }

/* Demo CTA */
.demo-section { padding: 80px 24px 120px; text-align: center; position: relative; }
.demo-section::before {
  content: ''; position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  width: 1px; height: 80px; background: linear-gradient(var(--border), transparent);
}
.demo-inner {
  max-width: 620px; margin: 0 auto; background: var(--surface);
  border: 1px solid var(--border); border-radius: 20px; padding: 56px 48px;
  position: relative; overflow: hidden;
}
.demo-inner::after {
  content: ''; position: absolute; top: -60px; right: -60px;
  width: 200px; height: 200px; border-radius: 50%;
  background: radial-gradient(rgba(124,58,237,.08), transparent 70%); pointer-events: none;
}
.demo-title { font-size: 26px; font-weight: 700; letter-spacing: -.5px; margin-bottom: 12px; }
.demo-desc  { font-size: 14px; color: var(--text-dim); line-height: 1.7; margin-bottom: 32px; }
.demo-steps { display: flex; justify-content: center; gap: 0; margin-bottom: 36px; }
.demo-step {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  position: relative; padding: 0 24px;
}
.demo-step:not(:last-child)::after {
  content: ''; position: absolute; top: 14px; right: -2px;
  width: 28px; height: 1px; background: var(--border);
}
.step-num {
  width: 28px; height: 28px; border-radius: 50%;
  background: rgba(167,139,250,.12); border: 1px solid rgba(167,139,250,.25);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600; color: var(--purple);
}
.step-lbl { font-size: 11px; color: var(--text-dim); white-space: nowrap; }

/* Footer */
.site-footer {
  position: relative; z-index: 1; border-top: 1px solid var(--border);
  padding: 24px 48px; display: flex; align-items: center; justify-content: space-between;
  font-size: 12px; color: var(--text-muted);
}
.site-footer a { color: var(--text-muted); text-decoration: none; }
.site-footer a:hover { color: var(--text-dim); }

/* Reveal animation */
.reveal { opacity: 0; transform: translateY(24px); transition: opacity .6s ease, transform .6s ease; }
.reveal.visible { opacity: 1; transform: translateY(0); }
.reveal-delay-1 { transition-delay: .1s; }
.reveal-delay-2 { transition-delay: .2s; }
.reveal-delay-3 { transition-delay: .3s; }

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .cards-grid { grid-template-columns: 1fr; }
  .demo-inner { padding: 36px 24px; }
  .site-footer { flex-direction: column; gap: 8px; text-align: center; padding: 20px; }
}
</style>
