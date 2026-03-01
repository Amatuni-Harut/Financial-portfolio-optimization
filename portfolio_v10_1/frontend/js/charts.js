/**
 * charts.js — Создание Chart.js графиков для дашборда.
 *
 * Извлечено из dashboard.js (v6) для разделения ответственности.
 * Содержит только инициализацию графиков — никакого рендеринга HTML.
 *
 * Улучшения v7:
 * 1. Централизованная функция chartDefaults() — общие опции не дублируются.
 * 2. Добавлен initEfficientFrontierChart() — эффективная граница Марковица
 *    (данные были в ответе API, но не визуализировались).
 */

const COLORS = [
    '#A1A364','#C8C68A','#797E44','#c27878',
    '#EDE8B5','#525929','#9b8ea0','#d4a574',
    '#6b9e6b','#7a9bbf','#e0a060','#a06080',
];

// ================================================================
// ОБЩИЕ НАСТРОЙКИ
// ================================================================

function chartDefaults() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false,
                labels: { color: 'var(--text-primary)', font: { size: 12 } },
            },
        },
        scales: {
            y: {
                ticks:  { color: 'var(--text-secondary)', font: { size: 11 } },
                grid:   { color: 'var(--border)' },
            },
            x: {
                ticks:  { color: 'var(--text-secondary)', font: { size: 11 } },
                grid:   { display: false },
            },
        },
    };
}

function pieDefaults() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true,
                position: 'bottom',
                labels: { color: 'var(--text-primary)', padding: 16, font: { size: 12 } },
            },
            tooltip: {
                callbacks: {
                    label: ctx => ` ${ctx.label}: ${ctx.raw}%`,
                },
            },
        },
    };
}

/** Безопасно создаёт Chart и сохраняет в DashboardState.charts */
function safeChart(id, config) {
    const el = document.getElementById(id);
    if (!el) return null;
    const chart = new Chart(el, config);
    DashboardState.charts[id] = chart;
    return chart;
}


// ================================================================
// ГРАФИКИ ВВЕДЁННОГО ПОРТФЕЛЯ
// ================================================================

function initInputPieChart(data) {
    const p = data.input_portfolio;
    if (!p) return;
    safeChart('inputPieChart', {
        type: 'doughnut',
        data: {
            labels: p.tickers,
            datasets: [{
                data: p.weights.map(w => (w * 100).toFixed(1)),
                backgroundColor: COLORS,
                borderWidth: 2,
                borderColor: 'var(--bg-card)',
            }],
        },
        options: pieDefaults(),
    });
}


// ================================================================
// СРАВНЕНИЕ АКЦИЙ
// ================================================================

function initStockCharts(data) {
    const stats = data.stock_stats;
    if (!stats?.length) return;

    const labels = stats.map(s => s.ticker);

    const barOpts = () => ({ ...chartDefaults() });

    safeChart('stockReturnChart', {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: stats.map(s => s.mean_ret_pct),
                backgroundColor: stats.map(s => s.mean_ret_pct >= 0 ? '#A1A364' : '#c27878'),
                borderRadius: 4,
            }],
        },
        options: barOpts(),
    });

    safeChart('stockRiskChart', {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: stats.map(s => s.std_ret_pct),
                backgroundColor: '#9b8ea0',
                borderRadius: 4,
            }],
        },
        options: barOpts(),
    });

    safeChart('stockSharpeChart', {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: stats.map(s => s.sharpe),
                backgroundColor: stats.map(s => s.sharpe >= 0 ? '#C8C68A' : '#c27878'),
                borderRadius: 4,
            }],
        },
        options: barOpts(),
    });
}


// ================================================================
// ГРАФИКИ ОПТИМИЗИРОВАННОГО ПОРТФЕЛЯ
// ================================================================

function initOptPieChart(portfolio, canvasId) {
    if (!portfolio) return;
    safeChart(canvasId, {
        type: 'doughnut',
        data: {
            labels: portfolio.tickers,
            datasets: [{
                data: (portfolio.weights || []).map(w => (w * 100).toFixed(1)),
                backgroundColor: COLORS,
                borderWidth: 2,
                borderColor: 'var(--bg-card)',
            }],
        },
        options: pieDefaults(),
    });
}


