# 🎬 InkReel — AI 小说转剧本工具

将 3 章以上的小说文本自动转换为结构化剧本（YAML 格式），帮助作者快速获得可编辑、可打磨的剧本初稿。

> 🏆 XEngineer 新工科计划 第三批 · 题目三

## ✨ 特性

- 📖 **智能章节分割** — 自动识别中英文章节标题（第X章 / Chapter X）
- 👥 **人物提取** — AI 扫描全文，自动识别所有人物及其关系
- 🎭 **场景转换** — 逐章将叙述性文本转换为标准剧本场景+对话
- 📜 **YAML 输出** — 结构化、可读、可编辑的剧本格式
- 🌐 **双模式** — 云端 DeepSeek API 或离线 Ollama 本地模型，一键切换
- 🎨 **暗色 UI** — 上传→预览→下载，三步完成

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动（在线模式需要设置环境变量）
set OPENAI_API_KEY=your_deepseek_key
python backend/server.py

# 3. 打开浏览器
# http://localhost:8766
```

或直接双击 `start.bat`

### 离线模式

需要安装 [Ollama](https://ollama.com) 并拉取模型：

```bash
ollama pull qwen2.5:7b
# 然后在界面中点击切换到"离线"
```

## 📁 项目结构

```
inkreel/
├── backend/
│   ├── server.py           # FastAPI 服务
│   ├── config.py            # 配置（在线/离线切换）
│   ├── chapter_parser.py    # 章节分割
│   ├── extractor.py         # 人物提取 (Pass 1)
│   ├── converter.py         # 逐章转换 (Pass 2)
│   ├── merger.py            # 合并去重 (Pass 3)
│   └── schema.py            # YAML Schema 定义
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── docs/
│   └── yaml-schema.md       # Schema 设计文档
├── sample/
│   └── sample_novel.txt     # 示例小说（3 章）
└── requirements.txt
```

## 📋 YAML Schema

生成的剧本结构：

```yaml
meta:         # 元信息（标题、作者、类型）
characters:   # 人物表（含关系网）
scenes:       # 场景列表（对话+动作+情绪+潜台词）
acts:         # 分幕结构（自动推断四幕）
```

详见 `docs/yaml-schema.md`

## 🔧 技术栈

- **后端**: Python 3.9 + FastAPI
- **AI**: DeepSeek API / Ollama (qwen2.5)
- **前端**: 原生 HTML/CSS/JS（零框架）
- **输出**: YAML 1.2

## 📄 License

MIT
