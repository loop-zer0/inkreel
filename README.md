# 🎬 InkReel — AI 小说转剧本工具

将小说文本自动转换为结构化剧本（YAML 格式），帮助作者快速获得可编辑、可打磨的剧本初稿。

> 🏆 XEngineer 新工科计划 第三批 · 题目三：AI 小说转剧本工具

📺 **Demo 视频**：[待上传至 Bilibili / 云盘，链接见此处]

---

## ✨ 特性

### 📖 导入与转换
- **多格式支持** — .txt / .md / .docx / .epub，自动编码检测
- **智能章节分割** — 中英文 + 罗马数字 + 书信体章节自动识别（12 种正则联合匹配）
- **人物提取** — AI 扫描全文，自动识别所有人物及角色关系
- **逐章场景转换** — 上下文注入保持剧情连贯性
- **章节选择 + 批量转换** — 上传后预览所有章节，自由勾选，一键批量处理
- **跨剧本复用** — 同一小说多个改编版本之间自动复用已完成章节

### 🧩 合并剧本
- **自由选择章节** — 按需勾选任意章节合并为独立剧本
- **多版本管理** — 一部小说可创建多个合并剧本（如"序幕"、"第一幕"、"完整版"）
- **动态更新** — 引用 `script_chapter_id`，章节重转后合并剧本自动跟随更新
- **增删改查** — 创建、查看、重命名、删除合并剧本

### 🌐 多语言翻译
- **双向翻译** — 中文 ↔ 英语/日语/韩语/法语/德语/西班牙语
- **保留结构** — YAML 键名不变，只翻译对话/描述/叙述等文本值
- **译文列表** — 左右分栏，左侧译文列表切换，右侧预览内容

### 📎 智能章节同步
- **差异预览** — 上传更新文件后自动对比新增/修改/未变章节
- **批量处理** — 勾选后一键应用，支持新增章节追加、修改章节覆盖

### ✎ 小说编辑器
- **树状目录** — 左侧章节目录树，右侧 textarea 编辑
- **实时保存** — 编辑后即时写入数据库
- **原文预览** — 每个章节支持 📖 原文查看

### 🎨 其他
- **多剧本管理** — 一部小说可创建多个改编版本，自由切换
- **在线 YAML 编辑** — 生成后可直接在浏览器中编辑，自动保存
- **三栏布局** — 仓库 | 剧本预览 | 章节操作，面板宽度可拖拽调节
- **产品页 + 工具页** — Landing 介绍页（`/`）和工具面板（`/app`）双入口
- **用户认证** — 邮箱/手机号注册登录，Token 鉴权

## 🚀 快速开始

```bash
# 1. 安装依赖（Python 3.9+）
pip install -r requirements.txt

# 2. 配置 .env（可选）
#    在项目根目录创建 .env 文件：
#    INKREEL_API_KEY=your_key_here

# 3. 启动
python run.py

# 4. 打开浏览器
#    产品页：http://localhost:8766
#    工具页：http://localhost:8766/app
#    默认账户：admin@inkreel.local / inkreel
```

或双击 `start.bat` 一键启动。

### .env 配置

```bash
INKREEL_API_KEY=your_key_here                  # API 密钥（必填）
INKREEL_MODEL=mimo-v2.5-pro                    # 模型名（可选）
INKREEL_BASE_URL=https://.../v1                # API 地址（可选）

# 邮件验证码（QQ 邮箱 SMTP，可选）
INKREEL_SMTP_USER=your@qq.com
INKREEL_SMTP_PASSWORD=your_smtp_code

# 安全（可选）
INKREEL_SECRET_KEY=your_random_secret_key
```

## 📁 项目结构

