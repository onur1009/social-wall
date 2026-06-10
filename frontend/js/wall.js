/**
 * Social Wall v2 — wall.js
 * Twitter, Instagram, Reddit, TikTok, News, Facebook, LinkedIn
 * Auto-refresh every 60s, News Ticker, Kiosk mode, Platform filters
 */

const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:8765'
  : window.location.origin;
const REFRESH_INTERVAL = 30; // seconds

/* ── URL Params ─────────────────────────────────── */
const urlParams  = new URLSearchParams(window.location.search);
const KEYWORDS   = urlParams.get('keywords')  || 'teknoloji';
const PLATFORMS  = urlParams.get('platforms') || 'twitter,news,facebook,linkedin';
const CUSTOM_RSS = urlParams.get('custom_rss') || '';

/* ── State ──────────────────────────────────────── */
let allPosts         = [];
let pendingPosts     = [];
let activePlatFilter = 'all';
let secondsLeft      = REFRESH_INTERVAL;
let refreshTimer     = null;
let countdownTimer   = null;
let isLoading        = false;
let postIdsSeen      = new Set();
let tickerPosts      = [];

/* ── DOM refs ───────────────────────────────────── */
const wallGrid       = document.getElementById('wall-grid');
const loadingOverlay = document.getElementById('wall-loading');
const refreshBar     = document.getElementById('refresh-bar');
const nextRefreshEl  = document.getElementById('next-refresh');
const postCountEl    = document.getElementById('post-count');
const newPostsBtn    = document.getElementById('new-posts-btn');
const toastEl        = document.getElementById('wall-toast');
const tickerInner    = document.getElementById('ticker-inner');

/* ── Platform config ────────────────────────────── */
const PLATFORM_ICONS = {
  twitter:   '𝕏',
  facebook:  '📘',
  linkedin:  '💼',
  news:      '📰',
};

const PLATFORM_COLORS = {
  twitter:   '#1d9bf0',
  facebook:  '#1877f2',
  linkedin:  '#0a66c2',
  news:      '#f59e0b',
};

/* ── Boot ───────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  setupTopbar();
  setupPlatformFilters();
  updateLoadingPlatIcons();
  fetchAndRender(true);
  startRefreshCycle();
});

/* ── Topbar Setup ───────────────────────────────── */
function setupTopbar() {
  // Keywords strip
  const strip = document.getElementById('keywords-strip');
  KEYWORDS.split(',').forEach(kw => {
    const chip = document.createElement('span');
    chip.className = 'wall-keyword-chip';
    chip.textContent = '#' + kw.trim();
    strip.appendChild(chip);
  });

  document.getElementById('back-btn').addEventListener('click', () => {
    window.close();
    window.history.back();
  });

  document.getElementById('refresh-btn').addEventListener('click', () => {
    clearInterval(refreshTimer);
    clearInterval(countdownTimer);
    fetchAndRender(false);
    startRefreshCycle();
  });
}

function updateLoadingPlatIcons() {
  const el = document.getElementById('loading-plat-icons');
  if (!el) return;
  const active = PLATFORMS.split(',').map(p => PLATFORM_ICONS[p.trim()] || '').filter(Boolean);
  el.textContent = active.join('  ');
}

/* ── Platform Filter Chips ──────────────────────── */
function setupPlatformFilters() {
  document.querySelectorAll('.platform-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.platform-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activePlatFilter = chip.dataset.plat;
      filterAndRender();
    });
  });
}

