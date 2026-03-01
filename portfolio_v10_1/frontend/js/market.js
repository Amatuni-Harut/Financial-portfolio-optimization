/**
 * market.js — Скринер рынка.
 *
 * Улучшения v7 vs v6:
 * 1. Event delegation вместо inline onclick в шаблонах:
 *    в v6 каждая строка таблицы генерировала onclick="openAssetModal(...)"
 *    → утечка памяти при перерендере, нельзя передавать сложные строки.
 *    В v7: один делегированный слушатель на tbody.
 * 2. Поиск перенесён в initSearch() и слушатель добавляется один раз.
 * 3. Skeleton-loader вместо спиннера при загрузке.
 */

let fullMarketData = [];
let detailChart    = null;

document.addEventListener('DOMContentLoaded', () => {
    loadMarketData();
    initModalClose();
    initSearch();
    // initFilterTabs уже вызывается из ui.js
});


/* ================================================================
   ЗАГРУЗКА ДАННЫХ
================================================================ */

async function loadMarketData() {
    renderSkeleton();
    try {
        const response = await fetchMarketData();
        fullMarketData = response.data || [];
        renderTable(fullMarketData);
        renderTrending(fullMarketData.slice(0, 5));
    } catch (err) {
        console.error('Ошибка загрузки скринера:', err.message);
        const tbody = document.getElementById('marketTableBody');
        if (tbody) tbody.innerHTML =
            '<tr><td colspan="6" class="table-error">⚠️ Ошибка загрузки данных. Попробуйте позже.</td></tr>';
    }
}

function renderSkeleton() {
    const tbody = document.getElementById('marketTableBody');
    if (!tbody) return;
    tbody.innerHTML = Array.from({ length: 6 }, (_, i) => `
        <tr style="opacity:${1 - i * 0.12}">
            <td><div class="skeleton" style="width:24px;height:14px;"></div></td>
            <td>
                <div style="display:flex;align-items:center;gap:12px;">
                    <div class="skeleton" style="width:36px;height:36px;border-radius:50%;"></div>
                    <div>
                        <div class="skeleton" style="width:80px;height:14px;margin-bottom:4px;"></div>
                        <div class="skeleton" style="width:50px;height:12px;"></div>
                    </div>
                </div>
            </td>
            <td><div class="skeleton" style="width:70px;height:14px;margin-left:auto;"></div></td>
            <td><div class="skeleton" style="width:50px;height:14px;margin-left:auto;"></div></td>
            <td><div class="skeleton" style="width:60px;height:14px;margin-left:auto;"></div></td>
            <td></td>
        </tr>`).join('');
}


/* ================================================================
   ТАБЛИЦА
================================================================ */

