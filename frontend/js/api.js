/** InkReel — API 请求层 */

const API = {
    _token() {
        return localStorage.getItem('inkreel_token') || '';
    },

    _headers(isJson) {
        const h = { 'Authorization': 'Bearer ' + this._token() };
        if (isJson !== false) h['Content-Type'] = 'application/json';
        return h;
    },

    async _fetch(url, options = {}) {
        const headers = { ...(options.headers || {}) };
        // 自动注入 Authorization
        if (!headers['Authorization']) {
            headers['Authorization'] = 'Bearer ' + this._token();
        }
        // POST/PUT 有 body 时自动加 Content-Type
        if (options.body && !headers['Content-Type']) {
            headers['Content-Type'] = 'application/json';
        }
        const res = await fetch(url, { ...options, headers });
        const ct = res.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
            return res.json();
        }
        return { status: 'error', message: '非 JSON 响应' };
    },

    // ── 系统 ──

    async getSchema() {
        return this._fetch('/api/schema');
    },

    // ── 导入 ──

    async preview(formData) {
        const res = await fetch('/api/novels/preview', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + this._token() },
            body: formData,
        });
        return res.json();
    },

    async importNovel(title, author) {
        return this._fetch('/api/novels/import', {
            method: 'POST',
            headers: this._headers(),
            body: JSON.stringify({ title, author }),
        });
    },

    // ── 仓库 ──

    async listNovels() {
        return this._fetch('/api/novels');
    },

    async getNovel(novelId) {
        return this._fetch('/api/novels/' + novelId);
    },

    async deleteNovel(novelId) {
        return this._fetch('/api/novels/' + novelId, { method: 'DELETE' });
    },

    async updateNovel(novelId, data) {
        return this._fetch('/api/novels/' + novelId, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    },

    // ── 转换 ──

    async convertChapter(novelId, chapterNum) {
        return this._fetch('/api/novels/' + novelId + '/convert/' + chapterNum, {
            method: 'POST',
            headers: this._headers(),
            body: '{}',
        });
    },

    async convertBatch(novelId, chapterNumbers) {
        return this._fetch('/api/novels/' + novelId + '/convert/batch', {
            method: 'POST',
            headers: this._headers(),
            body: JSON.stringify({ chapter_numbers: chapterNumbers }),
        });
    },

    async getChapterYaml(novelId, chapterNum) {
        return this._fetch('/api/novels/' + novelId + '/chapters/' + chapterNum + '/yaml');
    },

    // ── 剧本 ──

    async newScript(novelId, title) {
        return this._fetch('/api/novels/' + novelId + '/scripts/new', {
            method: 'POST',
            headers: this._headers(),
            body: JSON.stringify({ title }),
        });
    },

    async getScript(scriptId) {
        return this._fetch('/api/scripts/' + scriptId);
    },

    async updateScript(scriptId, data) {
        return this._fetch('/api/scripts/' + scriptId, {
            method: 'PUT',
            headers: this._headers(),
            body: JSON.stringify(data),
        });
    },

    async deleteScript(scriptId) {
        return this._fetch('/api/scripts/' + scriptId, { method: 'DELETE' });
    },

    async mergeScript(scriptId, title) {
        return this._fetch('/api/scripts/' + scriptId + '/merge', {
            method: 'POST',
            headers: this._headers(),
            body: JSON.stringify({ title: title || null }),
        });
    },

    // ── 合并剧本 ──

    async listMerges(scriptId) {
        return this._fetch('/api/scripts/' + scriptId + '/merges');
    },

    async createMerge(scriptId, data) {
        return this._fetch('/api/scripts/' + scriptId + '/merges', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    async getMerge(mergeId) {
        return this._fetch('/api/merges/' + mergeId);
    },

    async updateMerge(mergeId, data) {
        return this._fetch('/api/merges/' + mergeId, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    },

    async deleteMerge(mergeId) {
        return this._fetch('/api/merges/' + mergeId, { method: 'DELETE' });
    },

    // ── 小说编辑 ──

    async updateChapter(novelId, chapterId, data) {
        return this._fetch(`/api/novels/${novelId}/chapters/${chapterId}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    },

    async syncPreview(novelId, file) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(`/api/novels/${novelId}/sync-preview`, {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + this._token() },
            body: formData,
        });
        return res.json();
    },

    async syncApply(novelId, add, update) {
        return this._fetch(`/api/novels/${novelId}/sync-apply`, {
            method: 'POST',
            body: JSON.stringify({ add, update }),
        });
    },

    async appendChapters(novelId, file) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(`/api/novels/${novelId}/append`, {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + this._token() },
            body: formData,
        });
        return res.json();
    },

    async getChapterContent(novelId, chapterNum) {
        return this._fetch(`/api/novels/${novelId}/chapters/${chapterNum}/content`);
    },

    // ── 翻译 ──

    async listTranslations(scriptId) {
        return this._fetch(`/api/scripts/${scriptId}/translations`);
    },

    async translateScript(scriptId, language, languageLabel, direction) {
        return this._fetch(`/api/scripts/${scriptId}/translate`, {
            method: 'POST',
            body: JSON.stringify({ language, language_label: languageLabel, direction }),
        });
    },

    async getTranslation(transId) {
        return this._fetch('/api/translations/' + transId);
    },

    async deleteTranslation(transId) {
        return this._fetch('/api/translations/' + transId, { method: 'DELETE' });
    },

    async getLanguages() {
        return this._fetch('/api/languages');
    },

    // ── Auth ──

    async register(email, phone, password) {
        return this._fetch('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, phone, password }),
        });
    },

    async login(account, password) {
        return this._fetch('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ account, password }),
        });
    },

    async resetPassword(email, phone) {
        return this._fetch('/api/auth/reset-password', {
            method: 'POST',
            body: JSON.stringify({ email, phone }),
        });
    },

    async checkAuth() {
        return this._fetch('/api/auth/check');
    },
};
