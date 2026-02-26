/**
 * api.js — адаптер между AssetAlpha frontend и FastAPI backend
 */

const API_BASE = '';

async function apiRequest(endpoint, method = 'GET', data = null) {
    const url = `${API_BASE}${endpoint}`;
    const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
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

// Поиск тикеров
async function searchStocks(query) {
    return apiRequest(`/api/stocks/search?query=${encodeURIComponent(query)}`);
}

// Запуск оптимизации
async function runOptimization(payload) {
    return apiRequest('/api/optimize', 'POST', payload);
}

// Получить все данные рынка
async function fetchMarketData() {
    return apiRequest('/api/markets/all');
}

// Обновить рыночные данные
async function refreshMarket() {
    return apiRequest('/api/market/refresh');
}

// Очистить кэш
async function clearServerCache() {
    return apiRequest('/cache', 'DELETE');
}
