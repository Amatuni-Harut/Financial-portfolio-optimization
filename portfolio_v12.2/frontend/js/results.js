/**
 * results.js — Рендеринг блоков результатов оптимизации.
 *
 * Извлечено из dashboard.js (v6) для разделения ответственности.
 * Строит HTML-строки для блоков beginner и professional режимов.
 * Инициализация графиков — в charts.js.
 */


// ================================================================
// УТИЛИТЫ РЕНДЕРИНГА
// ================================================================

/** Безопасное форматирование числа, возвращает '—' если нет данных */
function fmt(value, decimals = 2, suffix = '') {
    if (value == null || isNaN(value)) return '—';
    return Number(value).toFixed(decimals) + suffix;
}

/** Карточка-секция */
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

/** Canvas-обёртка */
function canvasBlock(id, height = 300) {
    return `<div class="chart-container" style="height:${height}px;position:relative;">
                <canvas id="${id}"></canvas>
            </div>`;
}

/** Таблица метрик + состав портфеля */
function portfolioMetricsTable(p) {
    if (!p?.metrics) return '<p class="text-muted">Нет данных</p>';
    const m = p.metrics;

    const rows = [
        ['Бюджет',          m.budget         != null ? `$${Number(m.budget).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}` : '—'],
        ['Прибыль/мес',     m.monthly_profit != null ? `$${fmt(m.monthly_profit)}` : '—'],
        ['Риск/мес',        m.monthly_risk   != null ? `$${fmt(m.monthly_risk)}`   : '—'],
        ['Доходность/мес',  fmt(m.return_pct, 4, '%')],
        ['Sharpe',          fmt(m.sharpe, 4)],
        ['Окупаемость',     m.payback_months != null ? `${fmt(m.payback_months, 1)} мес` : '—'],
    ];

    const tickers   = p.tickers  || [];
    const maxWeight = Math.max(...(p.weights || [0]).map(w => w * 100), 1);

    const compositionRows = tickers.map((t, i) => {
        const shares = p.shares?.[i]  ?? '—';
        const wPct   = p.weights?.[i] != null ? p.weights[i] * 100 : null;
        const barW   = wPct != null ? Math.round((wPct / maxWeight) * 120) : 0;
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

/** Матрица корреляций/ковариаций с тепловой картой */
function matrixTable(matrixData, decimals = 4) {
    if (!matrixData?.tickers) return '<p>Нет данных</p>';
    const { tickers, matrix } = matrixData;

    const allVals = [];
    matrix.forEach((row, i) => row.forEach((v, j) => { if (i !== j) allVals.push(v); }));
    const minV = Math.min(...allVals);
    const maxV = Math.max(...allVals);

    const heatColor = (v, isDiag) => {
        if (isDiag) return '';
        const t = maxV === minV ? 0.5 : (v - minV) / (maxV - minV);
        const r = Math.round(161 * t);
        const g = Math.round(100 + 58 * t);
        const b = Math.round(100 * (1 - t));
        return `background:rgba(${r},${g},${b},0.18);`;
    };

    const headerRow = `<tr>
        <th style="text-align:left;min-width:60px;"></th>
        ${tickers.map(t => `<th>${t}</th>`).join('')}
    </tr>`;

    const rows = tickers.map((t, i) => `
        <tr>
            <td class="row-label">${t}</td>
            ${matrix[i].map((v, j) => {
                const isDiag = i === j;
                return `<td class="cell-val ${isDiag ? 'cell-diag' : ''}"
                            style="${heatColor(v, isDiag)}">${v.toFixed(decimals)}</td>`;
            }).join('')}
        </tr>`).join('');

    return `<div class="matrix-wrap">
        <table class="matrix-table">
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
        ? [{ name: 'Введённый', metrics: input.metrics, isInput: true }, ...portfolios]
        : portfolios;

    const getM = p => p.metrics || {};
    const maxSharpe  = Math.max(...allP.map(p => getM(p).sharpe  ?? 0));
    const maxReturn  = Math.max(...allP.map(p => getM(p).return_pct ?? 0));
    const minRisk    = Math.min(...allP.map(p => getM(p).monthly_risk ?? Infinity));

    const rows = allP.map(p => {
        const m      = getM(p);
        const isBest = p.name === data.best_portfolio;
        const isInp  = p.isInput;

        const icon = isInp ? '📋' : isBest ? '⭐' : '✅';
        const nameBadge = isBest
            ? `<span class="cmp-badge cmp-best">ЛУЧШИЙ</span>`
            : isInp ? `<span class="cmp-badge cmp-input">ВВЕДЁН</span>` : '';

        const sharpeClass = (!isInp && m.sharpe     === maxSharpe) ? 'cmp-highlight-green' : '';
        const retClass    = (!isInp && m.return_pct === maxReturn)  ? 'cmp-highlight-green' : '';
        const riskClass   = (!isInp && m.monthly_risk === minRisk)  ? 'cmp-highlight-blue'  : '';
        const sharpeBar   = maxSharpe > 0 ? Math.round(((m.sharpe ?? 0) / maxSharpe) * 60) : 0;

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
            <td class="cmp-val ${retClass}">${fmt(m.return_pct, 4, '%')}</td>
            <td class="cmp-val">${m.payback_months != null ? fmt(m.payback_months, 1)+' мес' : '—'}</td>
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
// БЛОКИ — ОБЩИЕ ДЛЯ ОБОИХ УРОВНЕЙ
// ================================================================

function blockInputPieChart(data) {
    if (!data.input_portfolio) return '';
    return section('📊 Введённый портфель — распределение', null, canvasBlock('inputPieChart', 280));
}

function blockInputTable(data) {
    if (!data.input_portfolio) return '';
    return section('📋 Введённый портфель — метрики', null, portfolioMetricsTable(data.input_portfolio));
}

function blockStockCharts(data) {
    if (!data.stock_stats?.length) return '';
    return section('📈 Анализ акций', null, `
        <div class="chart-grid-3">
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


// ================================================================
// BEGINNER — рендеринг результатов
// ================================================================

function renderBeginnerResults(data, container) {
    const best = getBestPortfolio(data);

    let html = '';
    html += blockInputPieChart(data);
    html += blockInputTable(data);
    html += blockStockCharts(data);

    if (best) {
        html += section('✅ Оптимизированный портфель — метрики', 'ЛУЧШИЙ',
            portfolioMetricsTable(best));
    }
    if (best) {
        html += section('🥧 Оптимизированный портфель — распределение', null,
            canvasBlock('optPieChart', 280));
    }
    if (data.input_portfolio && best) {
        html += section('🔀 Сравнение: введённый vs оптимизированный', null,
            canvasBlock('compareChart', 300));
    }

    container.innerHTML = html;

    // Инициализация графиков (в charts.js)
    initInputPieChart(data);
    initStockCharts(data);
    if (best) initOptPieChart(best, 'optPieChart');
    if (data.input_portfolio && best) initCompareChart(data, [best]);
}


// ================================================================
// PROFESSIONAL — рендеринг результатов
// ================================================================

function renderProResults(data, container) {
    const portfolios = data.all_portfolios || [];
    const best       = getBestPortfolio(data);

    let html = '';
    html += blockInputPieChart(data);
    html += blockInputTable(data);
    html += blockStockCharts(data);

    if (data.correlation) html += section('🔗 Матрица корреляций', null, matrixTable(data.correlation, 4));
    if (data.covariance)  html += section('📐 Матрица ковариаций',  null, matrixTable(data.covariance, 6));

    portfolios.forEach(p => {
        html += section(
            `✅ Портфель: ${p.name}`,
            p.name === data.best_portfolio ? 'ЛУЧШИЙ' : null,
            portfolioMetricsTable(p)
        );
    });

    if (portfolios.length) {
        const pieSections = portfolios.map((p, i) => `
            <div class="chart-wrapper">
                <div class="chart-title">${p.name}</div>
                ${canvasBlock('optPie_' + i, 240)}
            </div>`).join('');
        html += section('🥧 Распределение оптимизированных портфелей', null,
            `<div class="chart-grid">${pieSections}</div>`);
    }

    if (data.input_portfolio && portfolios.length) {
        html += section('🔀 Сравнение портфелей по метрикам', null, canvasBlock('compareChart', 320));
    }

    if (portfolios.length) {
        html += section('📊 Итоговое сравнение всех портфелей', null, allPortfoliosTable(data));
    }

    container.innerHTML = html;

    // Инициализация графиков
    initInputPieChart(data);
    initStockCharts(data);
    portfolios.forEach((p, i) => initOptPieChart(p, 'optPie_' + i));
    if (data.input_portfolio && portfolios.length) initCompareChart(data, portfolios);
}


// ================================================================
// ВСПОМОГАТЕЛЬНЫЕ
// ================================================================

function getBestPortfolio(data) {
    const portfolios = data.all_portfolios || [];
    if (!portfolios.length) return null;
    return portfolios.find(p => p.name === data.best_portfolio) || portfolios[0];
}
