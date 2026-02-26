/**
 * dashboard.js — логика главной страницы (портфель + оптимизация).
 * Заменяет Calculation.js. Зависит от: appState.js, api.js
 */

// Состояние страницы
const DashboardState = {
    assets: [],       // { ticker, name, sector, weight? }
    charts: { weights: null, risk: null },
    isManualWeights: false
};

/* -----------------------------------------------
   Инициализация
----------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
    initDates();
    bindEvents();
    applyKnowledgeLevel();
    renderAssetList();
});

function initDates() {
    const end = new Date();
    const start = new Date();
    start.setFullYear(end.getFullYear() - 3);
    document.getElementById('endDate').valueAsDate = end;
    document.getElementById('startDate').valueAsDate = start;
}

function applyKnowledgeLevel() {
    const level = AppState.get('knowledgeLevel');

    // Показываем блок ручных весов только профессионалам
    const proBlock = document.getElementById('proFeatures');
    if (proBlock) proBlock.style.display = level === 'professional' ? 'block' : 'none';

    // Скрываем сложные метрики для новичков
    const sortinoCard = document.getElementById('sortinoCard');
    const cvarCard = document.getElementById('cvarCard');
    if (level === 'beginner') {
        if (sortinoCard) sortinoCard.style.display = 'none';
        if (cvarCard) cvarCard.style.display = 'none';
    }
}

/* -----------------------------------------------
   Привязка событий
----------------------------------------------- */
function bindEvents() {
    // Поиск тикеров
    const searchInput = document.getElementById('searchInput');
    let searchTimeout;
    searchInput?.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => handleSearch(e.target.value), 300);
    });
    searchInput?.addEventListener('blur', () => setTimeout(hideSearch, 200));

    // Кнопки действий
    document.getElementById('optimizeBtn')?.addEventListener('click', runOptimize);
    document.getElementById('frontierBtn')?.addEventListener('click', showFrontier);
    document.getElementById('refreshDataBtn')?.addEventListener('click', handleRefreshData);

    // Переключатель ручных весов (для профессионалов)
    const divToggle = document.getElementById('diversificationToggle');
    divToggle?.addEventListener('click', () => {
        divToggle.classList.toggle('active');
        DashboardState.isManualWeights = divToggle.classList.contains('active');
        renderAssetList();
    });
}

/* -----------------------------------------------
   Поиск активов
----------------------------------------------- */
async function handleSearch(query) {
    if (query.length < 2) { hideSearch(); return; }

    try {
        const results = await searchStocks(query);
        renderSearchResults(results);
    } catch (err) {
        console.error('Ошибка поиска:', err.message);
    }
}

function renderSearchResults(stocks) {
    const container = document.getElementById('searchResults');
    if (!stocks.length) {
        container.innerHTML = '<div class="search-item">Ничего не найдено</div>';
    } else {
        container.innerHTML = stocks.map(s => `
            <div class="search-item" onclick="addAsset('${s.ticker}', '${s.name}', '${s.sector || ''}')">
                <div>
                    <span class="search-ticker">${s.ticker}</span>
                    <span class="search-name">${s.name}</span>
                </div>
                ${s.sector ? `<span class="search-sector">${s.sector}</span>` : ''}
            </div>
        `).join('');
    }
    container.classList.add('active');
}

function hideSearch() {
    document.getElementById('searchResults')?.classList.remove('active');
}

/* -----------------------------------------------
   Управление активами
----------------------------------------------- */
function addAsset(ticker, name, sector) {
    if (DashboardState.assets.some(a => a.ticker === ticker)) {
        alert('Актив уже добавлен!');
        return;
    }
    DashboardState.assets.push({ ticker, name, sector });
    document.getElementById('searchInput').value = '';
    hideSearch();
    renderAssetList();
}

function removeAsset(ticker) {
    DashboardState.assets = DashboardState.assets.filter(a => a.ticker !== ticker);
    renderAssetList();
}

function updateAssetWeight(ticker, value) {
    const asset = DashboardState.assets.find(a => a.ticker === ticker);
    if (asset) asset.weight = parseFloat(value) || null;
}

