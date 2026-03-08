/**
 * appState.js — единое хранилище состояния приложения.
 * Используется на всех страницах. Загружается первым.
 *
 * Исправления v13.1:
 * - setKnowledgeLevel синхронизирует localStorage И Auth.level (если Auth доступен)
 * - getKnowledgeLevel берёт уровень из Auth.getLevel() приоритетно (там уровень из JWT)
 */
const AppState = {
    defaults: {
        knowledgeLevel: 'beginner',
        currency: 'usd',
        language: 'ru',
        timezone: 'utc',
        dateFormat: 'ymd',
        compactMode: false,
        theme: 'dark'
    },

    get(key) {
        // Для knowledgeLevel — приоритет у Auth (JWT), потом localStorage
        if (key === 'knowledgeLevel') {
            if (typeof Auth !== 'undefined' && Auth.getLevel) {
                const authLevel = Auth.getLevel();
                if (authLevel) return authLevel;
            }
        }
        const val = localStorage.getItem(key);
        if (val === null) return this.defaults[key];
        if (val === 'true') return true;
        if (val === 'false') return false;
        return val;
    },

    set(key, value) {
        localStorage.setItem(key, String(value));
    },

    reset() {
        Object.keys(this.defaults).forEach(key => localStorage.removeItem(key));
    },

    setKnowledgeLevel(level) {
        this.set('knowledgeLevel', level);
        // Синхронизируем с Auth если доступен
        if (typeof Auth !== 'undefined' && Auth.setLevel) {
            Auth.setLevel(level);
        }
    },

    getSettingsHeaders() {
        return {
            'X-Settings-Currency':   this.get('currency'),
            'X-Settings-Language':   this.get('language'),
            'X-Settings-Timezone':   this.get('timezone'),
            'X-Settings-DateFormat': this.get('dateFormat'),
            'X-Knowledge-Level':     this.get('knowledgeLevel'),
        };
    },

    applyCompactMode() {
        document.body.classList.toggle('compact', this.get('compactMode') === true);
    },

    applyLanguage(lang) {
        const target = lang || this.get('language') || 'ru';
        if (typeof applyTranslations === 'function') {
            applyTranslations(target);
        }
        document.documentElement.setAttribute('lang', target === 'ru' ? 'ru' : 'en');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    AppState.applyCompactMode();
    AppState.applyLanguage();
});
