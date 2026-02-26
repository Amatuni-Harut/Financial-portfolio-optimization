/**
 * api.js — HTTP-адаптер между фронтендом и FastAPI бэкендом.
 * Все запросы проходят через apiRequest с единой обработкой ошибок.
 */

const API_BASE = '';

/**
 * Базовая функция запроса. Добавляет заголовки настроек из AppState.
 */
async function apiRequest(endpoint, method = 'GET', data = null) {
    const url = `${API_BASE}${endpoint}`;

    const headers = {
        'Content-Type': 'application/json',
        ...(typeof AppState !== 'undefined' ? AppState.getSettingsHeaders() : {})
    };

    const response = await fetch(url, {
        method,
        headers,
        body: data ? JSON.stringify(data) : null
    });

    if (!response.ok) {
        let message = `HTTP ${response.status}`;
        try {
            const err = await response.json();
            message = err.detail || err.message || message;
        } catch (_) {}
        throw new Error(message);
    }
    return response.json();
}

// ================================================================
// УРОВЕНЬ ЗНАНИЙ
// ================================================================

/**
 * Отправляет уровень знаний на бэкенд.
 * Бэкенд сохраняет его и запускает bootstrap загрузку данных.
 */
async function sendKnowledgeLevel(level) {
    return apiRequest('/api/user/level', 'POST', { level });
}

async function getUserLevel() {
    return apiRequest('/api/user/level');
}

// ================================================================
// ПОИСК ТИКЕРОВ
// ================================================================

async function searchStocks(query) {
    return apiRequest(`/api/stocks/search?query=${encodeURIComponent(query)}`);
}

// ================================================================
// ДЕТАЛИ АКТИВА (для модального окна скринера)
// ================================================================

/**
 * Получает детальные данные по активу:
 * цена, макс. цена, изменение, доходность, риск, Sharpe, история цен.
 */
async function fetchAssetDetails(symbol) {
    return apiRequest(`/api/assets/${encodeURIComponent(symbol)}/details`);
}

// ================================================================
// ОПТИМИЗАЦИЯ
// ================================================================

/**
 * Собирает payload для запроса оптимизации.
 * 
 * @param {Array} assets - [{ticker, name, weight?, minWeight?, maxWeight?}]
 * @param {Object} params - {budget, startDate, endDate, optimizationModel,
 *                           riskFreeRate, maxAssets, isManualWeights}
 * @param {string} knowledgeLevel - 'beginner' | 'professional'
 */
function buildOptimizationPayload(assets, params, knowledgeLevel) {
    const {
        budget = 10000,
        startDate = null,
        endDate = null,
        optimizationModel = 'max_sharpe',
        riskFreeRate = 0.02,
        maxAssets = null,
        isManualWeights = false
    } = params;

    // Формируем allocation_limits из полей активов
    const allocationLimits = {};
    let hasAnyLimit = false;

    assets.forEach(a => {
        const min = a.minWeight != null ? parseFloat(a.minWeight) / 100 : null;
        const max = a.maxWeight != null ? parseFloat(a.maxWeight) / 100 : null;

        if (min != null || max != null) {
            hasAnyLimit = true;
            allocationLimits[a.ticker] = {
                min: min != null ? min : 0.0,
                max: max != null ? max : 1.0
            };
        }
    });

    return {
        assets: assets.map(a => ({
            ticker: a.ticker,
            weight: isManualWeights && a.weight ? parseFloat(a.weight) / 100 : null
        })),
        budget: parseFloat(budget),
        start_date: startDate,
        end_date: endDate,
        optimization_model: optimizationModel,
        risk_free_rate: parseFloat(riskFreeRate),
        max_assets: maxAssets ? parseInt(maxAssets) : null,
        allocation_limits: hasAnyLimit ? allocationLimits : null,
        manual_weights: isManualWeights,
        knowledge_level: knowledgeLevel || AppState.get('knowledgeLevel') || 'beginner'
    };
}

async function runOptimization(assets, params, knowledgeLevel) {
    const payload = buildOptimizationPayload(assets, params, knowledgeLevel);
    return apiRequest('/api/optimize', 'POST', payload);
}

// ================================================================
// РЫНОК
// ================================================================

async function fetchMarketData() {
    return apiRequest('/api/markets/all');
}

async function refreshMarket() {
    return apiRequest('/api/market/refresh');
}

// ================================================================
// СИСТЕМНЫЕ
// ================================================================

async function clearServerCache() {
    return apiRequest('/cache', 'DELETE');
}

async function checkHealth() {
    return apiRequest('/health');
}
