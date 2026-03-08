/**
 * assetTable.js — Управление таблицей активов.
 *
 * Извлечено из dashboard.js (v6) для уменьшения размера файла.
 * Отвечает за: добавление/удаление активов, рендер таблицы,
 * валидацию allocation, event delegation для строк таблицы.
 *
 * Улучшения v7:
 * 1. Event delegation вместо inline onclick="" в строках таблицы:
 *    в v6 каждая строка имела до 5 атрибутов onchange/onclick
 *    → XSS-риск при специальных символах в тикерах.
 * 2. showError() / showConfirm() вместо alert() / confirm().
 * 3. XSS-защита: escapeAttr() для всех data-атрибутов.
 */

// ================================================================
// СОСТОЯНИЕ ТАБЛИЦЫ
// ================================================================

const TableState = {
    showMinMax:  true,
    showAllRows: true,   // всегда показываем все строки
};

// ================================================================
// КЕШ ЦЕН — реальный бюджет без запуска алгоритма
// ================================================================

// Кеш цен: { AAPL: 213.45, MSFT: 415.20, ... }
const _priceCache = {};

/** Получает цену тикера — из кеша или через API */
async function fetchTickerPrice(ticker) {
    if (_priceCache[ticker] != null) return _priceCache[ticker];
    try {
        const data = await fetchAssetDetails(ticker);
        // data.priceRaw — число USD (если бэкенд вернул)
        // data.price    — строка "$213.45" или "₽23,825"
        let raw = null;
        if (typeof data.priceRaw === 'number' && data.priceRaw > 0) {
            raw = data.priceRaw;
        } else if (data.price) {
            // убираем всё кроме цифр и точки, берём первое совпадение
            const match = String(data.price).replace(/,/g, '').match(/[\d]+\.?[\d]*/);
            if (match) raw = parseFloat(match[0]);
        }
        if (raw != null && !isNaN(raw) && raw > 0) {
            _priceCache[ticker] = raw;
        }
        return _priceCache[ticker] ?? null;
    } catch(e) {
        console.warn('fetchTickerPrice failed for', ticker, e);
        return null;
    }
}

/** Пересчитывает и отображает бюджет в реальном времени */
/** Символ и курс текущей валюты из AppState */
// ── Валюта: символы и курсы ──────────────────────────────────────────
const _SYMBOLS = { usd: '$', eur: '€', amd: '֏', rub: '₽' };
// Дефолтные курсы (перезаписываются актуальными с сервера)
let _ratesCache = { usd: 1.0, eur: 0.92, amd: 387.0, rub: 90.0 };

function _getCurCode() {
    return (localStorage.getItem('currency') || 'usd').toLowerCase();
}

async function _loadRates() {
    try {
        const res = await fetch('/api/currency/rates');
        if (res.ok) {
            const data = await res.json();
            Object.assign(_ratesCache, data.rates || {});
        }
    } catch (e) { /* используем дефолт */ }
}

// Запускаем обновление курсов каждые 60 секунд (стриминг через polling)
_loadRates();
setInterval(_loadRates, 60_000);

// Слушаем изменение валюты из другой вкладки (settings.html → index.html)
window.addEventListener('storage', (e) => {
    if (e.key === 'currency') {
        // Сбрасываем price cache чтобы пересчитать с новым курсом
        Object.keys(_priceCache).forEach(k => delete _priceCache[k]);
        updateBudgetDisplay();
    }
});

