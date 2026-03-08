/**
 * login.js — Страница аутентификации AssetAlpha.
 *
 * Исправления v13.1:
 * - После authLogin/authRegister берём knowledge_level прямо из ответа сервера
 *   (сервер возвращает уровень из БД в JWT) вместо хардкода 'beginner'
 * - sendKnowledgeLevel теперь вызывает PATCH /api/auth/level (обновляет JWT)
 * - Очистка localStorage ограничена только данными дашборда (не Auth)
 */
document.addEventListener('DOMContentLoaded', () => {

    // ── Табы Login / Register ────────────────────────────────────
    document.querySelectorAll('.auth-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.auth-section').forEach(s => s.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`tab-${tab.dataset.tab}`)?.classList.add('active');
            clearErrors();
        });
    });

    // ── Вход ─────────────────────────────────────────────────────
    document.getElementById('loginBtn')?.addEventListener('click', handleLogin);
    document.getElementById('loginPassword')?.addEventListener('keydown', e => {
        if (e.key === 'Enter') handleLogin();
    });

    async function handleLogin() {
        const username = document.getElementById('loginUsername').value.trim();
        const password = document.getElementById('loginPassword').value;
        if (!username || !password) { setError('loginError', 'Введите логин и пароль'); return; }

        setLoading('loginBtn', true);
        clearErrors();
        try {
            const data = await authLogin(username, password);
            // FIX: уровень берём из ответа сервера (из JWT), не хардкодим 'beginner'
            const level = data.knowledge_level || 'beginner';
            AppState.setKnowledgeLevel(level);
            showStep2(username, false, level);
        } catch (err) {
            setError('loginError', err.message);
        } finally {
            setLoading('loginBtn', false);
        }
    }

    // ── Регистрация ───────────────────────────────────────────────
    document.getElementById('regBtn')?.addEventListener('click', handleRegister);
    document.getElementById('regPassword')?.addEventListener('keydown', e => {
        if (e.key === 'Enter') handleRegister();
    });

    async function handleRegister() {
        const username = document.getElementById('regUsername').value.trim();
        const email    = document.getElementById('regEmail').value.trim() || null;
        const password = document.getElementById('regPassword').value;

        if (!username) { setError('regError', 'Введите логин'); return; }
        if (password.length < 6) { setError('regError', 'Пароль минимум 6 символов'); return; }

        setLoading('regBtn', true);
        clearErrors();
        try {
            const data = await authRegister(username, password, email);
            // Новый пользователь — всегда beginner
            showStep2(username, true, 'beginner');
        } catch (err) {
            setError('regError', err.message);
        } finally {
            setLoading('regBtn', false);
        }
    }

    // ── Гость ─────────────────────────────────────────────────────
    document.getElementById('guestLink')?.addEventListener('click', () => {
        showStep2(null, false, AppState.get('knowledgeLevel') || 'beginner');
    });

    // ── Шаг 2: выбор уровня знаний ───────────────────────────────
    function showStep2(username, isNew = false, currentLevel = 'beginner') {
        document.getElementById('step-auth').style.display  = 'none';
        document.getElementById('step-level').style.display = 'block';

        const welcomeMsg = document.getElementById('welcomeMsg');
        if (welcomeMsg) {
            if (!username) {
                welcomeMsg.innerHTML = 'Вы вошли как <strong>гость</strong>';
            } else if (isNew) {
                welcomeMsg.innerHTML = `Аккаунт создан! Добро пожаловать, <strong>${escapeHtml(username)}</strong> 🎉`;
            } else {
                welcomeMsg.innerHTML = `Добро пожаловать, <strong>${escapeHtml(username)}</strong>!`;
            }
        }

        // Подсвечиваем текущий уровень
        const beginnerBtn = document.getElementById('beginnerBtn');
        const proBtn      = document.getElementById('proBtn');
        if (beginnerBtn) beginnerBtn.classList.toggle('btn-primary',     currentLevel === 'beginner');
        if (beginnerBtn) beginnerBtn.classList.toggle('btn-secondary',   currentLevel !== 'beginner');
        if (proBtn)      proBtn.classList.toggle('btn-primary',          currentLevel === 'professional');
        if (proBtn)      proBtn.classList.toggle('btn-secondary',        currentLevel !== 'professional');
    }

    // ── Выход / смена аккаунта ────────────────────────────────────
    document.getElementById('switchAccountBtn')?.addEventListener('click', () => {
        Auth.clear();
        document.getElementById('step-level').style.display = 'none';
        document.getElementById('step-auth').style.display  = 'block';
        ['loginUsername','loginPassword','regUsername','regEmail','regPassword'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        clearErrors();
        document.querySelectorAll('.auth-tab').forEach(t =>
            t.classList.toggle('active', t.dataset.tab === 'login'));
        document.querySelectorAll('.auth-section').forEach(s =>
            s.classList.toggle('active', s.id === 'tab-login'));
    });

    // ── Выбор уровня знаний ───────────────────────────────────────
    document.getElementById('beginnerBtn')?.addEventListener('click', () => selectLevel('beginner'));
    document.getElementById('proBtn')?.addEventListener('click',      () => selectLevel('professional'));

    async function selectLevel(level) {
        AppState.setKnowledgeLevel(level);
        setLevelLoading(true, level);

        // Очищаем только данные дашборда (не Auth токен!)
        localStorage.removeItem('da_assets');
        localStorage.removeItem('da_result');
        localStorage.removeItem('da_manual');

        try {
            // FIX: sendKnowledgeLevel теперь вызывает PATCH /api/auth/level
            // бэкенд сохраняет в БД и возвращает новый JWT с level внутри
            await sendKnowledgeLevel(level);
        } catch (err) {
            console.warn('Бэкенд недоступен:', err.message);
        }

        // Загружаем сохранённый портфель пользователя из БД
        try {
            const portfolio = await apiRequest('/api/user/portfolio', 'GET');
            if (portfolio && portfolio.assets && portfolio.assets.length > 0) {
                localStorage.setItem('da_assets', JSON.stringify(portfolio.assets));
            }
        } catch (err) {
            console.warn('Портфель не загружен:', err.message);
        }

        setTimeout(() => { window.location.href = 'index.html'; }, 500);
    }

    function setLevelLoading(loading, level) {
        const statusEl    = document.getElementById('bootstrapStatus');
        const beginnerBtn = document.getElementById('beginnerBtn');
        const proBtn      = document.getElementById('proBtn');

        if (statusEl) {
            if (loading) {
                const label = level === 'professional' ? 'профессионала' : 'новичка';
                statusEl.innerHTML = `
                    <div class="spinner" style="width:16px;height:16px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:8px;"></div>
                    <span>Подготовка данных для ${label}...</span>`;
                statusEl.style.display     = 'flex';
                statusEl.style.alignItems  = 'center';
            } else {
                statusEl.style.display = 'none';
            }
        }
        if (beginnerBtn) beginnerBtn.disabled = loading;
        if (proBtn)      proBtn.disabled      = loading;
    }

    // ── Утилиты ───────────────────────────────────────────────────
    function setError(elId, msg) {
        const el = document.getElementById(elId);
        if (el) el.textContent = msg;
    }

    function clearErrors() {
        ['loginError', 'regError'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '';
        });
    }

    function setLoading(btnId, loading) {
        const btn = document.getElementById(btnId);
        if (btn) btn.disabled = loading;
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    // Если уже авторизован — сразу показываем шаг 2
    if (typeof Auth !== 'undefined' && Auth.isLoggedIn()) {
        showStep2(Auth.getUsername(), false, Auth.getLevel());
    }
});
