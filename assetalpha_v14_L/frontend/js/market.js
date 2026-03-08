/**
 * market.js — Скринер рынка с фильтрацией по секторам.
 */

let fullMarketData = [];
let detailChart    = null;
let activeSector   = 'all';
let activeFilter   = 'all';

const SECTOR_META = {
    'Technology':             { icon: '💻', label: 'Технологии' },
    'Financial Services':     { icon: '🏦', label: 'Финансы' },
    'Healthcare':             { icon: '🏥', label: 'Здравоохранение' },
    'Consumer Cyclical':      { icon: '🛒', label: 'Потреб. цикличные' },
    'Consumer Defensive':     { icon: '🛡️', label: 'Потреб. защитные' },
    'Energy':                 { icon: '⚡', label: 'Энергетика' },
    'Industrials':            { icon: '🏭', label: 'Промышленность' },
    'Communication Services': { icon: '📡', label: 'Коммуникации' },
    'Real Estate':            { icon: '🏢', label: 'Недвижимость' },
    'Utilities':              { icon: '💡', label: 'Коммунальные' },
};

document.addEventListener('DOMContentLoaded', () => {
    loadMarketData();
    initModalClose();
    initSearch();
    initSectorTabs();
    initFilterTabs();
});

async function loadMarketData() {
    renderSkeleton();
    try {
        const response = await fetchMarketData();
        fullMarketData = response.data || [];
        applyFilters();
        renderTrending([...fullMarketData].sort((a, b) => b.change - a.change).slice(0, 5));
        renderSectorSummary();
    } catch (err) {
        console.error('Ошибка загрузки скринера:', err.message);
        const tbody = document.getElementById('marketTableBody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="table-error">⚠️ Ошибка загрузки данных.</td></tr>';
    }
}

function renderSkeleton() {
    const tbody = document.getElementById('marketTableBody');
    if (!tbody) return;
    tbody.innerHTML = Array.from({ length: 8 }, (_, i) => `
        <tr style="opacity:${1 - i * 0.1}">
            <td><div class="skeleton" style="width:24px;height:14px;"></div></td>
            <td><div style="display:flex;align-items:center;gap:12px;">
                <div class="skeleton" style="width:36px;height:36px;border-radius:50%;"></div>
                <div>
                    <div class="skeleton" style="width:120px;height:14px;margin-bottom:4px;"></div>
                    <div class="skeleton" style="width:50px;height:12px;"></div>
                </div></div></td>
            <td><div class="skeleton" style="width:70px;height:14px;margin-left:auto;"></div></td>
            <td><div class="skeleton" style="width:50px;height:14px;margin-left:auto;"></div></td>
            <td><div class="skeleton" style="width:60px;height:14px;margin-left:auto;"></div></td>
            <td></td>
        </tr>`).join('');
}

function initSectorTabs() {
    const container = document.getElementById('sectorTabs');
    if (!container) return;
    container.addEventListener('click', e => {
        const tab = e.target.closest('.sector-tab');
        if (!tab) return;
        container.querySelectorAll('.sector-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        activeSector = tab.dataset.sector;
        updateSectorHeader();
        applyFilters();
    });
}

function updateSectorHeader() {
    const header  = document.getElementById('sectorHeader');
    const iconEl  = document.getElementById('sectorHeaderIcon');
    const titleEl = document.getElementById('sectorHeaderTitle');
    const countEl = document.getElementById('sectorHeaderCount');
    if (!header) return;
    if (activeSector === 'all') { header.style.display = 'none'; return; }
    const meta  = SECTOR_META[activeSector] || { icon: '📈', label: activeSector };
    const count = fullMarketData.filter(s => s.sector === activeSector).length;
    const word  = count === 1 ? 'компания' : count < 5 ? 'компании' : 'компаний';
    header.style.display = 'flex';
    iconEl.textContent   = meta.icon;
    titleEl.textContent  = meta.label;
    countEl.textContent  = `${count} ${word}`;
}

function initSearch() {
    document.getElementById('marketSearch')?.addEventListener('input', applyFilters);
}

function initFilterTabs() {
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            activeFilter = tab.dataset.filter || 'all';
            applyFilters();
        });
    });
}

function applyFilters() {
    const query = (document.getElementById('marketSearch')?.value || '').toLowerCase().trim();
    let filtered = fullMarketData;
    if (activeSector !== 'all') filtered = filtered.filter(i => i.sector === activeSector);
    if (query) filtered = filtered.filter(i =>
        i.symbol.toLowerCase().includes(query) || (i.name || '').toLowerCase().includes(query));
    if (activeFilter === 'favorites') {
        const favs = getFavorites();
        filtered = filtered.filter(i => favs.includes(i.symbol));
    }
    renderTable(filtered);
}

