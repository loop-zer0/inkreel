# InkReel 测试报告与流程分析

> 测试时间：2026-06-06
> 测试环境：Python 3.9 + FastAPI 0.104.1 + Uvicorn 0.24.0

---

## 一、测试结果概览

### ✅ 正常工作

| 功能 | 状态 | 备注 |
|------|------|------|
| 首页 `/` (landing.html) | ✅ 200 | 30KB HTML 介绍页 |
| 工具页 `/app` | ✅ 200 | 9.2KB HTML |
| 健康检查 `GET /api/health` | ✅ 200 | 返回 mode/online_available |
| Favicon `/favicon.ico` | ✅ 200 | |
| 前端静态文件 `/static/js/*`, `/static/css/*` | ✅ 200 | 6个文件全部正常 |
| 用户登录 `POST /api/auth/login` | ✅ 200 | 字段名是 `account`, 不是 `email` |
| Token 验证 `GET /api/auth/check` | ✅ 200 | |
| 用户注册 `POST /api/auth/register` | ✅ 200 | 重复注册返回"该邮箱已注册" |
| 密码重置 `POST /api/auth/reset-password` | ✅ 200 | 未注册返回"该账号未注册" |
| 小说上传预览 `POST /api/novels/preview` | ✅ 200 | 3章武侠小说, 2076字 |
| 小说导入 `POST /api/novels/import` | ✅ 200 | 两步流程(预览→确认)正常 |
| 仓库列表 `GET /api/novels` | ✅ 200 | 含 script_summaries |
| 小说详情 `GET /api/novels/{id}` | ✅ 200 | 含章节和剧本列表 |
| 更新小说 `PUT /api/novels/{id}` | ✅ 200 | |
| 获取剧本 `GET /api/scripts/{id}` | ✅ 200 | 含完整 YAML 内容 |
| 更新剧本 `PUT /api/scripts/{id}` | ✅ 200 | |
| 获取 YAML Schema `GET /api/schema` | ✅ 200 | |
| 模式切换 `POST /api/mode` | ✅ 200 | |
| 获取模式 `GET /api/mode` | ✅ 200 | |

---

## 二、发现的问题

### 🐛 1. LLM_MODE 运行时切换无效

**位置**: `app/config.py:32` + `app/routers/system.py`

**根因**: `from app.config import LLM_MODE` 是值导入，`set_llm_mode()` 虽然改了 `config.py` 中的全局变量，但 `system.py` 里已导入的 `LLM_MODE` 是旧值的副本，不会更新。

**表现**:
```
切换到 offline → 返回 {"mode":"online","model":"qwen2.5:7b"}
```
mode 始终是 "online"，只是 model 变了。前端无法真正切换 LLM API 地址。

**修复**: `system.py` 中改为 `from app import config` 然后用 `config.LLM_MODE` 访问。

---

### 🐛 2. 缺少剧本列表 API

前端 `api.js` 中有 `API.listScripts(novelId)` 的调用意图，但后端 `scripts.py` 只有 `GET /api/scripts/{script_id}` 和 `DELETE/PUT`，没有 `GET /api/scripts` 列表路由。

`repositories/script.py` 中 `list_scripts(novel_id)` 方法存在但没有暴露为 API。

目前靠 `GET /api/novels` 返回的 `script_summaries` 字段绕过了这个问题。

---

### 🐛 3. 删除不存在资源返回 200

`DELETE /api/novels/2`（ID=2 不存在）返回 `200 OK {"status":"ok","message":"已删除"}`，应该返回 404。

---

### 🐛 4. 下载 API 路径安全问题

`GET /api/download/{filename}` 只做了简单的路径拼接，没有 path traversal 防护。虽然只限定在 OUTPUT_DIR，但如果 filename 包含 `../` 可能造成问题。

---

### ⚠️ 5. 合并流程（核心混乱点）

这是整个项目最绕的地方，详见第三节。

---

## 三、合并流程分析（核心问题）

### 当前流程

```
上传小说 → 自动创建"草稿"剧本
  → 转换第1章（单章YAML）
  → 转换第2章（单章YAML）
  → 转换第3章（单章YAML，此时 >= 3 章）
  → 出现"合并"按钮
  → 点合并 → 剧本状态变为 complete
  → 展示完整 YAML
```

### 用户困惑点

1. **概念多余**：用户以为"转完就是剧本了"，为什么要多一个"合并"步骤？

2. **阈值不合理**：合并按钮显示条件是 `generated.length >= 3`。1-2 章的小说永远看不到合并按钮，永远出不了完整剧本。

3. **合并前后视觉无区别**：合并前 YAML 区域显示单章数据，合并后显示完整数据，但位置和样式完全一样，用户看不出变化。

