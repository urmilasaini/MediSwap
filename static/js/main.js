/* ═══════════════════════════════════════════════════════════════════════════
   PharmaAI — frontend
   ═══════════════════════════════════════════════════════════════════════════ */

const API = '';          // same-origin; change if backend runs elsewhere
const DEBOUNCE_MS = 320;

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  mode: 'fuzzy',         // 'fuzzy' | 'semantic'
  query: '',
  lastResults: [],
  selectedId: null,
  indexReady: false,
  indexBuilding: false,
};

// ── DOM refs ───────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const searchInput   = $('searchInput');
const resultsSection = $('resultsSection');
const detailSection  = $('detailSection');
const resultsGrid    = $('resultsGrid');
const resultsMeta    = $('resultsMeta');
const detailMain     = $('detailMain');
const detailSide     = $('detailSide');
const statusDot      = $('statusDot');
const statusText     = $('statusText');

// ── Utilities ──────────────────────────────────────────────────────────────
function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

async function apiFetch(path) {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function categoryClass(cat) {
  const map = {
    'Analgesic': 'analgesic',
    'Anti-inflammatory': 'anti-inflammatory',
    'Antibiotic': 'antibiotic',
    'Antidiabetic': 'antidiabetic',
    'Antihypertensive': 'antihypertensive',
    'Statin': 'statin',
    'Proton Pump Inhibitor': 'ppi',
    'Antihistamine': 'antihistamine',
    'Bronchodilator': 'bronchodilator',
    'Vitamin': 'vitamin',
    'Thyroid': 'thyroid',
    'Antidepressant': 'antidepressant',
  };
  return `badge badge-${map[cat] || 'default'}`;
}

function scoreColor(score) {
  if (score >= 90) return '#22c55e';
  if (score >= 75) return '#f59e0b';
  return '#94a3b8';
}

function toast(msg, ms = 2800) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  })[char]);
}

function splitList(value) {
  return String(value || '')
    .split(/[,;|]\s*/)
    .map(item => item.trim())
    .filter(Boolean);
}

function renderTags(value, className) {
  const items = splitList(value);
  if (!items.length) return '<span class="detail-empty">Not available</span>';
  return items.map(item =>
    `<span class="${className}">${escapeHTML(item)}</span>`
  ).join('');
}

function reviewBar(label, value, tone) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  const displayPct = Number.isInteger(pct) ? pct : pct.toFixed(1);
  return `
    <div class="review-row">
      <div class="review-meta">
        <span>${label}</span>
        <strong>${displayPct}%</strong>
      </div>
      <div class="review-track" role="progressbar" aria-label="${label} reviews"
           aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}">
        <span class="review-fill review-${tone}" style="width:${pct}%"></span>
      </div>
    </div>`;
}

// ── Status poll ────────────────────────────────────────────────────────────
async function pollStatus() {
  try {
    const s = await apiFetch('/api/status');
    state.indexReady    = s.index_ready;
    state.indexBuilding = s.index_building;

    if (s.medicines_loaded === 0) {
      setStatus('warn', `No medicines loaded`);
    } else if (s.index_ready) {
      setStatus('ok', `${s.medicines_loaded} medicines · ${s.vector_count} vectors`);
    } else if (s.index_building) {
      setStatus('warn', 'Building AI index…');
      setTimeout(pollStatus, 3000);
    } else {
      setStatus('warn', `${s.medicines_loaded} medicines · AI index pending`);
    }
  } catch {
    setStatus('error', 'Backend offline');
  }
}

function setStatus(type, text) {
  statusDot.className = `status-dot ${type}`;
  statusText.textContent = text;
}

// ── Mode toggle ────────────────────────────────────────────────────────────
document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    state.mode = btn.dataset.mode;
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    if (state.query) performSearch(state.query);
  });
});

// ── Quick chips ────────────────────────────────────────────────────────────
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const q    = chip.dataset.q;
    const mode = chip.dataset.mode || 'fuzzy';
    state.mode = mode;
    document.querySelectorAll('.mode-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.mode === mode));
    searchInput.value = q;
    performSearch(q);
  });
});

// ── Search input ───────────────────────────────────────────────────────────
searchInput.addEventListener('input', debounce(e => {
  const q = e.target.value.trim();
  state.query = q;
  if (!q) { hideAll(); return; }
  performSearch(q);
}, DEBOUNCE_MS));

document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    searchInput.focus();
  }
  if (e.key === 'Escape') {
    if (!detailSection.classList.contains('hidden')) showResults();
    else { searchInput.value = ''; state.query = ''; hideAll(); }
  }
});

