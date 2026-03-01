/**
 * translations.js — Система локализации интерфейса AssetAlpha.
 * v9: реализован полноценный i18n через data-i18n атрибуты.
 *
 * Использование:
 *   <span data-i18n="nav.portfolio">Портфель</span>
 *   applyTranslations('en') — применит английский
 */

const TRANSLATIONS = {
    ru: {
        // Навигация
        "nav.main":        "Главное",
        "nav.account":     "Аккаунт",
        "nav.portfolio":   "Портфель",
        "nav.screener":    "Скринер рынка",
        "nav.settings":    "Настройки",
        "nav.theme":       "Тема",
        "nav.logout":      "Выход",

        // Общие
        "common.save":     "Сохранить",
        "common.reset":    "Сбросить",
        "common.loading":  "Загрузка...",
        "common.error":    "Ошибка",
        "common.search":   "Поиск...",

        // Настройки
        "settings.title":            "Настройки",
        "settings.subtitle":         "Параметры приложения и отображения",
        "settings.display":          "Параметры отображения",
        "settings.currency":         "Валюта",
        "settings.language":         "Язык интерфейса",
        "settings.timezone":         "Часовой пояс",
        "settings.dateFormat":       "Формат дат",
        "settings.darkMode":         "Тёмная тема",
        "settings.darkModeDesc":     "Переключить между тёмным и светлым режимом.",
        "settings.compactMode":      "Компактный режим",
        "settings.compactModeDesc":  "Плотные таблицы для работы с большим количеством тикеров.",
        "settings.saved":            "Настройки сохранены",
        "settings.reset":            "Настройки сброшены",
        "settings.confirmReset":     "Сбросить все настройки до значений по умолчанию?",

        // Скринер рынка
        "market.title":        "Скринер рынка",
        "market.subtitle":     "Цены и статистика по торгуемым инструментам",
        "market.search":       "Поиск по названию или тикеру...",
        "market.all":          "Все",
        "market.favorites":    "Избранное",
        "market.trending":     "Топ активы",
        "market.rank":         "#",
        "market.asset":        "Актив",
        "market.price":        "Цена",
        "market.change":       "Изм. (мес.)",
        "market.volume":       "Мар. кап.",
        "market.error":        "⚠️ Ошибка загрузки данных. Попробуйте позже.",
        "market.empty":        "Ничего не найдено",

        // Портфель (dashboard)
        "dashboard.title":        "Мой портфель",
        "dashboard.optimize":     "Оптимизировать",
        "dashboard.addAsset":     "Добавить актив",
        "dashboard.totalValue":   "Итоговая стоимость",
        "dashboard.monthReturn":  "Доходность/мес",
        "dashboard.risk":         "Риск",
        "dashboard.sharpe":       "Коэф. Шарпа",

        // Тосты
        "toast.settingsSaved": "Настройки сохранены",
        "toast.settingsReset": "Настройки сброшены",
    },

    en: {
        // Navigation
        "nav.main":        "Main",
        "nav.account":     "Account",
        "nav.portfolio":   "Portfolio",
        "nav.screener":    "Market Screener",
        "nav.settings":    "Settings",
        "nav.theme":       "Theme",
        "nav.logout":      "Logout",

        // Common
        "common.save":     "Save",
        "common.reset":    "Reset",
        "common.loading":  "Loading...",
        "common.error":    "Error",
        "common.search":   "Search...",

        // Settings
        "settings.title":            "Settings",
        "settings.subtitle":         "Application and display preferences",
        "settings.display":          "Display Options",
        "settings.currency":         "Currency",
        "settings.language":         "Interface Language",
        "settings.timezone":         "Timezone",
        "settings.dateFormat":       "Date Format",
        "settings.darkMode":         "Dark Theme",
        "settings.darkModeDesc":     "Toggle between dark and light mode.",
        "settings.compactMode":      "Compact Mode",
        "settings.compactModeDesc":  "Dense tables for working with many tickers.",
        "settings.saved":            "Settings saved",
        "settings.reset":            "Settings reset",
        "settings.confirmReset":     "Reset all settings to defaults?",

        // Market screener
        "market.title":        "Market Screener",
        "market.subtitle":     "Prices and statistics for tradeable instruments",
        "market.search":       "Search by name or ticker...",
        "market.all":          "All",
        "market.favorites":    "Favorites",
        "market.trending":     "Top Assets",
        "market.rank":         "#",
        "market.asset":        "Asset",
        "market.price":        "Price",
        "market.change":       "Change (mo.)",
        "market.volume":       "Mkt Cap",
        "market.error":        "⚠️ Failed to load data. Please try again.",
        "market.empty":        "Nothing found",

        // Dashboard
        "dashboard.title":        "My Portfolio",
        "dashboard.optimize":     "Optimize",
        "dashboard.addAsset":     "Add Asset",
        "dashboard.totalValue":   "Total Value",
        "dashboard.monthReturn":  "Monthly Return",
        "dashboard.risk":         "Risk",
        "dashboard.sharpe":       "Sharpe Ratio",

        // Toasts
        "toast.settingsSaved": "Settings saved",
        "toast.settingsReset": "Settings reset",
    }
};

/**
 * Возвращает переведённую строку по ключу.
 * Если ключ не найден — возвращает сам ключ.
 */
function t(key) {
    const lang = (typeof AppState !== 'undefined' ? AppState.get('language') : null) || 'ru';
    const dict = TRANSLATIONS[lang] || TRANSLATIONS['ru'];
    return dict[key] || TRANSLATIONS['ru'][key] || key;
}

/**
 * Применяет переводы ко всем элементам с атрибутом data-i18n.
 * Вызывается при загрузке страницы и при смене языка.
 */
function applyTranslations(lang) {
    const dict = TRANSLATIONS[lang] || TRANSLATIONS['ru'];
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (dict[key]) {
            el.textContent = dict[key];
        }
    });
    // Применяем placeholder отдельно
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (dict[key]) {
            el.placeholder = dict[key];
        }
    });
    // Обновляем title страницы
    const pageTitle = document.querySelector('[data-i18n-title]');
    if (pageTitle) {
        const key = pageTitle.getAttribute('data-i18n-title');
        if (dict[key]) document.title = dict[key] + ' — AssetAlpha';
    }
}
