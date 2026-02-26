/**
 * dashboard.js — Главная страница: оптимизация + условный рендеринг результатов.
 *
 * НОВИЧОК (beginner) — блоки результатов:
 *   1. Диаграмма введённого портфеля
 *   2. Таблица введённого портфеля (метрики + состав)
 *   3. Графики сравнения акций (доходность / риск / Sharpe)
 *   4. Таблица оптимизированного портфеля
 *   5. Диаграмма оптимизированного портфеля
 *   6. График сравнения введённого vs оптимизированного
 *
 * ПРОФЕССИОНАЛ (professional) — блоки результатов:
 *   1. Диаграмма введённого портфеля
 *   2. Таблица введённого портфеля
 *   3. Графики сравнения акций
 *   4. Таблицы корреляций и ковариаций
 *   5. Таблицы всех оптимизированных портфелей
 *   6. Диаграммы всех оптимизированных портфелей
 *   7. Графики сравнения введённого vs всех оптимизированных
 *   8. Итоговая сравнительная таблица
 */

// ================================================================
// СОСТОЯНИЕ
// ================================================================
const DashboardState = {
    assets: [],   // { ticker, name, sector, quantity, weight, minWeight, maxWeight }
    charts: {},   // хранилище Chart.js инстанций
    isManualWeights: false,
    lastResult: null,
};

const COLORS = [
    '#A1A364','#C8C68A','#797E44','#c27878',
    '#EDE8B5','#525929','#9b8ea0','#d4a574',
    '#6b9e6b','#7a9bbf','#e0a060','#a06080',
];

// ================================================================
// ИНИЦИАЛИЗАЦИЯ
// ================================================================
document.addEventListener('DOMContentLoaded', () => {
    initDates();
    applyKnowledgeLevel();
    bindEvents();
    renderAssetList();
});

function initDates() {
    const end = new Date();
    const start = new Date();
    start.setFullYear(end.getFullYear() - 3);
    document.getElementById('endDate').valueAsDate   = end;
    document.getElementById('startDate').valueAsDate = start;
}

function applyKnowledgeLevel() {
    const isPro = AppState.get('knowledgeLevel') === 'professional';

    // Блок диверсификации — только pro
    const proBlock = document.getElementById('proFeatures');
    if (proBlock) proBlock.style.display = isPro ? 'block' : 'none';

    // Скрытые метрики для новичка
    ['sortinoCard','cvarCard'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = isPro ? '' : 'none';
    });

    // Модели оптимизации: для новичка убираем сложные
    if (!isPro) {
        ['risk_parity','min_cvar','all'].forEach(val => {
            const opt = document.querySelector(`#algorithm option[value="${val}"]`);
            if (opt) opt.remove();
        });
    }
}

// ================================================================
// СОБЫТИЯ
// ================================================================
function bindEvents() {
    const searchInput = document.getElementById('searchInput');
    let searchTimer;
    searchInput?.addEventListener('input', e => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => handleSearch(e.target.value), 300);
    });
    searchInput?.addEventListener('blur', () => setTimeout(hideSearch, 200));

    document.getElementById('optimizeBtn')?.addEventListener('click', runOptimize);
    document.getElementById('refreshDataBtn')?.addEventListener('click', handleRefreshData);

    const divToggle = document.getElementById('diversificationToggle');
    divToggle?.addEventListener('click', () => {
        divToggle.classList.toggle('active');
        DashboardState.isManualWeights = divToggle.classList.contains('active');
        renderAssetList();
    });
}

// ================================================================
// ПОИСК
// ================================================================
async function handleSearch(query) {
    if (query.length < 2) { hideSearch(); return; }
    try {
        const results = await searchStocks(query);
        renderSearchResults(results);
    } catch (err) {
        console.error('Поиск:', err.message);
    }
}

function renderSearchResults(stocks) {
    const container = document.getElementById('searchResults');
    container.innerHTML = stocks.length
        ? stocks.map(s => `
            <div class="search-item"
                 onclick="addAsset('${s.ticker}','${s.name}','${s.sector||''}')">
                <div>
                    <span class="search-ticker">${s.ticker}</span>
                    <span class="search-name">${s.name}</span>
                </div>
                ${s.sector ? `<span class="search-sector">${s.sector}</span>` : ''}
            </div>`).join('')
        : '<div class="search-item">Ничего не найдено</div>';
    container.classList.add('active');
}

