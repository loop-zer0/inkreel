/** InkReel 主应用 */

const App = {
    state: Store.create({
        currentNovelId: null,
        currentScriptId: null,
        availableScripts: [],
        chapters: [],
        generatedChapters: [],
        convertingChapters: new Set(),
        currentYaml: '',
        previewFilename: '',
        previewTotalChars: 0,
        previewGenre: '',
        selectedChapters: new Set(),
        mergedScripts: [],
        currentTranslation: '',
        currentTransLabel: '🌐 译文',
        currentTransId: null,
        translations: [],
    }),

    // 统一渲染入口：读取 App.state，刷新所有已注册组件
    render() {
        Component.renderAll(App.state);
    },

    async init() {
        // token 校验
        const authed = await Auth.initApp();
        if (!authed) return;

        Resizer.init();
        this._bindEvents();
        this._debouncedRefreshLibrary = Util.debounce(() => this._loadLibrary(), 3000);
        await this._loadLibrary();
    },

    // ── 事件绑定 ──
    _bindEvents() {
        // 退出登录
        document.getElementById('btnLogout').addEventListener('click', () => Auth.logout());
        // 仓库刷新
        document.getElementById('btnRefresh').addEventListener('click', () => this._loadLibrary());

        // 导入按钮 → 触发文件选择
        document.getElementById('btnImport').addEventListener('click', () => {
            document.getElementById('fileInput').click();
        });

        // 文件选择
        document.getElementById('fileInput').addEventListener('change', (e) => {
            if (e.target.files.length) this._handleFile(e.target.files[0]);
        });

        // 导入模态框
        document.getElementById('btnConfirmImport').addEventListener('click', () => this._confirmImport());
        document.getElementById('btnCancelImport').addEventListener('click', () => View.hideImportModal());

        // Preview 标签
        document.querySelectorAll('.preview-tab').forEach(tab => {
            tab.addEventListener('click', () => this._switchPreviewTab(tab));
        });

        // 下载
        document.getElementById('btnDownload').addEventListener('click', () => this._download());

        // YAML 编辑/保存
        document.getElementById('btnEditYaml').addEventListener('click', () => {
            const btn = document.getElementById('btnEditYaml');
            if (btn.dataset.mode === 'edit') {
                View.saveEdit();
            } else {
                View.startEdit();
            }
        });

        // 元信息编辑
        document.getElementById('btnEditMeta').addEventListener('click', () => View.startMetaEdit());
        document.getElementById('btnSaveMeta').addEventListener('click', () => View.saveMetaEdit());
        document.getElementById('btnCancelMeta').addEventListener('click', () => View._cancelMetaEdit());

        // 关闭详情
        document.getElementById('btnCloseDetail').addEventListener('click', () => View.hideNovelDetail());

        // 翻译按钮
        document.getElementById('btnTranslate').addEventListener('click', () => this._startTranslate());
        document.getElementById('btnRefreshTrans').addEventListener('click', () => this._loadTranslations());
        document.getElementById('btnDelTrans').addEventListener('click', () => this._deleteCurrentTranslation());
        document.getElementById('transListItems').addEventListener('click', (e) => {
            const item = e.target.closest('.trans-item');
            if (item) this._viewTranslation(parseInt(item.dataset.transId));
        });

        // 小说编辑
        document.getElementById('btnEditNovel').addEventListener('click', () => this._openNovelEditor());
        document.getElementById('btnAppendChapters').addEventListener('click', () => {
            document.getElementById('appendFileInput').click();
        });
        document.getElementById('appendFileInput').addEventListener('change', (e) => {
            if (e.target.files.length) this._handleSyncFile(e.target.files[0]);
        });
        document.getElementById('btnSaveChapter').addEventListener('click', () => this._saveChapter());
        document.getElementById('btnCloseEditor').addEventListener('click', () => View.hideNovelEditor());
        document.getElementById('novelEditorToc').addEventListener('click', (e) => {
            const item = e.target.closest('.editor-toc-item');
            if (item) this._loadChapterForEdit(parseFloat(item.dataset.chNum));
        });

        // 同步模态框
        document.getElementById('btnSyncApply').addEventListener('click', () => this._applySync());
        document.getElementById('btnSyncClose').addEventListener('click', () => View.hideSyncModal());
        document.getElementById('syncModal').addEventListener('click', (e) => {
            const toggle = e.target.closest('.sync-toggle');
            if (toggle) {
                const target = toggle.dataset.target;
                const cbs = document.querySelectorAll(`.sync-cb-${target}`);
                const allChecked = [...cbs].every(cb => cb.checked);
                cbs.forEach(cb => cb.checked = !allChecked);
            }
        });

        // 仓库列表点击（委托）
        document.getElementById('libraryList').addEventListener('click', (e) => {
            const card = e.target.closest('.library-card');
            if (!card) return;
            const nid = parseInt(card.dataset.novelId);

            if (e.target.closest('.lib-btn-del')) {
                this._deleteNovel(nid);
            } else if (e.target.closest('.lib-btn-open')) {
                this._openNovel(nid);
            } else {
                this._openNovel(nid);
            }
        });

        // 剧本选择器（委托）
        document.getElementById('chapterList').addEventListener('change', (e) => {
            if (e.target.id === 'scriptSelect') {
                const script = this.state.availableScripts.find(s => s.id === parseInt(e.target.value));
                if (script) this._selectScript(script);
            }
        });
        document.getElementById('chapterList').addEventListener('click', (e) => {
            if (e.target.id === 'btnNewScript') {
                this._createNewScript();
            }
            if (e.target.id === 'btnRenameScript') {
                this._startRenameScript();
            }
            if (e.target.id === 'btnDeleteScript') {
                this._deleteScript();
            }
        });

        // 章节操作（委托）
        document.getElementById('chapterList').addEventListener('click', (e) => {
            const menuBtn = e.target.closest('.ch-menu-trigger');
            const checkBox = e.target.closest('.ch-checkbox');
            if (menuBtn) {
                e.stopPropagation();
                View.showChapterMenu(menuBtn, parseFloat(menuBtn.dataset.ch));
                return;
            }
            if (checkBox) this._toggleChapterSelect(parseFloat(checkBox.dataset.ch), checkBox.checked);
        });

        // 章节弹出菜单点击（全局委托，因为菜单 append 在 body 上）
        document.addEventListener('click', (e) => {
            const menuItem = e.target.closest('.ch-menu-item');
            if (!menuItem) return;
            const k = menuItem.dataset.k;
            const chNum = parseFloat(menuItem.dataset.ch);
            View._closeChapterMenu();
            if (k === 'convert') this._convertChapter(chNum, menuItem);
            if (k === 'reuse') this._reuseChapter(chNum, menuItem);
            if (k === 'view') this._viewChapter(chNum);
            if (k === 'orig') this._viewOriginal(chNum);
            if (k === 'delete') this._deleteChapter(chNum);
        });

        // 关闭原文查看
        document.getElementById('btnCloseOriginal').addEventListener('click', () => this._closeOriginal());

        // 全选 / 批量转换（委托，在 chapterSelect 容器上）
        document.getElementById('chapterSelect').addEventListener('click', (e) => {
            const selectAll = e.target.closest('#btnSelectAll');
            const batchConvert = e.target.closest('#btnBatchConvert');
            if (selectAll) this._toggleSelectAll();
            if (batchConvert) this._batchConvert();
        });

        // 锁定按钮 + 查看按钮（委托）
        document.getElementById('detailPanel').addEventListener('click', (e) => {
            const lockBtn = e.target.closest('#btnLock');
            const viewBtn = e.target.closest('#btnLockView');
            if (lockBtn) this._lockScript();
            if (viewBtn) {
                const yamlTab = document.querySelector('.preview-tab[data-tab="yaml"]');
                if (yamlTab) yamlTab.click();
                if (!this.state.currentYaml) {
                    this._loadCurrentScriptYaml();
                }
                View.scrollToYaml();
                View.flashYaml();
            }
        });

        // 合并剧本区块（委托）— 安全绑定
        const mergeSection = document.getElementById('mergedScriptsSection');
        if (mergeSection) {
            mergeSection.addEventListener('click', (e) => {
                const createBtn = e.target.closest('#btnCreateMerge');
                const confirmBtn = e.target.closest('#btnConfirmMerge');
                const cancelBtn = e.target.closest('#btnCancelMerge');
                const viewBtn = e.target.closest('.merged-btn-view');
                const renameBtn = e.target.closest('.merged-btn-rename');
                const delBtn = e.target.closest('.merged-btn-del');

                if (createBtn) this._showMergeCreateForm();
                if (confirmBtn) this._confirmCreateMerge();
                if (cancelBtn) this._cancelCreateMerge();
                if (viewBtn) this._viewMerge(parseInt(viewBtn.dataset.mergeId));
                if (renameBtn) this._startRenameMerge(parseInt(renameBtn.dataset.mergeId));
                if (delBtn) this._deleteMerge(parseInt(delBtn.dataset.mergeId));
            });
        }

        // 拖拽上传
        const dropZone = document.getElementById('dropZone');
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length) this._handleFile(e.dataTransfer.files[0]);
        });
        dropZone.addEventListener('click', () => document.getElementById('fileInput').click());

        // 全局键盘快捷键
        document.addEventListener('keydown', (e) => {
            // Esc — 关闭所有模态框
            if (e.key === 'Escape') {
                const modals = [
                    { id: 'importModal', hide: View.hideImportModal },
                    { id: 'novelEditorModal', hide: View.hideNovelEditor },
                    { id: 'syncModal', hide: View.hideSyncModal },
                ];
                for (const m of modals) {
                    if (document.getElementById(m.id).style.display !== 'none') {
                        m.hide.call(View);
                        return;
                    }
                }
                // 关闭原文查看
                if (document.getElementById('originalViewer').style.display !== 'none') {
                    this._closeOriginal();
                }
            }
            // Ctrl+Enter — 确认导入
            if (e.ctrlKey && e.key === 'Enter') {
                if (document.getElementById('importModal').style.display !== 'none') {
                    e.preventDefault();
                    this._confirmImport();
                }
            }
            // Ctrl+S — 保存章节编辑
            if (e.ctrlKey && e.key === 's') {
                if (document.getElementById('novelEditorModal').style.display !== 'none') {
                    e.preventDefault();
                    this._saveChapter();
                }
            }
        });
    },

    // ── Preview 标签 ──
    _switchPreviewTab(tab) {
        document.querySelectorAll('.preview-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const target = tab.dataset.tab;
        document.getElementById('previewYaml').style.display = target === 'yaml' ? '' : 'none';
        document.getElementById('previewTranslation').style.display = target === 'translation' ? '' : 'none';
    },

    // ── 导入流程 ──
    async _handleFile(file) {
        if (!file.name.match(/\.(txt|text|md|markdown|docx|epub)$/i)) {
            Util.showToast('请上传 .txt / .md / .docx / .epub 文件', 'error');
            return;
        }
        const formData = new FormData();
        formData.append('file', file);

        try {
            const data = await API.preview(formData);
            if (data.status !== 'ok') {
                Util.showToast(data.message || '预览失败', 'error');
                return;
            }
            this.state.previewFilename = data.filename;
            this.state.previewTotalChars = data.total_chars;
            this.state.previewGenre = data.genre;
            View.showImportModal(data.chapters, data.genre);
        } catch (e) {
            Util.showToast('预览请求失败: ' + e.message, 'error');
        }
    },

    async _confirmImport() {
        const title = document.getElementById('importTitle').value.trim();
        try {
            const data = await API.importNovel(title, '');
            if (data.status === 'ok') {
                View.hideImportModal();
                Util.showToast('导入成功 ✅', 'success');
                await this._loadLibrary();
                // 自动打开
                setTimeout(() => this._openNovel(data.novel_id), 300);
            } else {
                Util.showToast(data.message || '导入失败', 'error');
            }
        } catch (e) {
            Util.showToast('导入失败: ' + e.message, 'error');
        }
    },

    // ── 仓库 ──
    async _loadLibrary() {
        try {
            const data = await API.listNovels();
            if (data.status === 'ok') {
                View.renderLibrary(data.novels);
            } else {
                View.renderLibrary([]);
            }
        } catch (_) {
            View.renderLibrary([]);
        }
        this.render();
    },

    async _reloadNovelDetail() {
        if (!this.state.currentNovelId) return;
        try {
            const data = await API.getNovel(this.state.currentNovelId);
            if (data.status !== 'ok') return;
            const novel = data.novel;
            this.state.availableScripts = novel.scripts || [];
            // 优先保留当前选中（如果还在），其次选草稿，最后选已完成
            const current = this.state.availableScripts.find(s => s.id === this.state.currentScriptId);
            const draft = this.state.availableScripts.find(s => s.status === 'draft');
            const best = current || draft || this.state.availableScripts[0];
            if (best) this._selectScript(best);
            View.showNovelHeader(novel);
        } catch (_) {}
    },

    async _openNovel(novelId) {
        try {
            const data = await API.getNovel(novelId);
            if (data.status !== 'ok') {
                Util.showToast('加载小说失败', 'error');
                return;
            }
            const novel = data.novel;
            this.state.currentNovelId = novelId;
            this.state.chapters = novel.chapters.map(c => ({
                num: c.chapter_number, title: c.title, chars: c.char_count, id: c.id,
            }));
            this.state.availableScripts = novel.scripts || [];

            // 优先选草稿（继续工作），没有草稿才选已完成剧本
            if (this.state.availableScripts.length > 0) {
                const draft = this.state.availableScripts.find(s => s.status === 'draft');
                const best = draft || this.state.availableScripts[0];
                this._selectScript(best);
            } else {
                this.state.currentScriptId = null;
                this.state.generatedChapters = [];
                this.state.currentYaml = '';
                View.showPlaceholder();
                document.getElementById('btnDownload').style.display = 'none';
                View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                                       this.state.availableScripts, this.state.currentScriptId);
                this._loadMergedScripts();
            }

            View.showNovelHeader(novel);
            View.showDetailButtons();
        } catch (e) {
            Util.showToast('加载失败: ' + e.message, 'error');
        }
    },

    _selectScript(script) {
        this.state.currentScriptId = script.id;
        this.state.generatedChapters = (script.chapters || []).map(c => c.chapter_number);
        // 有 yaml_content 就直接展示（不论 complete 还是 draft）
        if (script.yaml_content) {
            this.state.currentYaml = script.yaml_content;
            View.showYaml(script.yaml_content);
            document.getElementById('btnDownload').style.display = '';
            View.showTranslationTab();
        } else if (this.state.generatedChapters.length > 0) {
            // draft 剧本可能列表接口没带 yaml_content，主动拉取
            this._loadCurrentScriptYaml();
        } else {
            View.showPlaceholder();
            document.getElementById('btnDownload').style.display = 'none';
        }
        View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                               this.state.availableScripts, this.state.currentScriptId);
        this._loadMergedScripts();
        this._loadTranslations();
    },

    async _deleteNovel(novelId) {
        if (!confirm('确定删除此小说及其所有关联数据？')) return;
        await API.deleteNovel(novelId);
        if (this.state.currentNovelId === novelId) View.hideNovelDetail();
        Util.showToast('已删除', 'info');
        await this._loadLibrary();
    },

    async _deleteChapter(chNum) {
        const ch = this.state.chapters.find(c => c.num === chNum);
        if (!ch || !ch.id) { Util.showToast('无法找到章节', 'error'); return; }
        const label = ch.title || '第' + chNum + '章';
        if (!confirm('确定删除 「' + label + '」？\n\n此操作不可撤销，关联的剧本转换数据将一同删除。')) return;
        try {
            const data = await API.deleteChapter(this.state.currentNovelId, ch.id);
            if (data.status === 'ok') {
                Util.showToast('已删除：' + label, 'info');
                // 刷新小说详情
                await this._openNovel(this.state.currentNovelId);
                await this._loadLibrary();
            } else {
                Util.showToast(data.message || '删除失败', 'error');
            }
        } catch (e) {
            Util.showToast('删除失败: ' + e.message, 'error');
        }
    },

    // ── 章节勾选 ──
    _toggleChapterSelect(chNum, checked) {
        if (checked) {
            this.state.selectedChapters.add(chNum);
        } else {
            this.state.selectedChapters.delete(chNum);
        }
        View.updateBatchBar(this.state.selectedChapters, this.state.chapters);
    },

    _toggleSelectAll() {
        const allNums = this.state.chapters.map(c => c.num);
        const allSelected = allNums.every(n => this.state.selectedChapters.has(n));
        if (allSelected) {
            this.state.selectedChapters.clear();
        } else {
            allNums.forEach(n => this.state.selectedChapters.add(n));
        }
        // 重新渲染勾选状态
        View.refreshCheckboxes(this.state.selectedChapters);
        View.updateBatchBar(this.state.selectedChapters, this.state.chapters);
    },

    async _batchConvert() {
        if (!this.state.currentNovelId || this.state.selectedChapters.size === 0) return;
        const chapters = [...this.state.selectedChapters].sort((a, b) => a - b);
        const total = chapters.length;
        const btn = document.getElementById('btnBatchConvert');
        if (btn) { btn.disabled = true; btn.textContent = '⏳ 0/' + total; }
        View.setStatus('active', '⏳ 0/' + total + ' 章');
        Util.showToast('并行转换启动 — ' + total + ' 章同时处理中', 'info');

        // 标记所有选中章节为"转换中"
        this.state.convertingChapters = new Set(chapters);
        this.state.selectedChapters.clear();

        // 章节号 → 标题映射
        const labelMap = {};
        for (const c of this.state.chapters) labelMap[c.num] = c.title || '第' + c.num + '章';

        let scriptId = this.state.currentScriptId;
        let mergedYaml = null;
        let completed = 0;
        let failed = 0;
        const failedList = [];

        try {
            const resp = await API.convertBatchStream(this.state.currentNovelId, chapters);
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ message: '请求失败' }));
                throw new Error(err.message || 'HTTP ' + resp.status);
            }

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const jsonStr = line.slice(6);
                    if (!jsonStr.trim()) continue;

                    try {
                        const evt = JSON.parse(jsonStr);
                        switch (evt.type) {
                            case 'chapter': {
                                const cn = evt.chapter_number;
                                const label = labelMap[cn] || '第' + cn + '章';
                                this.state.convertingChapters.delete(cn);
                                completed++;

                                if (evt.status === 'ok') {
                                    if (evt.script_id && evt.script_id !== scriptId) {
                                        scriptId = evt.script_id;
                                    }
                                    if (!this.state.generatedChapters.includes(cn)) {
                                        this.state.generatedChapters.push(cn);
                                    }
                                    View.setStatus('active',
                                        '⏳ ' + evt.progress + '  ·  ' + label + ' ✓');
                                    if (btn) btn.textContent = '⏳ ' + evt.progress;
                                    if (completed === total) {
                                        Util.showToast('✅ ' + label + ' — 全部完成！', 'success');
                                    } else {
                                        Util.showToast('✅ ' + label + ' (' + evt.scenes_count + '场景)', 'success');
                                    }
                                    if (evt.yaml) {
                                        this.state.currentYaml = evt.yaml;
                                        View.showYaml(evt.yaml);
                                        document.getElementById('btnDownload').style.display = '';
                                    }
                                } else {
                                    failed++;
                                    failedList.push(label + '：' + (evt.message || '未知错误'));
                                    console.error('[BatchStream] ' + label + '失败:', evt);
                                    View.setStatus('active',
                                        '⏳ ' + evt.progress + '  ·  ' + label + ' ✗');
                                    if (btn) btn.textContent = '⏳ ' + evt.progress;
                                    Util.showToast('✗ ' + label + '失败：' + (evt.message || '未知'), 'error');
                                }
                                // 实时刷新章节列表高亮
                                View.renderChapterList(this.state.chapters,
                                    this.state.generatedChapters,
                                    this.state.availableScripts, scriptId);
                                break;
                            }
                            case 'merge': {
                                if (evt.merged && evt.yaml) {
                                    mergedYaml = evt.yaml;
                                    this.state.currentYaml = evt.yaml;
                                    View.showYaml(evt.yaml);
                                    document.getElementById('btnDownload').style.display = '';
                                    View.scrollToYaml();
                                }
                                break;
                            }
                            case 'done': {
                                scriptId = evt.script_id || scriptId;
                                this.state.convertingChapters.clear();
                                // 更新 availableScripts
                                if (!this.state.availableScripts.find(s => s.id === scriptId)) {
                                    this.state.availableScripts.push({
                                        id: scriptId, status: 'draft',
                                        chapters: this.state.generatedChapters.map(cn => ({ chapter_number: cn })),
                                        yaml_content: mergedYaml || '',
                                        created_at: new Date().toISOString(),
                                    });
                                } else {
                                    const s = this.state.availableScripts.find(sc => sc.id === scriptId);
                                    if (s) {
                                        s.chapters = this.state.generatedChapters.map(cn => ({ chapter_number: cn }));
                                        if (mergedYaml) s.yaml_content = mergedYaml;
                                    }
                                }
                                this.state.currentScriptId = scriptId;
                                const ok = evt.success, er = evt.failed;
                                const summary = '✅ 转换完成 ' + ok + '/' + evt.total + ' 章' + (er > 0 ? '（' + er + '章失败）' : '');
                                View.setStatus(ok === evt.total ? 'success' : 'error', summary);
                                if (failedList.length > 0) {
                                    Util.showToast('失败章节: ' + failedList.join(', '), 'error');
                                }
                                View.renderChapterList(this.state.chapters,
                                    this.state.generatedChapters,
                                    this.state.availableScripts, scriptId);
                                View.showTranslationTab();
                                break;
                            }
                        }
                    } catch (parseErr) { /* 跳过 */ }
                }
            }
        } catch (e) {
            this.state.convertingChapters.clear();
            Util.showToast('转换请求失败: ' + e.message, 'error');
            View.setStatus('error', '❌ 网络错误');
        }
        if (btn) { btn.disabled = false; btn.textContent = '🎬 批量转换'; }
    },

    // ── 逐章转换 ──
    async _convertChapter(chNum, btnEl) {
        if (!this.state.currentNovelId) return;
        if (btnEl && btnEl.disabled !== undefined) { btnEl.disabled = true; btnEl.textContent = '⏳...'; }
        View.setStatus('active', `⏳ 转换第${chNum}章...`);
        Util.showToast('AI 处理中，预计 1-2 分钟，请耐心等待...', 'info');

        try {
            const data = await API.convertChapter(this.state.currentNovelId, chNum);
            if (data.status === 'ok') {
                if (data.reused) {
                    Util.showToast(`第${chNum}章已复用 (${data.scenes_count}个场景)`, 'info');
                } else {
                    Util.showToast(`第${chNum}章转换完成 (${data.scenes_count}个场景)`, 'success');
                }
                View.setStatus('success', `✅ 第${chNum}章完成`);

                // 如果后端创建了新草稿（旧剧本已完成），切换到新剧本
                const prevScriptId = this.state.currentScriptId;
                if (data.script_id !== prevScriptId) {
                    // 新草稿：重置章节列表，更新 availableScripts
                    this.state.generatedChapters = [chNum];
                    this.state.currentScriptId = data.script_id;
                    this.state.availableScripts.push({
                        id: data.script_id,
                        status: 'draft',
                        chapters: [{ chapter_number: chNum }],
                        yaml_content: '',
                        created_at: new Date().toISOString(),
                    });
                    Util.showToast('已自动创建新改编草稿', 'info');
                } else {
                    // 同一剧本：追加章节
                    if (!this.state.generatedChapters.includes(chNum)) {
                        this.state.generatedChapters.push(chNum);
                    }
                    this.state.currentScriptId = data.script_id;
                }

                // 确保 availableScripts 包含当前剧本
                if (!this.state.availableScripts.find(s => s.id === data.script_id)) {
                    this.state.availableScripts.push({
                        id: data.script_id,
                        status: 'draft',
                        chapters: this.state.generatedChapters.map(cn => ({ chapter_number: cn })),
                        yaml_content: '',
                        created_at: new Date().toISOString(),
                    });
                }

                // 优先显示完整合并 YAML，否则显示单章
                if (data.merged_yaml) {
                    this.state.currentYaml = data.merged_yaml;
                    View.showYaml(data.merged_yaml);
                } else {
                    View.showYaml(data.yaml);
                }
                document.getElementById('btnDownload').style.display = '';
                View.scrollToYaml();

                // 刷新章节列表
                View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                                       this.state.availableScripts, this.state.currentScriptId);
            } else {
                Util.showToast(data.message || '转换失败', 'error');
                View.setStatus('error', '❌ 转换失败');
            }
        } catch (e) {
            Util.showToast('请求失败: ' + e.message, 'error');
            View.setStatus('error', '❌ 网络错误');
        }
        if (btnEl && btnEl.disabled !== undefined) { btnEl.disabled = false; btnEl.textContent = '🔄 重转'; }
    },

    // ── 复用已在其他改编中完成的章节（秒完成，不走 LLM）──
    async _reuseChapter(chNum, btnEl) {
        if (!this.state.currentNovelId) return;
        if (btnEl && btnEl.disabled !== undefined) { btnEl.disabled = true; btnEl.textContent = '📋 ...'; }
        View.setStatus('active', `📋 复用第${chNum}章...`);

        try {
            const data = await API.convertChapter(this.state.currentNovelId, chNum);
            if (data.status === 'ok') {
                View.setStatus('success', `✅ 第${chNum}章已复用`);
                Util.showToast(`第${chNum}章已复用 (${data.scenes_count}个场景)`, 'success');

                if (data.script_id !== this.state.currentScriptId) {
                    this.state.generatedChapters = [chNum];
                    this.state.currentScriptId = data.script_id;
                    if (!this.state.availableScripts.find(s => s.id === data.script_id)) {
                        this.state.availableScripts.push({
                            id: data.script_id, status: 'draft',
                            chapters: [{ chapter_number: chNum }],
                            yaml_content: '', created_at: new Date().toISOString(),
                        });
                    }
                } else {
                    if (!this.state.generatedChapters.includes(chNum)) {
                        this.state.generatedChapters.push(chNum);
                    }
                }

                if (data.merged_yaml) {
                    this.state.currentYaml = data.merged_yaml;
                    View.showYaml(data.merged_yaml);
                } else {
                    View.showYaml(data.yaml);
                }
                document.getElementById('btnDownload').style.display = '';
                View.scrollToYaml();
                View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                                       this.state.availableScripts, this.state.currentScriptId);
            } else {
                Util.showToast(data.message || '复用失败', 'error');
                View.setStatus('error', '❌ 复用失败');
            }
        } catch (e) {
            Util.showToast('请求失败: ' + e.message, 'error');
            View.setStatus('error', '❌ 网络错误');
        }
        if (btnEl && btnEl.disabled !== undefined) { btnEl.disabled = false; btnEl.textContent = '📋 复用'; }
    },

    async _viewChapter(chNum) {
        try {
            const data = await API.getChapterYaml(this.state.currentNovelId, chNum);
            if (data.status === 'ok' && data.yaml) {
                this.state.currentYaml = data.yaml;
                View.showYaml(data.yaml);
                Util.showToast(`第${chNum}章 YAML`, 'info');
            } else {
                Util.showToast(`第${chNum}章暂无数据`, 'error');
            }
        } catch (e) {
            Util.showToast('获取失败', 'error');
        }
    },

    async _viewOriginal(chNum) {
        try {
            const data = await API.getChapterContent(this.state.currentNovelId, chNum);
            if (data.status === 'ok' && data.chapter) {
                View.showOriginal(data.chapter);
            }
        } catch (e) {
            Util.showToast('获取原文失败', 'error');
        }
    },

    _closeOriginal() {
        View.hideOriginal();
    },

    async _createNewScript() {
        if (!this.state.currentNovelId) return;
        try {
            const data = await API.newScript(this.state.currentNovelId, '（新改编）');
            if (data.status === 'ok') {
                // 重新加载
                const novel = await API.getNovel(this.state.currentNovelId);
                if (novel.status === 'ok') {
                    this.state.availableScripts = novel.novel.scripts || [];
                    const newest = this.state.availableScripts[this.state.availableScripts.length - 1];
                    if (newest) this._selectScript(newest);
                }
                Util.showToast(data.message || '已完成', 'success');
            }
        } catch (e) {
            Util.showToast('创建失败', 'error');
        }
    },

    // ── 删除当前剧本 ──
    async _deleteScript() {
        if (!this.state.currentScriptId) return;
        const script = this.state.availableScripts.find(s => s.id === this.state.currentScriptId);
        const title = script ? (script.title || '（未命名）') : '当前剧本';
        if (!confirm(`确定删除「${title}」及其所有章节数据？此操作不可撤销。`)) return;

        try {
            const data = await API.deleteScript(this.state.currentScriptId);
            if (data.status !== 'ok') {
                Util.showToast(data.message || '删除失败', 'error');
                return;
            }
            Util.showToast('剧本已删除 ✅', 'success');

            // 重新加载小说，获取最新的剧本列表
            const novel = await API.getNovel(this.state.currentNovelId);
            if (novel.status === 'ok') {
                this.state.availableScripts = novel.novel.scripts || [];

                // 切换到剩余剧本
                if (this.state.availableScripts.length > 0) {
                    const draft = this.state.availableScripts.find(s => s.status === 'draft');
                    const best = draft || this.state.availableScripts[0];
                    this._selectScript(best);
                } else {
                    // 没有剩余剧本了，重置状态
                    this.state.currentScriptId = null;
                    this.state.generatedChapters = [];
                    this.state.currentYaml = '';
                    View.showPlaceholder();
                    document.getElementById('btnDownload').style.display = 'none';
                    View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                                           this.state.availableScripts, this.state.currentScriptId);
                }
            }

            await this._loadLibrary();
        } catch (e) {
            Util.showToast('删除失败: ' + e.message, 'error');
        }
    },

    // ── 合并剧本 ──

    async _loadMergedScripts() {
        if (!this.state.currentScriptId) {
            this.state.mergedScripts = [];
            View.renderMergedScripts([], this.state.chapters, this.state.generatedChapters);
            return;
        }
        try {
            const data = await API.listMerges(this.state.currentScriptId);
            if (data.status === 'ok') {
                this.state.mergedScripts = data.merges || [];
                View.renderMergedScripts(this.state.mergedScripts, this.state.chapters, this.state.generatedChapters);
            }
        } catch (_) {
            View.renderMergedScripts([], this.state.chapters, this.state.generatedChapters);
        }
    },

    _showMergeCreateForm() {
        View.showMergeCreateForm();
        View._renderMergeChapterPicker(this.state.chapters, this.state.generatedChapters);
    },

    _cancelCreateMerge() {
        View.hideMergeCreateForm();
    },

    async _confirmCreateMerge() {
        const name = document.getElementById('mergeName').value.trim();
        const note = document.getElementById('mergeNote').value.trim();

        const checkboxes = document.querySelectorAll('.merge-ch-cb:checked');
        const chapterNumbers = [...checkboxes].map(cb => parseFloat(cb.dataset.ch)).sort((a, b) => a - b);

        if (chapterNumbers.length === 0) {
            Util.showToast('请至少选择一个章节', 'error');
            return;
        }

        const genSet = new Set(this.state.generatedChapters);
        const unconverted = chapterNumbers.filter(cn => !genSet.has(cn));
        if (unconverted.length > 0) {
            Util.showToast(`警告：${unconverted.length} 个章节未转换（${unconverted.join(', ')}），将被跳过`, 'info');
        }

        const btn = document.getElementById('btnConfirmMerge');
        if (btn) { btn.disabled = true; btn.textContent = '⏳ 合并中...'; }
        View.setStatus('active', '⏳ 合并剧本...');

        try {
            const data = await API.createMerge(this.state.currentScriptId, {
                title: name || '（未命名）',
                note: note,
                chapter_numbers: chapterNumbers,
            });

            if (data.status === 'ok') {
                View.hideMergeCreateForm();
                Util.showToast(data.message || '合并完成 ✅', 'success');

                if (data.yaml) {
                    this.state.currentYaml = data.yaml;
                    View.showYaml(data.yaml);
                    document.getElementById('btnDownload').style.display = '';
                    View.scrollToYaml();
                }

                // 从后端刷新章节状态（可能有新完成的转换）
                await this._reloadNovelDetail();
                await this._loadMergedScripts();
                View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                                       this.state.availableScripts, this.state.currentScriptId);
            } else {
                Util.showToast(data.message || '合并失败', 'error');
                View.setStatus('error', '❌ 合并失败');
            }
        } catch (e) {
            Util.showToast('请求失败: ' + e.message, 'error');
            View.setStatus('error', '❌ 网络错误');
        }
        if (btn) { btn.disabled = false; btn.textContent = '确认合并'; }
    },

    async _viewMerge(mergeId) {
        try {
            const data = await API.getMerge(mergeId);
            if (data.status === 'ok' && data.merge) {
                const ms = data.merge;
                const yaml = ms.yaml_content || '';
                if (yaml) {
                    this.state.currentYaml = yaml;
                    View.showYaml(yaml);
                    document.getElementById('btnDownload').style.display = '';
                    View.scrollToYaml();
                    const title = ms.title || '（未命名）';
                    Util.showToast(`查看合并剧本：${title}`, 'info');
                } else {
                    Util.showToast('该合并剧本暂无内容', 'error');
                }
            }
        } catch (e) {
            Util.showToast('加载失败: ' + e.message, 'error');
        }
    },

    async _startRenameMerge(mergeId) {
        const ms = this.state.mergedScripts.find(m => m.id === mergeId);
        if (!ms) return;
        const curName = ms.title && ms.title !== '（未命名）' ? ms.title : '';
        const newName = prompt('重命名合并剧本：', curName);
        if (newName === null) return;
        const trimmed = newName.trim();
        if (!trimmed || trimmed === curName) return;

        try {
            const data = await API.updateMerge(mergeId, { title: trimmed });
            if (data.status === 'ok') {
                Util.showToast('已重命名 ✅', 'success');
                await this._loadMergedScripts();
            }
        } catch (e) {
            Util.showToast('重命名失败', 'error');
        }
    },

    async _deleteMerge(mergeId) {
        const ms = this.state.mergedScripts.find(m => m.id === mergeId);
        const title = ms ? (ms.title || '（未命名）') : '此合并剧本';
        if (!confirm(`确定删除「${title}」？此操作不可撤销。`)) return;

        try {
            const data = await API.deleteMerge(mergeId);
            if (data.status === 'ok') {
                Util.showToast('已删除 ✅', 'success');
                await this._loadMergedScripts();
            } else {
                Util.showToast(data.message || '删除失败', 'error');
            }
        } catch (e) {
            Util.showToast('删除失败: ' + e.message, 'error');
        }
    },

    // ── 小说编辑器 ──

    _openNovelEditor() {
        if (!this.state.currentNovelId) return;
        View.showNovelEditor(this.state.chapters);
        // 自动加载第一章
        const first = this.state.chapters[0];
        if (first) this._loadChapterForEdit(first.num);
    },

    async _loadChapterForEdit(chNum) {
        try {
            const data = await API.getChapterContent(this.state.currentNovelId, chNum);
            if (data.status === 'ok' && data.chapter) {
                View.setEditorContent(data.chapter);
            }
        } catch (_) {}
    },

    async _saveChapter() {
        const title = document.getElementById('editorChTitle').value;
        const content = document.getElementById('editorChContent').value;
        const statusEl = document.getElementById('editorStatus');

        // 找到当前章节id
        const active = document.querySelector('.editor-toc-item.active');
        if (!active) { Util.showToast('请先选择章节', 'error'); return; }
        const chId = parseInt(active.dataset.chId);
        const chNum = parseFloat(active.dataset.chNum);

        statusEl.textContent = '保存中...';
        try {
            const data = await API.updateChapter(this.state.currentNovelId, chId, { title, content });
            if (data.status === 'ok') {
                statusEl.textContent = '已保存 ✓';
                // 更新本地章节列表
                const ch = this.state.chapters.find(c => c.num === chNum);
                if (ch) { ch.title = title; ch.chars = content.length; }
                Util.showToast('章节已保存 ✅', 'success');
            }
        } catch (e) {
            statusEl.textContent = '保存失败';
            Util.showToast('保存失败', 'error');
        }
    },

    async _handleSyncFile(file) {
        if (!this.state.currentNovelId) return;
        Util.showToast('正在对比章节差异...', 'info');
        try {
            const data = await API.syncPreview(this.state.currentNovelId, file);
            if (data.status === 'ok') {
                this._syncDiff = data;
                View.showSyncModal(data);
            } else {
                Util.showToast(data.message || '分析失败', 'error');
            }
        } catch (e) {
            Util.showToast('分析失败: ' + e.message, 'error');
        }
        document.getElementById('appendFileInput').value = '';
    },

    async _applySync() {
        if (!this._syncDiff) return;
        const add = [...document.querySelectorAll('.sync-cb-new:checked')].map(cb => parseFloat(cb.dataset.ch));
        const update = [...document.querySelectorAll('.sync-cb-mod:checked')].map(cb => parseFloat(cb.dataset.ch));

        if (add.length === 0 && update.length === 0) {
            Util.showToast('请至少选择一项操作', 'error');
            return;
        }

        const btn = document.getElementById('btnSyncApply');
        btn.disabled = true; btn.textContent = '⏳ 同步中...';
        try {
            const data = await API.syncApply(this.state.currentNovelId, add, update);
            if (data.status === 'ok') {
                View.hideSyncModal();
                Util.showToast(`同步完成：新增 ${data.added} 章，更新 ${data.updated} 章 ✅`, 'success');
                this._syncDiff = null;
                await this._openNovel(this.state.currentNovelId);
            } else {
                Util.showToast(data.message || '同步失败', 'error');
            }
        } catch (e) {
            Util.showToast('同步失败: ' + e.message, 'error');
        }
        btn.disabled = false; btn.textContent = '确认同步';
    },

    // ── 翻译 ──

    async _startTranslate() {
        if (!this.state.currentScriptId || !this.state.currentYaml) {
            Util.showToast('请先选择已转换的剧本', 'error');
            return;
        }

        // 先选方向
        const direction = prompt('选择翻译方向:\n  1 = 中文 → 外语\n  2 = 外语 → 中文\n\n输入 1 或 2：', '1');
        if (!direction || (direction !== '1' && direction !== '2')) return;

        const isZh2xx = direction === '1';
        const languages = {
            'en': 'English', 'ja': '日本語', 'ko': '한국어',
            'fr': 'Français', 'de': 'Deutsch', 'es': 'Español',
        };
        const directionLabel = isZh2xx ? '中文 → 外语' : '外语 → 中文';

        const choice = prompt(
            `${directionLabel}\n选择目标语言:\n` +
            Object.entries(languages).map(([k, v]) => `  ${k} = ${v}`).join('\n') +
            '\n\n输入语言代码（如 en）：', 'en'
        );
        if (!choice || !languages[choice]) return;

        const langLabel = languages[choice];
        const dirCode = isZh2xx ? 'zh2xx' : 'xx2zh';
        const directionText = isZh2xx ? `中文 → ${langLabel}` : `${langLabel} → 中文`;

        // 取剧本名称
        const script = this.state.availableScripts.find(s => s.id === this.state.currentScriptId);
        const scriptTitle = script ? (script.title || '（未命名）') : '（未命名）';

        const fullLabel = `🌐 ${scriptTitle} · ${directionText}`;
        View.showTranslationTab();
        View.showTranslationLoading(fullLabel);
        View.setStatus('active', `🌐 翻译中...`);
        Util.showToast(`AI 翻译中：${scriptTitle} (${directionText})，预计需要 1-2 分钟...`, 'info');

        try {
            const data = await API.translateScript(this.state.currentScriptId, choice, langLabel, dirCode);
            if (data.status === 'ok') {
                View.setStatus('success', '✅ 翻译完成');
                this.state.currentTranslation = data.yaml;
                this.state.currentTransLabel = fullLabel;
                this.state.currentTransId = data.translation_id;
                View.showTranslation(data.yaml, fullLabel);
                View.showTransDeleteBtn();
                View.setStatus('success', '✅');
                Util.showToast(`翻译完成：${scriptTitle} · ${directionText} ✅`, 'success');
                await this._loadTranslations();
                View.selectTranslationInList(data.translation_id);
            } else {
                Util.showToast(data.message || '翻译失败', 'error');
                View.setStatus('error', '❌ 翻译失败');
            }
        } catch (e) {
            Util.showToast('翻译请求失败: ' + e.message, 'error');
            View.setStatus('error', '❌ 网络错误');
        }
    },

    async _loadTranslations() {
        if (!this.state.currentScriptId) return;
        try {
            const data = await API.listTranslations(this.state.currentScriptId);
            if (data.status === 'ok') {
                this.state.translations = data.translations || [];
                View.renderTranslationList(this.state.translations, this.state.currentTransId, data.script_title);
            }
        } catch (_) {}
    },

    async _viewTranslation(transId) {
        try {
            const data = await API.getTranslation(transId);
            if (data.status === 'ok' && data.translation) {
                const t = data.translation;
                const script = this.state.availableScripts.find(s => s.id === this.state.currentScriptId);
                const scriptTitle = script ? (script.title || '（未命名）') : '（未命名）';
                this.state.currentTranslation = t.translated_yaml;
                this.state.currentTransId = t.id;
                this.state.currentTransLabel = `🌐 ${scriptTitle} · ${t.language_label || t.language}`;
                View.showTranslation(t.translated_yaml, this.state.currentTransLabel);
                View.selectTranslationInList(t.id);
                View.showTransDeleteBtn();
            }
        } catch (e) {
            Util.showToast('加载译文失败', 'error');
        }
    },

    async _deleteCurrentTranslation() {
        if (!this.state.currentTransId) return;
        if (!confirm('确定删除此译文？')) return;
        try {
            const data = await API.deleteTranslation(this.state.currentTransId);
            if (data.status === 'ok') {
                View.removeTranslationFromList(this.state.currentTransId);
                this.state.currentTransId = null;
                this.state.currentTranslation = '';
                View.showTranslationPlaceholder();
                View.setStatus('success', '✅');
                Util.showToast('译文已删除 ✅', 'success');
            }
        } catch (e) {
            Util.showToast('删除失败', 'error');
        }
    },

    // ── 重命名当前剧本 ──
    _startRenameScript() {
        if (!this.state.currentScriptId) return;
        const display = document.getElementById('scriptNameDisplay');
        const input = document.getElementById('scriptNameInput');
        if (!display || !input) return;

        const current = this.state.availableScripts.find(s => s.id === this.state.currentScriptId);
        const curName = current && current.title && current.title !== '（未命名）' && current.title !== '（新改编）'
            ? current.title : '';

        display.style.display = 'none';
        input.style.display = '';
        input.value = curName;
        input.placeholder = '输入剧本名称...';
        input.focus();
        input.select();

        const save = async () => {
            const newName = input.value.trim();
            input.style.display = 'none';
            display.style.display = '';
            if (newName && newName !== curName) {
                await this._renameScript(newName);
            }
        };

        input.onkeydown = (e) => {
            if (e.key === 'Enter') { e.preventDefault(); save(); }
            if (e.key === 'Escape') { input.style.display = 'none'; display.style.display = ''; }
        };
        input.onblur = () => save();
    },

    async _renameScript(newName) {
        try {
            await API.updateScript(this.state.currentScriptId, { title: newName });
            // 更新本地状态
            const s = this.state.availableScripts.find(sc => sc.id === this.state.currentScriptId);
            if (s) s.title = newName;
            // 刷新显示
            View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                                   this.state.availableScripts, this.state.currentScriptId);
            await this._loadLibrary();
            Util.showToast('剧本已重命名 ✅', 'success');
        } catch (e) {
            Util.showToast('重命名失败', 'error');
        }
    },

    // ── 锁定 ──
    async _lockScript() {
        if (!this.state.currentScriptId) return;
        const btn = document.getElementById('btnLock');
        if (btn) { btn.disabled = true; btn.textContent = '⏳ 锁定中...'; }
        View.setStatus('active', '⏳ 锁定中...');

        try {
            const data = await API.mergeScript(this.state.currentScriptId, null);
            if (data.status === 'ok') {
                this.state.currentYaml = data.yaml;
                View.showYaml(data.yaml);
                View.scrollToYaml();
                document.getElementById('btnDownload').style.display = '';
                View.setStatus('success', '✅ 剧本已锁定');
                Util.showToast(`剧本已锁定！(${data.stats.scenes}场景)`, 'success');

                const draft = this.state.availableScripts.find(s => s.id === this.state.currentScriptId);
                if (draft) {
                    draft.status = 'complete';
                    draft.yaml_content = data.yaml;
                }

                View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                                       this.state.availableScripts, this.state.currentScriptId);

                this._debouncedRefreshLibrary();
                await this._reloadNovelDetail();
            } else {
                Util.showToast(data.message || '发布失败', 'error');
                View.setStatus('error', '❌ 锁定失败');
                if (btn) { btn.disabled = false; btn.textContent = '🔒 锁定剧本'; }
            }
        } catch (e) {
            Util.showToast('请求失败: ' + e.message, 'error');
            View.setStatus('error', '❌ 网络错误');
            if (btn) { btn.disabled = false; btn.textContent = '🔒 锁定剧本'; }
        }
    },

    // ── 从 API 加载当前剧本 YAML（fallback：用于打开已有小说时恢复状态）──
    async _loadCurrentScriptYaml() {
        if (!this.state.currentScriptId) return;
        try {
            const data = await API.getScript(this.state.currentScriptId);
            if (data.status !== 'ok' || !data.script) return;
            const script = data.script;
            // 优先用 script 级别的 yaml_content（complete 剧本有）
            if (script.yaml_content) {
                this.state.currentYaml = script.yaml_content;
                View.showYaml(script.yaml_content);
                document.getElementById('btnDownload').style.display = '';
                return;
            }
            // draft 剧本：聚合所有已转换章节的 YAML
            const chapters = script.chapters || [];
            if (chapters.length > 0) {
                const parts = [];
                for (const ch of chapters) {
                    if (ch.yaml_content) {
                        parts.push(`# ── 第${ch.chapter_number}章 ──\n\n${ch.yaml_content}`);
                    }
                }
                if (parts.length > 0) {
                    const combined = parts.join('\n\n');
                    this.state.currentYaml = combined;
                    View.showYaml(combined);
                    document.getElementById('btnDownload').style.display = '';
                    return;
                }
            }
            // 没有任何内容
            View.showPlaceholder();
            document.getElementById('btnDownload').style.display = 'none';
        } catch (_) {}
    },

    // ── 下载 ──
    _download() {
        if (!this.state.currentYaml) return;
        const blob = new Blob([this.state.currentYaml], { type: 'text/yaml;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'script.yaml';
        a.click();
        URL.revokeObjectURL(url);
        Util.showToast('已下载 YAML 剧本文件', 'success');
    },
};

document.addEventListener('DOMContentLoaded', () => App.init());
