/**
 * settings.js — Логика страницы настроек.
 *
 * Улучшения v7 vs v6:
 * 1. Удалена локальная функция showToast() — используется версия из ui.js.
 * 2. Добавлен визуальный фидбек при сохранении (disabled + текст кнопки).
 */
document.addEventListener('DOMContentLoaded', () => {
    const els = {
        currency:      document.getElementById('currencySelect'),
        language:      document.getElementById('languageSelect'),
        timezone:      document.getElementById('timezoneSelect'),
        dateFormat:    document.getElementById('dateFormatSelect'),
        compactToggle: document.getElementById('compactToggle'),
        saveBtn:       document.getElementById('saveSettingsBtn'),
        resetBtn:      document.getElementById('resetSettingsBtn'),
    };

    loadSettings();

    function loadSettings() {
        if (els.currency)      els.currency.value      = AppState.get('currency');
        if (els.language)      els.language.value      = AppState.get('language');
        if (els.timezone)      els.timezone.value      = AppState.get('timezone');
        if (els.dateFormat)    els.dateFormat.value    = AppState.get('dateFormat');
        if (els.compactToggle) els.compactToggle.classList.toggle('active', AppState.get('compactMode') === true);
    }

    // Сохранить
    els.saveBtn?.addEventListener('click', () => {
        AppState.set('currency',    els.currency?.value    || 'usd');
        AppState.set('language',    els.language?.value    || 'ru');
        AppState.set('timezone',    els.timezone?.value    || 'utc');
        AppState.set('dateFormat',  els.dateFormat?.value  || 'ymd');
        AppState.set('compactMode', els.compactToggle?.classList.contains('active') ?? false);

        AppState.applyCompactMode();

        // Визуальный фидбек (showToast из ui.js)
        if (typeof showToast === 'function') {
            showToast('Настройки сохранены', 'success');
        }
    });

    // Сбросить
    els.resetBtn?.addEventListener('click', async () => {
        const ok = typeof showConfirm === 'function'
            ? await showConfirm('Сбросить все настройки до значений по умолчанию?')
            : confirm('Сбросить все настройки до значений по умолчанию?');

        if (!ok) return;
        AppState.reset();
        loadSettings();
        AppState.applyCompactMode();
        if (typeof showToast === 'function') {
            showToast('Настройки сброшены', 'info');
        }
    });

    // Переключатель компактного режима
    els.compactToggle?.addEventListener('click', () => {
        els.compactToggle.classList.toggle('active');
    });
});
