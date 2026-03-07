/**
 * dashboard.js — Главный оркестратор дашборда AssetAlpha.
 *
 * Изменения v7 vs v6:
 * - Файл сокращён с 1013 до ~200 строк.
 * - Рендеринг таблицы → assetTable.js
 * - Создание графиков → charts.js
 * - HTML результатов → results.js
 * - alert()/confirm() → showError()/showConfirm() из ui.js
 *
 * Этот файл отвечает за:
 * - Инициализацию страницы
 * - Валидацию формы
 * - Запуск оптимизации
 * - Роутинг рендеринга (beginner/pro)
 */

// ================================================================
// ГЛОБАЛЬНОЕ СОСТОЯНИЕ
// ================================================================

const DashboardState = {
    assets:          [],  // { ticker, name, sector, quantity, weight, minWeight, maxWeight }
    charts:          {},  // хранилище Chart.js инстанций (ключ: canvas id)
    isManualWeights: false,
    lastResult:      null,
};


// ================================================================
// ИНИЦИАЛИЗАЦИЯ
// ================================================================

document.addEventListener('DOMContentLoaded', () => {
    initDates();
    applyKnowledgeLevel();
    bindEvents();
    renderAssetList();  // из assetTable.js
});

function initDates() {
    const end   = new Date();
    const start = new Date();
    start.setFullYear(end.getFullYear() - 3);
    document.getElementById('endDate').valueAsDate   = end;
    document.getElementById('startDate').valueAsDate = start;
}

function applyKnowledgeLevel() {
    const isPro = AppState.get('knowledgeLevel') === 'professional';

    const proBlock = document.getElementById('proFeatures');
    if (proBlock) proBlock.style.display = isPro ? 'block' : 'none';

    // Модели оптимизации: для новичка скрываем сложные
    if (!isPro) {
        ['risk_parity', 'min_cvar', 'all'].forEach(val => {
            const opt = document.querySelector(`#algorithm option[value="${val}"]`);
            if (opt) opt.remove();
        });
    }
}


// ================================================================
// СОБЫТИЯ
// ================================================================

function bindEvents() {
    // Поиск тикеров
    const searchInput = document.getElementById('searchInput');
    let searchTimer;
    searchInput?.addEventListener('input', e => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => handleSearch(e.target.value), 300);
    });
    searchInput?.addEventListener('focus', () => {
        // При фокусе без текста — показываем избранное
        if (!searchInput.value.trim()) showFavoritesInSearch();
    });
    searchInput?.addEventListener('blur', () => setTimeout(hideSearch, 200));

    // Кнопки
    document.getElementById('optimizeBtn')?.addEventListener('click', runOptimize);
    document.getElementById('refreshDataBtn')?.addEventListener('click', handleRefreshData);

    // Заголовок таблицы — очистить все
    document.getElementById('clearAssetsBtn')?.addEventListener('click', clearAllAssets);

    // Переключатель диверсификации (pro)
    const divToggle = document.getElementById('diversificationToggle');
    divToggle?.addEventListener('click', () => {
        divToggle.classList.toggle('active');
        DashboardState.isManualWeights = divToggle.classList.contains('active');
        renderAssetList();
    });

    // Переключатель колонок Min/Max
    document.getElementById('colToggleBtn')?.addEventListener('click', toggleExtraColumns);

    // Кнопка "очистить" (trash)
    document.getElementById('clearBtn')?.addEventListener('click', clearAllAssets);
}


// ================================================================
// ПОИСК ТИКЕРОВ
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

function getFavoriteTickers() {
    try { return JSON.parse(localStorage.getItem('favorites') || '[]'); }
    catch { return []; }
}

function showFavoritesInSearch() {
    const favs = getFavoriteTickers();
    if (!favs.length) return;

    // Берём данные из fullMarketData если он есть (загружен скринером),
    // иначе строим заглушки только из тикеров
    const marketData = (typeof fullMarketData !== 'undefined' && fullMarketData.length)
        ? fullMarketData
        : [];

    const favItems = favs.map(ticker => {
        const found = marketData.find(m => m.symbol === ticker);
        return {
            ticker,
            name:   found?.name   || ticker,
            sector: found?.sector || '',
        };
    });

    renderSearchResults(favItems, true);
}

