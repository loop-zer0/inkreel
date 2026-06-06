/** InkReel 主应用 */

const App = {
    state: {
        isOffline: false,
        currentNovelId: null,
        currentScriptId: null,
        availableScripts: [],
        chapters: [],
        generatedChapters: [],
        currentYaml: '',
        previewFilename: '',
        previewTotalChars: 0,
        previewGenre: '',
        selectedChapters: new Set(),
    },

    async init() {
        // token 校验
        const authed = await Auth.initApp();
        if (!authed) return;

        Resizer.init();
        this._bindEvents();
        await this._initMode();
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

        // 模式切换
        document.getElementById('modeToggle').addEventListener('change', () => this._switchMode());

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
        });

        // 章节操作（委托）
        document.getElementById('chapterList').addEventListener('click', (e) => {
            const chBtn = e.target.closest('.ch-btn-convert');
            const reuseBtn = e.target.closest('.ch-btn-reuse');
            const viewBtn = e.target.closest('.ch-btn-view');
            const checkBox = e.target.closest('.ch-checkbox');
            if (chBtn) this._convertChapter(parseFloat(chBtn.dataset.ch), chBtn);
            if (reuseBtn) this._reuseChapter(parseFloat(reuseBtn.dataset.ch), reuseBtn);
            if (viewBtn) this._viewChapter(parseFloat(viewBtn.dataset.ch));
            if (checkBox) this._toggleChapterSelect(parseFloat(checkBox.dataset.ch), checkBox.checked);
        });

        // 全选 / 批量转换（委托，在 chapterSelect 容器上）
        document.getElementById('chapterSelect').addEventListener('click', (e) => {
            const selectAll = e.target.closest('#btnSelectAll');
            const batchConvert = e.target.closest('#btnBatchConvert');
            if (selectAll) this._toggleSelectAll();
            if (batchConvert) this._batchConvert();
        });

        // 合并按钮 + 查看按钮（委托）
        document.getElementById('detailPanel').addEventListener('click', (e) => {
            const mergeBtn = e.target.closest('#btnMerge');
            const viewBtn = e.target.closest('#btnMergeView');
            if (mergeBtn) this._mergeScript();
            if (viewBtn) {
                // 切换到 YAML 预览并滚动
                const yamlTab = document.querySelector('.preview-tab[data-tab="yaml"]');
                if (yamlTab) yamlTab.click();
                // 确保 YAML 可见
                if (!this.state.currentYaml) {
                    this._loadCurrentScriptYaml();
                }
                View.scrollToYaml();
                // 高亮闪烁 YAML 区域
                View.flashYaml();
            }
        });

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
    },

    // ── 模式 ──
    async _initMode() {
        try {
            const data = await API.getMode();
            this.state.isOffline = data.mode === 'offline';
            this._updateModeUI();
        } catch (_) {}
    },

    _updateModeUI() {
        const toggle = document.getElementById('modeToggle');
        const label = document.getElementById('modeLabel');
        toggle.checked = this.state.isOffline;
        label.textContent = this.state.isOffline ? '🏠 离线' : '🌐 云端';
        label.classList.toggle('offline', this.state.isOffline);
    },

    async _switchMode() {
        this.state.isOffline = !this.state.isOffline;
        this._updateModeUI();
        try {
            await API.switchMode(this.state.isOffline ? 'offline' : 'online');
            Util.showToast(this.state.isOffline ? '已切换到离线模式' : '已切换到云端模式', 'info');
        } catch (_) {
            Util.showToast('模式切换失败', 'error');
        }
    },

    // ── Preview 标签 ──
    _switchPreviewTab(tab) {
        document.querySelectorAll('.preview-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const target = tab.dataset.tab;
        document.getElementById('previewYaml').style.display = target === 'yaml' ? '' : 'none';
        document.getElementById('previewSchema').style.display = target === 'schema' ? '' : 'none';
        if (target === 'schema') this._loadSchema();
    },

    async _loadSchema() {
        const el = document.getElementById('schemaDoc');
        if (el.textContent !== '加载中...') return;
        try {
            const data = await API.getSchema();
            el.innerHTML = Util.renderMarkdown(data.content);
        } catch (_) {
            el.textContent = '加载失败';
        }
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
                num: c.chapter_number, title: c.title, chars: c.char_count,
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
            }

            View.showNovelHeader(novel);
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
        } else if (this.state.generatedChapters.length > 0) {
            // draft 剧本可能列表接口没带 yaml_content，主动拉取
            this._loadCurrentScriptYaml();
        } else {
            View.showPlaceholder();
            document.getElementById('btnDownload').style.display = 'none';
        }
        View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                               this.state.availableScripts, this.state.currentScriptId);
    },

    async _deleteNovel(novelId) {
        if (!confirm('确定删除此小说及其所有关联数据？')) return;
        await API.deleteNovel(novelId);
        if (this.state.currentNovelId === novelId) View.hideNovelDetail();
        Util.showToast('已删除', 'info');
        await this._loadLibrary();
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
        const btn = document.getElementById('btnBatchConvert');
        if (btn) { btn.disabled = true; btn.textContent = `⏳ 转换中...`; }
        View.setStatus('active', `⏳ 批量转换 ${chapters.length} 章...`);

        try {
            const data = await API.convertBatch(this.state.currentNovelId, chapters);
            if (data.status === 'ok') {
                // 如果后端创建了新草稿（旧剧本已完成），重置状态
                if (data.script_id !== this.state.currentScriptId) {
                    this.state.generatedChapters = [];
                    this.state.currentScriptId = data.script_id;
                    Util.showToast('已自动创建新改编草稿', 'info');
                }

                let totalScenes = 0;
                for (const r of data.results) {
                    if (r.status === 'ok') {
                        totalScenes += r.scenes_count || 0;
                        if (!this.state.generatedChapters.includes(r.chapter_number)) {
                            this.state.generatedChapters.push(r.chapter_number);
                        }
                    }
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

                // 清除选择
                this.state.selectedChapters.clear();
                View.setStatus('success', `✅ 批量转换完成`);
                Util.showToast(`批量转换完成 (${data.results.length}章, ${totalScenes}场景)`, 'success');
                View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                                       this.state.availableScripts, this.state.currentScriptId);

                // 显示最后一章的 YAML
                const lastOk = [...data.results].reverse().find(r => r.status === 'ok');
                if (lastOk && lastOk.yaml) {
                    View.showYaml(lastOk.yaml);
                    document.getElementById('btnDownload').style.display = '';
                    View.scrollToYaml();
                }

                if (data.can_merge) {
                    Util.showToast('当前改编已可合并！', 'info');
                }
            } else {
                Util.showToast(data.message || '批量转换失败', 'error');
                View.setStatus('error', '❌ 批量转换失败');
            }
        } catch (e) {
            Util.showToast('请求失败: ' + e.message, 'error');
            View.setStatus('error', '❌ 网络错误');
        }
        if (btn) { btn.disabled = false; btn.textContent = '🎬 批量转换'; }
    },

    // ── 逐章转换 ──
    async _convertChapter(chNum, btnEl) {
        if (!this.state.currentNovelId) return;
        btnEl.disabled = true;
        btnEl.textContent = '⏳...';
        View.setStatus('active', `⏳ 转换第${chNum}章...`);

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

                View.showYaml(data.yaml);
                document.getElementById('btnDownload').style.display = '';
                View.scrollToYaml();

                // 刷新章节列表
                View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                                       this.state.availableScripts, this.state.currentScriptId);

                if (data.can_merge) {
                    Util.showToast('当前改编已可合并！', 'info');
                }
            } else {
                Util.showToast(data.message || '转换失败', 'error');
                View.setStatus('error', '❌ 转换失败');
            }
        } catch (e) {
            Util.showToast('请求失败: ' + e.message, 'error');
            View.setStatus('error', '❌ 网络错误');
        }
        btnEl.disabled = false;
        btnEl.textContent = '🔄 重转';
    },

    // ── 复用已在其他改编中完成的章节（秒完成，不走 LLM）──
    async _reuseChapter(chNum, btnEl) {
        if (!this.state.currentNovelId) return;
        btnEl.disabled = true;
        btnEl.textContent = '📋 ...';
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

                View.showYaml(data.yaml);
                document.getElementById('btnDownload').style.display = '';
                View.scrollToYaml();
                View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                                       this.state.availableScripts, this.state.currentScriptId);

                if (data.can_merge) {
                    Util.showToast('当前改编已可合并！', 'info');
                }
            } else {
                Util.showToast(data.message || '复用失败', 'error');
                View.setStatus('error', '❌ 复用失败');
            }
        } catch (e) {
            Util.showToast('请求失败: ' + e.message, 'error');
            View.setStatus('error', '❌ 网络错误');
        }
        btnEl.disabled = false;
        btnEl.textContent = '📋 复用';
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
            this._debouncedRefreshLibrary();
            Util.showToast('剧本已重命名 ✅', 'success');
        } catch (e) {
            Util.showToast('重命名失败', 'error');
        }
    },

    // ── 合并 ──
    async _mergeScript() {
        if (!this.state.currentScriptId) return;
        const btn = document.getElementById('btnMerge');
        if (btn) { btn.disabled = true; btn.textContent = '⏳ 合并中...'; }
        View.setStatus('active', '⏳ 合并中...');

        try {
            // 不传 title，后端会用小说原标题
            const data = await API.mergeScript(this.state.currentScriptId, null);
            if (data.status === 'ok') {
                this.state.currentYaml = data.yaml;
                View.showYaml(data.yaml);
                View.scrollToYaml();
                document.getElementById('btnDownload').style.display = '';
                View.setStatus('success', '✅ 剧本合并完成');
                Util.showToast(`完整剧本已生成！(${data.stats.scenes}场景)`, 'success');

                // 立即更新本地状态，标记为已完成（防止 _reloadNovelDetail 失败时 UI 卡住）
                const draft = this.state.availableScripts.find(s => s.id === this.state.currentScriptId);
                if (draft) {
                    draft.status = 'complete';
                    draft.yaml_content = data.yaml;
                }

                // 立即刷新 UI（不等 API）
                View.renderChapterList(this.state.chapters, this.state.generatedChapters,
                                       this.state.availableScripts, this.state.currentScriptId);

                // 异步刷新仓库（防抖）和详情
                this._debouncedRefreshLibrary();
                await this._reloadNovelDetail();
            } else {
                Util.showToast(data.message || '合并失败', 'error');
                View.setStatus('error', '❌ 合并失败');
                if (btn) { btn.disabled = false; btn.textContent = '🧩 合并为完整剧本'; }
            }
        } catch (e) {
            Util.showToast('请求失败: ' + e.message, 'error');
            View.setStatus('error', '❌ 网络错误');
            if (btn) { btn.disabled = false; btn.textContent = '🧩 合并为完整剧本'; }
        }
    },

    // ── 从 API 加载当前剧本 YAML ──
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
