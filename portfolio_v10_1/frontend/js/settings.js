/**
 * settings.js — Логика страницы настроек.
 *
 * v9:
 * 1. applyLanguage() вызывается сразу при изменении select — live-preview
 * 2. Кнопка «Сохранить» даёт визуальный фидбек (disabled + текст)
 * 3. Сброс сразу перезагружает переводы
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

    // Live-preview языка при изменении select (до нажатия Сохранить)
    els.language?.addEventListener('change', () => {
        AppState.applyLanguage(els.language.value);
    });

    // Сохранить
    els.saveBtn?.addEventListener('click', () => {
        AppState.set('currency',    els.currency?.value    || 'usd');
        AppState.set('language',    els.language?.value    || 'ru');
        AppState.set('timezone',    els.timezone?.value    || 'utc');
        AppState.set('dateFormat',  els.dateFormat?.value  || 'ymd');
        AppState.set('compactMode', els.compactToggle?.classList.contains('active') ?? false);

        AppState.applyCompactMode();
        AppState.applyLanguage();

        // Визуальный фидбек кнопки
        if (els.saveBtn) {
            const originalText = els.saveBtn.textContent;
            els.saveBtn.disabled = true;
            els.saveBtn.textContent = t('settings.saved');
            setTimeout(() => {
                els.saveBtn.disabled = false;
                els.saveBtn.textContent = originalText;
            }, 1500);
        }

        if (typeof showToast === 'function') {
            showToast(t('toast.settingsSaved'), 'success');
        }
    });

    // Сбросить
    els.resetBtn?.addEventListener('click', async () => {
        const confirmMsg = t('settings.confirmReset');
        const ok = typeof showConfirm === 'function'
            ? await showConfirm(confirmMsg)
            : confirm(confirmMsg);

        if (!ok) return;
        AppState.reset();
        loadSettings();
        AppState.applyCompactMode();
        AppState.applyLanguage();

        if (typeof showToast === 'function') {
            showToast(t('toast.settingsReset'), 'info');
        }
    });

    // Переключатель компактного режима
    els.compactToggle?.addEventListener('click', () => {
        els.compactToggle.classList.toggle('active');
    });
});
