/**
 * login.js — логика страницы выбора уровня знаний.
 */
document.addEventListener('DOMContentLoaded', () => {
    const beginnerBtn = document.getElementById('beginnerBtn');
    const proBtn = document.getElementById('proBtn');

    async function selectLevel(level) {
        AppState.setKnowledgeLevel(level);

        try {
            await sendKnowledgeLevel(level);
        } catch (err) {
            // Бэкенд недоступен — продолжаем без ошибки, уровень сохранён локально
            console.warn('Не удалось отправить уровень знаний на сервер:', err.message);
        }

        window.location.href = 'index.html';
    }

    beginnerBtn?.addEventListener('click', () => selectLevel('beginner'));
    proBtn?.addEventListener('click', () => selectLevel('professional'));
});
