/**
 * appState.js — единое хранилище состояния приложения.
 * Используется на всех страницах. Загружается первым.
 */
const AppState = {
    // Настройки по умолчанию
    defaults: {
        knowledgeLevel: 'beginner',
        currency: 'usd',
        language: 'ru',
        timezone: 'utc',
        dateFormat: 'ymd',
        compactMode: false,
        theme: 'dark'
    },

    /**
     * Получить значение из localStorage с fallback на default.
     */
    get(key) {
        const val = localStorage.getItem(key);
        if (val === null) return this.defaults[key];
        if (val === 'true') return true;
        if (val === 'false') return false;
        return val;
    },

    /**
     * Сохранить значение в localStorage.
     */
    set(key, value) {
        localStorage.setItem(key, String(value));
    },

    /**
     * Сбросить все настройки до дефолтных.
     */
    reset() {
        Object.keys(this.defaults).forEach(key => localStorage.removeItem(key));
    },

    /**
     * Установить уровень знаний пользователя.
     */
    setKnowledgeLevel(level) {
        this.set('knowledgeLevel', level);
    },

    /**
     * Сформировать HTTP-заголовки для API-запросов на основе настроек.
     */
    getSettingsHeaders() {
        return {
            'X-Settings-Currency': this.get('currency'),
            'X-Settings-Language': this.get('language'),
            'X-Settings-Timezone': this.get('timezone'),
            'X-Settings-DateFormat': this.get('dateFormat'),
            'X-Knowledge-Level': this.get('knowledgeLevel')
        };
    },

    /**
     * Применить компактный режим к body.
     */
    applyCompactMode() {
        document.body.classList.toggle('compact', this.get('compactMode') === true);
    }
};

// Применяем компактный режим сразу при загрузке страницы
document.addEventListener('DOMContentLoaded', () => AppState.applyCompactMode());