// ================================================================
// СРАВНЕНИЕ ПОРТФЕЛЕЙ
// ================================================================

function initCompareChart(data, portfolios) {
    const inputP = data.input_portfolio;
    if (!inputP) return;

    const labels = ['Доходность/мес %', 'Риск/мес %', 'Sharpe', 'Окупаемость (мес)'];

    const getVals = (p) => {
        const m = p?.metrics || {};
        return [
            m.return_pct   ?? 0,
            m.budget > 0   ? (m.monthly_risk / m.budget * 100) : 0,
            m.sharpe       ?? 0,
            Math.min(m.payback_months ?? 999, 200),
        ];
    };

    const datasets = [
        {
            label: 'Введённый',
            data: getVals(inputP),
            backgroundColor: 'rgba(161,163,100,0.7)',
            borderRadius: 4,
        },
        ...portfolios.map((p, i) => ({
            label: p.name,
            data: getVals(p),
            backgroundColor: COLORS[(i + 1) % COLORS.length] + 'CC',
            borderRadius: 4,
        })),
    ];

    const opts = chartDefaults();
    opts.plugins.legend.display = true;
    opts.plugins.legend.position = 'top';

    safeChart('compareChart', {
        type: 'bar',
        data: { labels, datasets },
        options: opts,
    });
}


// ================================================================
// ЭФФЕКТИВНАЯ ГРАНИЦА (новый график в v7)
// ================================================================

/**
 * Scatter-график эффективной границы Марковица.
 * В v6 данные были в ответе API, но не отображались.
 */
function initEfficientFrontierChart(data) {
    const frontier = data.efficient_frontier;
    if (!frontier?.length) return;

    const best = data.all_portfolios?.find(p => p.name === data.best_portfolio);

    const points = frontier.map(p => ({ x: p.risk, y: p.return, sharpe: p.sharpe }));

    // Сортируем по Sharpe для цветовой карты
    const maxSharpe = Math.max(...frontier.map(p => p.sharpe));
    const colors = frontier.map(p => {
        const t = maxSharpe > 0 ? p.sharpe / maxSharpe : 0;
        return `rgba(${Math.round(82 + 79 * t)}, ${Math.round(89 + 74 * t)}, 41, ${0.4 + 0.5 * t})`;
    });

    const datasets = [{
        label: 'Портфели',
        data: points,
        pointBackgroundColor: colors,
        pointRadius: 3,
        pointHoverRadius: 5,
    }];

    // Отмечаем лучший портфель
    if (best?.metrics) {
        const m = best.metrics;
        const riskPct = m.budget > 0 ? m.monthly_risk / m.budget * 100 : 0;
        datasets.push({
            label: `Лучший (${best.name})`,
            data: [{ x: parseFloat(riskPct.toFixed(2)), y: m.return_pct }],
            pointBackgroundColor: '#C8C68A',
            pointBorderColor: '#EDE8B5',
            pointBorderWidth: 2,
            pointRadius: 8,
            pointHoverRadius: 10,
        });
    }

    const opts = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true,
                position: 'top',
                labels: { color: 'var(--text-primary)', font: { size: 11 } },
            },
            tooltip: {
                callbacks: {
                    label: ctx => [
                        `Риск: ${ctx.parsed.x.toFixed(2)}%`,
                        `Доходность: ${ctx.parsed.y.toFixed(2)}%`,
                        ctx.raw.sharpe != null ? `Sharpe: ${ctx.raw.sharpe.toFixed(4)}` : '',
                    ].filter(Boolean),
                },
            },
        },
        scales: {
            x: {
                title: { display: true, text: 'Риск, %', color: 'var(--text-muted)' },
                ticks: { color: 'var(--text-secondary)', font: { size: 11 } },
                grid:  { color: 'var(--border)' },
            },
            y: {
                title: { display: true, text: 'Доходность, %', color: 'var(--text-muted)' },
                ticks: { color: 'var(--text-secondary)', font: { size: 11 } },
                grid:  { color: 'var(--border)' },
            },
        },
    };

    safeChart('efficientFrontierChart', { type: 'scatter', data: { datasets }, options: opts });
}