function hideSearch() {
    document.getElementById('searchResults')?.classList.remove('active');
}

// ================================================================
// УПРАВЛЕНИЕ АКТИВАМИ
// ================================================================
function addAsset(ticker, name, sector) {
    if (DashboardState.assets.some(a => a.ticker === ticker)) {
        alert('Актив уже добавлен!'); return;
    }
    DashboardState.assets.push({ ticker, name, sector,
        quantity: null, weight: null, minWeight: null, maxWeight: null });
    document.getElementById('searchInput').value = '';
    hideSearch();
    renderAssetList();
}

function removeAsset(ticker) {
    DashboardState.assets = DashboardState.assets.filter(a => a.ticker !== ticker);
    renderAssetList();
}

function updateAssetField(ticker, field, value) {
    const asset = DashboardState.assets.find(a => a.ticker === ticker);
    if (asset) asset[field] = value !== '' ? parseFloat(value) : null;
}

function renderAssetList() {
    const container = document.getElementById('assetList');
    const badge     = document.getElementById('assetBadge');
    const count     = document.getElementById('assetCount');
    const isPro     = AppState.get('knowledgeLevel') === 'professional';
    const isManual  = DashboardState.isManualWeights;
    const n         = DashboardState.assets.length;

    if (badge) badge.textContent = `${n} ВЫБРАНО`;
    if (count) count.textContent = `Активов: ${n}`;

    if (!n) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📈</div>
                <p>Добавьте минимум 2 актива и укажите количество акций</p>
            </div>`;
        return;
    }

    container.innerHTML = DashboardState.assets.map(a => `
        <div class="asset-card">
            <div class="asset-info">
                <div class="asset-ticker">${a.ticker}</div>
                <div class="asset-name">${a.name}</div>
            </div>
            <div class="asset-field">
                <label class="asset-field-label">Кол-во <span style="color:var(--negative)">*</span></label>
                <input type="number" class="form-input asset-input" placeholder="шт."
                    min="1" step="1" value="${a.quantity ?? ''}"
                    onchange="updateAssetField('${a.ticker}','quantity',this.value)">
            </div>
            ${isManual && isPro ? `
                <div class="asset-field">
                    <label class="asset-field-label">Вес %</label>
                    <input type="number" class="form-input asset-input" placeholder="%"
                        min="0" max="100" value="${a.weight ?? ''}"
                        onchange="updateAssetField('${a.ticker}','weight',this.value)">
                </div>` : ''}
            ${isPro ? `
                <div class="asset-field">
                    <label class="asset-field-label">Мин %</label>
                    <input type="number" class="form-input asset-input" placeholder="0"
                        min="0" max="100" value="${a.minWeight ?? ''}"
                        onchange="updateAssetField('${a.ticker}','minWeight',this.value)">
                </div>
                <div class="asset-field">
                    <label class="asset-field-label">Макс %</label>
                    <input type="number" class="form-input asset-input" placeholder="100"
                        min="0" max="100" value="${a.maxWeight ?? ''}"
                        onchange="updateAssetField('${a.ticker}','maxWeight',this.value)">
                </div>` : ''}
            <button class="btn btn-danger" onclick="removeAsset('${a.ticker}')">✕</button>
        </div>`).join('');
}

// ================================================================
// ВАЛИДАЦИЯ
// ================================================================
function validateForm() {
    const assets = DashboardState.assets;

    if (assets.length < 2)
        return 'Добавьте минимум 2 актива.';

    for (const a of assets) {
        if (!a.quantity || a.quantity <= 0)
            return `Укажите количество акций для ${a.ticker} (> 0).`;
    }

    const budget = parseFloat(document.getElementById('budget')?.value);
    if (!budget || budget < 100)
        return 'Бюджет должен быть не менее $100.';

    const isPro = AppState.get('knowledgeLevel') === 'professional';
    if (isPro) {
        let totalMin = 0;
        for (const a of assets) {
            if (a.minWeight != null) totalMin += parseFloat(a.minWeight);
            if (a.minWeight != null && a.maxWeight != null &&
                parseFloat(a.minWeight) > parseFloat(a.maxWeight))
                return `${a.ticker}: минимум (${a.minWeight}%) > максимума (${a.maxWeight}%)`;
        }
        if (totalMin > 100)
            return `Сумма минимальных долей (${totalMin.toFixed(1)}%) превышает 100%.`;
    }

    return null;
}

// ================================================================
// ОПТИМИЗАЦИЯ
// ================================================================
async function runOptimize() {
    const err = validateForm();
    if (err) { alert(err); return; }

    const loader  = document.getElementById('loader');
    const results = document.getElementById('results');
    loader.classList.add('active');
    if (results) results.style.display = 'none';

    try {
        const params = {
            budget:            parseFloat(document.getElementById('budget')?.value || 10000),
            startDate:         document.getElementById('startDate').value,
            endDate:           document.getElementById('endDate').value,
            optimizationModel: document.getElementById('algorithm').value,
            riskFreeRate:      parseFloat(document.getElementById('riskFreeRate').value) / 100,
            maxAssets:         document.getElementById('maxAssets')?.value || null,
            isManualWeights:   DashboardState.isManualWeights,
        };
        const level = AppState.get('knowledgeLevel') || 'beginner';
        const data  = await runOptimization(DashboardState.assets, params, level);

        DashboardState.lastResult = data;
        renderResults(data, level);
    } catch (err) {
        alert('Ошибка оптимизации: ' + err.message);
    } finally {
        loader.classList.remove('active');
    }
}

// ================================================================
// ГЛАВНЫЙ РОУТЕР РЕНДЕРИНГА
// ================================================================
function renderResults(data, level) {
    const resultsEl = document.getElementById('results');
    if (!resultsEl) return;

    // Очищаем все старые графики
    destroyAllCharts();

    // Очищаем контейнер результатов
    resultsEl.innerHTML = '';

    if (level === 'professional') {
        renderProResults(data, resultsEl);
    } else {
        renderBeginnerResults(data, resultsEl);
    }

    resultsEl.style.display = 'block';
    resultsEl.scrollIntoView({ behavior: 'smooth' });
}

function destroyAllCharts() {
    Object.values(DashboardState.charts).forEach(c => { if (c) c.destroy(); });
    DashboardState.charts = {};
}

// ================================================================
// ВСПОМОГАТЕЛЬНЫЕ УТИЛИТЫ
// ================================================================

/** Безопасное форматирование — если значения нет, возвращает '—' */
function fmt(value, decimals = 2, suffix = '') {
    if (value == null || isNaN(value)) return '—';
    return Number(value).toFixed(decimals) + suffix;
}

/** Создаёт карточку-секцию */
function section(title, badge, content) {
    return `
        <div class="card animate-in" style="margin-bottom:24px;">
            <div class="card-header">
                <h2 class="card-title">${title}</h2>
                ${badge ? `<span class="badge">${badge}</span>` : ''}
            </div>
            ${content}
        </div>`;
}

/** Таблица метрик портфеля (введённый или оптимизированный) */
function portfolioMetricsTable(p) {
    if (!p || !p.metrics) return '<p class="text-muted">Нет данных</p>';
    const m = p.metrics;
    const rows = [
        ['Бюджет',          m.budget        != null ? `$${Number(m.budget).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}` : '—'],
        ['Прибыль/мес',     m.monthly_profit!= null ? `$${fmt(m.monthly_profit)}` : '—'],
        ['Риск/мес',        m.monthly_risk  != null ? `$${fmt(m.monthly_risk)}`  : '—'],
        ['Доходность/мес',  fmt(m.return_pct, 4, '%')],
        ['Sharpe',          fmt(m.sharpe, 4)],
        ['Окупаемость',     m.payback_months != null ? `${fmt(m.payback_months, 1)} мес` : '—'],
    ];

    // Состав
    const composition = (p.tickers || []).map((t, i) => `
        <tr>
            <td>${t}</td>
            <td class="text-right">${p.shares?.[i] ?? '—'}</td>
            <td class="text-right">${p.weights?.[i] != null ? fmt(p.weights[i]*100, 1)+'%' : '—'}</td>
        </tr>`).join('');

    return `
        <div class="metrics-dashboard">
            ${rows.map(([label, val]) => `
                <div class="metric-card">
                    <div class="metric-label">${label}</div>
                    <div class="metric-value">${val}</div>
                </div>`).join('')}
        </div>
        ${composition ? `
        <div style="margin-top:16px;overflow-x:auto;">
            <table class="market-table">
                <thead><tr>
                    <th>Тикер</th>
                    <th class="text-right">Кол-во</th>
                    <th class="text-right">Доля</th>
                </tr></thead>
                <tbody>${composition}</tbody>
            </table>
        </div>` : ''}`;
}

/** Создаёт canvas-обёртку и возвращает id */
function canvasBlock(id, height = 300) {
    return `<div class="chart-container" style="height:${height}px;position:relative;">
                <canvas id="${id}"></canvas>
            </div>`;
}

/** Безопасно создаёт Chart — проверяет наличие canvas */
function safeChart(id, config) {
    const el = document.getElementById(id);
    if (!el) return null;
    const chart = new Chart(el, config);
    DashboardState.charts[id] = chart;
    return chart;
}

// ================================================================
// БЛОКИ — ОБЩИЕ ДЛЯ ОБОИХ УРОВНЕЙ
// ================================================================

/** Блок 1: Диаграмма весов введённого портфеля */
function blockInputPieChart(data) {
    const p = data.input_portfolio;
    if (!p) return '';
    const id = 'inputPieChart';
    return section('📊 Введённый портфель — распределение', null,
        canvasBlock(id, 280));
}
function initInputPieChart(data) {
    const p = data.input_portfolio;
    if (!p) return;
    safeChart('inputPieChart', {
        type: 'doughnut',
        data: {
            labels: p.tickers,
            datasets: [{ data: p.weights.map(w => (w*100).toFixed(1)), backgroundColor: COLORS }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { color: 'var(--text-primary)' } } }
        }
    });
}

/** Блок 2: Таблица введённого портфеля */
function blockInputTable(data) {
    const p = data.input_portfolio;
    if (!p) return '';
    return section('📋 Введённый портфель — метрики', null, portfolioMetricsTable(p));
}

/** Блок 3: Сравнение акций по доходности / риску / Sharpe */
function blockStockCharts(data) {
    const stats = data.stock_stats;
    if (!stats || !stats.length) return '';

    return section('📈 Анализ акций', null, `
        <div class="chart-grid">
            <div class="chart-wrapper">
                <div class="chart-title">Доходность/мес (%)</div>
                ${canvasBlock('stockReturnChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">Риск/мес (%)</div>
                ${canvasBlock('stockRiskChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">Sharpe Ratio</div>
                ${canvasBlock('stockSharpeChart', 220)}
            </div>
        </div>`);
}
function initStockCharts(data) {
    const stats = data.stock_stats;
    if (!stats || !stats.length) return;

    const labels    = stats.map(s => s.ticker);
    const barOpts   = (color) => ({
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            y: { ticks: { color: 'var(--text-secondary)' }, grid: { color: 'var(--border)' } },
            x: { ticks: { color: 'var(--text-secondary)' }, grid: { display: false } }
        }
    });

    safeChart('stockReturnChart', {
        type: 'bar',
        data: { labels, datasets: [{ data: stats.map(s => s.mean_ret_pct), backgroundColor: '#A1A364' }] },
        options: barOpts()
    });
    safeChart('stockRiskChart', {
        type: 'bar',
        data: { labels, datasets: [{ data: stats.map(s => s.std_ret_pct), backgroundColor: '#c27878' }] },
        options: barOpts()
    });
    safeChart('stockSharpeChart', {
        type: 'bar',
        data: { labels, datasets: [{ data: stats.map(s => s.sharpe), backgroundColor: '#C8C68A' }] },
        options: barOpts()
    });
}

// ================================================================
// BEGINNER — рендеринг
// ================================================================
function renderBeginnerResults(data, container) {
    const best = getBestPortfolio(data);

    let html = '';
    html += blockInputPieChart(data);
    html += blockInputTable(data);
    html += blockStockCharts(data);

    // Блок 4: Таблица оптимизированного портфеля
    if (best) {
        html += section('✅ Оптимизированный портфель — метрики', 'ЛУЧШИЙ',
            portfolioMetricsTable(best));
    }

    // Блок 5: Диаграмма оптимизированного
    if (best) {
        html += section('🥧 Оптимизированный портфель — распределение', null,
            canvasBlock('optPieChart', 280));
    }

    // Блок 6: Сравнение введённого vs оптимизированного
    if (data.input_portfolio && best) {
        html += section('🔀 Сравнение: введённый vs оптимизированный', null,
            canvasBlock('compareChart', 280));
    }

    container.innerHTML = html;

    // Инициализация графиков
    initInputPieChart(data);
    initStockCharts(data);
    if (best) initOptPieChart(best, 'optPieChart');
    if (data.input_portfolio && best) initCompareChart(data, [best]);
}

// ================================================================
// PROFESSIONAL — рендеринг
// ================================================================
function renderProResults(data, container) {
    const portfolios = data.all_portfolios || [];
    const best       = getBestPortfolio(data);

    let html = '';
    html += blockInputPieChart(data);
    html += blockInputTable(data);
    html += blockStockCharts(data);

    // Блок 4: Корреляция и ковариация
    if (data.correlation) {
        html += section('🔗 Матрица корреляций', null, matrixTable(data.correlation, 4));
    }
    if (data.covariance) {
        html += section('📐 Матрица ковариаций', null, matrixTable(data.covariance, 6));
    }

    // Блок 5: Таблицы всех оптимизированных портфелей
    portfolios.forEach(p => {
        html += section(`✅ Портфель: ${p.name}`,
            p.name === data.best_portfolio ? 'ЛУЧШИЙ' : null,
            portfolioMetricsTable(p));
    });

    // Блок 6: Диаграммы всех оптимизированных портфелей
    if (portfolios.length) {
        const pieSections = portfolios.map((p, i) => `
            <div class="chart-wrapper">
                <div class="chart-title">${p.name}</div>
                ${canvasBlock('optPie_' + i, 240)}
            </div>`).join('');
        html += section('🥧 Распределение оптимизированных портфелей', null,
            `<div class="chart-grid">${pieSections}</div>`);
    }

    // Блок 7: Сравнение введённого vs всех оптимизированных
    if (data.input_portfolio && portfolios.length) {
        html += section('🔀 Сравнение портфелей по метрикам', null,
            canvasBlock('compareChart', 320));
    }

    // Блок 8: Итоговая таблица сравнения
    if (portfolios.length) {
        html += section('📊 Итоговое сравнение всех портфелей', null,
            allPortfoliosTable(data));
    }

    container.innerHTML = html;

    // Инициализация
    initInputPieChart(data);
    initStockCharts(data);
    portfolios.forEach((p, i) => initOptPieChart(p, 'optPie_' + i));
    if (data.input_portfolio && portfolios.length) initCompareChart(data, portfolios);
}

// ================================================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ РЕНДЕРИНГА
// ================================================================

function getBestPortfolio(data) {
    const portfolios = data.all_portfolios || [];
    if (!portfolios.length) return null;
    return portfolios.find(p => p.name === data.best_portfolio) || portfolios[0];
}

function initOptPieChart(portfolio, canvasId) {
    if (!portfolio) return;
    safeChart(canvasId, {
        type: 'doughnut',
        data: {
            labels: portfolio.tickers,
            datasets: [{
                data: (portfolio.weights || []).map(w => (w * 100).toFixed(1)),
                backgroundColor: COLORS
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { color: 'var(--text-primary)' } } }
        }
    });
}

/** Grouped bar chart: сравнение портфелей по 4 метрикам */
function initCompareChart(data, portfolios) {
    const inputP = data.input_portfolio;
    if (!inputP) return;

    const labels   = ['Доходность/мес %', 'Риск/мес %', 'Sharpe', 'Окупаемость (мес)'];
    const getVals  = (p) => {
        const m = p?.metrics || {};
        return [
            m.return_pct   ?? 0,
            m.budget > 0 ? (m.monthly_risk / m.budget * 100) : 0,
            m.sharpe       ?? 0,
            Math.min(m.payback_months ?? 999, 200),
        ];
    };

    const datasets = [
        {
            label: 'Введённый',
            data: getVals(inputP),
            backgroundColor: 'rgba(161,163,100,0.7)',
        },
        ...portfolios.map((p, i) => ({
            label: p.name,
            data: getVals(p),
            backgroundColor: COLORS[(i + 1) % COLORS.length] + 'CC',
        }))
    ];

    safeChart('compareChart', {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'top', labels: { color: 'var(--text-primary)' } } },
            scales: {
                y: { ticks: { color: 'var(--text-secondary)' }, grid: { color: 'var(--border)' } },
                x: { ticks: { color: 'var(--text-secondary)' }, grid: { display: false } }
            }
        }
    });
}

/** Матрица корреляций/ковариаций */
function matrixTable(matrixData, decimals = 4) {
    if (!matrixData || !matrixData.tickers) return '<p>Нет данных</p>';
    const tickers = matrixData.tickers;
    const matrix  = matrixData.matrix;

    const headerRow = `<tr><th></th>${tickers.map(t => `<th class="text-right">${t}</th>`).join('')}</tr>`;
    const rows = tickers.map((t, i) => `
        <tr>
            <td><strong>${t}</strong></td>
            ${matrix[i].map(v => `<td class="text-right" style="font-size:12px;">${fmt(v, decimals)}</td>`).join('')}
        </tr>`).join('');

    return `
        <div style="overflow-x:auto;">
            <table class="market-table">
                <thead>${headerRow}</thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
}

/** Итоговая сравнительная таблица всех портфелей */
function allPortfoliosTable(data) {
    const portfolios = data.all_portfolios || [];
    const input      = data.input_portfolio;
    if (!portfolios.length) return '';

    const allP = input
        ? [{ name: 'Введённый', metrics: input.metrics }, ...portfolios]
        : portfolios;

    const headers = ['Портфель','Бюджет','Прибыль/мес','Риск/мес','Sharpe','Доходность/мес','Окупаемость'];

    const rows = allP.map(p => {
        const m = p.metrics || {};
        const isBest = p.name === data.best_portfolio;
        return `<tr ${isBest ? 'style="background:rgba(161,163,100,0.08);"' : ''}>
            <td><strong>${p.name}</strong>${isBest ? ' ⭐' : ''}</td>
            <td class="text-right">${m.budget   != null ? '$'+Number(m.budget).toLocaleString('en-US',{maximumFractionDigits:0}) : '—'}</td>
            <td class="text-right positive">${m.monthly_profit != null ? '$'+fmt(m.monthly_profit) : '—'}</td>
            <td class="text-right negative">${m.monthly_risk   != null ? '$'+fmt(m.monthly_risk)   : '—'}</td>
            <td class="text-right">${fmt(m.sharpe, 4)}</td>
            <td class="text-right">${fmt(m.return_pct, 4, '%')}</td>
            <td class="text-right">${m.payback_months != null ? fmt(m.payback_months, 1)+' мес' : '—'}</td>
        </tr>`;
    }).join('');

    return `
        <div style="overflow-x:auto;">
            <table class="market-table">
                <thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
}

// ================================================================
// ВСПОМОГАТЕЛЬНЫЕ ДЕЙСТВИЯ
// ================================================================
async function handleRefreshData() {
    const btn = document.getElementById('refreshDataBtn');
    if (!btn) return;
    btn.disabled    = true;
    btn.textContent = '⏳ Обновление...';
    try {
        await refreshMarket();
        const cs = document.getElementById('cacheStatus');
        if (cs) { cs.textContent = 'Cache: Updated'; setTimeout(()=>{ cs.textContent='Cache: Ready'; }, 3000); }
    } catch (err) {
        console.error('Обновление:', err.message);
    } finally {
        btn.disabled    = false;
        btn.textContent = '🔄 Обновить данные';
    }
}
