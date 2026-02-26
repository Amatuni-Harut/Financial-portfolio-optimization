/**
 * ui.js — общие UI-утилиты для всех страниц.
 * Заменяет templatemo-crypto-script.js.
 * Загружается после appState.js.
 */
(function () {
    'use strict';

    /* -----------------------------------------------
       Тема: переключение тёмной/светлой
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
       Мобильное меню (sidebar)
    ----------------------------------------------- */
    function initMobileMenu() {
        const toggle = document.getElementById('mobileMenuToggle');
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebarOverlay');
        if (!toggle || !sidebar || !overlay) return;

        function open() {
            toggle.classList.add('active');
            sidebar.classList.add('active');
            overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        }

        function close() {
            toggle.classList.remove('active');
            sidebar.classList.remove('active');
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        }

        function isOpen() { return sidebar.classList.contains('active'); }

        toggle.addEventListener('click', () => isOpen() ? close() : open());
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
       Фильтр-вкладки (markets.html)
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
       Инициализация
    ----------------------------------------------- */
    document.addEventListener('DOMContentLoaded', () => {
        initTheme();
        initMobileMenu();
        initFilterTabs();
    });

})();
