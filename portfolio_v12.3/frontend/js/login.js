/**
 * login.js — Страница выбора уровня знаний.
 *
 * Улучшения v7 vs v6:
 * 1. Исправлен баг: в v6 setLoadingState(false) вызывал textContent = '',
 *    что удаляло спиннер из DOM. Теперь управление через classList.
 * 2. Статус показывает анимированный спиннер + текст через innerHTML.
 */
document.addEventListener('DOMContentLoaded', () => {
    const beginnerBtn = document.getElementById('beginnerBtn');
    const proBtn      = document.getElementById('proBtn');
    const statusEl    = document.getElementById('bootstrapStatus');

    async function selectLevel(level) {
        // Сохраняем локально — интерфейс работает сразу без ожидания сервера
        AppState.setKnowledgeLevel(level);
        setLoadingState(true, level);

        try {
            // Отправляем на бэкенд — он запустит bootstrap в фоне
            const result = await sendKnowledgeLevel(level);
            console.info('Уровень знаний отправлен:', result.message);
        } catch (err) {
            // Бэкенд недоступен — продолжаем: данные загрузятся при первом запросе
            console.warn('Бэкенд недоступен, продолжаем офлайн:', err.message);
        }

        // Переходим на дашборд (не ждём окончания bootstrap — он в фоне)
        setTimeout(() => { window.location.href = 'index.html'; }, 600);
    }

    function setLoadingState(loading, level) {
        if (!statusEl) return;

        if (loading) {
            const label = level === 'professional' ? 'профессионала' : 'новичка';
            // Используем innerHTML для спиннера (v6 использовал textContent — терял разметку)
            statusEl.innerHTML = `
                <div class="spinner" style="width:16px;height:16px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:8px;"></div>
                <span>Подготовка данных для ${label}...</span>`;
            statusEl.style.display = 'flex';
            statusEl.style.alignItems = 'center';
        } else {
            statusEl.style.display = 'none';
        }

        if (beginnerBtn) beginnerBtn.disabled = loading;
        if (proBtn)      proBtn.disabled      = loading;
    }

    beginnerBtn?.addEventListener('click', () => selectLevel('beginner'));
    proBtn?.addEventListener('click',      () => selectLevel('professional'));
});
