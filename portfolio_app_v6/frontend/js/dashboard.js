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

function clearAllAssets() {
    if (DashboardState.assets.length === 0) return;
    if (!confirm('Очистить список активов?')) return;
    DashboardState.assets = [];
    renderAssetList();
}

// Показывать ли колонки Min/Max Weight (toggled by gear button)
let _showMinMax = true;

function toggleExtraColumns() {
    _showMinMax = !_showMinMax;
    renderAssetList();
}

function updateAssetField(ticker, field, value) {
    const asset = DashboardState.assets.find(a => a.ticker === ticker);
    if (asset) {
        asset[field] = value !== '' ? parseFloat(value) : null;
        // При изменении поля — обновляем бюджет и предупреждение
        if (field === 'quantity') updateBudgetDisplay();
        if (field === 'weight')   updateAllocWarning();
    }
}

// TABLE_ROWS — сколько строк показывать сразу
const TABLE_ROWS = 10;
let _showAllRows = false;

/** Обновляет отображение авто-бюджета в шапке */
function updateBudgetDisplay() {
    // Бюджет = сумма (quantity * цена). Цены нам неизвестны без бэкенда,
    // поэтому показываем сумму акций * "текущая цена" только если данные придут из результата.
    // До запуска — показываем количество акций (сумма).
    const assets = DashboardState.assets;
    const totalShares = assets.reduce((s, a) => s + (a.quantity || 0), 0);
    const budgetVal = document.getElementById('budgetValue');
    const budgetHidden = document.getElementById('budget');

    if (DashboardState.lastResult && DashboardState.lastResult.input_portfolio) {
        const ip = DashboardState.lastResult.input_portfolio;
        const calcBudget = ip.metrics?.budget;
        if (calcBudget && budgetVal) {
            budgetVal.textContent = '$' + Number(calcBudget).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            if (budgetHidden) budgetHidden.value = calcBudget;
        }
    } else if (totalShares > 0) {
        if (budgetVal) budgetVal.textContent = `${totalShares} акц.`;
    } else {
        if (budgetVal) budgetVal.textContent = '—';
    }
}

/** Показывает предупреждение о сумме Allocation */
function updateAllocWarning() {
    const assets = DashboardState.assets;
    const filled = assets.filter(a => a.weight != null && a.weight > 0);
    if (!filled.length) {
        renderAllocWarning(null);
        return;
    }
    const total = assets.reduce((s, a) => s + (a.weight || 0), 0);
    renderAllocWarning(total);
}

function renderAllocWarning(total) {
    // Обновляем строку Total в таблице — вызовется через renderAssetList
    // Также рендерим банер под таблицей
    let el = document.getElementById('allocWarning');
    if (!el) {
        el = document.createElement('div');
        el.id = 'allocWarning';
        const wrap = document.getElementById('assetList');
        if (wrap) wrap.parentNode.insertBefore(el, wrap.nextSibling);
    }

    if (total === null) { el.innerHTML = ''; return; }

    const diff = Math.abs(total - 100).toFixed(1);
    if (Math.abs(total - 100) < 0.1) {
        el.innerHTML = `<div class="alloc-warning warn-ok">✅ Сумма Allocation = 100% — отлично!</div>`;
    } else if (total < 100) {
        el.innerHTML = `<div class="alloc-warning warn-under">⚠️ Сумма Allocation = ${total.toFixed(1)}% — не хватает ${diff}% до 100%</div>`;
    } else {
        el.innerHTML = `<div class="alloc-warning warn-over">❌ Сумма Allocation = ${total.toFixed(1)}% — превышает 100% на ${diff}%</div>`;
    }
}