/* ── Fetch Posts ────────────────────────────────── */
async function fetchAndRender(initial = false) {
  if (isLoading) return;
  isLoading = true;

  if (initial) showLoading(true);

  try {
    let url = `${API_BASE}/api/posts?keywords=${encodeURIComponent(KEYWORDS)}&platforms=${encodeURIComponent(PLATFORMS)}&limit=80`;
    if (CUSTOM_RSS) {
      url += `&custom_rss=${encodeURIComponent(CUSTOM_RSS)}`;
    }
    const res  = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const freshPosts = data.posts || [];
    const newOnes    = freshPosts.filter(p => !postIdsSeen.has(p.id));

    if (initial) {
      allPosts = freshPosts;
      freshPosts.forEach(p => postIdsSeen.add(p.id));
      filterAndRender(true);
      buildTicker(freshPosts);
    } else {
      if (newOnes.length > 0) {
        newOnes.forEach(p => postIdsSeen.add(p.id));
        pendingPosts = [...newOnes, ...allPosts].slice(0, 100);
        showNewPostsButton(newOnes.length);
        // Update ticker with new news items
        const newNews = newOnes.filter(p => p.platform === 'news');
        if (newNews.length > 0) appendTicker(newNews);
      } else {
        allPosts = freshPosts;
        filterAndRender(false);
      }
    }

    updatePostCount();
    const src = data.cached ? '(önbellekten)' : '';
    showToast(`✅ ${freshPosts.length} gönderi ${src}`, 'success');

    const lastUpdateEl = document.getElementById('last-update');
    if (lastUpdateEl) {
      const now = new Date();
      lastUpdateEl.textContent = `Son: ${now.toLocaleTimeString('tr-TR')}`;
    }

  } catch (err) {
    console.error('[Wall] Fetch error:', err);
    if (initial) renderOfflineState();
    showToast('⚠️ Bağlantı hatası — tekrar deneniyor', 'error');
  } finally {
    isLoading = false;
    if (initial) showLoading(false);
  }
}

/* ── Render Wall ────────────────────────────────── */
function filterAndRender(initial = false) {
  const filtered = activePlatFilter === 'all'
    ? allPosts
    : allPosts.filter(p => p.platform === activePlatFilter);

  renderCards(filtered, initial);
  updatePostCount(filtered.length);
}

function renderCards(posts, initial = false) {
  if (posts.length === 0) {
    wallGrid.innerHTML = `
      <div class="wall-empty" style="column-span:all;">
        <div class="wall-empty-icon">📡</div>
        <h3>İçerik bulunamadı</h3>
        <p>Bu filtre için gösterilecek gönderi yok. Başka bir platform seçin.</p>
      </div>`;
    return;
  }

  if (!initial && wallGrid.children.length > 0) {
    const oldCards = Array.from(wallGrid.children);
    oldCards.forEach((card, i) => {
      card.style.animationDelay = `${i * 18}ms`;
      card.classList.add('card-exit');
    });
    setTimeout(() => {
      wallGrid.innerHTML = '';
      appendCards(posts);
    }, 360);
  } else {
    wallGrid.innerHTML = '';
    appendCards(posts);
  }
}

function appendCards(posts) {
  posts.forEach((post, i) => {
    const card = createCard(post, i);
    wallGrid.appendChild(card);
  });
}

/* ── New Posts Button ───────────────────────────── */
function showNewPostsButton(count) {
  newPostsBtn.textContent = `▲ ${count} yeni gönderi — görüntüle`;
  newPostsBtn.classList.add('visible');
  newPostsBtn.onclick = () => {
    allPosts = pendingPosts;
    pendingPosts = [];
    filterAndRender(false);
    newPostsBtn.classList.remove('visible');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };
}

