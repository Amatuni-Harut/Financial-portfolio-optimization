/**
 * ui.js — Общие UI-утилиты для всех страниц AssetAlpha.
 *
 * Улучшения v7 vs v6:
 * 1. showToast() перенесена из settings.js сюда — единый источник.
 * 2. showError() — заменяет alert() во всём приложении:
 *    красивый модальный диалог вместо браузерного popup.
 * 3. showConfirm() — заменяет confirm() там, где нужно подтверждение.
 * 4. Мобильное меню, тема, фильтр-вкладки — без изменений.
 */
(function () {
    'use strict';

    /* -----------------------------------------------
       ТЕМА: тёмная / светлая
    ----------------------------------------------- */
    function initTheme() {
        const html = document.documentElement;

        function setTheme(theme) {
            html.setAttribute('data-theme', theme);
            localStorage.setItem('theme', theme);
        }

        // Переключатель в сайдбаре (все страницы кроме login)
        const themeSwitch = document.getElementById('themeSwitch');
        if (themeSwitch) {
            themeSwitch.addEventListener('click', () => {
                const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
                setTheme(next);
                syncDarkModeToggle();
            });
        }

        // Кнопка на странице login
        const themeToggleBtn = document.getElementById('themeToggle');
        if (themeToggleBtn) {
            themeToggleBtn.addEventListener('click', () => {
                const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
                setTheme(next);
            });
        }

        // Переключатель на странице settings (синхронизован с themeSwitch)
        const darkModeToggle = document.getElementById('darkModeToggle');
        if (darkModeToggle && themeSwitch) {
            darkModeToggle.addEventListener('click', () => themeSwitch.click());
        }

        syncDarkModeToggle();
    }

    function syncDarkModeToggle() {
        const darkModeToggle = document.getElementById('darkModeToggle');
        if (!darkModeToggle) return;
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        darkModeToggle.classList.toggle('active', isDark);
    }

    /* -----------------------------------------------
       МОБИЛЬНОЕ МЕНЮ (sidebar)
    ----------------------------------------------- */
    function initMobileMenu() {
        const toggle  = document.getElementById('mobileMenuToggle');
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebarOverlay');
        if (!toggle || !sidebar || !overlay) return;

        const open  = () => {
            toggle.classList.add('active');
            sidebar.classList.add('active');
            overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        };
        const close = () => {
            toggle.classList.remove('active');
            sidebar.classList.remove('active');
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        };
        const isOpen = () => sidebar.classList.contains('active');

        toggle.addEventListener('click',  () => isOpen() ? close() : open());
        overlay.addEventListener('click', close);

        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                if (window.innerWidth <= 1024 && isOpen()) close();
            });
        });

        window.addEventListener('resize', () => {
            if (window.innerWidth > 1024 && isOpen()) close();
        });
    }

    /* -----------------------------------------------
       ФИЛЬТР-ВКЛАДКИ (markets.html)
    ----------------------------------------------- */
    function initFilterTabs() {
        document.querySelectorAll('.filter-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
            });
        });
    }

    /* -----------------------------------------------
       ИНИЦИАЛИЗАЦИЯ
    ----------------------------------------------- */
    document.addEventListener('DOMContentLoaded', () => {
        initTheme();
        initMobileMenu();
        initFilterTabs();
    });

})();


/* ================================================================
   TOAST УВЕДОМЛЕНИЯ
   Единая точка для всего приложения (была только в settings.js)
================================================================ */

/**
 * Показывает уведомление-тост в правом нижнем углу.
 * @param {string} message  - Текст сообщения
 * @param {'info'|'success'|'error'} type - Тип (влияет на иконку и цвет)
 */
function showToast(message, type = 'info') {
    // Удаляем предыдущий тост если есть
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const icons = { info: 'ℹ️', success: '✅', error: '❌' };

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<span style="margin-right:8px;">${icons[type] || ''}</span>${message}`;

    if (type === 'error') {
        toast.style.borderColor = 'var(--negative)';
        toast.style.color = 'var(--text-primary)';
    } else if (type === 'success') {
        toast.style.borderColor = 'var(--positive)';
    }

    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('visible'));

    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 320);
    }, 3000);
}


/* ================================================================
   VALIDATION MODAL
   Заменяет браузерный alert() — красивый встроенный диалог.
================================================================ */

/**
 * Показывает ошибку валидации в красивом модальном окне.
 * @param {string} message - Сообщение об ошибке
 */
function showError(message) {
    const overlay = document.createElement('div');
    overlay.className = 'v-modal-overlay';
    overlay.innerHTML = `
        <div class="v-modal" role="alertdialog" aria-modal="true" aria-labelledby="vModalTitle">
            <div class="v-modal-icon">⚠️</div>
            <div class="v-modal-title" id="vModalTitle">Проверьте данные</div>
            <div class="v-modal-msg">${message}</div>
            <button class="v-modal-btn" id="vModalOk">OK</button>
        </div>`;

    document.body.appendChild(overlay);

    const close = () => {
        overlay.style.opacity = '0';
        setTimeout(() => overlay.remove(), 200);
    };

    overlay.querySelector('#vModalOk').addEventListener('click', close);
    overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
    document.addEventListener('keydown', function onKey(e) {
        if (e.key === 'Escape' || e.key === 'Enter') { close(); document.removeEventListener('keydown', onKey); }
    });

    // Фокус на кнопку для accessibility
    setTimeout(() => overlay.querySelector('#vModalOk').focus(), 50);
}


/**
 * Показывает диалог подтверждения (заменяет confirm()).
 * @param {string} message - Текст вопроса
 * @returns {Promise<boolean>}
 */
function showConfirm(message) {
    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.className = 'v-modal-overlay';
        overlay.innerHTML = `
            <div class="v-modal" role="dialog" aria-modal="true">
                <div class="v-modal-icon">🤔</div>
                <div class="v-modal-msg">${message}</div>
                <div style="display:flex;gap:12px;">
                    <button class="v-modal-btn" id="vConfirmYes" style="flex:1;">Да</button>
                    <button class="v-modal-btn" id="vConfirmNo"
                        style="flex:1;background:transparent;border:1px solid var(--border);color:var(--text-secondary);">
                        Отмена
                    </button>
                </div>
            </div>`;

        document.body.appendChild(overlay);

        const close = (value) => {
            overlay.style.opacity = '0';
            setTimeout(() => overlay.remove(), 200);
            resolve(value);
        };

        overlay.querySelector('#vConfirmYes').addEventListener('click', () => close(true));
        overlay.querySelector('#vConfirmNo').addEventListener('click',  () => close(false));
        overlay.addEventListener('click', e => { if (e.target === overlay) close(false); });

        document.addEventListener('keydown', function onKey(e) {
            if (e.key === 'Escape') { close(false); document.removeEventListener('keydown', onKey); }
            if (e.key === 'Enter')  { close(true);  document.removeEventListener('keydown', onKey); }
        });
    });
}