function renderSearchResults(stocks, isFavorites = false) {
    const container = document.getElementById('searchResults');
    if (!container) return;

    const favs = getFavoriteTickers();

    const header = isFavorites
        ? '<div class="search-section-header">⭐ Избранное</div>'
        : '';

    container.innerHTML = header + (stocks.length
        ? stocks.map(s => {
            const isFav = favs.includes(s.ticker);
            return `
            <div class="search-item"
                 data-ticker="${escapeAttr(s.ticker)}"
                 data-name="${escapeAttr(s.name)}"
                 data-sector="${escapeAttr(s.sector || '')}">
                <div style="display:flex;align-items:center;gap:8px;">
                    ${isFav ? '<span class="search-fav-star" title="В избранном">★</span>' : ''}
                    <span class="search-ticker">${escapeHtml(s.ticker)}</span>
                    <span class="search-name">${escapeHtml(s.name)}</span>
                </div>
                ${s.sector ? `<span class="search-sector">${escapeHtml(s.sector)}</span>` : ''}
            </div>`;
          }).join('')
        : '<div class="search-item search-empty">Ничего не найдено</div>');

    container.classList.add('active');

    container.addEventListener('click', e => {
        const item = e.target.closest('[data-ticker]');
        if (item) {
            addAsset(item.dataset.ticker, item.dataset.name, item.dataset.sector);
        }
    }, { once: true });
}

function hideSearch() {
    document.getElementById('searchResults')?.classList.remove('active');
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
            return `Укажите количество акций для <strong>${a.ticker}</strong> (> 0).`;
        if (a.quantity > 1000)
            return `${a.ticker}: максимальное количество акций — 1000.`;
    }

    if (AppState.get('knowledgeLevel') === 'professional') {
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
    if (err) { showError(err); return; }  // showError из ui.js

    const loader  = document.getElementById('loader');
    const results = document.getElementById('results');
    if (loader)  loader.classList.add('active');
    if (results) results.style.display = 'none';

    try {
        const params = {
            budget:            999999999,  // бэкенд пересчитает по реальным ценам
            startDate:         document.getElementById('startDate').value    || null,
            endDate:           document.getElementById('endDate').value      || null,
            optimizationModel: document.getElementById('algorithm').value,
            riskFreeRate:      parseFloat(document.getElementById('riskFreeRate').value) / 100,
            maxAssets:         document.getElementById('maxAssets')?.value   || null,
            isManualWeights:   DashboardState.isManualWeights,
        };
        const level = AppState.get('knowledgeLevel') || 'beginner';
        const data  = await runOptimization(DashboardState.assets, params, level);

        DashboardState.lastResult = data;
        updateBudgetDisplay();   // из assetTable.js
        renderResults(data, level);

    } catch (err) {
        showError('Ошибка оптимизации: ' + err.message);
    } finally {
        if (loader) loader.classList.remove('active');
    }
}


// ================================================================
// РОУТЕР РЕНДЕРИНГА РЕЗУЛЬТАТОВ
// ================================================================

function renderResults(data, level) {
    const resultsEl = document.getElementById('results');
    if (!resultsEl) return;

    destroyAllCharts();
    resultsEl.innerHTML = '';

    if (level === 'professional') {
        renderProResults(data, resultsEl);       // в results.js
    } else {
        renderBeginnerResults(data, resultsEl);  // в results.js
    }

    resultsEl.style.display = 'block';
    resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function destroyAllCharts() {
    Object.values(DashboardState.charts).forEach(c => { if (c) c.destroy(); });
    DashboardState.charts = {};
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
        if (cs) {
            cs.textContent = 'Cache: Updated';
            setTimeout(() => { cs.textContent = 'Cache: Ready'; }, 3000);
        }
        showToast('Данные обновлены', 'success');
    } catch (err) {
        showToast('Ошибка обновления: ' + err.message, 'error');
    } finally {
        btn.disabled    = false;
        btn.textContent = '🔄 Обновить данные';
    }
}