function renderAssetList() {
    const container = document.getElementById('assetList');
    const badge     = document.getElementById('assetBadge');
    const count     = document.getElementById('assetCount');
    const isPro     = AppState.get('knowledgeLevel') === 'professional';
    const isManual  = DashboardState.isManualWeights;
    const assets    = DashboardState.assets;
    const n         = assets.length;

    if (badge) badge.textContent = `${n} ВЫБРАНО`;
    if (count) count.textContent = `Активов: ${n}`;

    updateBudgetDisplay();

    // Вычисляем суммарный allocation
    const totalAlloc = assets.reduce((sum, a) => sum + (a.weight || 0), 0);
    const allocFilled = assets.some(a => a.weight != null && a.weight > 0);

    // Строим заголовки таблицы
    const showMin    = _showMinMax && isPro;
    const showMax    = _showMinMax && isPro;
    const showManual = isManual && isPro;

    const headerCols = `
        <th style="width:48px;">&nbsp;</th>
        <th>Тикер</th>
        <th>Кол-во акций</th>
        <th>Allocation</th>
        ${showMin ? '<th>Min. Weight</th>' : ''}
        ${showMax ? '<th>Max. Weight</th>' : ''}
        ${showManual ? '<th>Вес %</th>' : ''}
        <th class="th-actions" style="width:40px;"></th>
    `;

    // Список строк — ограничиваем если нужно
    const displayed = (_showAllRows || n <= TABLE_ROWS) ? assets : assets.slice(0, TABLE_ROWS);
    const hasMore   = n > TABLE_ROWS && !_showAllRows;
    const lastIdx   = displayed.length - 1;

    const rows = displayed.map((a, i) => {
        const rowNum = i + 1;
        const isLast = i === lastIdx && hasMore;
        return `
        <tr>
            <td>
                <div class="row-num-cell">
                    <span>${rowNum}</span>
                    ${isLast ? `<span class="more-link" onclick="_showAllRows=true;renderAssetList()">(More)</span>` : ''}
                </div>
            </td>
            <td class="ticker-cell" style="position:relative;">
                <div class="ticker-input-wrap">
                    <span class="ticker-badge">
                        <span style="color:var(--accent);font-weight:700;">${a.ticker}</span>
                        <span class="ticker-badge-name">${a.name ? '— ' + a.name : ''}</span>
                    </span>
                    <button class="ticker-search-btn" onclick="openTickerSearch('${a.ticker}')" title="Поиск">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                        </svg>
                    </button>
                </div>
            </td>
            <td>
                <div class="pct-input-wrap">
                    <input type="number" class="pct-input" placeholder="шт."
                        min="1" max="100" step="1" value="${a.quantity ?? ''}"
                        onchange="updateAssetField('${a.ticker}','quantity',this.value)">
                </div>
            </td>
            <td>
                <div class="pct-input-wrap">
                    <input type="number" class="pct-input" placeholder=""
                        min="0" max="100" step="0.1" value="${a.weight ?? ''}"
                        onchange="updateAssetField('${a.ticker}','weight',this.value)">
                    <span class="pct-suffix">%</span>
                </div>
            </td>
            ${showMin ? `<td>
                <div class="pct-input-wrap">
                    <input type="number" class="pct-input" placeholder="0"
                        min="0" max="100" step="0.1" value="${a.minWeight ?? ''}"
                        onchange="updateAssetField('${a.ticker}','minWeight',this.value)">
                    <span class="pct-suffix">%</span>
                </div>
            </td>` : ''}
            ${showMax ? `<td>
                <div class="pct-input-wrap">
                    <input type="number" class="pct-input" placeholder="100"
                        min="0" max="100" step="0.1" value="${a.maxWeight ?? ''}"
                        onchange="updateAssetField('${a.ticker}','maxWeight',this.value)">
                    <span class="pct-suffix">%</span>
                </div>
            </td>` : ''}
            ${showManual ? `<td>
                <div class="pct-input-wrap">
                    <input type="number" class="pct-input" placeholder="%"
                        min="0" max="100" step="0.1" value="${a.weight ?? ''}"
                        onchange="updateAssetField('${a.ticker}','weight',this.value)">
                    <span class="pct-suffix">%</span>
                </div>
            </td>` : ''}
            <td style="text-align:center;">
                <button class="row-delete-btn" onclick="removeAsset('${a.ticker}')" title="Удалить">✕</button>
            </td>
        </tr>`;
    }).join('');

    // Цвет итога
    const overLimit  = totalAlloc > 100.05;
    const underLimit = allocFilled && totalAlloc < 99.95;
    const totalColor = overLimit ? 'color:var(--negative);font-weight:700;'
                     : underLimit ? 'color:#d4a574;font-weight:700;'
                     : allocFilled ? 'color:var(--positive);font-weight:700;' : '';

    // Подвал с итогом
    const colSpanBefore = 3; // #, ticker, qty
    const extraCols = (showMin ? 1 : 0) + (showMax ? 1 : 0) + (showManual ? 1 : 0);

    container.innerHTML = `
        <table class="asset-table">
            <thead>
                <tr>${headerCols}</tr>
            </thead>
            <tbody>
                ${rows || `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--text-muted);">
                    Добавьте минимум 2 актива через строку поиска выше
                </td></tr>`}
            </tbody>
            <tfoot>
                <tr>
                    <td colspan="${colSpanBefore}"><strong>Total</strong></td>
                    <td>
                        <div class="total-alloc-cell" style="${totalColor}">
                            <span class="total-alloc-val" style="${totalColor}">${totalAlloc > 0 ? totalAlloc.toFixed(1) : 0}</span>
                            <span class="total-alloc-suffix">%</span>
                        </div>
                    </td>
                    ${showMin ? '<td></td>' : ''}
                    ${showMax ? '<td></td>' : ''}
                    ${showManual ? '<td></td>' : ''}
                    <td></td>
                </tr>
            </tfoot>
        </table>`;

    // Обновить предупреждение об allocation
    updateAllocWarning();
}

