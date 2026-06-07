/** InkReel 工具函数 */

const Util = {
    formatSize(chars) {
        if (chars >= 10000) return (chars / 10000).toFixed(1) + '万';
        if (chars >= 1000) return (chars / 1000).toFixed(1) + 'k';
        return chars + '';
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    formatDate(iso) {
        if (!iso) return '';
        // 统一处理 ISO (T分隔) 和 SQLite (空格分隔) 格式
        let s = iso.replace('T', ' ').trim();
        // 去掉秒和毫秒，保留到分钟: "2026-06-06 13:10"
        const m = s.match(/^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})/);
        if (m) return m[1] + ' ' + m[2];
        return s.substring(0, 16);
    },

    highlightYaml(yaml) {
        return yaml
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/^(\s*)(#.*)/gm, '<span class="y-comment">$1$2</span>')
            .replace(/^(\s*)([\w_]+):/gm, '$1<span class="y-key">$2</span>:')
            .replace(/:\s+"([^"]*)"/g, ': <span class="y-str">"$1"</span>')
            .replace(/:\s+'([^']*)'/g, ': <span class="y-str">\'$1\'</span>')
            .replace(/:\s+(\d+\.?\d*)/g, ': <span class="y-num">$1</span>')
            .replace(/:\s+(true|false)/g, ': <span class="y-bool">$1</span>')
            .replace(/-\s+(\w[\w_\d]*)/g, '- <span class="y-list">$1</span>');
    },

    renderMarkdown(md) {
        let html = md
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/^### (.+)$/gm, '<h3>$1</h3>')
            .replace(/^## (.+)$/gm, '<h2>$1</h2>')
            .replace(/^# (.+)$/gm, '<h1>$1</h1>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/^\- (.+)$/gm, '<li>$1</li>')
            .replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
            .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');
        return '<p>' + html + '</p>';
    },

    _toastQueue: [],
    _toasting: false,

    showToast(msg, type) {
        this._toastQueue.push({ msg, type });
        if (!this._toasting) this._nextToast();
    },

    _nextToast() {
        if (this._toastQueue.length === 0) { this._toasting = false; return; }
        this._toasting = true;
        const { msg, type } = this._toastQueue.shift();
        const toast = document.getElementById('toast');
        toast.textContent = msg;
        toast.className = 'toast ' + type + ' show';
        clearTimeout(toast._t);
        toast._t = setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => this._nextToast(), 200);
        }, type === 'error' ? 4000 : 2200);
    },

    // 防抖工厂
    debounce(fn, delay) {
        let timer;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    },

    // requestAnimationFrame 包装
    raf(fn) {
        let pending = false;
        return function (...args) {
            if (pending) return;
            pending = true;
            requestAnimationFrame(() => {
                pending = false;
                fn.apply(this, args);
            });
        };
    },
};

/** 面板拖拽调节 */
const Resizer = {
    STORAGE_KEY: 'inkreel_panel_widths',
    _defaults: { sidebar: 260, detail: 280 },

    init() {
        // 恢复保存的宽度
        const saved = this._load();
        this._apply('--sidebar-w', saved.sidebar);
        this._apply('--detail-w', saved.detail);

        this._bind('resizeLeft', '--sidebar-w', saved.sidebar);
        this._bind('resizeRight', '--detail-w', saved.detail);
    },

    _apply(varName, px) {
        document.querySelector('.main-layout').style.setProperty(varName, px + 'px');
    },

    _bind(handleId, varName, initialPx) {
        const handle = document.getElementById(handleId);
        if (!handle) return;
        let startX = 0, startW = initialPx, dragging = false;

        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            dragging = true;
            startX = e.clientX;
            startW = this._getWidth(varName);
            handle.classList.add('active');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        });

        window.addEventListener('mousemove', (e) => {
            if (!dragging) return;
            const dx = e.clientX - startX;
            // 左拖拽手柄向右拖=缩小sidebar，右拖拽手柄向左拖=缩小detail
            const sign = handleId === 'resizeLeft' ? 1 : -1;
            let newW = startW + dx * sign;
            newW = Math.round(newW);
            this._apply(varName, newW);
            this._save();
        });

        window.addEventListener('mouseup', () => {
            if (!dragging) return;
            dragging = false;
            handle.classList.remove('active');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            this._save();
        });
    },

    _getWidth(varName) {
        const v = document.querySelector('.main-layout').style.getPropertyValue(varName);
        return parseFloat(v) || this._defaults[varName === '--sidebar-w' ? 'sidebar' : 'detail'];
    },

    _save() {
        const layout = document.querySelector('.main-layout');
        const data = {
            sidebar: parseFloat(layout.style.getPropertyValue('--sidebar-w')) || this._defaults.sidebar,
            detail: parseFloat(layout.style.getPropertyValue('--detail-w')) || this._defaults.detail,
        };
        try { localStorage.setItem(this.STORAGE_KEY, JSON.stringify(data)); } catch (_) {}
    },

    _load() {
        try {
            const raw = localStorage.getItem(this.STORAGE_KEY);
            if (raw) return { ...this._defaults, ...JSON.parse(raw) };
        } catch (_) {}
        return { ...this._defaults };
    },
};