function renderAssetList() {
    const container = document.getElementById('assetList');
    const badge = document.getElementById('assetBadge');
    const count = document.getElementById('assetCount');

    const n = DashboardState.assets.length;
    badge.textContent = `${n} ВЫБРАНО`;
    count.textContent = `Активов: ${n}`;

    if (!n) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📈</div>
                <p>Добавьте минимум 2 актива для расчёта эффективной границы портфеля</p>
            </div>
        `;
        return;
    }

    container.innerHTML = DashboardState.assets.map(a => `
        <div class="asset-card">
            <div class="asset-info">
                <div class="asset-ticker">${a.ticker}</div>
                <div class="asset-name">${a.name}</div>
            </div>
            ${DashboardState.isManualWeights ? `
                <input type="number" class="weight-input form-input" placeholder="%" min="0" max="100"
                    value="${a.weight || ''}"
                    onchange="updateAssetWeight('${a.ticker}', this.value)">
            ` : ''}
            <button class="btn btn-danger" onclick="removeAsset('${a.ticker}')">✕</button>
        </div>
    `).join('');
}

/* -----------------------------------------------
   Оптимизация
----------------------------------------------- */
async function runOptimize() {
    if (DashboardState.assets.length < 2) {
        alert('Добавьте минимум 2 актива!');
        return;
    }

    const loader = document.getElementById('loader');
    const results = document.getElementById('results');

    loader.classList.add('active');
    results.style.display = 'none';

    try {
        const payload = {
            assets: DashboardState.assets.map(a => ({
                ticker: a.ticker,
                weight: DashboardState.isManualWeights ? (a.weight ? a.weight / 100 : null) : null
            })),
            start_date: document.getElementById('startDate').value,
            end_date: document.getElementById('endDate').value,
            optimization_goal: document.getElementById('algorithm').value,
            risk_free_rate: parseFloat(document.getElementById('riskFreeRate').value) / 100,
            manual_weights: DashboardState.isManualWeights
        };

        const data = await runOptimization(payload);
        renderResults(data);
    } catch (err) {
        alert('Ошибка оптимизации: ' + err.message);
    } finally {
        loader.classList.remove('active');
    }
}

function renderResults(data) {
    document.getElementById('metricReturn').textContent = data.expected_return.toFixed(2) + '%';
    document.getElementById('metricVol').textContent = data.expected_volatility.toFixed(2) + '%';
    document.getElementById('metricSharpe').textContent = data.sharpe_ratio.toFixed(3);
    document.getElementById('metricSortino').textContent = data.metrics.sortino_ratio.toFixed(3);
    document.getElementById('metricDiv').textContent = data.diversification_ratio.toFixed(3);
    document.getElementById('metricCVaR').textContent = data.metrics.cvar_95.toFixed(2) + '%';

    buildCharts(data);

    const resultsEl = document.getElementById('results');
    resultsEl.style.display = 'block';
    resultsEl.scrollIntoView({ behavior: 'smooth' });
}

function buildCharts(data) {
    const tickers = Object.keys(data.optimized_weights);
    const weights = Object.values(data.optimized_weights);
    const COLORS = ['#A1A364', '#C8C68A', '#797E44', '#c27878', '#EDE8B5', '#525929'];

    // Уничтожаем предыдущие графики
    if (DashboardState.charts.weights) DashboardState.charts.weights.destroy();
    if (DashboardState.charts.risk) DashboardState.charts.risk.destroy();

    DashboardState.charts.weights = new Chart(
        document.getElementById('weightsChart'), {
            type: 'doughnut',
            data: {
                labels: tickers,
                datasets: [{ data: weights, backgroundColor: COLORS }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: 'var(--text-primary)' } }
                }
            }
        }
    );

    DashboardState.charts.risk = new Chart(
        document.getElementById('riskChart'), {
            type: 'bar',
            data: {
                labels: ['Доходность', 'Волатильность', 'Sharpe ×10', 'Sortino ×10', 'Диверс. ×100'],
                datasets: [{
                    label: 'Метрики',
                    data: [
                        data.expected_return,
                        data.expected_volatility,
                        data.sharpe_ratio * 10,
                        data.metrics.sortino_ratio * 10,
                        data.diversification_ratio * 100
                    ],
                    backgroundColor: '#A1A364'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { ticks: { color: 'var(--text-secondary)' }, grid: { color: 'var(--border)' } },
                    x: { ticks: { color: 'var(--text-secondary)' }, grid: { display: false } }
                }
            }
        }
    );
}

/* -----------------------------------------------
   Вспомогательные действия
----------------------------------------------- */
async function showFrontier() {
    alert('Визуализация эффективной границы — скоро будет добавлена!');
}

async function handleRefreshData() {
    const btn = document.getElementById('refreshDataBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Обновление...';

    try {
        const data = await refreshMarket();
        if (data?.prices) updatePriceDisplay(data.prices);
        if (data?.topStocks) updateTopStocksUI(data.topStocks);
        document.getElementById('cacheStatus').textContent = 'Cache: Updated';
        setTimeout(() => {
            document.getElementById('cacheStatus').textContent = 'Cache: Ready';
        }, 3000);
    } catch (err) {
        console.error('Ошибка обновления данных:', err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '🔄 Обновить данные';
    }
}

function updatePriceDisplay(prices) {
    Object.entries(prices).forEach(([symbol, price]) => {
        document.querySelectorAll(`[data-symbol="${symbol}"]`).forEach(el => {
            el.textContent = price;
            el.classList.add('price-flash');
            setTimeout(() => el.classList.remove('price-flash'), 500);
        });
    });
}

function updateTopStocksUI(stocks) {
    const container = document.getElementById('topStocksContainer');
    if (!container) return;
    container.innerHTML = stocks.map(s => `
        <div class="trending-item">
            <div class="trending-coin">
                <div class="trending-icon">${s.symbol[0]}</div>
                <div>
                    <div class="trending-name">${s.symbol}</div>
                    <div class="trending-price">${s.price}</div>
                </div>
            </div>
            <div class="trending-change ${s.change.includes('+') ? 'positive' : 'negative'}">${s.change}</div>
        </div>
    `).join('');
}
