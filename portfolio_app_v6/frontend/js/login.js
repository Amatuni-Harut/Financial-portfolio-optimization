/**
 * login.js — Страница выбора уровня знаний.
 * После выбора: сохраняет в localStorage, отправляет на бэкенд (фон),
 * показывает индикатор пока бэкенд инициализирует данные.
 */
document.addEventListener('DOMContentLoaded', () => {
    const beginnerBtn = document.getElementById('beginnerBtn');
    const proBtn      = document.getElementById('proBtn');
    const statusEl    = document.getElementById('bootstrapStatus');

    async function selectLevel(level) {
        // Сохраняем локально — интерфейс работает сразу без ожидания сервера
        AppState.setKnowledgeLevel(level);

        // Показываем индикатор
        setLoadingState(true, level);

        try {
            // Отправляем на бэкенд — он запустит bootstrap в фоне
            const result = await sendKnowledgeLevel(level);
            console.info('Уровень знаний отправлен:', result.message);
        } catch (err) {
            // Бэкенд недоступен — продолжаем, данные загрузятся при первом запросе
            console.warn('Бэкенд недоступен, продолжаем офлайн:', err.message);
        }

        // Переходим на дашборд (не ждём окончания bootstrap — он в фоне)
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 600);
    }

    function setLoadingState(loading, level) {
        if (!statusEl) return;

        if (loading) {
            const label = level === 'professional' ? 'профессионала' : 'новичка';
            statusEl.textContent = `Подготовка данных для ${label}...`;
            statusEl.style.display = 'block';
        } else {
            statusEl.style.display = 'none';
        }

        if (beginnerBtn) beginnerBtn.disabled = loading;
        if (proBtn)      proBtn.disabled      = loading;
    }

    beginnerBtn?.addEventListener('click', () => selectLevel('beginner'));
    proBtn?.addEventListener('click',      () => selectLevel('professional'));
});
