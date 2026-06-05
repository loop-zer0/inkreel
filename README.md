# 🎬 InkReel — AI 小说转剧本工具

将 3 章以上的小说文本自动转换为结构化剧本（YAML 格式），帮助作者快速获得可编辑、可打磨的剧本初稿。

> 🏆 XEngineer 新工科计划 第三批 · 题目三：AI 小说转剧本工具

📺 **Demo 视频**：[待录制]

---

## ✨ 特性

- 📖 **智能章节分割** — 中英文 + 罗马数字章节自动识别（第X章 / Chapter I / CHAPTER 1）
- 📂 **多格式支持** — .txt / .md / .docx / .epub，自动编码检测
- 👥 **人物提取** — AI 扫描全文，自动识别所有人物及关系
- 🎭 **场景转换** — 三遍处理流水线：提取人物 → 逐章转换 → 合并去重
- ☑️ **章节选择** — 上传后预览所有章节，自由勾选转换范围
- 📜 **YAML 输出** — 结构化剧本（meta + characters + scenes + acts），自动保存到 output/
- 🌐 **双模式** — 云端 DeepSeek API / 离线 Ollama 本地模型，界面一键切换
- 🎨 **暗色 UI** — 拖拽上传 → 选章 → 预览 → 下载，零框架纯原生实现

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置 API Key（在线模式）
set OPENAI_API_KEY=your_deepseek_key

# 3. 启动
python backend/server.py

# 4. 打开 http://localhost:8766
```

或双击 `start.bat` 一键启动。

### 离线模式

需安装 [Ollama](https://ollama.com) 并拉取模型：

```bash
ollama pull qwen2.5:7b
# 启动后在界面中点击云端/离线开关
```

## 📁 项目结构

```
inkreel/
├── backend/                # 后端（Python 3.9 + FastAPI）
│   ├── server.py           # FastAPI 主服务 (9 个 API 端点)
│   ├── config.py            # 全局配置、在线/离线模式切换
│   ├── chapter_parser.py    # 章节正则分割 + 长章节分段
│   ├── format_reader.py     # 多格式文本提取 (.txt/.docx/.epub)
│   ├── extractor.py         # Pass 1: LLM 人物提取
│   ├── converter.py         # Pass 2: LLM 逐章转场景
│   ├── merger.py            # Pass 3: 合并去重 + 分幕推断
│   └── schema.py            # YAML Schema 定义 + 验证 + 序列化
├── frontend/               # 前端（原生 HTML/CSS/JS，零框架）
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── docs/
│   └── yaml-schema.md       # Schema 设计文档（含设计理由）
├── sample/
│   └── sample_novel.txt     # 示例武侠小说（3 章）
├── output/                  # 转换结果输出目录
├── requirements.txt
└── start.bat
```

## 📦 第三方依赖与原创说明

| 依赖 | 用途 | 是否原创 |
|------|------|:------:|
| FastAPI + Uvicorn | HTTP/WebSocket 服务框架 | 框架 |
| openai | DeepSeek API 调用（OpenAI 兼容） | 框架 |
| PyYAML | YAML 解析与序列化 | 框架 |
| python-multipart | 文件上传解析 | 框架 |
| python-docx | .docx 文档文本提取 | 框架 |
| ebooklib | .epub 电子书文本提取 | 框架 |

**原创核心模块**（backend/ 下除框架调用外的全部逻辑）：

| 模块 | 功能 | 技术思路 |
|------|------|----------|
| `chapter_parser.py` | 章节分割 | 12 种正则联合匹配，覆盖中/英/罗马数字/书信体 |
| `format_reader.py` | 多格式提取 | 统一接口，自动编码检测，HTML 标签剥离 |
| `extractor.py` | 人物提取 (Pass 1) | 采样首尾章节 → LLM 提取 → JSON → 分配 CHAR_ID |
| `converter.py` | 场景转换 (Pass 2) | 人物上下文注入 System Prompt → YAML 输出 → 解析 |
| `merger.py` | 合并去重 (Pass 3) | 同名人物去重、场景重编号、四幕结构推断 |
| `schema.py` | Schema 定义 | 自研 YAML Schema v1.0，含 LLM 引导模板、验证器 |
| `server.py` | API 服务 | 7 个端点：health/mode/preview/convert/schema/download |
| `docs/yaml-schema.md` | Schema 文档 | 设计理念、字段说明、与 Final Draft/Fountain 对比 |
| `frontend/` | 全部前端代码 | 拖拽上传、章节选择、YAML 语法高亮、模式切换 |

## 📋 YAML Schema

```yaml
meta:         # 元信息（标题、作者、类型、生成时间）
characters:   # 人物表（id + name + role + description + relations）
scenes:       # 场景列表（location + time + dialogue + action + emotion + subtext）
acts:         # 分幕结构（四幕：开端→发展→高潮→结局）
```

详见 [`docs/yaml-schema.md`](docs/yaml-schema.md)

## 🎬 Demo 视频

[待录制]

## 📄 License

MIT
