/**
 * results.js — Рендеринг блоков результатов оптимизации.
 *
 * Извлечено из dashboard.js (v6) для разделения ответственности.
 * Строит HTML-строки для блоков beginner и professional режимов.
 * Инициализация графиков — в charts.js.
 */


// ================================================================
// ПЕРИОД РАСЧЁТОВ
// ================================================================

/**
 * Возвращает текущий выбранный период: 'day' | 'month' | 'year'
 * Дефолт — 'month'
 */
function getCalcPeriod() {
    return document.getElementById('calcPeriod')?.value || 'month';
}

/**
 * Коэффициенты пересчёта из месячных значений:
 *   day:   делим на ~21 торговый день
 *   month: × 1 (базовый период бэкенда)
 *   year:  × 12 (для прибыли/риска в $), аннуализация compound для %
 */
function getPeriodMultiplier() {
    const p = getCalcPeriod();
    if (p === 'day')  return { money: 1 / 21, pct: 1 / 21, payback: 21,  label: 'день' };
    if (p === 'year') return { money: 12,      pct: null,   payback: 1/12, label: 'год'  };
    return             { money: 1,        pct: 1,    payback: 1,    label: 'мес'  };
}

/**
 * Аннуализирует месячную доходность в % (compound)
 * (1 + r/100)^12 - 1
 */
function annualizeReturnPct(monthlyPct) {
    if (monthlyPct == null || isNaN(monthlyPct)) return null;
    return ((1 + monthlyPct / 100) ** 12 - 1) * 100;
}

/**
 * Аннуализирует месячную волатильность (в %) через sqrt(12)
 */
function annualizeRiskPct(monthlyRiskPct) {
    if (monthlyRiskPct == null || isNaN(monthlyRiskPct)) return null;
    return monthlyRiskPct * Math.sqrt(12);
}

/**
 * Дневная доходность из месячной через геометрическое деление
 * (1 + r_monthly)^(1/21) - 1
 */
function dailyReturnPct(monthlyPct) {
    if (monthlyPct == null || isNaN(monthlyPct)) return null;
    return ((1 + monthlyPct / 100) ** (1 / 21) - 1) * 100;
}

/**
 * Адаптирует метрики портфеля под выбранный период.
 * Возвращает объект с пересчитанными значениями.
 */
function adaptMetrics(m) {
    if (!m) return null;
    const period = getCalcPeriod();
    const mul    = getPeriodMultiplier();

    let profit    = m.monthly_profit != null ? m.monthly_profit * mul.money : null;
    let risk      = m.monthly_risk   != null ? m.monthly_risk   * mul.money : null;
    let returnPct = m.return_pct;
    let payback   = m.payback_months != null ? m.payback_months * mul.payback : null;

    if (period === 'year') {
        returnPct = annualizeReturnPct(m.return_pct);
        // Волатильность — sqrt(12) от месячного % (если есть)
        if (m.monthly_risk != null && m.budget > 0) {
            const monthlyRiskPct = (m.monthly_risk / m.budget) * 100;
            risk = annualizeRiskPct(monthlyRiskPct) / 100 * m.budget;
        }
    } else if (period === 'day') {
        returnPct = dailyReturnPct(m.return_pct);
    }

    return {
        budget:         m.budget,
        monthly_profit: profit,
        monthly_risk:   risk,
        return_pct:     returnPct,
        sharpe:         m.sharpe,
        payback_months: payback,
    };
}

/**
 * Подпись "Прибыль/мес" → "Прибыль/день" или "Прибыль/год" и т.д.
 */
function periodLabel(base) {
    const map = { day: 'день', month: 'мес', year: 'год' };
    return map[getCalcPeriod()] || 'мес';
}



/** Безопасное форматирование числа, возвращает '—' если нет данных */
function fmt(value, decimals = 2, suffix = '') {
    if (value == null || isNaN(value)) return '—';
    return Number(value).toFixed(decimals) + suffix;
}

/** Возвращает символ текущей валюты из localStorage */
function currSym() {
    const map = { usd: '$', eur: '€', amd: '֏', rub: '₽' };
    const cur = (localStorage.getItem('currency') || 'usd').toLowerCase();
    return map[cur] || '$';
}

