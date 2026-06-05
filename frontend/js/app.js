/** Novel2Script — 前端应用 */
(() => {
    // ── DOM ──
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const fileChapters = document.getElementById('fileChapters');
    const btnConvert = document.getElementById('btnConvert');
    const btnDownload = document.getElementById('btnDownload');
    const progressArea = document.getElementById('progressArea');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const statsArea = document.getElementById('statsArea');
    const yamlOutput = document.getElementById('yamlOutput');
    const previewPlaceholder = document.getElementById('previewPlaceholder');
    const statusEl = document.getElementById('statusEl');
    const toast = document.getElementById('toast');
    const modeToggle = document.getElementById('modeToggle');
    const modeLabel = document.getElementById('modeLabel');
    const titleInput = document.getElementById('titleInput');
    const authorInput = document.getElementById('authorInput');
    const schemaDoc = document.getElementById('schemaDoc');

    let selectedFile = null;
    let currentYaml = '';
    let isOffline = false;

    // ── 在线/离线切换 ──
    async function initMode() {
        try {
            const resp = await fetch('/api/mode');
            const data = await resp.json();
            isOffline = data.mode === 'offline';
            updateModeUI();
        } catch (_) {}
    }

    function updateModeUI() {
        modeToggle.checked = isOffline;
        if (isOffline) {
            modeLabel.textContent = '🏠 离线';
            modeLabel.classList.add('offline');
        } else {
            modeLabel.textContent = '🌐 云端';
            modeLabel.classList.remove('offline');
        }
    }

    modeToggle.addEventListener('change', async () => {
        isOffline = modeToggle.checked;
        updateModeUI();
        try {
            await fetch('/api/mode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: isOffline ? 'offline' : 'online' }),
            });
            showToast(isOffline ? '已切换到离线模式（本地 Ollama）' : '已切换到云端模式（DeepSeek）', 'info');
        } catch (_) {
            showToast('模式切换失败', 'error');
        }
    });

    // ── 文件上传 ──
    uploadZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) handleFile(fileInput.files[0]);
    });

    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
    });

    function handleFile(file) {
        if (!file.name.match(/\.(txt|text|md|markdown|docx|epub)$/i)) {
            showToast('请上传 .txt / .md / .docx / .epub 文件', 'error');
            return;
        }
        selectedFile = file;
        fileName.textContent = file.name;
        fileSize.textContent = (file.size / 1024).toFixed(1) + ' KB';
        fileChapters.textContent = '章节检测中...';
        fileInfo.style.display = '';
        uploadZone.classList.add('has-file');
        btnConvert.disabled = false;
        // 重置预览
        yamlOutput.style.display = 'none';
        previewPlaceholder.style.display = '';
        statsArea.style.display = 'none';
        btnDownload.style.display = 'none';
        progressArea.style.display = 'none';
    }

    // ── 转换 ──
    btnConvert.addEventListener('click', async () => {
        if (!selectedFile) return;

        btnConvert.disabled = true;
        progressArea.style.display = '';
        progressFill.style.width = '10%';
        progressText.textContent = '正在分割章节...';
        setStatus('active', '⏳ 处理中...');

        const formData = new FormData();
        formData.append('file', selectedFile);
        if (titleInput.value.trim()) formData.append('title', titleInput.value.trim());
        if (authorInput.value.trim()) formData.append('author', authorInput.value.trim());

        try {
            const resp = await fetch('/api/convert', {
                method: 'POST',
                body: formData,
            });

            const data = await resp.json();

            if (data.status === 'error') {
                setStatus('error', '❌ 转换失败');
                showToast(data.message, 'error');
                progressArea.style.display = 'none';
                btnConvert.disabled = false;
                return;
            }

            // 成功
            progressFill.style.width = '100%';
            progressText.textContent = '完成!';
            setStatus('success', '✅ 转换完成');

            // 显示统计
            statsArea.style.display = '';
            document.getElementById('statChapters').textContent = data.stats.chapters;
            document.getElementById('statChars').textContent = data.stats.characters;
            document.getElementById('statScenes').textContent = data.stats.scenes;

            // YAML 预览（语法高亮）
            currentYaml = data.yaml;
            yamlOutput.innerHTML = highlightYaml(currentYaml);
            yamlOutput.style.display = '';
            previewPlaceholder.style.display = 'none';

            // 显示验证错误
            if (data.errors && data.errors.length > 0) {
                const errDiv = document.createElement('div');
                errDiv.className = 'errors-box';
                errDiv.innerHTML = '<strong>⚠ 验证警告</strong><ul>' +
                    data.errors.map(e => '<li>' + e + '</li>').join('') + '</ul>';
                yamlOutput.parentElement.insertBefore(errDiv, yamlOutput.nextSibling);
            }

            // 更新文件信息中的章节数
            fileChapters.textContent = data.stats.chapters + ' 章';

            // 显示输出文件路径
            if (data.output_file) {
                const pathEl = document.getElementById('outputPath');
                pathEl.textContent = 'Saved: ' + data.output_file;
                pathEl.style.display = '';
            }

            btnDownload.style.display = '';
            btnConvert.disabled = false;

        } catch (e) {
            setStatus('error', '❌ 网络错误');
            showToast('请求失败: ' + e.message, 'error');
            progressArea.style.display = 'none';
            btnConvert.disabled = false;
        }
    });

    // ── 下载 ──
    btnDownload.addEventListener('click', () => {
        if (!currentYaml) return;
        const blob = new Blob([currentYaml], { type: 'text/yaml;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = (titleInput.value.trim() || 'script') + '.yaml';
        a.click();
        URL.revokeObjectURL(url);
        showToast('已下载 YAML 剧本文件', 'success');
    });

    // ── Tab 切换 ──
    document.querySelectorAll('.preview-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.preview-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const target = tab.dataset.tab;
            document.getElementById('previewYaml').style.display = target === 'yaml' ? '' : 'none';
            document.getElementById('previewSchema').style.display = target === 'schema' ? '' : 'none';
            if (target === 'schema') loadSchemaDoc();
        });
    });

    async function loadSchemaDoc() {
        if (schemaDoc.textContent !== '加载中...') return;
        try {
            const resp = await fetch('/api/schema');
            const data = await resp.json();
            schemaDoc.innerHTML = renderMarkdown(data.content);
        } catch (_) {
            schemaDoc.textContent = '加载 Schema 文档失败';
        }
    }

    // ── 简易 Markdown 渲染 ──
    function renderMarkdown(md) {
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
    }

    // ── YAML 语法高亮 ──
    function highlightYaml(yaml) {
        return yaml
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/^(\s*)(#.*)/gm, '<span class="y-comment">$1$2</span>')
            .replace(/^(\s*)([\w_]+):/gm, '$1<span class="y-key">$2</span>:')
            .replace(/:\s+"([^"]*)"/g, ': <span class="y-str">"$1"</span>')
            .replace(/:\s+'([^']*)'/g, ': <span class="y-str">\'$1\'</span>')
            .replace(/:\s+(\d+\.?\d*)/g, ': <span class="y-num">$1</span>')
            .replace(/:\s+(true|false)/g, ': <span class="y-bool">$1</span>')
            .replace(/-\s+(\w[\w_\d]*)/g, '- <span class="y-list">$1</span>');
    }

    // ── 工具函数 ──
    function setStatus(state, text) {
        statusEl.className = 'status ' + state;
        statusEl.textContent = text;
    }

    function showToast(msg, type) {
        toast.textContent = msg;
        toast.className = 'toast ' + type + ' show';
        clearTimeout(toast._t);
        toast._t = setTimeout(() => toast.classList.remove('show'), 3000);
    }

    // ── 初始化 ──
    initMode();
})();
