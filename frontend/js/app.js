/**
 * Social Wall — app.js
 * Config panel logic: keyword management, platform toggles, localStorage persistence
 */

// Online deploy'da aynı origin'den API çağrısı yapılır,
// local dev'de fallback olarak 8765 kullan
const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:8765'
  : window.location.origin;

const state = {
  keywords: [],
  platforms: {
    twitter:  true,
    facebook: true,
    linkedin: true,
    news:     true
  }
};

/* ── DOM refs ─────────────────────────────────── */
const keywordInput   = document.getElementById('keyword-input');
const addBtn         = document.getElementById('add-keyword-btn');
const tagContainer   = document.getElementById('tag-container');
const launchBtn      = document.getElementById('launch-wall-btn');
const previewBtn     = document.getElementById('preview-btn');
const keywordCount   = document.getElementById('keyword-count');
const statusDot      = document.getElementById('api-status-dot');
const statusText     = document.getElementById('api-status-text');
const platformItems  = document.querySelectorAll('.platform-item');

/* ── Init ─────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  loadFromStorage();
  renderTags();
  updatePlatformToggles();
  checkApiHealth();
  setInterval(checkApiHealth, 15000);
  bindEvents();
  animateOnLoad();
});

/* ── Events ───────────────────────────────────── */
function bindEvents() {
  addBtn.addEventListener('click', handleAddKeyword);
  keywordInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') handleAddKeyword();
  });

  launchBtn.addEventListener('click', launchWall);
  if (previewBtn) previewBtn.addEventListener('click', launchWall);

  // Platform toggles
  document.querySelectorAll('.platform-toggle-input').forEach(toggle => {
    toggle.addEventListener('change', e => {
      const platform = e.target.dataset.platform;
      state.platforms[platform] = e.target.checked;
      saveToStorage();
      updateActivePlatformCount();
    });
  });

  // Keyword input animation
  keywordInput.addEventListener('focus', () => {
    keywordInput.parentElement.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.15)';
  });
  keywordInput.addEventListener('blur', () => {
    keywordInput.parentElement.style.boxShadow = '';
  });
}

/* ── Keyword Management ───────────────────────── */
function handleAddKeyword() {
  const raw = keywordInput.value.trim();
  if (!raw) { shake(keywordInput); return; }

  const keywords = raw.split(/[,;]+/).map(k => k.trim().replace(/^#/, '')).filter(Boolean);

  let added = 0;
  keywords.forEach(kw => {
    if (!state.keywords.includes(kw) && state.keywords.length < 15) {
      state.keywords.push(kw);
      added++;
    }
  });

  if (added > 0) {
    keywordInput.value = '';
    renderTags();
    saveToStorage();
    updateLaunchButton();
    flashSuccess(addBtn);
  } else {
    shake(keywordInput);
  }
}

function removeKeyword(kw) {
  state.keywords = state.keywords.filter(k => k !== kw);
  renderTags();
  saveToStorage();
  updateLaunchButton();
}

function renderTags() {
  tagContainer.innerHTML = '';

  if (state.keywords.length === 0) {
    tagContainer.innerHTML = `
      <span style="color:var(--text-muted);font-size:13px;padding:4px 0;">
        Henüz keyword eklenmedi — yukarıdan ekleyin
      </span>`;
    keywordCount.textContent = '0';
    updateLaunchButton();
    return;
  }

  state.keywords.forEach((kw, i) => {
    const tag = document.createElement('div');
    tag.className = 'tag';
    tag.style.animationDelay = `${i * 40}ms`;
    tag.innerHTML = `
      <span>#${kw}</span>
      <button class="tag-remove" onclick="removeKeyword('${kw}')" title="Kaldır">✕</button>
    `;
    tagContainer.appendChild(tag);

    // Entrance animation
    tag.style.opacity = '0';
    tag.style.transform = 'scale(0.8)';
    requestAnimationFrame(() => {
      tag.style.transition = 'all 0.25s cubic-bezier(0.34,1.56,0.64,1)';
      tag.style.opacity = '1';
      tag.style.transform = 'scale(1)';
    });
  });

  keywordCount.textContent = state.keywords.length;
  updateLaunchButton();
}

/* ── Platform Toggles ────────────────────────── */
function updatePlatformToggles() {
  document.querySelectorAll('.platform-toggle-input').forEach(toggle => {
    const platform = toggle.dataset.platform;
    toggle.checked = state.platforms[platform] !== false;
  });
  updateActivePlatformCount();
}

function updateActivePlatformCount() {
  const count = Object.values(state.platforms).filter(Boolean).length;
  const el = document.getElementById('active-platform-count');
  if (el) el.textContent = count;
}

/* ── Launch Wall ──────────────────────────────── */
function launchWall() {
  if (state.keywords.length === 0) {
    showNotification('En az 1 keyword girmelisiniz!', 'warning');
    shake(keywordInput);
    return;
  }

  const activePlatforms = Object.entries(state.platforms)
    .filter(([, v]) => v)
    .map(([k]) => k)
    .join(',');

  if (!activePlatforms) {
    showNotification('En az 1 platform seçmelisiniz!', 'warning');
    return;
  }

  const params = new URLSearchParams({
    keywords: state.keywords.join(','),
    platforms: activePlatforms
  });

  window.open(`wall.html?${params.toString()}`, '_blank');
}

/* ── API Health Check ─────────────────────────── */
async function checkApiHealth() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);
    const res = await fetch(`${API_BASE}/api/health`, { signal: controller.signal });
    clearTimeout(timeout);

    if (res.ok) {
      statusDot.className = 'status-dot online';
      statusText.textContent = 'API Bağlı';
      statusText.style.color = '#22c55e';
    } else {
      throw new Error('not ok');
    }
  } catch {
    statusDot.className = 'status-dot offline';
    statusText.textContent = 'API Bağlanamıyor';
    statusText.style.color = '#f87171';
  }
}