function renderTable(data) {
    const tbody = document.getElementById('marketTableBody');
    if (!tbody) return;
    if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:32px;color:var(--text-muted);">Ничего не найдено</td></tr>';
        return;
    }
    const favs = getFavorites();
    tbody.innerHTML = data.map((item, i) => {
        const isFav      = favs.includes(item.symbol);
        const changeSign = item.change >= 0 ? '+' : '';
        const sector     = item.sector || '';
        const meta       = SECTOR_META[sector] || { icon: '📈', label: sector };
        const badgeHtml  = sector
            ? `<span class="coin-sector-badge">${meta.icon} ${escapeHtml(meta.label)}</span>`
            : '';
        return `
        <tr>
            <td><span class="coin-rank">${i + 1}</span></td>
            <td>
                <div class="coin-cell"
                     data-action="open-modal"
                     data-symbol="${escapeAttr(item.symbol)}"
                     data-name="${escapeAttr(item.name || item.symbol)}"
                     data-sector="${escapeAttr(sector)}"
                     style="cursor:pointer;">
                    <div class="coin-icon">${item.symbol[0]}</div>
                    <div>
                        <div class="coin-name">${escapeHtml(item.name || item.symbol)}</div>
                        <div class="coin-symbol">${escapeHtml(item.symbol)} ${badgeHtml}</div>
                    </div>
                </div>
            </td>
            <td class="text-right price-cell">${item.price}</td>
            <td class="text-right change-cell ${item.change >= 0 ? 'positive' : 'negative'}">${changeSign}${item.change}%</td>
            <td>
                <button class="btn-icon star-btn ${isFav ? 'active' : ''}"
                        data-action="toggle-fav"
                        data-symbol="${escapeAttr(item.symbol)}"
                        title="${isFav ? 'Убрать из избранного' : 'Добавить в избранное'}">
                    ${isFav ? '★' : '☆'}
                </button>
            </td>
        </tr>`;
    }).join('');
    tbody.addEventListener('click', handleTableClick, { once: true });
}

function handleTableClick(e) {
    const tbody = document.getElementById('marketTableBody');
    const cell  = e.target.closest('[data-action]');
    if (!cell) return;
    if (cell.dataset.action === 'open-modal')
        openAssetModal(cell.dataset.symbol, cell.dataset.name, cell.dataset.sector);
    if (cell.dataset.action === 'toggle-fav') {
        const sym   = cell.dataset.symbol;
        const isFav = cell.textContent.trim() === '★';
        cell.textContent = isFav ? '☆' : '★';
        cell.classList.toggle('active', !isFav);
        cell.title = isFav ? 'Добавить в избранное' : 'Убрать из избранного';
        toggleFavorite(sym);
    }
    if (tbody) tbody.addEventListener('click', handleTableClick, { once: true });
}

function renderSectorSummary() {
    const container = document.getElementById('sectorSummaryList');
    if (!container) return;
    const sectorMap = {};
    for (const item of fullMarketData) {
        const sec = item.sector || 'Другое';
        if (!sectorMap[sec]) sectorMap[sec] = { count: 0, totalChange: 0 };
        sectorMap[sec].count++;
        sectorMap[sec].totalChange += (item.change || 0);
    }
    const ordered = [
        ...Object.keys(SECTOR_META).filter(s => sectorMap[s]),
        ...Object.keys(sectorMap).filter(s => !SECTOR_META[s]),
    ];
    container.innerHTML = ordered.map(sec => {
        const { count, totalChange } = sectorMap[sec];
        const avg  = count > 0 ? totalChange / count : 0;
        const meta = SECTOR_META[sec] || { icon: '📈', label: sec };
        return `
        <div class="sector-summary-item" data-sector="${escapeAttr(sec)}" style="cursor:pointer;">
            <div class="sector-summary-icon">${meta.icon}</div>
            <div class="sector-summary-info">
                <div class="sector-summary-name">${escapeHtml(meta.label)}</div>
                <div class="sector-summary-count">${count} акций</div>
            </div>
            <div class="sector-summary-change ${avg >= 0 ? 'positive' : 'negative'}">${avg >= 0 ? '+' : ''}${avg.toFixed(2)}%</div>
        </div>`;
    }).join('');
    container.addEventListener('click', e => {
        const item = e.target.closest('[data-sector]');
        if (!item) return;
        const sec = item.dataset.sector;
        document.querySelectorAll('.sector-tab').forEach(t => t.classList.toggle('active', t.dataset.sector === sec));
        activeSector = sec;
        updateSectorHeader();
        applyFilters();
        document.querySelector('.market-main-col')?.scrollIntoView({ behavior: 'smooth' });
    });
}

