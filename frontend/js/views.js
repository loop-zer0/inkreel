/** InkReel UI 渲染 */

const View = {
    // ── 章节号 → 范围文本，如 [1,2,3,5,6] → "1-3, 5-6章" ──
    _chapterRange(nums) {
        if (!nums || !nums.length) return '';
        const sorted = [...nums].sort((a, b) => a - b);
        const ranges = [];
        let start = sorted[0], end = sorted[0];
        for (let i = 1; i < sorted.length; i++) {
            if (sorted[i] === end + 1) {
                end = sorted[i];
            } else {
                ranges.push(start === end ? `${start}` : `${start}-${end}`);
                start = end = sorted[i];
            }
        }
        ranges.push(start === end ? `${start}` : `${start}-${end}`);
        return ranges.join(', ') + '章';
    },

    // ── 仓库列表 ──
    renderLibrary(novels) {
        const el = document.getElementById('libraryList');
        if (!novels.length) {
            el.innerHTML = `<div class="library-empty">
                📭 仓库为空<br><span class="hint">点击上方「导入小说」开始</span></div>`;
            return;
        }
        el.innerHTML = novels.map(n => {
            const sc = n.script_count || 0;
            // 构建剧本章节范围描述
            let scriptInfo = '';
            if (sc > 0 && n.script_summaries) {
                const parts = n.script_summaries.map(s => {
                    const range = s.ch_count > 0 ? this._chapterRange([s.ch_min, s.ch_max]) : '';
                    let badge = s.status === 'complete' ? '✅' : '📝';
                    return `${badge}${range || '空'}`;
                });
                scriptInfo = `<span>🎬 ${parts.join(' · ')}</span>`;
            } else if (sc > 0) {
                scriptInfo = `<span>🎬 剧本: ${sc}个</span>`;
            } else {
                scriptInfo = `<span style="color:#555">🎬 未转换</span>`;
            }

            return `<div class="library-card" data-novel-id="${n.id}">
                <div class="lib-title">${Util.escapeHtml(n.title)}</div>
                <div class="lib-meta">
                    <span>📄 ${(n.file_format || 'txt').toUpperCase()}</span>
                    <span>📖 ${n.chapter_count}章</span>
                    <span>${Util.formatSize(n.total_chars)}字</span>
                    ${n.genre ? `<span class="lib-genre">${Util.escapeHtml(n.genre)}</span>` : ''}
                    <span>🕐 ${Util.formatDate(n.updated_at || n.created_at)}</span>
                </div>
                <div class="lib-meta" style="margin-top:3px">${scriptInfo}</div>
                <div class="lib-actions">
                    <button class="btn-xs accent lib-btn-open">📖 打开</button>
                    <button class="btn-xs danger lib-btn-del">🗑 删除</button>
                </div>
            </div>`;
        }).join('');
    },

    // ── 章节列表（仓库详情模式）──
    renderChapterList(chapters, generated, scripts, currentScriptId) {
        // 防抖：同一帧内多次调用只渲染最后一次
        if (this._renderChRafId) cancelAnimationFrame(this._renderChRafId);
        this._renderChRafId = requestAnimationFrame(() => {
            this._renderChRafId = null;
            this._doRenderChapterList(chapters, generated, scripts, currentScriptId);
        });
    },

    _doRenderChapterList(chapters, generated, scripts, currentScriptId) {
        const el = document.getElementById('chapterList');
        const countEl = document.getElementById('chapterCount');
        const range = generated.length > 0 ? this._chapterRange(generated) : '无';

        // 批量操作工具栏
        const selCount = App.state.selectedChapters.size;
        countEl.innerHTML = `<span class="ch-range-label">已完成: ${range}</span>
            <span class="ch-total-label">（共${chapters.length}章）</span>
            <span class="ch-batch-bar" id="batchBar" style="${selCount > 0 ? '' : 'display:none'}">
                <button class="btn-xs" id="btnSelectAll">☐ 全选</button>
                <button class="btn-xs accent" id="btnBatchConvert">🎬 批量转换(${selCount})</button>
            </span>`;

        // ── 剧本信息行（始终显示，即使是 1 个剧本）──
        let scriptInfoHtml = '';
        const currentScript = scripts && scripts.length > 0
            ? (scripts.find(s => s.id === currentScriptId) || scripts[0])
            : null;

        // ── 收集其他剧本的已完成章节（用于跨剧本提示）──
        const otherDoneChapters = new Map(); // chNum → script index
        if (scripts) {
            scripts.forEach((s, i) => {
                if (s.id !== currentScriptId) {
                    (s.chapters || []).forEach(ch => {
                        const cn = ch.chapter_number;
                        if (!otherDoneChapters.has(cn)) {
                            otherDoneChapters.set(cn, i + 1); // 改编编号（1-based）
                        }
                    });
                }
            });
        }

        if (scripts && scripts.length > 0) {
            const chNums = currentScript
                ? (currentScript.chapters || []).map(c => c.chapter_number)
                : generated;
            const rng = chNums.length > 0 ? this._chapterRange(chNums) : '空';
            const statusIcon = currentScript && currentScript.status === 'complete' ? '✅' : '📝';
            const statusText = currentScript && currentScript.status === 'complete' ? '已完成' : '草稿';

            if (scripts.length > 1) {
                // 多剧本：显示下拉选择器
                const curTitle = currentScript ? (currentScript.title || '') : '';
                const displayTitle = curTitle && curTitle !== '（未命名）' && curTitle !== '（新改编）' ? curTitle : '';
                scriptInfoHtml = `<div class="script-selector-row">
                    <span class="script-label">📝 剧本：</span>
                    <span class="script-name-display" id="scriptNameDisplay">${Util.escapeHtml(displayTitle)}</span>
                    <input class="script-name-input" id="scriptNameInput" style="display:none" maxlength="30" />
                    <button class="btn-xs" id="btnRenameScript" title="重命名">✏️</button>
                    <select id="scriptSelect" class="script-select">
                        ${scripts.map((s, i) => {
                            const sNums = (s.chapters || []).map(c => c.chapter_number);
                            const sRng = sNums.length > 0 ? this._chapterRange(sNums) : '空';
                            const sIcon = s.status === 'complete' ? '✅' : '📝';
                            const sTitle = s.title && s.title !== '（未命名）' && s.title !== '（新改编）' ? s.title : '';
                            const label = sTitle
                                ? `${sTitle} · ${sIcon} ${s.status === 'complete' ? '完成' : '草稿'} · ${sRng}`
                                : `改编${String(s.id).slice(-4)} · ${sIcon} ${s.status === 'complete' ? '完成' : '草稿'} · ${sRng}`;
                            return `<option value="${s.id}"${s.id === currentScriptId ? ' selected' : ''}>
                                ${label} · ${Util.formatDate(s.created_at)}
                            </option>`;
                        }).join('')}
                    </select>
                    <button class="btn-xs accent" id="btnNewScript">+ 新建</button>
                </div>`;
            } else {
                // 单剧本：简洁信息行
                const s = scripts[0];
                const shortId = s ? String(s.id).slice(-4) : '1';
                const sTitle = s && s.title && s.title !== '（未命名）' && s.title !== '（新改编）' ? s.title : '';
                const displayTitle = sTitle || `改编${shortId}`;
                scriptInfoHtml = `<div class="script-single-row">
                    <span class="script-label">📝 <span id="scriptNameDisplay">${Util.escapeHtml(displayTitle)}</span></span>
                    <input class="script-name-input" id="scriptNameInput" style="display:none" maxlength="30" />
                    <button class="btn-xs" id="btnRenameScript" title="重命名">✏️</button>
                    <span class="script-status-badge ${currentScript && currentScript.status === 'complete' ? 'done' : 'draft'}">${statusIcon} ${statusText}</span>
                    <span class="script-meta">· ${rng}</span>
                    <span class="script-meta">· ${Util.formatDate(currentScript ? currentScript.created_at : '')}</span>
                    <button class="btn-xs accent" id="btnNewScript">+ 新建</button>
                </div>`;
            }
        }

        el.innerHTML = scriptInfoHtml + chapters.map(ch => {
            const isDoneHere = generated.includes(ch.num);
            const otherIdx = otherDoneChapters.get(ch.num);
            const isDoneElsewhere = !isDoneHere && !!otherIdx;
            const isChecked = App.state.selectedChapters.has(ch.num);

            let statusHtml = '';
            if (isDoneHere) {
                statusHtml = `<span class="ch-status done">✓</span>
                    <span class="ch-actions">
                        <button class="btn-xs ch-btn-view" data-ch="${ch.num}">👁 查看</button>
                        <button class="btn-xs accent ch-btn-convert" data-ch="${ch.num}">🔄</button>
                    </span>`;
            } else if (isDoneElsewhere) {
                statusHtml = `<span class="ch-status elsewhere" title="已在其他改编中完成，点击复用">📝</span>
                    <span class="ch-actions">
                        <button class="btn-xs ch-btn-reuse" data-ch="${ch.num}">📋 复用</button>
                    </span>`;
            } else {
                statusHtml = `<span class="ch-status pending"></span>
                    <span class="ch-actions">
                        <button class="btn-xs accent ch-btn-convert" data-ch="${ch.num}">🎬 转换</button>
                    </span>`;
            }

            return `<div class="chapter-item${isDoneHere ? ' checked' : ''}${isDoneElsewhere ? ' elsewhere' : ''}">
                <input type="checkbox" class="ch-checkbox" data-ch="${ch.num}" ${isChecked ? 'checked' : ''}>
                <span class="ch-num">#${ch.num}</span>
                <span class="ch-title">${Util.escapeHtml(ch.title)}</span>
                <span class="ch-chars">${Util.formatSize(ch.chars)}</span>
                ${statusHtml}
            </div>`;
        }).join('');

        // ── 合并 / 查看区域 ──
        const isComplete = currentScript && currentScript.status === 'complete';
        const isEmpty = generated.length === 0;

        let mergeArea = document.getElementById('mergeArea');
        if (!mergeArea) {
            mergeArea = document.createElement('div');
            mergeArea.id = 'mergeArea';
            document.getElementById('detailPanel').appendChild(mergeArea);
        }
        if (isComplete) {
            mergeArea.innerHTML = `<div class="merge-done">
                <span>✅ 完整剧本已保存</span>
                <button class="btn btn-xs accent" id="btnMergeView">📜 查看</button>
            </div>`;
        } else if (isEmpty) {
            mergeArea.innerHTML = `<div class="hint-text">选择章节点击 🎬 开始转换，满 3 章后可合并</div>`;
        } else if (generated.length >= 3) {
            mergeArea.innerHTML = `<div class="merge-ready">
                <button id="btnMerge" class="btn btn-xs accent">🧩 合并为完整剧本</button>
                <span class="merge-hint">（${range}）</span>
            </div>`;
        } else {
            mergeArea.innerHTML = `<div class="hint-text">转换 ≥3 章后可合并为完整剧本</div>`;
        }
    },

    // ── 批量操作栏更新 ──
    updateBatchBar(selectedSet, allChapters) {
        const bar = document.getElementById('batchBar');
        if (!bar) return;
        const count = selectedSet.size;
        if (count > 0) {
            bar.style.display = '';
            const allNums = allChapters.map(c => c.num);
            const allSelected = allNums.every(n => selectedSet.has(n));
            const selectBtn = document.getElementById('btnSelectAll');
            const batchBtn = document.getElementById('btnBatchConvert');
            if (selectBtn) selectBtn.textContent = allSelected ? '☑ 取消全选' : '☐ 全选';
            if (batchBtn) batchBtn.textContent = `🎬 批量转换(${count})`;
        } else {
            bar.style.display = 'none';
        }
    },

    refreshCheckboxes(selectedSet) {
        document.querySelectorAll('.ch-checkbox').forEach(cb => {
            cb.checked = selectedSet.has(parseFloat(cb.dataset.ch));
        });
    },

    // ── YAML 预览 ──
    showYaml(yaml) {
        const output = document.getElementById('yamlOutput');
        const editor = document.getElementById('yamlEditor');
        const placeholder = document.getElementById('previewPlaceholder');
        const editBtn = document.getElementById('btnEditYaml');

        output.style.display = '';
        editor.style.display = 'none';
        if (placeholder) placeholder.style.display = 'none';
        if (editBtn) editBtn.style.display = '';
        if (editBtn) { editBtn.textContent = '✎'; editBtn.title = '编辑 YAML'; editBtn.dataset.mode = 'view'; }

        // 相同内容跳过重复高亮
        if (this._lastYaml === yaml) return;
        this._lastYaml = yaml;

        // 用 rAF 延迟高亮渲染，避免阻塞 UI 线程
        if (this._yamlRafId) cancelAnimationFrame(this._yamlRafId);
        this._yamlRafId = requestAnimationFrame(() => {
            output.innerHTML = Util.highlightYaml(yaml);
        });
    },

    showPlaceholder() {
        const output = document.getElementById('yamlOutput');
        const editor = document.getElementById('yamlEditor');
        const placeholder = document.getElementById('previewPlaceholder');
        const editBtn = document.getElementById('btnEditYaml');
        output.style.display = 'none';
        editor.style.display = 'none';
        if (placeholder) placeholder.style.display = '';
        if (editBtn) editBtn.style.display = 'none';
    },

    // ── YAML 编辑模式 ──
    startEdit() {
        const output = document.getElementById('yamlOutput');
        const editor = document.getElementById('yamlEditor');
        const editBtn = document.getElementById('btnEditYaml');

        editor.value = App.state.currentYaml;
        output.style.display = 'none';
        editor.style.display = '';
        editBtn.textContent = '💾'; editBtn.title = '保存 YAML'; editBtn.dataset.mode = 'edit';
        editor.focus();
    },

    saveEdit() {
        const editor = document.getElementById('yamlEditor');
        const newYaml = editor.value;
        App.state.currentYaml = newYaml;
        this.showYaml(newYaml);
        // 保存到数据库
        this._persistYaml();
        Util.showToast('YAML 已保存到仓库 ✅', 'success');
    },

    // ── 滚动到 YAML 预览 ──
    scrollToYaml() {
        const preview = document.getElementById('previewYaml');
        if (preview) preview.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },

    // ── 高亮闪烁 YAML 区域 ──
    flashYaml() {
        const output = document.getElementById('yamlOutput');
        if (!output || output.style.display === 'none') return;
        output.style.transition = 'box-shadow 0.3s ease';
        output.style.boxShadow = '0 0 20px rgba(124,138,255,0.6)';
        setTimeout(() => {
            output.style.boxShadow = '';
        }, 800);
    },

    // ── 导入模态框 ──
    showImportModal(chapters) {
        const modal = document.getElementById('importModal');
        document.getElementById('importFileName').textContent = App.state.previewFilename || '';
        document.getElementById('importChapterCount').textContent =
            chapters.length + ' 章 · ' + Util.formatSize(App.state.previewTotalChars);
        document.getElementById('importGenre').textContent = App.state.previewGenre || '通用';
        document.getElementById('importTitle').value = App.state.previewFilename || '';
        modal.style.display = 'flex';
    },

    hideImportModal() {
        document.getElementById('importModal').style.display = 'none';
    },

    // ── 状态 ──
    setStatus(state, text) {
        const el = document.getElementById('statusEl');
        el.className = 'status ' + state;
        el.textContent = text;
    },

    // ── 小说详情头 ──
    showNovelHeader(novel) {
        document.getElementById('detailTitle').textContent = novel.title;
        document.getElementById('detailMeta').textContent =
            `${novel.author || '（未知）'} · ${novel.chapter_count}章 · ${Util.formatSize(novel.total_chars)}字 · ${novel.genre || '通用'}`;
        document.getElementById('detailPanel').style.display = '';
        document.getElementById('placeholderDetail').style.display = 'none';
        document.getElementById('btnEditMeta').style.display = '';
    },

    hideNovelDetail() {
        document.getElementById('detailPanel').style.display = 'none';
        document.getElementById('placeholderDetail').style.display = '';
        document.getElementById('btnEditMeta').style.display = 'none';
        this._cancelMetaEdit();
        App.state.currentNovelId = null;
        App.state.currentScriptId = null;
    },

    // ── 元信息编辑 ──
    startMetaEdit() {
        document.getElementById('detailMetaView').style.display = 'none';
        document.getElementById('detailMetaEdit').style.display = '';
        document.getElementById('btnEditMeta').style.display = 'none';

        // 从界面已显示的值预填，不用正则解析 YAML
        // （正则可能误匹配到嵌套字段，如 act title "结局 / 收束"）
        let title = document.getElementById('detailTitle').textContent;
        let author = '', genre = '';
        const metaText = document.getElementById('detailMeta').textContent;
        // meta 格式："作者 · 30章 · 89.7万字 · 通用"
        const parts = metaText.split(' · ');
        if (parts.length > 0 && parts[0] !== '（未知）') author = parts[0];
        if (parts.length > 3 && parts[3] !== '通用') genre = parts[3];

        document.getElementById('editTitle').value = title;
        document.getElementById('editAuthor').value = author;
        document.getElementById('editGenre').value = genre;
        document.getElementById('editTitle').focus();
    },

    _cancelMetaEdit() {
        document.getElementById('detailMetaView').style.display = '';
        document.getElementById('detailMetaEdit').style.display = 'none';
        document.getElementById('btnEditMeta').style.display = '';
    },

    saveMetaEdit() {
        const newTitle = document.getElementById('editTitle').value.trim();
        const newAuthor = document.getElementById('editAuthor').value.trim();
        const newGenre = document.getElementById('editGenre').value.trim();

        // 更新标题显示
        if (newTitle) document.getElementById('detailTitle').textContent = newTitle;

        // 更新 YAML 中的 meta
        if (App.state.currentYaml && (newTitle || newAuthor || newGenre)) {
            let yaml = App.state.currentYaml;
            if (newTitle) {
                yaml = yaml.replace(/^(\s+title:\s*)"?(.+?)"?(\s*)$/m, `$1"${newTitle}"$3`);
            }
            if (newAuthor) {
                if (yaml.includes('original_author:')) {
                    yaml = yaml.replace(/^(\s+original_author:\s*)"?(.+?)"?(\s*)$/m, `$1"${newAuthor}"$3`);
                } else {
                    yaml = yaml.replace(/(title:.*\n)/, `$1  original_author: "${newAuthor}"\n`);
                }
            }
            if (newGenre) {
                if (yaml.includes('genre:')) {
                    yaml = yaml.replace(/^(\s+genre:\s*)"?(.+?)"?(\s*)$/m, `$1"${newGenre}"$3`);
                } else {
                    yaml = yaml.replace(/(title:.*\n)/, `$1  genre: "${newGenre}"\n`);
                }
            }
            App.state.currentYaml = yaml;
            this.showYaml(yaml);

            // 保存到数据库
            this._persistYaml(newTitle);
        }

        this._cancelMetaEdit();
        Util.showToast('信息已更新 ✅', 'success');
    },

    // ── 将当前 YAML 持久化到数据库 ──
    async _persistYaml(title) {
        if (!App.state.currentScriptId) return;
        try {
            await API.updateScript(App.state.currentScriptId, {
                yaml_content: App.state.currentYaml,
                title: title || undefined,
            });
            // 防抖刷新仓库
            if (App._debouncedRefreshLibrary) App._debouncedRefreshLibrary();
            if (App._reloadNovelDetail) App._reloadNovelDetail();
        } catch (_) {}
    },
};