/* ── localStorage ─────────────────────────────── */
function saveToStorage() {
  localStorage.setItem('sw_keywords', JSON.stringify(state.keywords));
  localStorage.setItem('sw_platforms', JSON.stringify(state.platforms));
}

function loadFromStorage() {
  try {
    const kw = localStorage.getItem('sw_keywords');
    if (kw) state.keywords = JSON.parse(kw);
    const pl = localStorage.getItem('sw_platforms');
    if (pl) state.platforms = { ...state.platforms, ...JSON.parse(pl) };
  } catch {}
}

/* ── UI Helpers ───────────────────────────────── */
function updateLaunchButton() {
  const hasKeywords = state.keywords.length > 0;
  launchBtn.disabled = !hasKeywords;
  launchBtn.style.opacity = hasKeywords ? '1' : '0.5';
  launchBtn.style.cursor  = hasKeywords ? 'pointer' : 'not-allowed';
}

function shake(el) {
  el.style.animation = 'none';
  el.offsetHeight; // reflow
  el.style.animation = 'shake 0.4s ease';
  el.addEventListener('animationend', () => el.style.animation = '', { once: true });
}

function flashSuccess(el) {
  el.style.background = 'linear-gradient(135deg,#22c55e,#16a34a)';
  el.style.boxShadow  = '0 4px 20px rgba(34,197,94,0.4)';
  setTimeout(() => {
    el.style.background = '';
    el.style.boxShadow  = '';
  }, 600);
}

function showNotification(msg, type = 'info') {
  const existing = document.querySelector('.app-toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = 'app-toast';
  toast.style.cssText = `
    position:fixed; bottom:24px; right:24px;
    background:rgba(22,27,39,0.95); border:1px solid rgba(255,255,255,0.1);
    border-left: 3px solid ${type === 'warning' ? '#f59e0b' : '#6366f1'};
    border-radius:12px; padding:14px 18px; font-size:13px; font-weight:500;
    color:#f0f4ff; backdrop-filter:blur(20px); z-index:9999;
    box-shadow:0 8px 32px rgba(0,0,0,0.4);
    transform:translateY(20px); opacity:0; transition:all 0.3s ease;
  `;
  toast.textContent = msg;
  document.body.appendChild(toast);
  requestAnimationFrame(() => {
    toast.style.transform = 'translateY(0)';
    toast.style.opacity   = '1';
  });
  setTimeout(() => {
    toast.style.opacity   = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

/* ── Page Load Animations ─────────────────────── */
function animateOnLoad() {
  const cards = document.querySelectorAll('.animate-in');
  cards.forEach((card, i) => {
    card.style.opacity   = '0';
    card.style.transform = 'translateY(20px)';
    setTimeout(() => {
      card.style.transition = 'all 0.5s cubic-bezier(0.34,1.56,0.64,1)';
      card.style.opacity   = '1';
      card.style.transform = 'translateY(0)';
    }, i * 80);
  });
}

// Global (for onclick in HTML)
window.removeKeyword = removeKeyword;