4. **多版本混乱**：合并完成后（complete），用户点"+新建改编"：
   - 新剧本是 draft，所有章节显示"待转"
   - 之前转过的章在左上角显示"已在其他改编"的灰色标签
   - 用户以为工作丢了，不知道可以点"复用"
   - 新改编转了1-2章后，既不够 3 章无法合并，又不能把上一版内容带过来

### 建议改进方案：**去掉"合并"概念，改为"发布"**

把用户心智模型从：
```
转换 → 合并 → 完成
```
改成：
```
编辑各章节 → 发布完整剧本
```

**具体改动**:

1. **自动拼接**：每次章节转换完成后，后端自动把该章场景追加到当前剧本的完整 YAML 中。用户不需要手动触发 merge。

2. **按钮替换**：去掉"合并"按钮，改为"🚀 发布完整剧本"。发布 = 把状态冻结为 published。

3. **实时预览**：右侧 YAML 区域实时展示当前完整剧本（各章已转场景的拼接结果），用户随时可以看到"当前进度下的完整剧本长什么样"。

4. **取消 >= 3 限制**：1-2 章也可以查看完整剧本（场景数少但结构完整）。

5. **多版本管理简化**：
   - v1 已发布 → 只能查看/下载，不能编辑
   - 点"新建改编" → 创建 v2，自动从 v1 复制已转换的章节
   - 用户理解成"不同版本"而不是"不同的剧本"

### 需要改动的点

| 改动 | 后端 | 前端 |
|------|------|------|
| 去掉合并概念 | `convert.py` 中 merge 集成到转换完即自动拼接 | 去掉 `#btnMerge` 和相关监听 |
| 增加 is_published 字段 | `scripts` 表加字段，`finalize_script` 改为 `publish_script` | 状态显示改为"已发布/草稿" |
| 章节转换后自动刷新预览 | 转换 API 返回时带上完整 YAML | 请求完成后自动更新 YAML 区域 |
| 发布动作 | `POST /api/scripts/{id}/publish` | 替换原有合并按钮 |
| 去掉 can_merge | 后端不再返回 | 前端不再依赖 |

---

## 四、其他体验问题

### 6. 转换按钮文案

已转换的章节显示"🔄 重转"和"查看"两个按钮，位置在一起。建议区分更清晰：已完成章节默认显示"查看"，hover 或右键才出现"重转"。

### 7. Mimo 模型响应慢

`POST /api/novels/quick-convert` 超过 60 秒超时仍未返回结果。建议前端加 loading 动画和长时间等待提示（"正在调用 AI 模型，可能需要 1-2 分钟..."）。

### 8. 编码显示问题

中文在终端显示为乱码（如 `æµè¯æ­¦ä¾ å°è¯´`），这是 UTF-8 编码在 PowerShell 的显示问题，前端浏览器中显示正常，不影响使用。

### 9. landing 页无登录入口

landing.html 只做产品介绍，没有登录表单。登录要在 `/app` 页面通过 JS 弹框进行。如果能直接在 landing 页放一个"开始使用"按钮跳转登录可能更好。

---

## 五、后端 API 清单（全部已注册路由）

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/reset-password` | 重置密码 |
| GET | `/api/auth/check` | 验证 Token |
| GET | `/api/health` | 健康检查 |
| GET | `/api/mode` | 获取当前 LLM 模式 |
| POST | `/api/mode` | 切换 LLM 模式 |
| GET | `/api/schema` | 获取 YAML Schema 文档 |
| GET | `/api/download/{filename}` | 下载已生成的 YAML 文件 |
| POST | `/api/novels/preview` | 上传文件预览章节 |
| POST | `/api/novels/import` | 确认导入仓库 |
| POST | `/api/novels/quick-convert` | 一键上传+转换+合并 |
| GET | `/api/novels` | 仓库列表 |
| GET | `/api/novels/{novel_id}` | 小说详情（含章节和剧本） |
| PUT | `/api/novels/{novel_id}` | 更新小说元信息 |
| DELETE | `/api/novels/{novel_id}` | 删除小说 |
| POST | `/api/novels/{novel_id}/convert/batch` | 批量转换章节 |
| POST | `/api/novels/{novel_id}/convert/{chapter_num}` | 单章转换 |
| GET | `/api/novels/{novel_id}/preview` | 重建预览数据 |
| POST | `/api/novels/{novel_id}/scripts/new` | 新建改编版本 |
| GET | `/api/novels/{novel_id}/chapters/{chapter_num}/yaml` | 获取单章 YAML |
| POST | `/api/scripts/{script_id}/merge` | 合并为完整剧本 |
| GET | `/api/scripts/{script_id}` | 获取剧本详情 |
| PUT | `/api/scripts/{script_id}` | 更新剧本 |
| DELETE | `/api/scripts/{script_id}` | 删除剧本 |
| GET | `/` | 产品介绍页 |
| GET | `/app` | 工具页面 |
| GET | `/favicon.ico` | 网站图标 |