function renderTrending(stocks) {
    const container = document.getElementById('topStocksContainer');
    if (!container || !stocks.length) return;
    container.innerHTML = stocks.map((s, i) => `
        <div class="trending-item"
             data-action="open-modal"
             data-symbol="${escapeAttr(s.symbol)}"
             data-name="${escapeAttr(s.name || s.symbol)}"
             data-sector="${escapeAttr(s.sector || '')}"
             style="cursor:pointer;">
            <div class="trending-rank">${i + 1}</div>
            <div class="trending-coin">
                <div class="trending-icon">${s.symbol[0]}</div>
                <div>
                    <div class="trending-name">${escapeHtml(s.name || s.symbol)}</div>
                    <div class="trending-symbol">${escapeHtml(s.symbol)}</div>
                </div>
            </div>
            <div class="trending-change ${s.change >= 0 ? 'positive' : 'negative'}">${s.change >= 0 ? '+' : ''}${s.change}%</div>
        </div>`).join('');
    container.addEventListener('click', e => {
        const item = e.target.closest('[data-action="open-modal"]');
        if (item) openAssetModal(item.dataset.symbol, item.dataset.name, item.dataset.sector);
    });
}

function getFavorites() {
    try { return JSON.parse(localStorage.getItem('favorites') || '[]'); }
    catch { return []; }
}

function toggleFavorite(symbol) {
    const favs = getFavorites();
    const idx  = favs.indexOf(symbol);
    if (idx === -1) favs.push(symbol); else favs.splice(idx, 1);
    localStorage.setItem('favorites', JSON.stringify(favs));
}

async function openAssetModal(symbol, name, sector) {
    const modal = document.getElementById('assetModal');
    if (!modal) return;
    modal.style.display = 'flex';
    document.getElementById('modalAssetTitle').textContent = `${name} (${symbol})`;
    document.getElementById('modalAssetIcon').textContent  = symbol[0];
    const badgeEl = document.getElementById('modalSectorBadge');
    if (badgeEl) {
        if (sector && SECTOR_META[sector]) {
            const meta = SECTOR_META[sector];
            badgeEl.textContent   = `${meta.icon} ${meta.label}`;
            badgeEl.style.display = 'inline-block';
        } else {
            badgeEl.style.display = 'none';
        }
    }
    ['modalAssetPrice','modalAssetChange','modalMaxPrice','modalMeanReturn','modalRisk','modalSharpe']
        .forEach(id => { const el = document.getElementById(id); if (el) el.textContent = '…'; });
    try {
        const data = await fetchAssetDetails(symbol);
        setModalField('modalAssetPrice', data.price);
        const changeEl = document.getElementById('modalAssetChange');
        if (changeEl) {
            changeEl.textContent = data.change;
            changeEl.className = `mmt-value ${(data.change || '').startsWith('+') ? 'positive' : 'negative'}`;
        }
        setModalField('modalMaxPrice',   data.max_price);
        setModalField('modalMeanReturn', data.mean_return);
        setModalField('modalRisk',       data.risk);
        setModalField('modalSharpe', typeof data.sharpe === 'number' ? data.sharpe.toFixed(4) : data.sharpe);
        renderDetailChart(data.history || []);
    } catch (err) {
        console.error('Ошибка деталей:', err.message);
        ['modalAssetPrice','modalMaxPrice','modalMeanReturn','modalRisk','modalSharpe']
            .forEach(id => setModalField(id, '—'));
    }
}

function setModalField(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value ?? '—';
}

function renderDetailChart(historyData) {
    const canvas = document.getElementById('assetDetailChart');
    if (!canvas) return;
    if (detailChart) { detailChart.destroy(); detailChart = null; }
    if (!historyData.length) return;
    detailChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels:   historyData.map(d => d.date),
            datasets: [{ label: 'Цена', data: historyData.map(d => d.price),
                borderColor: '#A1A364', backgroundColor: 'rgba(161,163,100,0.12)',
                borderWidth: 2, fill: true, tension: 0.4, pointRadius: 0 }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: { legend: { display: false } },
            scales: {
                y: { ticks: { color: 'var(--text-secondary)' }, grid: { color: 'var(--border)' } },
                x: { ticks: { color: 'var(--text-secondary)', maxTicksLimit: 8 }, grid: { display: false } },
            },
        },
    });
}

function initModalClose() {
    const modal    = document.getElementById('assetModal');
    const closeBtn = document.getElementById('closeModalBtn');
    if (!modal) return;
    const closeModal = () => {
        modal.style.display = 'none';
        if (detailChart) { detailChart.destroy(); detailChart = null; }
    };
    closeBtn?.addEventListener('click', closeModal);
    modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && modal.style.display !== 'none') closeModal();
    });
}

function escapeHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function escapeAttr(str) {
    return String(str).replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