function fmtBudget(usdTotal) {
    // Читаем валюту КАЖДЫЙ РАЗ из localStorage — никакого кеша
    const rawCur = localStorage.getItem('currency');
    const cur    = (rawCur || 'usd').toLowerCase().trim();
    const rate   = _ratesCache[cur] ?? 1.0;
    const sym    = _SYMBOLS[cur]    ?? (cur === 'amd' ? '֏' : '$');
    const v      = usdTotal * rate;
    const noDecimals = (cur === 'rub' || cur === 'amd');
    if (noDecimals) return sym + Math.round(v).toLocaleString('ru-RU');
    return sym + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Форматирует уже сконвертированное число — только символ, без умножения на курс */
function fmtConverted(value) {
    const rawCur = localStorage.getItem('currency');
    const cur    = (rawCur || 'usd').toLowerCase().trim();
    const sym    = _SYMBOLS[cur] ?? (cur === 'amd' ? '֏' : '$');
    const noDecimals = (cur === 'rub' || cur === 'amd');
    if (noDecimals) return sym + Math.round(value).toLocaleString('ru-RU');
    return sym + Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

async function recalcBudgetRealtime() {
    const assets = DashboardState.assets.filter(a => parseFloat(a.quantity) > 0);
    if (!assets.length) {
        setBudgetDisplay('—', false);
        return;
    }

    setBudgetDisplay('⏳', false);

    // Загружаем недостающие цены параллельно
    await Promise.all(assets.map(a => fetchTickerPrice(a.ticker)));

    let total = 0;
    let allPricesKnown = true;
    for (const a of assets) {
        const price = _priceCache[a.ticker];
        if (price == null) { allPricesKnown = false; continue; }
        total += price * (parseFloat(a.quantity) || 0);
    }

    if (total > 0) {
        setBudgetDisplay(fmtBudget(total), true);
        const hidden = document.getElementById('budget');
        if (hidden) hidden.value = total.toFixed(2);
    } else {
        setBudgetDisplay(allPricesKnown ? fmtBudget(0) : '—', false);
    }
}

function setBudgetDisplay(text, isReal) {
    const val  = document.getElementById('budgetValue');
    const hint = document.querySelector('.budget-hint');
    if (val) val.textContent = text;
    if (hint) hint.textContent = isReal
        ? 'реальная стоимость портфеля'
        : 'рассчитывается по акциям';
}

// Вызывается при изменении количества акций — сбрасываем кеш цен для свежей загрузки
function invalidatePriceCache() {
    Object.keys(_priceCache).forEach(k => delete _priceCache[k]);
}

  // Строк до кнопки "ещё"


// ================================================================
// ДОБАВЛЕНИЕ / УДАЛЕНИЕ АКТИВОВ
// ================================================================

function addAsset(ticker, name, sector) {
    if (DashboardState.assets.some(a => a.ticker === ticker)) {
        showToast(`${ticker} уже добавлен`, 'info');
        return;
    }
    DashboardState.assets.push({ ticker, name, sector,
        quantity: null, weight: null, minWeight: null, maxWeight: null });
    document.getElementById('searchInput').value = '';
    hideSearch();
    DashboardState.save();   // сохраняем после добавления
    renderAssetList();
}

function removeAsset(ticker) {
    DashboardState.assets = DashboardState.assets.filter(a => a.ticker !== ticker);
    DashboardState.save();   // сохраняем после удаления
    renderAssetList();
}

async function clearAllAssets() {
    if (!DashboardState.assets.length) return;
    const ok = await showConfirm('Очистить список активов?');
    if (ok) {
        DashboardState.assets = [];
        DashboardState.lastResult = null;
        localStorage.removeItem('da_result');
        DashboardState.save();
        renderAssetList();
        // Скрываем результаты
        const resultsEl = document.getElementById('results');
        if (resultsEl) { resultsEl.innerHTML = ''; resultsEl.style.display = 'none'; }
    }
}

function toggleExtraColumns() {
    TableState.showMinMax = !TableState.showMinMax;
    renderAssetList();
}


// ================================================================
// ОБНОВЛЕНИЕ ПОЛЕЙ АКТИВА
// ================================================================

function updateAssetField(ticker, field, value) {
    const asset = DashboardState.assets.find(a => a.ticker === ticker);
    if (!asset) return;

    asset[field] = value !== '' ? parseFloat(value) : null;
    if (field === 'quantity') { updateBudgetDisplay(); DashboardState.save(); }
}

/** Обновляет отображение бюджета — запускает реальный расчёт по ценам */
// Пересчитать бюджет когда пользователь возвращается на страницу
// (например, после смены валюты в настройках)
document.addEventListener('visibilitychange', () => {
    if (!document.hidden) updateBudgetDisplay();
});
window.addEventListener('focus', () => {
    updateBudgetDisplay();
});

function updateBudgetDisplay() {
    // Если есть результат оптимизации — показываем его бюджет
    // ВАЖНО: бюджет уже сконвертирован бэкендом — только добавляем символ без умножения
    if (DashboardState.lastResult?.input_portfolio) {
        const budget = DashboardState.lastResult.input_portfolio.metrics?.budget;
        if (budget) {
            setBudgetDisplay(fmtConverted(Number(budget)), true);
            const hidden = document.getElementById('budget');
            if (hidden) hidden.value = budget;
            return;
        }
    }
    // Иначе — считаем в реальном времени по ценам из API (в USD → конвертируем)
    recalcBudgetRealtime();
}


// ================================================================
// РЕНДЕР ТАБЛИЦЫ АКТИВОВ
// ================================================================

function renderAssetList() {
    const container = document.getElementById('assetList');
    const badge     = document.getElementById('assetBadge');
    const countEl   = document.getElementById('assetCount');
    const isPro     = AppState.get('knowledgeLevel') === 'professional';
    const isManual  = DashboardState.isManualWeights;
    const assets    = DashboardState.assets;
    const n         = assets.length;

    if (badge)   badge.textContent   = `${n} ВЫБРАНО`;
    if (countEl) countEl.textContent = `Активов: ${n}`;

    updateBudgetDisplay();

    const showMin    = TableState.showMinMax && isPro;
    const showMax    = TableState.showMinMax && isPro;
    const showManual = isManual && isPro;

    const displayed = assets;
    const hasMore = false;

    const rows = displayed.map((a, i) => {
        const isLastVisible = i === displayed.length - 1 && hasMore;
        // Используем data-атрибуты — без inline onclick (XSS-безопасно)
        return `
        <tr>
            <td>
                <div class="row-num-cell">
                    <span>${i + 1}</span>
                    ${isLastVisible
                        ? `<span class="more-link" data-action="show-all">(More)</span>`
                        : ''}
                </div>
            </td>
            <td class="ticker-cell">
                <div class="ticker-input-wrap">
                    <span class="ticker-badge">
                        <span style="color:var(--accent);font-weight:700;">${escapeHtml(a.ticker)}</span>
                        <span class="ticker-badge-name">${a.name ? '— ' + escapeHtml(a.name) : ''}</span>
                    </span>
                    <button class="ticker-search-btn"
                            data-action="search-ticker"
                            data-ticker="${escapeAttr(a.ticker)}"
                            title="Поиск">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;">
                            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                        </svg>
                    </button>
                </div>
            </td>
            <td>
                <div class="pct-input-wrap">
                    <input type="number" class="pct-input" placeholder="шт."
                           min="1" step="1" value="${a.quantity ?? ''}"
                           data-action="update-field"
                           data-ticker="${escapeAttr(a.ticker)}"
                           data-field="quantity">
                </div>
            </td>
            ${showMin ? `<td>
                <div class="pct-input-wrap">
                    <input type="number" class="pct-input" placeholder="0"
                           min="0" max="100" step="0.1" value="${a.minWeight ?? ''}"
                           data-action="update-field"
                           data-ticker="${escapeAttr(a.ticker)}"
                           data-field="minWeight">
                    <span class="pct-suffix">%</span>
                </div>
            </td>` : ''}
            ${showMax ? `<td>
                <div class="pct-input-wrap">
                    <input type="number" class="pct-input" placeholder="100"
                           min="0" max="100" step="0.1" value="${a.maxWeight ?? ''}"
                           data-action="update-field"
                           data-ticker="${escapeAttr(a.ticker)}"
                           data-field="maxWeight">
                    <span class="pct-suffix">%</span>
                </div>
            </td>` : ''}
            ${showManual ? `<td>
                <div class="pct-input-wrap">
                    <input type="number" class="pct-input" placeholder="%"
                           min="0" max="100" step="0.1" value="${a.weight ?? ''}"
                           data-action="update-field"
                           data-ticker="${escapeAttr(a.ticker)}"
                           data-field="weight">
                    <span class="pct-suffix">%</span>
                </div>
            </td>` : ''}
            <td style="text-align:center;">
                <button class="row-delete-btn"
                        data-action="remove-asset"
                        data-ticker="${escapeAttr(a.ticker)}"
                        title="Удалить">✕</button>
            </td>
        </tr>`;
    }).join('');

    const totalQty    = assets.reduce((sum, a) => sum + (parseFloat(a.quantity) || 0), 0);

    const extraCols = (showMin ? 1 : 0) + (showMax ? 1 : 0) + (showManual ? 1 : 0);

    container.innerHTML = `
        <table class="asset-table">
            <thead>
                <tr>
                    <th style="width:48px;">&nbsp;</th>
                    <th>Тикер</th>
                    <th>Кол-во акций</th>
                    ${showMin ? '<th>Min. Weight</th>' : ''}
                    ${showMax ? '<th>Max. Weight</th>' : ''}
                    ${showManual ? '<th>Вес %</th>' : ''}
                    <th class="th-actions" style="width:40px;"></th>
                </tr>
            </thead>
            <tbody>
                ${rows || `<tr><td colspan="${4 + extraCols}" style="text-align:center;padding:24px;color:var(--text-muted);">
                    Добавьте минимум 2 актива через строку поиска выше
                </td></tr>`}
            </tbody>
            <tfoot>
                <tr class="tfoot-total-row">
                    <td colspan="2"><strong>Total</strong></td>
                    <td>
                        <div class="budget-display budget-display--inline" id="budgetDisplay">
                            <span class="budget-value" id="budgetValue">—</span>
                            <span class="budget-hint">стоимость портфеля</span>
                        </div>
                    </td>
                    ${Array(extraCols).fill('<td></td>').join('')}
                    <td></td>
                </tr>
            </tfoot>
        </table>`;

    // Event delegation — один слушатель на всю таблицу
    container.addEventListener('input', handleTableChange);
    container.addEventListener('click',  handleTableClick);
}

/** Делегат для input-событий (поля ввода — срабатывает при каждом символе) */
function handleTableChange(e) {
    const input = e.target.closest('[data-action="update-field"]');
    if (!input) return;
    updateAssetField(input.dataset.ticker, input.dataset.field, input.value);
}

/** Делегат для click-событий (кнопки удаления, поиска, "ещё") */
function handleTableClick(e) {
    const el = e.target.closest('[data-action]');
    if (!el) return;
    const action = el.dataset.action;

    if (action === 'remove-asset')  removeAsset(el.dataset.ticker);
    if (action === 'search-ticker') openTickerSearch(el.dataset.ticker);
    if (action === 'show-all') {
        TableState.showAllRows = true;
        renderAssetList();
    }
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
// УТИЛИТЫ XSS-ЗАЩИТЫ
// ================================================================

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function escapeAttr(str) {
    return String(str)
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