function renderTable(data) {
    const tbody = document.getElementById('marketTableBody');
    if (!tbody) return;

    if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="table-empty">Ничего не найдено</td></tr>';
        return;
    }

    const favs = getFavorites();

    tbody.innerHTML = data.map((item, i) => {
        const isFav      = favs.includes(item.symbol);
        const changeSign = item.change >= 0 ? '+' : '';
        return `
        <tr>
            <td><span class="coin-rank">${i + 1}</span></td>
            <td>
                <div class="coin-cell"
                     data-action="open-modal"
                     data-symbol="${escapeAttr(item.symbol)}"
                     data-name="${escapeAttr(item.name)}"
                     style="cursor:pointer;"
                     title="Нажмите для деталей">
                    <div class="coin-icon">${item.symbol[0]}</div>
                    <div>
                        <div class="coin-name">${escapeHtml(item.name)}</div>
                        <div class="coin-symbol">${escapeHtml(item.symbol)}</div>
                    </div>
                </div>
            </td>
            <td class="text-right price-cell">${item.price}</td>
            <td class="text-right change-cell ${item.change >= 0 ? 'positive' : 'negative'}">
                ${changeSign}${item.change}%
            </td>
            <td class="text-right volume-cell">${item.marketCap}</td>
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

    // Один делегированный слушатель вместо N inline-обработчиков
    tbody.addEventListener('click', handleTableClick, { once: true });
    // Повторная регистрация после каждого renderTable
    tbody._delegateAttached = true;
}

function handleTableClick(e) {
    // Переоткрываем делегацию для следующего рендера
    const tbody = document.getElementById('marketTableBody');

    const cell  = e.target.closest('[data-action]');
    if (!cell) return;

    const action = cell.dataset.action;

    if (action === 'open-modal') {
        openAssetModal(cell.dataset.symbol, cell.dataset.name);
    }

    if (action === 'toggle-fav') {
        const sym   = cell.dataset.symbol;
        const isFav = cell.textContent.trim() === '★';
        cell.textContent = isFav ? '☆' : '★';
        cell.classList.toggle('active', !isFav);
        cell.title = !isFav ? 'Убрать из избранного' : 'Добавить в избранное';
        toggleFavorite(sym);
    }

    // Переподключаем делегацию
    if (tbody) tbody.addEventListener('click', handleTableClick, { once: true });
}

function renderTrending(stocks) {
    const container = document.getElementById('topStocksContainer');
    if (!container || !stocks.length) return;

    container.innerHTML = stocks.map((s, i) => `
        <div class="trending-item"
             data-action="open-modal"
             data-symbol="${escapeAttr(s.symbol)}"
             data-name="${escapeAttr(s.name)}"
             style="cursor:pointer;">
            <div class="trending-rank">${i + 1}</div>
            <div class="trending-coin">
                <div class="trending-icon">${s.symbol[0]}</div>
                <div>
                    <div class="trending-name">${escapeHtml(s.name)}</div>
                    <div class="trending-symbol">${escapeHtml(s.symbol)}</div>
                </div>
            </div>
            <div class="trending-change ${s.change >= 0 ? 'positive' : 'negative'}">
                ${s.change >= 0 ? '+' : ''}${s.change}%
            </div>
        </div>`).join('');

    container.addEventListener('click', e => {
        const item = e.target.closest('[data-action="open-modal"]');
        if (item) openAssetModal(item.dataset.symbol, item.dataset.name);
    });
}


/* ================================================================
   ПОИСК И ФИЛЬТРЫ
================================================================ */

function initSearch() {
    const input = document.getElementById('marketSearch');
    if (!input) return;
    input.addEventListener('input', () => {
        const q      = input.value.toLowerCase().trim();
        const filter = document.querySelector('.filter-tab.active')?.dataset.filter || 'all';
        applyFilters(q, filter);
    });
}

function initFilterTabs() {
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const q = document.getElementById('marketSearch')?.value.toLowerCase().trim() || '';
            applyFilters(q, tab.dataset.filter);
        });
    });
}

function applyFilters(query, filter) {
    let filtered = fullMarketData;
    if (query) {
        filtered = filtered.filter(item =>
            item.symbol.toLowerCase().includes(query) ||
            item.name.toLowerCase().includes(query)
        );
    }
    if (filter === 'favorites') {
        const favs = getFavorites();
        filtered = filtered.filter(item => favs.includes(item.symbol));
    }
    renderTable(filtered);
}


/* ================================================================
   ИЗБРАННОЕ (localStorage)
================================================================ */

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


/* ================================================================
   МОДАЛЬНОЕ ОКНО — ДЕТАЛИ АКТИВА
================================================================ */

async function openAssetModal(symbol, name) {
    const modal = document.getElementById('assetModal');
    if (!modal) return;
    modal.style.display = 'flex';

    // Показываем skeleton-данные пока грузим
    document.getElementById('modalAssetTitle').textContent = `${name} (${symbol})`;
    document.getElementById('modalAssetIcon').textContent  = symbol[0];
    ['modalAssetPrice','modalAssetChange','modalMaxPrice',
     'modalMeanReturn','modalRisk','modalSharpe'].forEach(id => setModalField(id, '…'));

    try {
        const data = await fetchAssetDetails(symbol);

        document.getElementById('modalAssetPrice').textContent = data.price;

        const changeEl = document.getElementById('modalAssetChange');
        if (changeEl) {
            changeEl.textContent = data.change;
            changeEl.className   = `mmt-value ${data.change.includes('+') ? 'positive' : 'negative'}`;
        }

        setModalField('modalMaxPrice',   data.max_price);
        setModalField('modalMeanReturn', data.mean_return);
        setModalField('modalRisk',       data.risk);
        setModalField('modalSharpe',     typeof data.sharpe === 'number' ? data.sharpe.toFixed(4) : data.sharpe);

        renderDetailChart(data.history);

    } catch (err) {
        console.error('Ошибка загрузки деталей:', err.message);
        ['modalAssetPrice','modalMaxPrice','modalMeanReturn','modalRisk','modalSharpe']
            .forEach(id => setModalField(id, '—'));
        setModalField('modalAssetChange', 'Ошибка');
    }
}

function setModalField(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function renderDetailChart(historyData) {
    const canvas = document.getElementById('assetDetailChart');
    if (!canvas) return;
    if (detailChart) { detailChart.destroy(); detailChart = null; }

    detailChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: historyData.map(d => d.date),
            datasets: [{
                label: 'Цена',
                data: historyData.map(d => d.price),
                borderColor: '#A1A364',
                backgroundColor: 'rgba(161, 163, 100, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
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


/* ================================================================
   УТИЛИТЫ — защита от XSS при рендеринге данных из API
================================================================ */

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function escapeAttr(str) {
    return String(str)
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
