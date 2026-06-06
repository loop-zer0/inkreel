/** InkReel API 封装 */
const API = {
    _authHeaders() {
        const h = {};
        const token = sessionStorage.getItem('inkreel_token');
        if (token) h['Authorization'] = 'Bearer ' + token;
        return h;
    },

    async get(path) {
        const r = await fetch(path, { headers: this._authHeaders() });
        return r.json();
    },
    async post(path, body) {
        const h = this._authHeaders();
        if (!(body instanceof FormData)) h['Content-Type'] = 'application/json';
        const r = await fetch(path, {
            method: 'POST',
            headers: h,
            body: body instanceof FormData ? body : JSON.stringify(body),
        });
        return r.json();
    },
    async put(path, body) {
        const h = { ...this._authHeaders(), 'Content-Type': 'application/json' };
        const r = await fetch(path, {
            method: 'PUT',
            headers: h,
            body: JSON.stringify(body),
        });
        return r.json();
    },
    async del(path) {
        const r = await fetch(path, { method: 'DELETE', headers: this._authHeaders() });
        return r.json();
    },

    // System
    health:       ()           => API.get('/api/health'),
    getMode:      ()           => API.get('/api/mode'),
    switchMode:   (mode)       => API.post('/api/mode', { mode }),
    getSchema:    ()           => API.get('/api/schema'),

    // Novels
    preview:      (file)       => API.post('/api/novels/preview', file),
    importNovel:  (title, author) => API.post('/api/novels/import', { title, author }),
    listNovels:   ()           => API.get('/api/novels'),
    getNovel:     (id)         => API.get(`/api/novels/${id}`),
    deleteNovel:  (id)         => API.del(`/api/novels/${id}`),
    reloadPreview:(id)         => API.get(`/api/novels/${id}/preview`),
    quickConvert: (formData)   => API.post('/api/novels/quick-convert', formData),

    // Convert
    convertChapter: (novelId, chNum) =>
        API.post(`/api/novels/${novelId}/convert/${chNum}`, {}),
    convertBatch: (novelId, chapters) =>
        API.post(`/api/novels/${novelId}/convert/batch`, { chapter_numbers: chapters }),

    // Scripts
    getScript:    (id)         => API.get(`/api/scripts/${id}`),
    deleteScript: (id)         => API.del(`/api/scripts/${id}`),
    mergeScript:  (id, title)  => API.post(`/api/scripts/${id}/merge`, title ? { title } : {}),
    updateScript: (id, data)   => API.put(`/api/scripts/${id}`, data),
    newScript:    (novelId, title) => API.post(`/api/novels/${novelId}/scripts/new`, { title }),
    getChapterYaml: (novelId, chNum) => API.get(`/api/novels/${novelId}/chapters/${chNum}/yaml`),
};
