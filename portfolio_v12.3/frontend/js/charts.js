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

    // ── 3 дополнительных графика ──────────────────────────────

    safeChart('stockPriceChart', {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: stats.map(s => s.price),
                backgroundColor: '#7ea8be',
                borderRadius: 4,
            }],
        },
        options: {
            ...barOpts(),
            plugins: {
                ...barOpts().plugins,
                tooltip: {
                    callbacks: {
                        label: ctx => `$${Number(ctx.raw).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}`,
                    },
                },
            },
        },
    });

    safeChart('stockProfitChart', {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: stats.map(s => s.abs_profit),
                backgroundColor: stats.map(s => (s.abs_profit ?? 0) >= 0 ? '#A1A364' : '#c27878'),
                borderRadius: 4,
            }],
        },
        options: {
            ...barOpts(),
            plugins: {
                ...barOpts().plugins,
                tooltip: {
                    callbacks: {
                        label: ctx => `$${Number(ctx.raw).toFixed(4)}`,
                    },
                },
            },
        },
    });

    safeChart('stockAbsRiskChart', {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: stats.map(s => s.abs_risk),
                backgroundColor: '#c2a87c',
                borderRadius: 4,
            }],
        },
        options: {
            ...barOpts(),
            plugins: {
                ...barOpts().plugins,
                tooltip: {
                    callbacks: {
                        label: ctx => `$${Number(ctx.raw).toFixed(4)}`,
                    },
                },
            },
        },
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

    // Все портфели: сначала введённый, потом оптимизированные
    const allPortfolios = [
        { label: 'Введённый', p: inputP, color: 'rgba(161,163,100,0.85)' },
        ...portfolios.map((p, i) => ({
            label: p.name,
            p,
            color: COLORS[(i + 1) % COLORS.length] + 'CC',
        })),
    ];

    const labels    = allPortfolios.map(x => x.label);
    const legendOpt = { display: true, position: 'top' };

    // Вспомогательная функция — один датасет из одного значения
    const ds = (getValue) => allPortfolios.map(({ label, p, color }) => ({
        label,
        data: [getValue(p?.metrics || {})],
        backgroundColor: color,
        borderRadius: 6,
    }));

    // Опции для каждого графика
    const makeOpts = (fmt = v => v) => {
        const o = chartDefaults();
        o.plugins.legend.display  = true;
        o.plugins.legend.position = 'top';
        o.plugins.tooltip = {
            callbacks: { label: ctx => `${ctx.dataset.label}: ${fmt(ctx.raw)}` },
        };
        o.scales.x = { ticks: { display: false }, grid: { display: false } };
        return o;
    };

    // ── 6 отдельных графиков ─────────────────────────────────

    // 1. Бюджет ($)
    safeChart('cmpBudgetChart', {
        type: 'bar',
        data: { labels: [''], datasets: ds(m => +(m.budget ?? 0).toFixed(2)) },
        options: makeOpts(v => '$' + Number(v).toLocaleString('en-US', {minimumFractionDigits:2})),
    });

    // 2. Доходность/мес (%)
    safeChart('cmpReturnChart', {
        type: 'bar',
        data: { labels: [''], datasets: ds(m => +(m.return_pct ?? 0).toFixed(4)) },
        options: makeOpts(v => v + '%'),
    });

    // 3. Прибыль/мес ($)
    safeChart('cmpProfitChart', {
        type: 'bar',
        data: { labels: [''], datasets: ds(m => +(m.monthly_profit ?? 0).toFixed(2)) },
        options: makeOpts(v => '$' + Number(v).toFixed(2)),
    });

    // 4. Риск/мес (%)
    safeChart('cmpRiskChart', {
        type: 'bar',
        data: {
            labels: [''],
            datasets: ds(m => m.budget > 0 ? +((m.monthly_risk / m.budget) * 100).toFixed(4) : 0),
        },
        options: makeOpts(v => v + '%'),
    });

    // 5. Sharpe Ratio
    safeChart('cmpSharpeChart', {
        type: 'bar',
        data: { labels: [''], datasets: ds(m => +(m.sharpe ?? 0).toFixed(4)) },
        options: makeOpts(v => String(v)),
    });

    // 6. Окупаемость (мес)
    safeChart('cmpPaybackChart', {
        type: 'bar',
        data: {
            labels: [''],
            datasets: ds(m => Math.min(+(m.payback_months ?? 999).toFixed(1), 500)),
        },
        options: makeOpts(v => v + ' мес'),
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
