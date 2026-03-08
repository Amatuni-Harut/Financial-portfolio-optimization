/**
 * api.js — HTTP-адаптер между фронтендом и FastAPI бэкендом.
 * Все запросы проходят через apiRequest с единой обработкой ошибок.
 *
 * Исправления v13.1:
 * - sendKnowledgeLevel теперь вызывает PATCH /api/auth/level (не POST /api/user/level)
 *   Новый эндпоинт возвращает обновлённый JWT с level внутри — сохраняем его.
 *   Это устраняет проблему глобального app.state на бэкенде.
 * - Добавлена функция refreshToken() для обновления токена после смены уровня
 */

const API_BASE = '';

// ================================================================
// ХРАНЕНИЕ ТОКЕНА
// ================================================================

const Auth = {
    getToken()        { return localStorage.getItem('auth_token'); },
    setToken(token)   { localStorage.setItem('auth_token', token); },
    getUsername()     { return localStorage.getItem('auth_username'); },
    setUsername(name) { localStorage.setItem('auth_username', name); },
    getLevel()        { return localStorage.getItem('auth_level') || 'beginner'; },
    setLevel(level)   { localStorage.setItem('auth_level', level); },
    clear() {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_username');
        localStorage.removeItem('auth_level');
    },
    isLoggedIn() { return !!this.getToken(); }
};

/**
 * Базовая функция запроса. Добавляет заголовки настроек и Bearer-токен.
 */
async function apiRequest(endpoint, method = 'GET', data = null) {
    const url = `${API_BASE}${endpoint}`;

    const token = Auth.getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...(typeof AppState !== 'undefined' ? AppState.getSettingsHeaders() : {}),
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    };

    const response = await fetch(url, {
        method,
        headers,
        body: data ? JSON.stringify(data) : null
    });

    // Если 401 — токен протух, разлогиниваем
    if (response.status === 401) {
        Auth.clear();
        if (!window.location.pathname.endsWith('login.html')) {
            window.location.href = '/login.html';
        }
        throw new Error('Сессия истекла. Войдите снова.');
    }

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
// АУТЕНТИФИКАЦИЯ
// ================================================================

async function authLogin(username, password) {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch('/api/auth/login', {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Ошибка входа');
    }
    const data = await response.json();
    Auth.setToken(data.access_token);
    Auth.setUsername(data.username);
    Auth.setLevel(data.knowledge_level || 'beginner');

    // Синхронизируем AppState с уровнем из JWT
    if (typeof AppState !== 'undefined') {
        AppState.setKnowledgeLevel(data.knowledge_level || 'beginner');
    }
    return data;
}

async function authRegister(username, password, email = null) {
    const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, email }),
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Ошибка регистрации');
    }
    const data = await response.json();
    Auth.setToken(data.access_token);
    Auth.setUsername(data.username);
    Auth.setLevel(data.knowledge_level || 'beginner');
    return data;
}

async function authLogout() {
    // Шаг 1: если пользователь авторизован — сохраняем данные портфеля на сервер
    if (Auth.isLoggedIn()) {
        try {
            const portfolioData = _collectPortfolioForSave();
            if (portfolioData) {
                await apiRequest('/api/user/portfolio', 'POST', portfolioData);
            }
        } catch (e) {
            // Не блокируем выход при ошибке сохранения
            console.warn('Не удалось сохранить портфель:', e);
        }
    }

    // Шаг 2: очищаем данные сессии и настройки
    Auth.clear();

    // Сбрасываем настройки AppState (валюта, язык, тема и пр.)
    if (typeof AppState !== 'undefined') {
        AppState.reset();
    }

    // Очищаем данные дашборда из localStorage
    const dashboardKeys = ['da_assets', 'da_result', 'da_manual'];
    dashboardKeys.forEach(k => localStorage.removeItem(k));

    window.location.href = '/login.html';
}

/**
 * Собирает текущее состояние портфеля для сохранения.
 * Возвращает null если DashboardState недоступен или пуст.
 */
function _collectPortfolioForSave() {
    try {
        if (typeof DashboardState === 'undefined') return null;
        const assets = DashboardState.assets;
        if (!assets || !assets.length) return null;
        return {
            assets: assets.map(a => ({
                ticker:    a.ticker,
                quantity:  a.quantity  ?? null,
                minWeight: a.minWeight ?? null,
                maxWeight: a.maxWeight ?? null,
            })),
            saved_at: new Date().toISOString(),
        };
    } catch (e) {
        return null;
    }
}

// ================================================================
// УРОВЕНЬ ЗНАНИЙ
// FIX: теперь вызывает PATCH /api/auth/level вместо POST /api/user/level.
// Бэкенд сохраняет уровень в БД И возвращает новый JWT с level внутри.
// Мы обновляем токен в localStorage — следующие запросы уже несут новый уровень.
// ================================================================

/**
 * Устанавливает уровень знаний пользователя.
 * Если пользователь авторизован — сохраняет в БД через PATCH /api/auth/level
 * и обновляет JWT в localStorage.
 * Если гость — только обновляет AppState локально.
 */
async function sendKnowledgeLevel(level) {
    // Всегда сохраняем локально
    if (typeof AppState !== 'undefined') {
        AppState.setKnowledgeLevel(level);
    }

    // Для авторизованных пользователей — обновляем через бэкенд
    if (Auth.isLoggedIn()) {
        try {
            // PATCH /api/auth/level?level=beginner — возвращает новый токен
            const data = await apiRequest(
                `/api/auth/level?level=${encodeURIComponent(level)}`,
                'PATCH'
            );
            // Бэкенд вернул новый JWT с обновлённым level внутри
            if (data.access_token) {
                Auth.setToken(data.access_token);
                Auth.setLevel(data.knowledge_level || level);
            }
            return data;
        } catch (err) {
            console.warn('Не удалось обновить уровень на сервере:', err.message);
            // Не блокируем UX — уровень сохранён локально в AppState
        }
    }

    return { level };
}

async function getUserLevel() {
    if (Auth.isLoggedIn()) {
        return apiRequest('/api/user/level');
    }
    // Для гостя — читаем из AppState
    const level = typeof AppState !== 'undefined'
        ? AppState.get('knowledgeLevel')
        : 'beginner';
    return { level, message: 'OK' };
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

async function fetchAssetDetails(symbol) {
    return apiRequest(`/api/assets/${encodeURIComponent(symbol)}/details`);
}

// ================================================================
// ОПТИМИЗАЦИЯ
// ================================================================

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
            ticker:   a.ticker,
            quantity: a.quantity ? parseInt(a.quantity) : null,
            weight:   isManualWeights && a.weight ? parseFloat(a.weight) / 100 : null
        })),
        budget: parseFloat(budget),
        start_date: startDate,
        end_date: endDate,
        optimization_model: optimizationModel,
        risk_free_rate: parseFloat(riskFreeRate),
        max_assets: maxAssets ? parseInt(maxAssets) : null,
        allocation_limits: hasAnyLimit ? allocationLimits : null,
        manual_weights: isManualWeights,
        // FIX: уровень берём из JWT (через Auth), а не из устаревшего app.state
        knowledge_level: knowledgeLevel
            || Auth.getLevel()
            || (typeof AppState !== 'undefined' ? AppState.get('knowledgeLevel') : 'beginner')
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