function fmtMoney(value, decimals = 2) {
    if (value == null || isNaN(value)) return '—';
    const cur = (localStorage.getItem('currency') || 'usd').toLowerCase();
    const v = Number(value);
    return currSym() + (cur === 'rub'
        ? v.toLocaleString('ru-RU', { maximumFractionDigits: 0 })
        : v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }));
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
    const raw = p.metrics;
    const m   = adaptMetrics(raw);          // пересчёт под выбранный период
    const lbl = periodLabel();

    const rows = [
        ['Бюджет',                  m.budget         != null ? fmtMoney(m.budget) : '—'],
        [`Прибыль/${lbl}`,          m.monthly_profit != null ? fmtMoney(m.monthly_profit) : '—'],
        [`Риск/${lbl}`,             m.monthly_risk   != null ? fmtMoney(m.monthly_risk)   : '—'],
        [`Доходность/${lbl}`,       fmt(m.return_pct, 4, '%')],
        ['Sharpe',                  fmt(m.sharpe, 4)],
        ['Окупаемость',             m.payback_months != null ? `${fmt(m.payback_months, 1)} ${lbl}` : '—'],
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

    const lbl = periodLabel();

    const allP = input
        ? [{ name: 'Введённый', metrics: input.metrics, isInput: true }, ...portfolios]
        : portfolios;

    const getM = p => adaptMetrics(p.metrics || {});
    const maxSharpe  = Math.max(...allP.map(p => p.metrics?.sharpe  ?? 0));
    const maxReturn  = Math.max(...allP.map(p => adaptMetrics(p.metrics || {}).return_pct ?? 0));
    const minRisk    = Math.min(...allP.map(p => adaptMetrics(p.metrics || {}).monthly_risk ?? Infinity));

    const rows = allP.map(p => {
        const m      = getM(p);
        const isBest = p.name === data.best_portfolio;
        const isInp  = p.isInput;

        const icon = isInp ? '📋' : isBest ? '⭐' : '✅';
        const nameBadge = isBest
            ? `<span class="cmp-badge cmp-best">ЛУЧШИЙ</span>`
            : isInp ? `<span class="cmp-badge cmp-input">ВВЕДЁН</span>` : '';

        const sharpeClass = (!isInp && p.metrics?.sharpe    === maxSharpe) ? 'cmp-highlight-green' : '';
        const retClass    = (!isInp && m.return_pct          === maxReturn)  ? 'cmp-highlight-green' : '';
        const riskClass   = (!isInp && m.monthly_risk        === minRisk)    ? 'cmp-highlight-blue'  : '';
        const sharpeBar   = maxSharpe > 0 ? Math.round(((p.metrics?.sharpe ?? 0) / maxSharpe) * 60) : 0;

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
                <span class="cmp-dollar">${m.budget != null ? fmtMoney(m.budget, 0) : '—'}</span>
            </td>
            <td class="cmp-val cmp-positive">
                ${m.monthly_profit != null ? fmtMoney(m.monthly_profit) : '—'}
            </td>
            <td class="cmp-val ${riskClass}">
                ${m.monthly_risk != null ? fmtMoney(m.monthly_risk) : '—'}
            </td>
            <td class="cmp-val ${sharpeClass}">
                <div class="cmp-sharpe-wrap">
                    <span>${fmt(p.metrics?.sharpe, 4)}</span>
                    <div class="cmp-bar" style="width:${sharpeBar}px"></div>
                </div>
            </td>
            <td class="cmp-val ${retClass}">${fmt(m.return_pct, 4, '%')}</td>
            <td class="cmp-val">${m.payback_months != null ? fmt(m.payback_months, 1)+` ${lbl}` : '—'}</td>
        </tr>`;
    }).join('');

    return `
        <div class="cmp-table-wrap">
            <table class="cmp-table">
                <thead>
                    <tr>
                        <th class="cmp-th-name">Портфель</th>
                        <th class="cmp-th">Бюджет</th>
                        <th class="cmp-th">Прибыль/${lbl}</th>
                        <th class="cmp-th">Риск/${lbl}</th>
                        <th class="cmp-th">Sharpe</th>
                        <th class="cmp-th">Доходность/${lbl}</th>
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
    const lbl = periodLabel();
    return section('📈 Анализ акций', null, `
        <div class="chart-grid-3" style="margin-bottom:20px;">
            <div class="chart-wrapper">
                <div class="chart-title">Доходность/${lbl} (%)</div>
                ${canvasBlock('stockReturnChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">Риск/${lbl} (%)</div>
                ${canvasBlock('stockRiskChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">Sharpe Ratio</div>
                ${canvasBlock('stockSharpeChart', 220)}
            </div>
        </div>
        <div class="chart-grid-3">
            <div class="chart-wrapper">
                <div class="chart-title">Цена акции ($)</div>
                ${canvasBlock('stockPriceChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">Прибыль/${lbl} ($)</div>
                ${canvasBlock('stockProfitChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">Риск/${lbl} ($)</div>
                ${canvasBlock('stockAbsRiskChart', 220)}
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
    if (best) {
        html += section('🔀 Сравнение: введённый vs оптимизированный', null, `
        <div class="chart-grid-3" style="margin-bottom:20px;">
            <div class="chart-wrapper">
                <div class="chart-title">💰 Бюджет ($)</div>
                ${canvasBlock('cmpBudgetChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">📈 Доходность/${periodLabel()} (%)</div>
                ${canvasBlock('cmpReturnChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">💵 Прибыль/${periodLabel()} ($)</div>
                ${canvasBlock('cmpProfitChart', 220)}
            </div>
        </div>
        <div class="chart-grid-3">
            <div class="chart-wrapper">
                <div class="chart-title">⚡ Риск/${periodLabel()} (%)</div>
                ${canvasBlock('cmpRiskChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">🎯 Sharpe Ratio</div>
                ${canvasBlock('cmpSharpeChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">⏱ Окупаемость (${periodLabel()})</div>
                ${canvasBlock('cmpPaybackChart', 220)}
            </div>
        </div>`);
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
        html += section('🔀 Сравнение портфелей по метрикам', null, `
        <div class="chart-grid-3" style="margin-bottom:20px;">
            <div class="chart-wrapper">
                <div class="chart-title">💰 Бюджет ($)</div>
                ${canvasBlock('cmpBudgetChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">📈 Доходность/${periodLabel()} (%)</div>
                ${canvasBlock('cmpReturnChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">💵 Прибыль/${periodLabel()} ($)</div>
                ${canvasBlock('cmpProfitChart', 220)}
            </div>
        </div>
        <div class="chart-grid-3">
            <div class="chart-wrapper">
                <div class="chart-title">⚡ Риск/${periodLabel()} (%)</div>
                ${canvasBlock('cmpRiskChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">🎯 Sharpe Ratio</div>
                ${canvasBlock('cmpSharpeChart', 220)}
            </div>
            <div class="chart-wrapper">
                <div class="chart-title">⏱ Окупаемость (${periodLabel()})</div>
                ${canvasBlock('cmpPaybackChart', 220)}
            </div>
        </div>`);
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
