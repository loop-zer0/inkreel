/** InkReel 认证模块 — Landing 页 & 工具页共用 */

const Auth = {
    TOKEN_KEY: 'inkreel_token',

    /** 是否已登录 */
    loggedIn() {
        return !!localStorage.getItem(this.TOKEN_KEY);
    },

    /** 获取 token */
    getToken() {
        return localStorage.getItem(this.TOKEN_KEY);
    },

    /** 保存 token 并跳转到工具页 */
    _saveAndGo(token) {
        localStorage.setItem(this.TOKEN_KEY, token);
        window.location.href = '/app';
    },

    /** 退出登录，返回 landing */
    logout() {
        localStorage.removeItem(this.TOKEN_KEY);
        window.location.href = '/';
    },

    /** 登录（邮箱/手机号 + 密码） */
    async login(account, password) {
        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account, password }),
            });
            const data = await res.json();
            if (data.status === 'ok') {
                this._saveAndGo(data.token);
                return { ok: true };
            }
            return { ok: false, message: data.message || '登录失败' };
        } catch (e) {
            return { ok: false, message: '网络错误: ' + e.message };
        }
    },

    /** 注册（需验证码） */
    async register(email, phone, password, code) {
        try {
            const res = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, phone, password, code }),
            });
            const data = await res.json();
            if (data.status === 'ok') {
                this._saveAndGo(data.token);
                return { ok: true };
            }
            return { ok: false, message: data.message || '注册失败' };
        } catch (e) {
            return { ok: false, message: '网络错误: ' + e.message };
        }
    },

    /** 发送验证码 */
    async sendCode(account) {
        try {
            const body = account.includes('@')
                ? { email: account }
                : { phone: account };
            const res = await fetch('/api/auth/send-code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json();
            if (data.status === 'ok') {
                return { ok: true, code: data.code };
            }
            return { ok: false, message: data.message || '发送失败' };
        } catch (e) {
            return { ok: false, message: '网络错误: ' + e.message };
        }
    },

    /** 重置密码（需验证码） */
    async resetPassword(account, code) {
        try {
            const body = { code };
            if (account.includes('@')) body.email = account;
            else body.phone = account;
            const res = await fetch('/api/auth/reset-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json();
            if (data.status === 'ok') {
                return { ok: true, newPassword: data.new_password };
            }
            return { ok: false, message: data.message || '重置失败' };
        } catch (e) {
            return { ok: false, message: '网络错误: ' + e.message };
        }
    },

    /** 倒计时按钮 */
    _countdown(btn, seconds) {
        const orig = btn.textContent;
        btn.disabled = true;
        btn.classList.add('counting');
        let remain = seconds;
        btn.textContent = `${remain}s 后重发`;
        const timer = setInterval(() => {
            remain--;
            if (remain <= 0) {
                clearInterval(timer);
                btn.textContent = orig;
                btn.disabled = false;
                btn.classList.remove('counting');
            } else {
                btn.textContent = `${remain}s 后重发`;
            }
        }, 1000);
    },

    /** 验证当前 token */
    async check() {
        const token = this.getToken();
        if (!token) return false;
        try {
            const res = await fetch('/api/auth/check', {
                headers: { 'Authorization': 'Bearer ' + token },
            });
            const data = await res.json();
            return data.status === 'ok';
        } catch (_) {
            return false;
        }
    },

    /** 初始化 landing 页的登录 UI */
    initLanding() {
        // 已登录直接跳工具页
        if (this.loggedIn()) {
            this.check().then(ok => {
                if (ok) window.location.href = '/app';
                else localStorage.removeItem(this.TOKEN_KEY);
            });
            return;
        }

        // "↓ 了解更多" 点击滚动到特性区
        const scrollHint = document.getElementById('scrollHint');
        if (scrollHint) {
            scrollHint.addEventListener('click', () => {
                document.getElementById('features').scrollIntoView({ behavior: 'smooth' });
            });
        }

        const modal = document.getElementById('loginModal');
        const self = this;

        function showLogin() { self._switchTab('login'); modal.style.display = 'flex'; }
        function hideLogin() { modal.style.display = 'none'; }

        // 标签页切换
        modal.querySelectorAll('.modal-tab').forEach(tab => {
            tab.addEventListener('click', () => self._switchTab(tab.dataset.tab));
        });

        // 所有触发登录的按钮
        document.querySelectorAll('#btnHeroStart, #btnCtaStart, #btnNavLogin, #btnNavStart').forEach(btn => {
            btn.addEventListener('click', showLogin);
        });

        // ── 登录 ──
        document.getElementById('btnLogin').addEventListener('click', async () => {
            const account = document.getElementById('loginAccount').value.trim();
            const pw = document.getElementById('loginPassword').value.trim();
            const err = document.getElementById('loginError');
            if (!account) { err.textContent = '请输入邮箱或手机号'; err.style.display = ''; return; }
            if (!pw) { err.textContent = '请输入密码'; err.style.display = ''; return; }
            err.style.display = 'none';
            const btn = document.getElementById('btnLogin');
            btn.textContent = '登录中...'; btn.disabled = true;
            const result = await self.login(account, pw);
            if (!result.ok) {
                err.textContent = result.message; err.style.display = '';
                btn.textContent = '登录'; btn.disabled = false;
            }
        });

        // ── 发送验证码（注册）──
        document.getElementById('btnSendRegCode').addEventListener('click', async () => {
            const email = document.getElementById('regEmail').value.trim();
            const phone = document.getElementById('regPhone').value.trim();
            const err = document.getElementById('regError');
            const hint = document.getElementById('regCodeHint');
            err.style.display = 'none'; hint.style.display = 'none';
            if (!email && !phone) { err.textContent = '请先输入邮箱或手机号'; err.style.display = ''; return; }
            const btn = document.getElementById('btnSendRegCode');
            const result = await self.sendCode(email || phone);
            if (result.ok) {
                hint.textContent = result.code ? `验证码：${result.code}` : result.message;
                hint.style.display = '';
                self._countdown(btn, 60);
            } else {
                err.textContent = result.message; err.style.display = '';
            }
        });

        // ── 注册 ──
        document.getElementById('btnRegister').addEventListener('click', async () => {
            const email = document.getElementById('regEmail').value.trim();
            const phone = document.getElementById('regPhone').value.trim();
            const pw = document.getElementById('regPassword').value.trim();
            const pw2 = document.getElementById('regPassword2').value.trim();
            const code = document.getElementById('regCode').value.trim();
            const err = document.getElementById('regError');
            if (!email && !phone) { err.textContent = '邮箱和手机号至少填一个'; err.style.display = ''; return; }
            if (pw.length < 4) { err.textContent = '密码至少 4 位'; err.style.display = ''; return; }
            if (pw !== pw2) { err.textContent = '两次密码不一致'; err.style.display = ''; return; }
            if (!code) { err.textContent = '请输入验证码'; err.style.display = ''; return; }
            err.style.display = 'none';
            const btn = document.getElementById('btnRegister');
            btn.textContent = '注册中...'; btn.disabled = true;
            const result = await self.register(email, phone, pw, code);
            if (!result.ok) {
                err.textContent = result.message; err.style.display = '';
                btn.textContent = '注册'; btn.disabled = false;
            }
        });

        // ── 发送验证码（找回密码）──
        document.getElementById('btnSendResetCode').addEventListener('click', async () => {
            const account = document.getElementById('resetAccount').value.trim();
            const err = document.getElementById('resetError');
            const ok = document.getElementById('resetSuccess');
            err.style.display = 'none'; ok.style.display = 'none';
            if (!account) { err.textContent = '请先输入邮箱或手机号'; err.style.display = ''; return; }
            const btn = document.getElementById('btnSendResetCode');
            const result = await self.sendCode(account);
            if (result.ok) {
                ok.textContent = result.code ? `验证码：${result.code}` : result.message;
                ok.style.display = '';
                self._countdown(btn, 60);
            } else {
                err.textContent = result.message; err.style.display = '';
            }
        });

        // ── 找回密码 ──
        document.getElementById('btnReset').addEventListener('click', async () => {
            const account = document.getElementById('resetAccount').value.trim();
            const code = document.getElementById('resetCode').value.trim();
            const err = document.getElementById('resetError');
            const ok = document.getElementById('resetSuccess');
            err.style.display = 'none'; ok.style.display = 'none';
            if (!account) { err.textContent = '请输入邮箱或手机号'; err.style.display = ''; return; }
            if (!code) { err.textContent = '请输入验证码'; err.style.display = ''; return; }
            const btn = document.getElementById('btnReset');
            btn.textContent = '处理中...'; btn.disabled = true;
            const result = await self.resetPassword(account, code);
            if (result.ok) {
                ok.innerHTML = `密码已重置为：<strong>${result.newPassword}</strong><br>请复制保存，前往登录。`;
                ok.style.display = '';
                btn.textContent = '已重置';
                setTimeout(() => { self._switchTab('login'); btn.textContent = '重置密码'; btn.disabled = false; }, 3000);
            } else {
                err.textContent = result.message; err.style.display = '';
                btn.textContent = '重置密码'; btn.disabled = false;
            }
        });

        // 回车提交
        [document.getElementById('loginPassword'), document.getElementById('loginAccount')].forEach(el => {
            el.addEventListener('keydown', (e) => { if (e.key === 'Enter') document.getElementById('btnLogin').click(); });
        });
        ['regEmail','regPhone','regPassword','regPassword2'].forEach(id => {
            document.getElementById(id).addEventListener('keydown', (e) => { if (e.key === 'Enter') document.getElementById('btnRegister').click(); });
        });
        document.getElementById('resetAccount').addEventListener('keydown', (e) => { if (e.key === 'Enter') document.getElementById('btnReset').click(); });

        // 点击遮罩关闭
        modal.addEventListener('click', (e) => { if (e.target === modal) hideLogin(); });
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && modal.style.display !== 'none') hideLogin(); });
    },

    /** 切换弹窗标签页 */
    _switchTab(target) {
        const modal = document.getElementById('loginModal');
        modal.querySelectorAll('.modal-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === target));
        modal.querySelectorAll('.modal-panel').forEach(p => p.style.display = p.id === 'panel' + target[0].toUpperCase() + target.slice(1) ? '' : 'none');
    },

    /** 初始化工具页的 token 检查 */
    async initApp() {
        if (!this.loggedIn()) {
            window.location.href = '/';
            return false;
        }
        const ok = await this.check();
        if (!ok) {
            localStorage.removeItem(this.TOKEN_KEY);
            window.location.href = '/';
            return false;
        }
        return true;
    },
};