function openTickerSearch(currentTicker) {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.value = currentTicker;
        searchInput.focus();
        handleSearch(currentTicker);
    }
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
        if (a.quantity > 100)
            return `${a.ticker}: максимальное количество акций — 100.`;
    }

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
        // Бюджет = сумма quantity*price рассчитывается на бэкенде.
        // Передаём большое значение-заглушку (бэкенд всё равно пересчитает по реальным ценам).
        const params = {
            budget:            999999999,
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
        // Обновляем отображение бюджета из реального результата
        updateBudgetDisplay();
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

    // Красивая таблица состава
    const tickers = p.tickers || [];
    const maxWeight = Math.max(...(p.weights || [0]).map(w => w * 100));

    const compositionRows = tickers.map((t, i) => {
        const shares = p.shares?.[i] ?? '—';
        const wPct   = p.weights?.[i] != null ? p.weights[i] * 100 : null;
        const barW   = wPct != null ? Math.round((wPct / Math.max(maxWeight, 1)) * 120) : 0;
        return `<tr>
            <td><span class="comp-ticker">${t}</span></td>
            <td class="comp-shares">${shares}</td>
            <td class="comp-weight-cell">
                <div class="weight-bar-wrap">
                    <div class="weight-bar" style="width:${barW}px;"></div>
                    <span class="weight-pct">${wPct != null ? wPct.toFixed(1)+'%' : '—'}</span>
                </div>
            </td>
        </tr>`;
    }).join('');

    return `
        <div class="metrics-dashboard">
            ${rows.map(([label, val]) => `
                <div class="metric-card">
                    <div class="metric-label">${label}</div>
                    <div class="metric-value">${val}</div>
                </div>`).join('')}
        </div>
        ${compositionRows ? `
        <table class="composition-table">
            <thead>
                <tr>
                    <th>Тикер</th>
                    <th class="text-right">Кол-во акций</th>
                    <th class="text-right">Доля</th>
                </tr>
            </thead>
            <tbody>${compositionRows}</tbody>
        </table>` : ''}`;
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

/** Матрица корреляций/ковариаций — красивая с тепловой картой */
function matrixTable(matrixData, decimals = 4) {
    if (!matrixData || !matrixData.tickers) return '<p>Нет данных</p>';
    const tickers = matrixData.tickers;
    const matrix  = matrixData.matrix;

    // Находим min/max для тепловой карты (исключая диагональ у корреляции)
    let allVals = [];
    matrix.forEach((row, i) => row.forEach((v, j) => { if (i !== j) allVals.push(v); }));
    const minV = Math.min(...allVals);
    const maxV = Math.max(...allVals);

    function heatColor(v, isDiag) {
        if (isDiag) return '';
        // Нормализуем 0..1
        const t = maxV === minV ? 0.5 : (v - minV) / (maxV - minV);
        // От синего (cold) через нейтральный до зелёного (hot)
        const r = Math.round(161 * t);
        const g = Math.round(100 + 58 * t);
        const b = Math.round(100 * (1 - t));
        return `background:rgba(${r},${g},${b},0.18);`;
    }

    const headerRow = `<tr>
        <th style="text-align:left;min-width:60px;"></th>
        ${tickers.map(t => `<th>${t}</th>`).join('')}
    </tr>`;

    const rows = tickers.map((t, i) => `
        <tr>
            <td class="row-label">${t}</td>
            ${matrix[i].map((v, j) => {
                const isDiag = i === j;
                return `<td class="cell-val ${isDiag ? 'cell-diag' : ''}" style="${heatColor(v, isDiag)}">${v.toFixed(decimals)}</td>`;
            }).join('')}
        </tr>`).join('');

    return `
        <div class="matrix-wrap">
            <table class="matrix-table">
                <thead>${headerRow}</thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
}

/** Красивая итоговая сравнительная таблица всех портфелей */
function allPortfoliosTable(data) {
    const portfolios = data.all_portfolios || [];
    const input      = data.input_portfolio;
    if (!portfolios.length) return '';

    const allP = input
        ? [{ name: 'Введённый', metrics: input.metrics, isInput: true }, ...portfolios]
        : portfolios;

    // Найдём макс/мин значения для подсветки
    const getM = p => p.metrics || {};
    const sharpeVals  = allP.map(p => getM(p).sharpe ?? 0);
    const returnVals  = allP.map(p => getM(p).return_pct ?? 0);
    const riskVals    = allP.map(p => getM(p).monthly_risk ?? Infinity);
    const maxSharpe   = Math.max(...sharpeVals);
    const maxReturn   = Math.max(...returnVals);
    const minRisk     = Math.min(...riskVals);

    const rows = allP.map((p, idx) => {
        const m      = p.metrics || {};
        const isBest = p.name === data.best_portfolio;
        const isInp  = p.isInput;

        // Иконки и метки
        const icon = isInp  ? '📋'
                   : isBest ? '⭐'
                   : '✅';

        const nameBadge = isBest
            ? `<span class="cmp-badge cmp-best">ЛУЧШИЙ</span>`
            : isInp
            ? `<span class="cmp-badge cmp-input">ВВЕДЁН</span>`
            : '';

        // Sharpe — подсвечиваем лучший
        const sharpeClass = (!isInp && m.sharpe === maxSharpe) ? 'cmp-highlight-green' : '';
        // Return — подсвечиваем лучший
        const retClass    = (!isInp && m.return_pct === maxReturn) ? 'cmp-highlight-green' : '';
        // Risk — подсвечиваем минимальный (лучший)
        const riskClass   = (!isInp && m.monthly_risk === minRisk) ? 'cmp-highlight-blue' : '';

        // Mini sparkline — bar показывающий Sharpe относительно max
        const sharpeBar = maxSharpe > 0
            ? Math.round(((m.sharpe ?? 0) / maxSharpe) * 60)
            : 0;

        return `
        <tr class="cmp-row ${isBest ? 'cmp-row-best' : ''} ${isInp ? 'cmp-row-input' : ''}">
            <td class="cmp-name-cell">
                <div class="cmp-name-wrap">
                    <span class="cmp-icon">${icon}</span>
                    <div>
                        <div class="cmp-name">${p.name}</div>
                        ${nameBadge}
                    </div>
                </div>
            </td>
            <td class="cmp-val">
                <span class="cmp-dollar">${m.budget != null ? '$'+Number(m.budget).toLocaleString('en-US',{maximumFractionDigits:0}) : '—'}</span>
            </td>
            <td class="cmp-val cmp-positive">
                ${m.monthly_profit != null ? '$'+fmt(m.monthly_profit) : '—'}
            </td>
            <td class="cmp-val ${riskClass}">
                ${m.monthly_risk != null ? '$'+fmt(m.monthly_risk) : '—'}
            </td>
            <td class="cmp-val ${sharpeClass}">
                <div class="cmp-sharpe-wrap">
                    <span>${fmt(m.sharpe, 4)}</span>
                    <div class="cmp-bar" style="width:${sharpeBar}px"></div>
                </div>
            </td>
            <td class="cmp-val ${retClass}">
                ${fmt(m.return_pct, 4, '%')}
            </td>
            <td class="cmp-val">
                ${m.payback_months != null ? fmt(m.payback_months, 1)+' мес' : '—'}
            </td>
        </tr>`;
    }).join('');

    return `
        <div class="cmp-table-wrap">
            <table class="cmp-table">
                <thead>
                    <tr>
                        <th class="cmp-th-name">Портфель</th>
                        <th class="cmp-th">Бюджет</th>
                        <th class="cmp-th">Прибыль/мес</th>
                        <th class="cmp-th">Риск/мес</th>
                        <th class="cmp-th">Sharpe</th>
                        <th class="cmp-th">Доходность/мес</th>
                        <th class="cmp-th">Окупаемость</th>
                    </tr>
                </thead>
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
