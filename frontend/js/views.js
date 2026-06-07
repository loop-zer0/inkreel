/** InkReel — 视图渲染 */

const View = {
    // ── 导入模态框 ──

    showImportModal(chapters, genre) {
        document.getElementById('importFileName').textContent = App.state.previewFilename;
        document.getElementById('importChapterCount').textContent = chapters.length + ' 章';
        document.getElementById('importGenre').textContent = genre || '（自动识别）';
        document.getElementById('importTitle').value = '';
        document.getElementById('importModal').style.display = '';
    },

    hideImportModal() {
        document.getElementById('importModal').style.display = 'none';
    },

    // ── YAML 编辑 ──

    startEdit() {
        const pre = document.getElementById('yamlOutput');
        const editor = document.getElementById('yamlEditor');
        const btn = document.getElementById('btnEditYaml');

        editor.value = App.state.currentYaml;
        pre.style.display = 'none';
        editor.style.display = 'block';
        btn.textContent = '✓';
        btn.dataset.mode = 'edit';
        btn.title = '保存';
        document.getElementById('previewPlaceholder').style.display = 'none';
    },

    saveEdit() {
        const editor = document.getElementById('yamlEditor');
        const pre = document.getElementById('yamlOutput');
        const btn = document.getElementById('btnEditYaml');
        const newYaml = editor.value;

        App.state.currentYaml = newYaml;
        this.showYaml(newYaml);
        editor.style.display = 'none';
        pre.style.display = '';
        btn.textContent = '✎';
        btn.dataset.mode = 'view';
        btn.title = '编辑';

        // 异步保存到后端
        if (App.state.currentScriptId) {
            API.updateScript(App.state.currentScriptId, { yaml_content: newYaml }).catch(() => {});
        }
    },

    // ── 元信息编辑 ──

    startMetaEdit() {
        document.getElementById('detailMetaView').style.display = 'none';
        document.getElementById('detailMetaEdit').style.display = '';
        document.getElementById('btnEditMeta').style.display = 'none';

        const titleEl = document.getElementById('detailTitle');
        const metaEl = document.getElementById('detailMeta');
        document.getElementById('editTitle').value = titleEl.textContent || '';
        // 从 meta 文本中解析作者和类型
        const metaText = metaEl.textContent || '';
        const authorMatch = metaText.match(/作者[：:]\s*(.+)/);
        const genreMatch = metaText.match(/类型[：:]\s*(.+)/);
        document.getElementById('editAuthor').value = authorMatch ? authorMatch[1] : '';
        document.getElementById('editGenre').value = genreMatch ? genreMatch[1] : '';
    },

    saveMetaEdit() {
        const title = document.getElementById('editTitle').value.trim();
        const author = document.getElementById('editAuthor').value.trim();
        const genre = document.getElementById('editGenre').value.trim();

        document.getElementById('detailTitle').textContent = title || '（未命名）';
        document.getElementById('detailMeta').textContent =
            (author ? '作者：' + author + '　' : '') +
            (genre ? '类型：' + genre : '');

        document.getElementById('detailMetaView').style.display = '';
        document.getElementById('detailMetaEdit').style.display = 'none';
        document.getElementById('btnEditMeta').style.display = '';

        // 持久化 + 刷新侧栏
        if (App.state.currentNovelId) {
            API.updateNovel(App.state.currentNovelId, { title, author, genre })
                .then(() => App._loadLibrary())
                .catch(() => {});
        }
    },

    _cancelMetaEdit() {
        document.getElementById('detailMetaView').style.display = '';
        document.getElementById('detailMetaEdit').style.display = 'none';
        document.getElementById('btnEditMeta').style.display = '';
    },

    // ── 小说详情 ──

    hideNovelDetail() {
        document.getElementById('detailPanel').style.display = 'none';
        document.getElementById('placeholderDetail').style.display = '';
        document.getElementById('btnEditMeta').style.display = 'none';
        App.state.currentNovelId = null;
        App.state.chapters = [];
        App.state.generatedChapters = [];
        App.state.availableScripts = [];
        App.state.currentScriptId = null;
        App.state.currentYaml = '';
        this.showPlaceholder();
        document.getElementById('btnDownload').style.display = 'none';
        this.hideDetailButtons();
        this.hideTranslationTab();
    },

    showNovelHeader(novel) {
        document.getElementById('detailPanel').style.display = '';
        document.getElementById('placeholderDetail').style.display = 'none';
        document.getElementById('detailTitle').textContent = novel.title || '（未命名）';
        document.getElementById('detailMeta').textContent =
            (novel.author && novel.author !== '（未知）' ? '作者：' + novel.author + '　' : '') +
            (novel.genre ? '类型：' + novel.genre : '') +
            (novel.total_chars ? '　' + this._formatSize(novel.total_chars) : '');
        document.getElementById('btnEditMeta').style.display = '';
    },

    showPlaceholder() {
        document.getElementById('yamlOutput').style.display = 'none';
        document.getElementById('yamlEditor').style.display = 'none';
        document.getElementById('previewPlaceholder').style.display = '';
        const btn = document.getElementById('btnEditYaml');
        btn.style.display = 'none';
    },

    // ── 仓库列表 ──

    renderLibrary(novels) {
        const container = document.getElementById('libraryList');
        if (!novels || novels.length === 0) {
            container.innerHTML = '<div class="library-empty">暂无小说<p class="hint">拖入文件或点击导入</p></div>';
            // 隐藏刷新 + 重置所有 UI
            document.getElementById('btnRefresh').style.display = '';
            return;
        }

        document.getElementById('btnRefresh').style.display = '';

        container.innerHTML = novels.map(n => {
            const title = n.title || '（未命名）';
            const genre = n.genre ? '<span class="lib-genre">' + this._esc(n.genre) + '</span>' : '';
            const chapters = n.chapter_count != null ? n.chapter_count + '章' : '';
            const size = n.total_chars ? this._formatSize(n.total_chars) : '';
            const date = n.created_at ? n.created_at.slice(0, 10) : '';

            return `
            <div class="library-card" data-novel-id="${n.id}">
                <div class="lib-title">${this._esc(title)}</div>
                <div class="lib-meta">
                    ${genre}
                    ${chapters ? '<span>' + chapters + '</span>' : ''}
                    ${size ? '<span>' + size + '</span>' : ''}
                    ${date ? '<span>' + date + '</span>' : ''}
                </div>
                <div class="lib-actions">
                    <button class="btn-xs lib-btn-open">打开</button>
                    <button class="btn-xs danger lib-btn-del">删除</button>
                </div>
            </div>`;
        }).join('');
    },

    // ── 章节列表 ──

    renderChapterList(chapters, generated, scripts, currentScriptId) {
        const container = document.getElementById('chapterList');
        if (!chapters || chapters.length === 0) {
            container.innerHTML = '<div class="hint-text">暂无章节</div>';
            return;
        }

        const currentScript = scripts.find(s => s.id === currentScriptId);
        const isComplete = currentScript && currentScript.status === 'complete';

        // 剧本选择器 HTML
        let scriptSelectorHTML = '';
        if (scripts.length > 1) {
            const options = scripts.map(s => {
                const label = (s.title || '（未命名）') + (s.status === 'complete' ? ' ✓' : ' ✎');
                const sel = s.id === currentScriptId ? ' selected' : '';
                return '<option value="' + s.id + '"' + sel + '>' + this._esc(label) + '</option>';
            }).join('');
            scriptSelectorHTML = `
            <div class="script-selector-row">
                <span class="script-label">改编版本</span>
                <select class="script-select" id="scriptSelect">${options}</select>
                <button class="btn-xs" id="btnNewScript" title="新建改编">+</button>
                <span class="script-name-display" id="scriptNameDisplay" style="cursor:pointer" title="点击重命名">${this._esc(currentScript ? (currentScript.title || '（新改编）') : '')}</span>
                <input class="script-name-input" id="scriptNameInput" style="display:none" placeholder="输入剧本名称...">
                <button class="btn-icon" id="btnRenameScript" title="重命名" style="font-size:12px">✎</button>
                <button class="btn-icon" id="btnDeleteScript" title="删除剧本" style="font-size:12px;color:var(--red);margin-left:auto">×</button>
            </div>`;
        } else if (scripts.length === 1) {
            const s = scripts[0];
            const badge = isComplete
                ? '<span class="script-status-badge done">已完成</span>'
                : '<span class="script-status-badge draft">草稿</span>';
            const metaParts = [];
            if (s.scene_count) metaParts.push(s.scene_count + '场景');
            if (s.created_at) metaParts.push(s.created_at.slice(0, 10));
            scriptSelectorHTML = `
            <div class="script-single-row">
                ${badge}
                <span class="script-name-display" id="scriptNameDisplay" style="cursor:pointer" title="点击重命名">${this._esc(s.title || '（未命名）')}</span>
                <input class="script-name-input" id="scriptNameInput" style="display:none" placeholder="输入剧本名称...">
                <button class="btn-icon" id="btnRenameScript" title="重命名" style="font-size:12px">✎</button>
                <span class="script-meta">${metaParts.join(' · ')}</span>
                <button class="btn-icon" id="btnDeleteScript" title="删除剧本" style="font-size:12px;color:var(--red)">×</button>
                <button class="btn-xs" id="btnNewScript" title="新建改编" style="margin-left:auto">+新改编</button>
            </div>`;
        } else {
            scriptSelectorHTML = `
            <div class="script-single-row">
                <span class="script-label">暂无改编</span>
                <button class="btn-xs" id="btnNewScript" title="新建改编" style="margin-left:auto">+新改编</button>
            </div>`;
        }

        // 锁定区
        const totalChapters = chapters.length;
        let lockHTML = '';
        if (isComplete) {
            lockHTML = `
            <div class="merge-done">
                <span>🔒 剧本已锁定 · ${currentScript.scene_count || '?'} 场景</span>
                <button class="btn-xs" id="btnLockView" style="margin-left:auto">查看完整剧本</button>
            </div>`;
        } else if (generated.length > 0) {
            lockHTML = `
            <div class="merge-ready">
                <span class="merge-hint">已转换 ${generated.length}/${totalChapters} 章，检查无误后可锁定</span>
                <button class="btn-xs accent" id="btnLock" style="margin-left:auto">🔒 锁定剧本</button>
            </div>`;
        }

        // 章节行
        const generatedSet = new Set(generated);
        // 收集所有已有结果的 chapter_number（跨剧本）
        const allDoneSet = new Set();
        if (currentScript && currentScript.chapters) {
            currentScript.chapters.forEach(c => allDoneSet.add(c.chapter_number));
        }

        const chapterItems = chapters.map(c => {
            const num = c.num;
            const title = c.title || '';
            const chars = c.chars ? this._formatSize(c.chars) : '';
            const isChecked = App.state.selectedChapters.has(num);
            const doneHere = generatedSet.has(num);
            const doneElsewhere = !doneHere && allDoneSet.has(num);
            const elsewhereClass = doneElsewhere ? ' elsewhere' : '';
            const checkedClass = isChecked ? ' checked' : '';

            const statusHTML = doneHere
                ? '<span class="ch-status done">✓已转</span>'
                : doneElsewhere
                    ? '<span class="ch-status elsewhere">已在其他改编</span>'
                    : '<span class="ch-status pending">待转</span>';

            const actionsHTML = doneHere
                ? `<button class="btn-xs ch-btn-view" data-ch="${num}">YAML</button>
                   <button class="btn-xs ch-btn-original" data-ch="${num}">📖 原文</button>
                   <button class="btn-xs ch-btn-convert" data-ch="${num}">🔄重转</button>`
                : doneElsewhere
                    ? `<button class="btn-xs ch-btn-reuse" data-ch="${num}">📋复用</button>
                       <button class="btn-xs ch-btn-original" data-ch="${num}">📖 原文</button>`
                    : `<button class="btn-xs ch-btn-convert" data-ch="${num}">🎬转换</button>
                       <button class="btn-xs ch-btn-original" data-ch="${num}">📖 原文</button>`;

            return `
            <div class="chapter-item${elsewhereClass}${checkedClass}">
                <input type="checkbox" class="ch-checkbox" data-ch="${num}"${isChecked ? ' checked' : ''}>
                <span class="ch-num">${num}</span>
                <span class="ch-title">${this._esc(title)}</span>
                ${chars ? '<span class="ch-chars">' + chars + '</span>' : ''}
                <span class="ch-actions">${actionsHTML}</span>
                ${statusHTML}
            </div>`;
        }).join('');

        // 全选 + 批量转换条
        const selCount = App.state.selectedChapters.size;
        const batchBarHTML = totalChapters > 0 ? `
            <div class="ch-batch-bar" id="batchBar" style="${selCount > 0 ? '' : 'display:none'}">
                <button class="btn-xs" id="btnSelectAll">全选</button>
                <button class="btn-xs accent" id="btnBatchConvert">🎬 批量转换 (${selCount})</button>
            </div>` : '';

        container.innerHTML = `
            ${scriptSelectorHTML}
            <div class="chapter-select-header">
                <span class="chapter-count">
                    <span class="ch-range-label">${generated.length}/${totalChapters}</span>
                    <span class="ch-total-label">已转/总章节</span>
                </span>
                ${batchBarHTML}
            </div>
            <div style="flex:1;overflow-y:auto">${chapterItems}</div>
            ${lockHTML}
        `;
    },

    // ── YAML 展示 ──

    showYaml(yaml) {
        const pre = document.getElementById('yamlOutput');
        const placeholder = document.getElementById('previewPlaceholder');
        const editor = document.getElementById('yamlEditor');
        const btn = document.getElementById('btnEditYaml');

        placeholder.style.display = 'none';
        editor.style.display = 'none';
        pre.style.display = '';
        btn.style.display = '';
        btn.textContent = '✎';
        btn.dataset.mode = 'view';
        btn.title = '编辑';

        // 简易语法高亮
        pre.innerHTML = this._highlightYaml(yaml);
    },

    _highlightYaml(yaml) {
        if (!yaml) return '';
        let html = this._esc(yaml);
        // 注释
        html = html.replace(/^(#.*)$/gm, '<span class="y-comment">$1</span>');
        // key: value (key 着色)
        html = html.replace(/^([\w一-鿿_-]+)(\s*:)/gm,
            '<span class="y-key">$1</span>$2');
        // 字符串值（引号内）
        html = html.replace(/("(?:[^"\\]|\\.)*")/g, '<span class="y-str">$1</span>');
        // 数字
        html = html.replace(/\b(\d+\.?\d*)\b/g, '<span class="y-num">$1</span>');
        // bool
        html = html.replace(/\b(true|false|yes|no)\b/gi, '<span class="y-bool">$1</span>');
        // 列表项
        html = html.replace(/^(\s*-\s)/gm, '<span class="y-list">$1</span>');
        return html;
    },

    // ── 合并剧本区块 ──

    renderMergedScripts(merges, chapters, generatedChapters) {
        const listEl = document.getElementById('mergedList');
        if (!listEl) return;

        if (!merges || merges.length === 0) {
            listEl.innerHTML = '<div class="merged-empty">暂无合并剧本</div>';
            this._renderMergeChapterPicker(chapters, generatedChapters);
            return;
        }

        listEl.innerHTML = merges.map(m => {
            const itemCount = (m.items || []).length;
            const title = m.title || '（未命名）';
            const note = m.note ? '<span class="merged-note">' + this._esc(m.note) + '</span>' : '';
            const date = m.created_at ? m.created_at.slice(0, 10) : '';
            const scenes = m.scene_count ? m.scene_count + '场景' : '';
            return `
            <div class="merged-item" data-merge-id="${m.id}">
                <div class="merged-item-main">
                    <span class="merged-item-title">${this._esc(title)}</span>
                    ${note}
                    <span class="merged-item-meta">${date} · ${scenes} · ${itemCount}章</span>
                </div>
                <div class="merged-item-actions">
                    <button class="btn-xs merged-btn-view" data-merge-id="${m.id}">查看</button>
                    <button class="btn-xs merged-btn-rename" data-merge-id="${m.id}">重命名</button>
                    <button class="btn-xs danger merged-btn-del" data-merge-id="${m.id}">×</button>
                </div>
            </div>`;
        }).join('');

        this._renderMergeChapterPicker(chapters, generatedChapters);
    },

    _renderMergeChapterPicker(chapters, generatedChapters) {
        const picker = document.getElementById('mergeChapterPicker');
        if (!picker) return;

        const genSet = new Set(generatedChapters);
        if (!chapters || chapters.length === 0) {
            picker.innerHTML = '<div class="hint-text">暂无章节</div>';
            return;
        }

        picker.innerHTML = chapters.map(c => {
            const converted = genSet.has(c.num);
            const label = converted ? '✓' : '⚠️';
            const title = converted ? '已转换' : '尚未转换，合并时将跳过';
            const cls = converted ? '' : 'unconverted';
            return `
            <label class="merge-ch-opt ${cls}" title="${title}">
                <input type="checkbox" class="merge-ch-cb" data-ch="${c.num}" ${converted ? 'checked' : ''}>
                <span class="merge-ch-num">${c.num}</span>
                <span class="merge-ch-label">${this._esc(c.title || '')}</span>
                <span class="merge-ch-status">${label}</span>
            </label>`;
        }).join('');
    },

    showMergeCreateForm() {
        document.getElementById('mergedCreate').style.display = '';
        document.getElementById('btnCreateMerge').style.display = 'none';
        document.getElementById('mergeName').value = '';
        document.getElementById('mergeNote').value = '';
        document.getElementById('mergeName').focus();
    },

    hideMergeCreateForm() {
        document.getElementById('mergedCreate').style.display = 'none';
        document.getElementById('btnCreateMerge').style.display = '';
    },

    // ── 小说编辑器 ──

    showNovelEditor(chapters) {
        document.getElementById('novelEditorModal').style.display = '';
        document.getElementById('editorStatus').textContent = '';
        // 渲染章节目录
        const toc = document.getElementById('novelEditorToc');
        toc.innerHTML = chapters.map(c => `
            <div class="editor-toc-item" data-ch-num="${c.num}" data-ch-id="${c.id || ''}">
                <span class="editor-toc-num">${c.num}</span>
                <span class="editor-toc-title">${this._esc(c.title || '')}</span>
            </div>
        `).join('');
    },

    setEditorContent(chapter) {
        document.getElementById('editorChTitle').value = chapter.title || '';
        document.getElementById('editorChContent').value = chapter.content || '';
        document.getElementById('editorStatus').textContent = chapter.chapter_number
            ? `第 ${chapter.chapter_number} 章 · ${(chapter.char_count || 0)} 字`
            : '';
        // 高亮当前
        const num = chapter.chapter_number || chapter.num;
        document.querySelectorAll('.editor-toc-item').forEach(el => {
            el.classList.toggle('active', parseFloat(el.dataset.chNum) === parseFloat(num));
        });
    },

    hideNovelEditor() {
        document.getElementById('novelEditorModal').style.display = 'none';
    },

    // ── 同步预览 ──

    showSyncModal(diff) {
        document.getElementById('syncTitle').textContent = `章节同步 · ${diff.filename || ''}`;
        document.getElementById('syncSummary').innerHTML =
            `共 ${diff.total_incoming} 章 · ` +
            `<span class="sync-new">▲ 新增 ${diff.new.length}</span> · ` +
            `<span class="sync-mod">✎ 修改 ${diff.modified.length}</span> · ` +
            `<span class="sync-ok">✓ 未变 ${diff.unchanged}</span>`;

        // 新增区
        const newSec = document.getElementById('syncNewSection');
        if (diff.new.length > 0) {
            newSec.innerHTML = `
                <div class="sync-section-header">
                    <span>▲ 新增章节</span>
                    <span class="sync-toggle" data-target="new">全选 / 取消</span>
                </div>
                ${diff.new.map(c => `
                <label class="sync-ch-opt">
                    <input type="checkbox" class="sync-cb sync-cb-new" data-ch="${c.chapter_number}" checked>
                    <span class="sync-ch-num">${c.chapter_number}</span>
                    <span class="sync-ch-title">${this._esc(c.title || '')}</span>
                    <span class="sync-ch-size">${this._formatSize(c.char_count)}</span>
                </label>`).join('')}
            `;
            newSec.style.display = '';
        } else {
            newSec.style.display = 'none';
        }

        // 修改区
        const modSec = document.getElementById('syncModSection');
        if (diff.modified.length > 0) {
            modSec.innerHTML = `
                <div class="sync-section-header">
                    <span>✎ 已修改章节</span>
                    <span class="sync-toggle" data-target="mod">全选 / 取消</span>
                </div>
                ${diff.modified.map(c => `
                <label class="sync-ch-opt">
                    <input type="checkbox" class="sync-cb sync-cb-mod" data-ch="${c.chapter_number}">
                    <span class="sync-ch-num">${c.chapter_number}</span>
                    <span class="sync-ch-title">${this._esc(c.title || '')}</span>
                    <span class="sync-ch-size">${this._formatSize(c.old_char_count)}→${this._formatSize(c.char_count)}</span>
                </label>`).join('')}
            `;
            modSec.style.display = '';
        } else {
            modSec.style.display = 'none';
        }

        // 未变化
        document.getElementById('syncUnchanged').textContent =
            diff.unchanged > 0 ? `✓ ${diff.unchanged} 章未变化（跳过）` : '';

        document.getElementById('syncModal').style.display = '';
    },

    hideSyncModal() {
        document.getElementById('syncModal').style.display = 'none';
    },

    showDetailButtons() {
        document.getElementById('btnEditNovel').style.display = '';
        document.getElementById('btnAppendChapters').style.display = '';
    },

    hideDetailButtons() {
        document.getElementById('btnEditNovel').style.display = 'none';
        document.getElementById('btnAppendChapters').style.display = 'none';
    },

    // ── 翻译 ──

    showTranslationTab() {
        document.getElementById('tabTranslation').style.display = '';
        document.getElementById('btnTranslate').style.display = '';
        // 自动加载译文列表
        if (App.state.currentScriptId) {
            App._loadTranslations();
        }
    },

    hideTranslationTab() {
        document.getElementById('tabTranslation').style.display = 'none';
        document.getElementById('btnTranslate').style.display = 'none';
    },

    showTranslation(yaml, label) {
        document.getElementById('transLabel').textContent = label || '🌐 译文';
        document.getElementById('transOutput').innerHTML = this._highlightYaml(yaml);
    },

    showTranslationPlaceholder() {
        document.getElementById('transLabel').textContent = '🌐 选择一篇译文查看';
        document.getElementById('transOutput').textContent = '点击 🌐 翻译当前剧本';
        document.getElementById('btnDelTrans').style.display = 'none';
    },

    showTranslationLoading(langLabel) {
        document.getElementById('transLabel').textContent = `🌐 ${langLabel}`;
        document.getElementById('transOutput').textContent = `翻译中，请耐心等待...`;
        document.getElementById('btnDelTrans').style.display = 'none';
        const tab = document.getElementById('tabTranslation');
        if (tab) tab.click();
    },

    renderTranslationList(translations, activeId, scriptTitle) {
        const container = document.getElementById('transListItems');
        if (!container) return;
        // 显示剧本名
        const header = document.querySelector('.trans-list-header span');
        if (header && scriptTitle) header.textContent = '📋 ' + scriptTitle;
        if (!translations || translations.length === 0) {
            container.innerHTML = '<div class="trans-empty">暂无译文</div>';
            return;
        }
        container.innerHTML = translations.map(t => {
            const active = t.id === activeId ? ' active' : '';
            return `
            <div class="trans-item${active}" data-trans-id="${t.id}">
                <span class="trans-item-script">${this._esc(scriptTitle || '（未命名）')}</span>
                <span class="trans-item-lang">${this._esc(t.language_label || t.language)}</span>
                <span class="trans-item-date">${(t.created_at || '').slice(0, 10)}</span>
            </div>`;
        }).join('');
    },

    selectTranslationInList(id) {
        document.querySelectorAll('.trans-item').forEach(el => {
            el.classList.toggle('active', parseInt(el.dataset.transId) === id);
        });
    },

    removeTranslationFromList(id) {
        const el = document.querySelector(`.trans-item[data-trans-id="${id}"]`);
        if (el) el.remove();
        // if no more items, show empty
        const items = document.querySelectorAll('.trans-item');
        if (items.length === 0) {
            document.getElementById('transListItems').innerHTML = '<div class="trans-empty">暂无译文</div>';
        }
    },

    showTransDeleteBtn() {
        document.getElementById('btnDelTrans').style.display = '';
    },

    // ── 原文预览 ──

    showOriginal(chapter) {
        const title = chapter.title || `第${chapter.chapter_number}章`;
        document.getElementById('originalTitle').textContent = `📖 ${title}  ·  ${(chapter.char_count || 0)} 字`;
        document.getElementById('originalContent').textContent = chapter.content || '';
        document.getElementById('originalViewer').style.display = '';
        // 隐藏 YAML 编辑区
        document.getElementById('yamlOutput').style.display = 'none';
        document.getElementById('yamlEditor').style.display = 'none';
        document.getElementById('previewPlaceholder').style.display = 'none';
        document.getElementById('btnEditYaml').style.display = 'none';
    },

    hideOriginal() {
        document.getElementById('originalViewer').style.display = 'none';
    },

    // ── 辅助 ──

    scrollToYaml() {
        const el = document.getElementById('yamlOutput');
        if (el) {
            // 确保所在 tab 可见
            const yamlTab = document.querySelector('.preview-tab[data-tab="yaml"]');
            if (yamlTab && !yamlTab.classList.contains('active')) yamlTab.click();
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    },

    flashYaml() {
        const el = document.getElementById('yamlOutput');
        if (!el) return;
        el.style.transition = 'none';
        el.style.boxShadow = '0 0 0 3px rgba(91,122,110,0.3)';
        void el.offsetWidth;
        el.style.transition = 'box-shadow 1.5s ease-out';
        el.style.boxShadow = '0 0 0 0px rgba(91,122,110,0)';
    },

    setStatus(status, text) {
        const el = document.getElementById('statusEl');
        el.textContent = text;
        el.className = 'status ' + status;
    },

    updateBatchBar(selected, allChapters) {
        const bar = document.getElementById('batchBar');
        const btn = document.getElementById('btnBatchConvert');
        if (!bar || !btn) return;
        const count = selected.size;
        if (count > 0) {
            bar.style.display = '';
            btn.textContent = '🎬 批量转换 (' + count + ')';
        } else {
            bar.style.display = 'none';
        }
    },

    refreshCheckboxes(selected) {
        document.querySelectorAll('.ch-checkbox').forEach(cb => {
            const num = parseFloat(cb.dataset.ch);
            cb.checked = selected.has(num);
            const item = cb.closest('.chapter-item');
            if (item) item.classList.toggle('checked', selected.has(num));
        });
    },

    // ── 内部工具 ──

    _esc(s) {
        if (!s) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    },

    _formatSize(chars) {
        if (!chars) return '';
        if (chars >= 10000) return (chars / 10000).toFixed(1) + '万字';
        if (chars >= 1000) return (chars / 1000).toFixed(1) + '千字';
        return chars + '字';
    },
};

// ══════════════════════════════════════════════════════════════
// Resizer — 面板拖拽调节宽度
// ══════════════════════════════════════════════════════════════

const Resizer = {
    init() {
        this._setup('resizeLeft', '--sidebar-w', 200, 420);
        this._setup('resizeRight', '--detail-w', 220, 480);
    },

    _setup(handleId, cssVar, minW, maxW) {
        const handle = document.getElementById(handleId);
        if (!handle) return;
        const layout = document.querySelector('.main-layout');
        if (!layout) return;

        let dragging = false;

        handle.addEventListener('mousedown', (e) => {
            dragging = true;
            handle.classList.add('active');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!dragging) return;
            const rect = layout.getBoundingClientRect();
            let newW;
            if (handleId === 'resizeLeft') {
                newW = e.clientX - rect.left;
            } else {
                newW = rect.right - e.clientX;
            }
            newW = Math.max(minW, Math.min(maxW, newW));
            layout.style.setProperty(cssVar, newW + 'px');
        });

        document.addEventListener('mouseup', () => {
            if (dragging) {
                dragging = false;
                handle.classList.remove('active');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        });
    },
};


// ══════════════════════════════════════════════════════════════
// 组件注册 — 当 App.state 变化时自动重新渲染
// ══════════════════════════════════════════════════════════════

Component.register({
    id: 'library',
    mount: 'libraryList',
    render(s) {
        // _loadLibrary 回调中通过 App.render() 触发
    },
    shouldRender(s) {
        // 随仓库数据变化
        return true;
    },
});

Component.register({
    id: 'chapterPanel',
    mount: 'chapterList',
    render(s) {
        if (s.currentNovelId && s.chapters.length > 0) {
            View.renderChapterList(s.chapters, s.generatedChapters,
                s.availableScripts, s.currentScriptId);
        }
    },
    shouldRender(s) {
        return s.currentNovelId != null && s.chapters.length > 0;
    },
});

Component.register({
    id: 'mergedSection',
    mount: 'mergedList',
    render(s) {
        View.renderMergedScripts(s.mergedScripts, s.chapters, s.generatedChapters);
    },
    shouldRender(s) {
        return document.getElementById('mergedList') != null;
    },
});

Component.register({
    id: 'detailMeta',
    mount: 'detailPanel',
    render(s) {
        if (s.currentNovelId) {
            document.getElementById('btnEditNovel').style.display = '';
            document.getElementById('btnAppendChapters').style.display = '';
        }
    },
    shouldRender(s) { return s.currentNovelId != null; },
});

// 显示已转章节的 YAML 面板
Component.register({
    id: 'yamlPreview',
    mount: 'previewYaml',
    render(s) {
        if (s.currentYaml) {
            View.showYaml(s.currentYaml);
            document.getElementById('btnDownload').style.display = '';
            document.getElementById('btnEditYaml').style.display = '';
            View.showTranslationTab();
        }
    },
    shouldRender(s) { return s.currentYaml && s.currentYaml.length > 0; },
});