// ── Search ─────────────────────────────────────────────────────────────────
async function performSearch(q) {
  showSkeletons();
  try {
    if (state.mode === 'semantic') {
      await semanticSearch(q);
    } else {
      await fuzzySearch(q);
    }
  } catch (err) {
    showError(err.message);
  }
}

async function fuzzySearch(q) {
  const data = await apiFetch(`/api/search?q=${encodeURIComponent(q)}&limit=12`);
  state.lastResults = data.results;
  renderResults(data);
}

async function semanticSearch(q) {
  const data = await apiFetch(`/api/semantic?q=${encodeURIComponent(q)}&limit=10`);

  if (!data.index_ready) {
    renderIndexNotReady();
    // Also run fuzzy in background
    const fb = await apiFetch(`/api/search?q=${encodeURIComponent(q)}&limit=12`);
    state.lastResults = fb.results;
    renderResults(fb, /* semanticFallback */ true);
    return;
  }

  // Map semantic hits into same shape as search hits
  const results = data.results.map(r => ({ ...r, score: Math.round(r.score * 100) }));
  state.lastResults = results;
  renderResults({ query: data.query, results, total: results.length }, false, true);
}

// ── Render results ─────────────────────────────────────────────────────────
function renderResults(data, semanticFallback = false, isSemantic = false) {
  showSection(resultsSection);
  detailSection.classList.add('hidden');

  const label = isSemantic ? 'AI results' : semanticFallback ? 'fuzzy results (AI index building)' : 'results';
  resultsMeta.innerHTML = `<strong>${data.total}</strong> ${label} for "<em>${data.query}</em>"`;

  if (!data.results.length) {
    resultsGrid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-icon">🔬</div>
        <p>No medicines found for "<strong>${data.query}</strong>"</p>
        <p style="margin-top:.5rem;font-size:.8rem">Try a different spelling or switch to AI Search</p>
      </div>`;
    return;
  }

  resultsGrid.innerHTML = data.results.map(r => `
    <div class="result-card" data-id="${r.id}" tabindex="0">
      <div class="rc-name">${r.brand_name}</div>
      <div class="rc-comp">${r.composition}</div>
      <span class="${categoryClass(r.category)}">${r.category}</span>
      <div class="rc-foot">
        <span class="rc-mfr">${r.manufacturer}</span>
        <span class="rc-score" style="color:${scoreColor(r.score)}">${r.score}%</span>
      </div>
    </div>
  `).join('');

  resultsGrid.querySelectorAll('.result-card').forEach(card => {
    card.addEventListener('click', () => loadDetail(+card.dataset.id));
    card.addEventListener('keydown', e => { if (e.key === 'Enter') loadDetail(+card.dataset.id); });
  });
}

function renderIndexNotReady() {
  state.indexBuilding = true;
}

// ── Detail view ────────────────────────────────────────────────────────────
async function loadDetail(id) {
  state.selectedId = id;
  showSection(detailSection);
  resultsSection.classList.add('hidden');

  detailMain.innerHTML = skeletonCard(200);
  detailSide.innerHTML = skeletonCard(150) + skeletonCard(180);

  try {
    const [detail, semantic] = await Promise.all([
      apiFetch(`/api/medicine/${id}`),
      apiFetch(`/api/semantic?q=${encodeURIComponent(buildSemanticQuery(id))}&limit=6`)
        .catch(() => ({ results: [], index_ready: false })),
    ]);
    renderDetail(detail, semantic);
  } catch (err) {
    detailMain.innerHTML = `<div class="empty-state"><p>Failed to load: ${err.message}</p></div>`;
  }
}

function buildSemanticQuery(id) {
  const hit = state.lastResults.find(r => r.id === id);
  if (hit) return `${hit.brand_name} ${hit.composition || ''} ${hit.category || ''}`;
  return String(id);
}

function renderDetail(detail, semantic) {
  const m = detail.medicine;
  const usesHTML = renderTags(m.uses, 'use-tag');
  const sideEffectsHTML = renderTags(m.side_effects, 'side-effect-tag');
  const hasReviews = [
    m.excellent_review_pct,
    m.average_review_pct,
    m.poor_review_pct,
  ].some(value => Number(value) > 0);

  detailMain.innerHTML = `
    <div class="med-card">
      <div class="med-card-header">
        <div class="med-card-name">${m.brand_name}</div>
        <span class="${categoryClass(m.category)}">${m.category}</span>
      </div>
      <div class="med-card-body">
        <div class="info-row">
          <span class="info-label">Composition</span>
          <span class="info-value mono">${m.composition}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Salt / Generic</span>
          <span class="info-value">${m.salt_name}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Strength</span>
          <span class="info-value">${m.strength}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Manufacturer</span>
          <span class="info-value">${m.manufacturer}</span>
        </div>
        ${m.description ? `
        <div class="info-row">
          <span class="info-label">About</span>
          <span class="info-value" style="font-size:.84rem;color:var(--text-2)">${m.description}</span>
        </div>` : ''}
      </div>
    </div>
    <div class="detail-panel">
      <div class="detail-panel-title">Common uses</div>
      <div class="tag-list">${usesHTML}</div>
    </div>
    <div class="detail-panel">
      <div class="detail-panel-title">Possible side effects</div>
      <div class="tag-list">${sideEffectsHTML}</div>
    </div>
    <div class="detail-panel">
      <div class="detail-panel-title">User reviews</div>
      ${hasReviews ? `
        <div class="reviews">
          ${reviewBar('Excellent', m.excellent_review_pct, 'excellent')}
          ${reviewBar('Average', m.average_review_pct, 'average')}
          ${reviewBar('Poor', m.poor_review_pct, 'poor')}
        </div>
      ` : '<span class="detail-empty">No review data available</span>'}
    </div>
  `;

  // Alternatives panel
  let altHTML = '';
  if (detail.alternatives.length) {
    altHTML = detail.alternatives.map(a => `
      <div class="alt-item" data-id="${a.id}" tabindex="0">
        <div>
          <div class="alt-name">${a.brand_name}</div>
          <div class="alt-mfr">${a.manufacturer}</div>
        </div>
        <span class="alt-arrow">→</span>
      </div>
    `).join('');
  } else {
    altHTML = `<div class="empty-state" style="padding:1.5rem">
      <p>No other brands found for this exact composition.</p></div>`;
  }

  // Semantic panel
  let semHTML = '';
  const semResults = (semantic.results || []).filter(r => r.id !== m.id);

  if (!semantic.index_ready) {
    semHTML = `<div class="index-banner">
      <span class="spin">⟳</span>
      AI index is building… check back in a moment.
    </div>`;
  } else if (semResults.length) {
    semHTML = semResults.map(r => {
      const pct = Math.round(r.score * 100);
      return `
        <div class="sem-item" data-id="${r.id}" tabindex="0">
          <div class="sem-score-bar" style="--pct:${pct}" data-score="${pct}%"></div>
          <div class="sem-info">
            <div class="sem-name">${r.brand_name}</div>
            <div class="sem-cat">${r.category} · ${r.manufacturer}</div>
          </div>
        </div>`;
    }).join('');
  } else {
    semHTML = `<div class="empty-state" style="padding:1.5rem">
      <p>No similar medicines found.</p></div>`;
  }

  detailSide.innerHTML = `
    <div class="side-panel">
      <div class="panel-header">
        <span><span class="panel-icon">💊</span> Same Composition</span>
        <span class="panel-count">${detail.alternatives_count}</span>
      </div>
      <div class="panel-body">${altHTML}</div>
    </div>
    <div class="side-panel">
      <div class="panel-header">
        <span><span class="panel-icon">✨</span> AI Recommendations</span>
        <span class="panel-count">${semResults.length}</span>
      </div>
      <div class="panel-body">${semHTML}</div>
    </div>
  `;

  // Wire up click handlers
  detailSide.querySelectorAll('.alt-item, .sem-item').forEach(el => {
    el.addEventListener('click', () => loadDetail(+el.dataset.id));
    el.addEventListener('keydown', e => { if (e.key === 'Enter') loadDetail(+el.dataset.id); });
  });
}

// ── Navigation ─────────────────────────────────────────────────────────────
$('backBtn').addEventListener('click', showResults);

function showResults() {
  detailSection.classList.add('hidden');
  if (state.lastResults.length) showSection(resultsSection);
}

function showSection(el) {
  el.classList.remove('hidden');
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function hideAll() {
  resultsSection.classList.add('hidden');
  detailSection.classList.add('hidden');
}

// ── Skeleton helpers ───────────────────────────────────────────────────────
function showSkeletons() {
  showSection(resultsSection);
  detailSection.classList.add('hidden');
  resultsMeta.textContent = 'Searching…';
  resultsGrid.innerHTML = Array(6).fill('<div class="skeleton sk-card"></div>').join('');
}

function skeletonCard(h) {
  return `<div class="skeleton" style="height:${h}px;border-radius:12px;margin-bottom:1rem"></div>`;
}

function showError(msg) {
  resultsGrid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
    <div class="empty-icon">⚠️</div><p>${msg}</p></div>`;
}

// ── Init ───────────────────────────────────────────────────────────────────
pollStatus();
searchInput.focus();