/* ── Create Card Element ────────────────────────── */
function createCard(post, index) {
  const card = document.createElement('article');
  card.className = 'post-card card-new';
  card.dataset.platform = post.platform;
  card.dataset.id       = post.id;
  card.style.animationDelay = `${Math.min(index * 50, 700)}ms`;

  // Demo badge
  const demoBadge = post.is_demo
    ? `<div class="demo-badge">DEMO</div>`
    : '';

  // Avatar
  const avatarHtml = post.avatar
    ? `<img class="card-avatar" src="${esc(post.avatar)}" alt="${esc(post.author)}"
           onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
    : '';
  const avatarFallback = `
    <div class="card-avatar-placeholder" ${post.avatar ? 'style="display:none"' : ''}>
      ${esc((post.author || '?')[0].toUpperCase())}
    </div>`;

  // Platform icon
  const platIcon  = PLATFORM_ICONS[post.platform]  || '🌐';
  const platColor = PLATFORM_COLORS[post.platform] || '#6366f1';

  // Subtitle (subreddit, etc.)
  const subtitle = post.subtitle
    ? `<span class="card-subreddit">${esc(post.subtitle)}</span>`
    : '';

  // Media block
  let mediaHtml = '';
  if (post.media) {
    if (post.platform === 'tiktok') {
      // TikTok: show cover with play count overlay
      const plays = post.plays ? formatNum(post.plays) : null;
      mediaHtml = `
        <div class="card-video-overlay">
          <img src="${esc(post.media)}" alt="TikTok video" loading="lazy" onerror="this.parentElement.style.display='none'">
          ${plays ? `<div class="card-play-badge">▶ ${plays}</div>` : ''}
        </div>`;
    } else {
      mediaHtml = `<img class="card-media" src="${esc(post.media)}" alt="media"
           loading="lazy" onerror="this.style.display='none'">`;
    }
  }

  // Text
  const formattedText = formatText(post.text || '');

  // Stats
  const likes  = post.likes  > 0 ? formatNum(post.likes)  : null;
  const shares = post.shares > 0 ? formatNum(post.shares) : null;

  // TikTok plays in stats (if no media overlay)
  const plays = (post.platform === 'tiktok' && !post.media && post.plays > 0)
    ? `<span class="card-stat">▶ ${formatNum(post.plays)}</span>`
    : '';

  const statsHtml = (likes || shares || plays) ? `
    <div class="card-stats">
      ${likes  ? `<span class="card-stat">${heartSvg()} ${likes}</span>`  : ''}
      ${shares ? `<span class="card-stat">${getShareIcon(post.platform)} ${shares}</span>` : ''}
      ${plays}
    </div>` : '<div></div>';

  card.innerHTML = `
    ${demoBadge}
    <div class="card-inner">
      <div class="card-header">
        ${avatarHtml}
        ${avatarFallback}
        <div class="card-author-info">
          <div class="card-author-name">${esc(post.author || 'Bilinmeyen')}</div>
          <div class="card-author-subtitle">${esc(post.username || '')}${post.subtitle ? ' · ' + esc(post.subtitle) : ''}</div>
        </div>
        <span class="card-platform-icon" style="color:${platColor}">${platIcon}</span>
      </div>

      ${mediaHtml}

      <div class="card-text">${formattedText}</div>

      <div class="card-footer">
        ${statsHtml}
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
          ${subtitle}
          <span class="card-keyword">${esc(post.keyword || '')}</span>
          <span class="card-time">${timeAgo(post.timestamp)}</span>
          <button class="card-translate-btn" onclick="translatePost(event, this)">🌐 Çevir</button>
        </div>
      </div>
    </div>
  `;

  card.addEventListener('click', () => {
    if (post.url && post.url !== '#') window.open(post.url, '_blank');
  });

  return card;
}

/* ── News Ticker ────────────────────────────────── */
function buildTicker(posts) {
  tickerPosts = posts.filter(p => p.platform === 'news' || p.platform === 'twitter');
  renderTicker();
}

function appendTicker(newPosts) {
  tickerPosts = [...newPosts, ...tickerPosts].slice(0, 30);
  renderTicker();
}

function renderTicker() {
  if (!tickerInner || tickerPosts.length === 0) return;

  // Duplicate items for seamless loop
  const items = [...tickerPosts, ...tickerPosts];
  tickerInner.innerHTML = items.map(p => `
    <span class="ticker-item" onclick="window.open('${p.url && p.url !== '#' ? esc(p.url) : '#'}','_blank')">
      <span class="ticker-source">${PLATFORM_ICONS[p.platform] || '•'} ${esc(p.author || p.platform)}</span>
      <span class="ticker-dot"></span>
      <span>${esc(truncate(p.text || '', 90))}</span>
    </span>
  `).join('');
}

/* ── Refresh Cycle ──────────────────────────────── */
function startRefreshCycle() {
  secondsLeft = REFRESH_INTERVAL;
  updateCountdown();

  countdownTimer = setInterval(() => {
    secondsLeft--;
    updateCountdown();
    if (secondsLeft <= 0) secondsLeft = REFRESH_INTERVAL;
  }, 1000);

  refreshTimer = setInterval(() => {
    fetchAndRender(false);
    secondsLeft = REFRESH_INTERVAL;
  }, REFRESH_INTERVAL * 1000);
}

function updateCountdown() {
  if (nextRefreshEl) nextRefreshEl.textContent = `${secondsLeft}s`;
  const pct = ((REFRESH_INTERVAL - secondsLeft) / REFRESH_INTERVAL) * 100;
  if (refreshBar) refreshBar.style.width = `${pct}%`;
  
  const prog = document.getElementById('countdown-ring-prog');
  if (prog) {
    const CIRC = 2 * Math.PI * 12; // ~75.4
    prog.style.strokeDasharray = CIRC;
    prog.style.strokeDashoffset = CIRC * (1 - secondsLeft / REFRESH_INTERVAL);
  }
}

/* ── Loading Overlay ────────────────────────────── */
function showLoading(show) {
  if (!loadingOverlay) return;
  if (show) loadingOverlay.classList.remove('hidden');
  else      loadingOverlay.classList.add('hidden');
}

/* ── Post Count ─────────────────────────────────── */
function updatePostCount(count) {
  const n = count !== undefined ? count : allPosts.length;
  if (postCountEl) postCountEl.textContent = `${n} gönderi`;
}

/* ── Offline / Error State ──────────────────────── */
function renderOfflineState() {
  wallGrid.innerHTML = `
    <div class="wall-empty" style="column-span:all;">
      <div class="wall-empty-icon">⚡</div>
      <h3>Backend'e bağlanılamıyor</h3>
      <p>run.bat ile API'yi başlatın ve sayfayı yenileyin.</p>
      <button class="btn btn-primary" onclick="location.reload()" style="margin-top:16px;">
        🔄 Yenile
      </button>
    </div>`;
}

/* ── Toast ──────────────────────────────────────── */
let toastTimeout = null;
function showToast(msg, type = 'info') {
  if (!toastEl) return;
  clearTimeout(toastTimeout);
  toastEl.textContent = msg;
  toastEl.className = `toast ${type} show`;
  toastTimeout = setTimeout(() => toastEl.classList.remove('show'), 3500);
}

/* ── Helpers ────────────────────────────────────── */
function esc(str) {
  return String(str || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatText(text) {
  return esc(text)
    .replace(/(#\w+)/g, '<span class="hashtag">$1</span>')
    .replace(/\n/g, '<br>');
}

function formatNum(n) {
  if (!n) return '0';
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000)    return (n / 1000).toFixed(1)    + 'K';
  return String(n);
}

function truncate(str, len) {
  return str.length > len ? str.slice(0, len) + '…' : str;
}

function timeAgo(ts) {
  if (!ts) return '';
  const diff = Math.floor(Date.now() / 1000) - ts;
  if (diff < 60)    return 'Az önce';
  if (diff < 3600)  return `${Math.floor(diff / 60)}dk`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}sa`;
  return `${Math.floor(diff / 86400)}g`;
}

