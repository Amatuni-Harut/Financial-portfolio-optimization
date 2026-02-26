/**
 * market.js — Скринер рынка.
 * Включает реальный fetchAssetDetails для модального окна.
 * Зависит от: appState.js, api.js, ui.js
 */

let fullMarketData = [];
let detailChart = null;

document.addEventListener('DOMContentLoaded', () => {
    loadMarketData();
    initModalClose();
    initFilterTabs();
});

// ================================================================
// ЗАГРУЗКА ТАБЛИЦЫ
// ================================================================

async function loadMarketData() {
    try {
        const response = await fetchMarketData();
        fullMarketData = response.data || [];
        renderTable(fullMarketData);
        renderTrending(fullMarketData.slice(0, 5));
    } catch (err) {
        console.error('Ошибка загрузки скринера:', err.message);
        document.getElementById('marketTableBody').innerHTML =
            '<tr><td colspan="6" class="table-error">Ошибка загрузки данных. Попробуйте позже.</td></tr>';
    }
}

function renderTable(data) {
    const tbody = document.getElementById('marketTableBody');

    if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="table-empty">Ничего не найдено</td></tr>';
        return;
    }

    tbody.innerHTML = data.map((item, i) => `
        <tr>
            <td><span class="coin-rank">${i + 1}</span></td>
            <td>
                <div class="coin-cell" onclick="openAssetModal('${item.symbol}', '${item.name}')"
                     style="cursor:pointer;" title="Нажмите для деталей">
                    <div class="coin-icon">${item.symbol[0]}</div>
                    <div>
                        <div class="coin-name">${item.name}</div>
                        <div class="coin-symbol">${item.symbol}</div>
                    </div>
                </div>
            </td>
            <td class="text-right price-cell">${item.price}</td>
            <td class="text-right change-cell ${item.change >= 0 ? 'positive' : 'negative'}">
                ${item.change >= 0 ? '+' : ''}${item.change}%
            </td>
            <td class="text-right volume-cell">${item.marketCap}</td>
            <td>
                <button class="btn-icon star-btn" data-symbol="${item.symbol}" title="Добавить в избранное">☆</button>
            </td>
        </tr>
    `).join('');

    // Избранное
    tbody.querySelectorAll('.star-btn').forEach(btn => {
        const sym = btn.dataset.symbol;
        const favs = getFavorites();
        if (favs.includes(sym)) {
            btn.textContent = '★';
            btn.classList.add('active');
        }
        btn.addEventListener('click', () => {
            const isFav = btn.textContent === '★';
            btn.textContent = isFav ? '☆' : '★';
            btn.classList.toggle('active', !isFav);
            toggleFavorite(sym);
        });
    });
}

function renderTrending(stocks) {
    const container = document.getElementById('topStocksContainer');
    if (!container || !stocks.length) return;

    container.innerHTML = stocks.map((s, i) => `
        <div class="trending-item" onclick="openAssetModal('${s.symbol}', '${s.name}')">
            <div class="trending-rank">${i + 1}</div>
            <div class="trending-coin">
                <div class="trending-icon">${s.symbol[0]}</div>
                <div>
                    <div class="trending-name">${s.name}</div>
                    <div class="trending-symbol">${s.symbol}</div>
                </div>
            </div>
            <div class="trending-change ${s.change >= 0 ? 'positive' : 'negative'}">
                ${s.change >= 0 ? '+' : ''}${s.change}%
            </div>
        </div>
    `).join('');
}

// ================================================================
// ПОИСК И ФИЛЬТРЫ
// ================================================================

document.getElementById('marketSearch')?.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    const activeFilter = document.querySelector('.filter-tab.active')?.dataset.filter || 'all';
    applyFilters(q, activeFilter);
});

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

// ================================================================
// ИЗБРАННОЕ (localStorage)
// ================================================================

function getFavorites() {
    try {
        return JSON.parse(localStorage.getItem('favorites') || '[]');
    } catch {
        return [];
    }
}

function toggleFavorite(symbol) {
    const favs = getFavorites();
    const idx = favs.indexOf(symbol);
    if (idx === -1) {
        favs.push(symbol);
    } else {
        favs.splice(idx, 1);
    }
    localStorage.setItem('favorites', JSON.stringify(favs));
}

// ================================================================
// МОДАЛЬНОЕ ОКНО — ДЕТАЛИ АКТИВА
// ================================================================

async function openAssetModal(symbol, name) {
    const modal = document.getElementById('assetModal');
    modal.style.display = 'flex';

    // Показываем skeleton пока грузим
    document.getElementById('modalAssetTitle').textContent = `${name} (${symbol})`;
    document.getElementById('modalAssetIcon').textContent  = symbol[0];
    document.getElementById('modalAssetPrice').textContent  = '...';
    document.getElementById('modalAssetChange').textContent = '...';

    // Дополнительные поля
    setModalField('modalMaxPrice',   '...');
    setModalField('modalMeanReturn', '...');
    setModalField('modalRisk',       '...');
    setModalField('modalSharpe',     '...');

    try {
        const data = await fetchAssetDetails(symbol);

        document.getElementById('modalAssetPrice').textContent = data.price;

        const changeEl = document.getElementById('modalAssetChange');
        changeEl.textContent = data.change;
        changeEl.className = `metric-value ${data.change.includes('+') ? 'positive' : 'negative'}`;

        setModalField('modalMaxPrice',   data.max_price);
        setModalField('modalMeanReturn', data.mean_return);
        setModalField('modalRisk',       data.risk);
        setModalField('modalSharpe',     data.sharpe.toFixed(4));

        renderDetailChart(data.history);
    } catch (err) {
        console.error('Ошибка загрузки деталей:', err.message);
        document.getElementById('modalAssetPrice').textContent = 'Нет данных';
        setModalField('modalMaxPrice',   '—');
        setModalField('modalMeanReturn', '—');
        setModalField('modalRisk',       '—');
        setModalField('modalSharpe',     '—');
    }
}

function setModalField(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function renderDetailChart(historyData) {
    const canvas = document.getElementById('assetDetailChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (detailChart) detailChart.destroy();

    detailChart = new Chart(ctx, {
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
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: { legend: { display: false } },
            scales: {
                y: { ticks: { color: 'var(--text-secondary)' }, grid: { color: 'var(--border)' } },
                x: { ticks: { color: 'var(--text-secondary)', maxTicksLimit: 8 }, grid: { display: false } }
            }
        }
    });
}

function initModalClose() {
    const modal    = document.getElementById('assetModal');
    const closeBtn = document.getElementById('closeModalBtn');

    closeBtn?.addEventListener('click', () => {
        modal.style.display = 'none';
        if (detailChart) { detailChart.destroy(); detailChart = null; }
    });

    modal?.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
            if (detailChart) { detailChart.destroy(); detailChart = null; }
        }
    });

    // Закрытие по Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal?.style.display !== 'none') {
            modal.style.display = 'none';
            if (detailChart) { detailChart.destroy(); detailChart = null; }
        }
    });
}
