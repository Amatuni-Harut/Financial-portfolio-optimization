/**
 * settings.js — логика страницы настроек.
 * Зависит от: appState.js
 */
document.addEventListener('DOMContentLoaded', () => {
    const els = {
        currency:    document.getElementById('currencySelect'),
        language:    document.getElementById('languageSelect'),
        timezone:    document.getElementById('timezoneSelect'),
        dateFormat:  document.getElementById('dateFormatSelect'),
        compactToggle: document.getElementById('compactToggle'),
        saveBtn:     document.getElementById('saveSettingsBtn'),
        resetBtn:    document.getElementById('resetSettingsBtn')
    };

    // Загрузить текущие значения из AppState
    loadSettings();

    function loadSettings() {
        els.currency.value   = AppState.get('currency');
        els.language.value   = AppState.get('language');
        els.timezone.value   = AppState.get('timezone');
        els.dateFormat.value = AppState.get('dateFormat');
        els.compactToggle.classList.toggle('active', AppState.get('compactMode') === true);
    }

    // Сохранить
    els.saveBtn?.addEventListener('click', () => {
        AppState.set('currency',    els.currency.value);
        AppState.set('language',    els.language.value);
        AppState.set('timezone',    els.timezone.value);
        AppState.set('dateFormat',  els.dateFormat.value);
        AppState.set('compactMode', els.compactToggle.classList.contains('active'));

        AppState.applyCompactMode();

        showToast('Настройки сохранены');
    });

    // Сбросить
    els.resetBtn?.addEventListener('click', () => {
        if (!confirm('Сбросить все настройки до значений по умолчанию?')) return;
        AppState.reset();
        loadSettings();
        AppState.applyCompactMode();
        showToast('Настройки сброшены');
    });

    // Переключатель компактного режима
    els.compactToggle?.addEventListener('click', () => {
        els.compactToggle.classList.toggle('active');
    });
});

function showToast(message) {
    // Простое уведомление — можно заменить на кастомный toast
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('visible'), 10);
    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}