function getShareIcon(platform) {
  if (platform === 'reddit')  return '💬';  // comments
  if (platform === 'tiktok')  return '🔗';  // shares
  return shareSvg();
}

function heartSvg() {
  return `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>`;
}

function shareSvg() {
  return `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z"/></svg>`;
}

/* ── Translation ────────────────────────────────── */
window.translatePost = async function(e, btn) {
  e.stopPropagation(); // prevent card click (which opens new tab)
  if (btn.classList.contains('translating')) return;
  
  const card = btn.closest('.post-card');
  const textEl = card.querySelector('.card-text');
  // Grab raw text without HTML tags to send to translator
  const originalText = textEl.innerText || textEl.textContent;
  
  if (!originalText.trim()) return;

  btn.classList.add('translating');
  const oldHtml = btn.innerHTML;
  btn.innerHTML = '⏳ <span style="opacity:0.7">Çevriliyor...</span>';
  
  try {
    const res = await fetch(`${API_BASE}/api/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: originalText })
    });
    const data = await res.json();
    if (data.translated_text) {
      textEl.innerHTML = formatText(data.translated_text);
      btn.style.display = 'none'; // hide button after translation
      showToast('✅ Metin çevrildi', 'success');
    } else {
      throw new Error(data.error || 'Çeviri başarısız');
    }
  } catch (err) {
    console.error('[Translation]', err);
    btn.innerHTML = '❌ Hata';
    setTimeout(() => {
      btn.innerHTML = oldHtml;
      btn.classList.remove('translating');
    }, 2000);
  }
};