```
inkreel/
├── app/                           # 后端（Python 3.9 + FastAPI）
│   ├── main.py                    # FastAPI 入口 + Auth + 页面路由
│   ├── config.py                  # 全局配置、.env 加载
│   ├── database.py                # SQLite 连接 + 8 表自动初始化
│   ├── auth.py                    # Token 签发/验证、用户注册/登录、邮件验证码
│   ├── routers/                   # HTTP 路由层
│   │   ├── novels.py              #   上传预览、导入、仓库 CRUD、章节编辑、智能同步
│   │   ├── convert.py             #   逐章/批量转换、自动合并
│   │   ├── scripts.py             #   剧本 CRUD、章节 YAML 查询
│   │   ├── merges.py              #   合并剧本 CRUD
│   │   ├── translations.py        #   翻译 CRUD、语言列表
│   │   └── system.py              #   健康检查、Schema 文档
│   ├── services/                  # 业务逻辑层
│   │   ├── extractor.py           #   人物提取（LLM）
│   │   ├── converter.py           #   逐章场景转换（LLM）
│   │   ├── merger.py              #   合并去重 + 四幕结构推断
│   │   ├── translator.py          #   双向翻译（LLM）
│   │   ├── importer.py            #   文件解析 → 章节检测 → 入库
│   │   ├── llm.py                 #   统一 LLM 客户端（OpenAI 兼容）
│   │   └── genre.py               #   体裁分类
│   ├── repositories/              # 数据访问层
│   │   ├── novel.py               #   小说 & 章节 CRUD
│   │   ├── script.py              #   剧本 & 剧本章节 CRUD
│   │   ├── merged_script.py       #   合并剧本 & items CRUD
│   │   ├── translation.py         #   翻译记录 CRUD
│   │   └── context.py             #   上下文缓存读写
│   ├── schemas/                   # Prompt 模板 & 校验
│   │   ├── prompts.py             #   LLM System Prompt（提取 + 转换）
│   │   └── validator.py           #   YAML Schema v1.0 验证 + 序列化
│   └── utils/
│       ├── parser.py              #   12 种正则章节分割
│       └── reader.py              #   多格式文本提取
├── frontend/                      # 前端（纯 HTML/CSS/JS，零框架）
│   ├── landing.html               #   产品介绍页（粒子 + Three.js 3D 背景）
│   ├── index.html                 #   工具面板（三栏可拖拽布局）
│   ├── css/
│   │   └── style.css              #   完整样式（Editorial Light 主题）
│   └── js/
│       ├── core.js                #   自研微框架（Store + Component + DOM）
│       ├── auth.js                #   登录/注册/找回密码
│       ├── api.js                 #   REST API 封装
│       ├── utils.js               #   工具函数（YAML 高亮、防抖等）
│       ├── views.js               #   UI 渲染 + 组件注册
│       └── app.js                 #   主应用控制器
├── docs/
│   └── yaml-schema.md             # Schema 设计文档
├── sample/                        # 示例小说（5 本经典英文 + 1 本中文）
├── output/                        # 转换结果输出
├── data/                          # SQLite 数据库（运行时生成）
├── run.py                         # 启动入口
├── start.bat                      # Windows 一键启动
└── requirements.txt
```

## 📦 第三方依赖与原创说明

### 后端依赖

| 依赖 | 用途 |
|------|------|
| fastapi + uvicorn | HTTP 服务框架 |
| openai | LLM API 调用（OpenAI 兼容接口） |
| pyyaml | YAML 解析与序列化 |
| python-multipart | 文件上传解析 |
| python-docx | .docx 文档文本提取 |
| ebooklib | .epub 电子书文本提取 |

### 前端依赖

零依赖。纯 HTML/CSS/JS，无 npm、无框架、无构建工具。自研 `core.js`（~140 行）提供 Store（Proxy 反应式状态）、Component（UI 注册与自动渲染）、DOM（安全模板构建）。

### 原创核心模块

| 模块 | 功能 | 技术思路 |
|------|------|----------|
| `core.js` | 前端微框架 | Proxy 反应式 + requestAnimationFrame 批量渲染 + DOM 安全构建 |
| `merges.py` + `merged_script.py` | 合并剧本 | 双表关联引用 script_chapter_id，非快照模式，自动跟随更新 |
| `translator.py` + `translations.py` | 双向翻译 | 复用 Mimo LLM，System Prompt 控制 YAML 结构保留 |
| `novels.py` (sync) | 智能章节同步 | chapter_number + 内容字符串对比 → 差异预览 → 批量应用 |
| `views.js` (editor) | 小说编辑器 | 树状目录 + textarea，即时读写 |
| `utils/parser.py` | 章节分割 | 12 种正则联合匹配，中文数字/阿拉伯数字/罗马数字/书信体 |
| `utils/reader.py` | 多格式提取 | 统一接口，自动编码检测，docx 表格支持，epub HTML 剥离 |
| `services/extractor.py` | 人物提取 | 采样首尾章节 → LLM → JSON → 分配 CHAR_ID → 缓存 |
| `services/converter.py` | 场景转换 | 人物上下文 + 前文摘要注入 → YAML → 中文键名归一化 |
| `services/merger.py` | 合并去重 | 同名人物去重、场景全局重编号、四幕结构按比例推断 |
| `services/importer.py` | 导入流程 | 预览-确认两步模式，体裁自动检测 |
| `database.py` | 数据层 | 8 表自动初始化，WAL 模式 + 外键级联 |
| `auth.py` | 认证系统 | HMAC-SHA256 Token、SHA-256 + Salt 密码、QQ SMTP 验证码 |
| `schemas/prompts.py` | Prompt 模板 | 人物提取/基础转换/带上下文转换三套模板 |
| `frontend/` | 全部前端 | 三栏可拖拽布局、粒子+3D 背景、YAML 高亮编辑、批量转换、合并剧本、翻译面板、差异预览 |

## 📋 YAML Schema

```yaml
meta:         # 元信息（标题、原作者、改编者、来源章节、场景总数）
characters:   # 人物表（id + name + role + gender + description + relations）
scenes:       # 场景（id + location + time + characters_present + atmosphere + summary + dialogues + transitions_to）
  dialogues:  #   对白（speaker + line + action + emotion）
acts:         # 四幕结构（开端·建置 → 发展·对抗 → 高潮·转折 → 结局·收束）
```

详见 [`docs/yaml-schema.md`](docs/yaml-schema.md)

## 🎬 Demo 视频

[待上传至 Bilibili / 云盘]

---

## 📄 License

MIT
