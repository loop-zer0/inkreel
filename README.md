# 🎬 InkReel — AI 小说转剧本工具

将 3 章以上的小说文本自动转换为结构化剧本（YAML 格式），帮助作者快速获得可编辑、可打磨的剧本初稿。

> 🏆 XEngineer 新工科计划 第三批 · 题目三：AI 小说转剧本工具

📺 **Demo 视频**：[待录制]

---

## ✨ 特性

- 📖 **智能章节分割** — 中英文 + 罗马数字 + 书信体章节自动识别（12 种正则联合匹配）
- 📂 **多格式支持** — .txt / .md / .docx / .epub，自动编码检测
- 👥 **人物提取** — AI 扫描全文，自动识别所有人物及角色关系（采样首尾章节 + 缓存复用）
- 🎭 **逐章场景转换** — 三遍处理流水线：提取人物 → 逐章转换 → 合并去重
- 🧩 **上下文注入** — 逐章转换时自动注入前文章节摘要，保持剧情连贯性
- ☑️ **章节选择 + 批量转换** — 上传后预览所有章节，自由勾选，一键批量处理
- 📋 **跨剧本复用** — 同一小说多个改编版本之间自动复用已完成章节，无需重复调用 LLM
- 📚 **仓库系统** — SQLite 持久化存储，小说 × 剧本 × 上下文缓存三表关联
- 🎨 **多剧本管理** — 一部小说可创建多个改编版本（草稿 / 已完成），自由切换
- ✏️ **在线 YAML 编辑** — 生成后可直接在浏览器中编辑剧本，自动保存
- 🌐 **双模式** — 云端 Mimo API / 离线 Ollama 本地模型，界面一键切换
- 🔐 **用户认证** — 邮箱/手机号注册登录，Token 鉴权，验证码找回密码
- 🎬 **产品页 + 工具页** — Landing 介绍页（`/`）和工具面板（`/app`）双入口

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone <repo-url> && cd inkreel

# 2. 安装依赖（Python 3.9+）
pip install -r requirements.txt

# 3. 配置（可选，不配置则需手动切换到离线模式）
#    在项目根目录创建 .env 文件，参考下方 .env 配置说明

# 4. 启动
python run.py

# 5. 打开浏览器
#    产品页：http://localhost:8766
#    工具页：http://localhost:8766/app
#    默认账户：admin@inkreel.local / inkreel
```

或双击 `start.bat` 一键启动。

### .env 配置

```bash
# 在线模式（Mimo API）
INKREEL_API_KEY=your_key_here       # API 密钥
INKREEL_MODEL=mimo-v2.5-pro         # 模型名（可选）
INKREEL_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1  # API 地址（可选）

# 离线模式（Ollama）
NOVEL2SCRIPT_MODE=offline           # 切换到离线
OLLAMA_MODEL=qwen2.5:7b             # 本地模型名（可选）

# 邮件（QQ 邮箱 SMTP，用于发送验证码）
INKREEL_SMTP_USER=your@qq.com
INKREEL_SMTP_PASSWORD=your_smtp_code

# 安全
INKREEL_SECRET_KEY=your_random_secret_key
```

### 离线模式

需安装 [Ollama](https://ollama.com) 并拉取模型：

```bash
ollama pull qwen2.5:7b
# 启动后在界面右上角点击 🌐云端 / 🏠离线 切换
```

## 📁 项目结构

```
inkreel/
├── app/                        # 后端（Python 3.9 + FastAPI，25 个 API 端点）
│   ├── main.py                 # FastAPI 应用入口 + Auth 路由 + 页面路由
│   ├── config.py               # 全局配置、在线/离线模式切换、.env 加载
│   ├── database.py             # SQLite 连接 + 6 表自动初始化
│   ├── auth.py                 # Token 签发/验证、用户注册/登录、邮件验证码、Auth 中间件
│   ├── routers/                # HTTP 路由层（请求解析、响应组装）
│   │   ├── novels.py           #   上传预览、确认导入、仓库 CRUD、一键转换
│   │   ├── convert.py          #   逐章转换、批量转换、剧本合并、仓库预览
│   │   ├── scripts.py          #   剧本查看/删除/更新、新建改编、章节 YAML 查询
│   │   └── system.py           #   健康检查、模式切换、Schema 文档、文件下载
│   ├── services/               # 业务逻辑层（纯算法 + LLM 调用）
│   │   ├── extractor.py        #   Pass 1: 采样首尾章节 → LLM 提取人物 → JSON → 分配 ID
│   │   ├── converter.py        #   Pass 2: 上下文注入 + LLM 逐章转场景 → YAML 解析 + 键名归一化
│   │   ├── merger.py           #   Pass 3: 同名人物去重、场景重编号、四幕结构推断
│   │   ├── importer.py         #   文件解析 → 章节检测 → 体裁检测 → 入库
│   │   ├── llm.py              #   统一 LLM 客户端封装（OpenAI 兼容接口）
│   │   └── genre.py            #   关键词匹配 + 经典文学检测 → 体裁分类
│   ├── repositories/           # 数据访问层（SQLite CRUD）
│   │   ├── novel.py            #   小说 & 章节查询/删除
│   │   ├── script.py           #   剧本 & 逐章场景 CRUD、草稿管理
│   │   └── context.py          #   上下文缓存读写（章节摘要缓存）
│   ├── schemas/                # Schema 定义与验证
│   │   ├── prompts.py          #   LLM System Prompt 模板（提取 + 转换 × 2）
│   │   └── validator.py        #   YAML Schema 验证 + 序列化（v1.0）
│   └── utils/                  # 工具函数
│       ├── parser.py           #   12 种正则章节分割 + 中文/罗马数字解析 + 超长章节分段
│       └── reader.py           #   多格式文本提取（自动编码检测、HTML 剥离）
├── frontend/                   # 前端（原生 HTML/CSS/JS，零框架）
│   ├── landing.html            #   产品介绍页（特性展示 + 登录注册）
│   ├── index.html              #   工具面板（三栏布局：仓库 | 预览 | 操作）
│   ├── css/
│   │   ├── landing.css         #   产品页样式
│   │   └── style.css           #   工具页暗色主题样式
│   └── js/
│       ├── auth.js             #   登录/注册/找回密码 UI 逻辑
│       ├── api.js              #   REST API 封装（自动注入 Token）
│       ├── utils.js            #   工具函数（YAML 高亮、Markdown 渲染、防抖）
│       ├── views.js            #   UI 渲染（仓库列表、章节列表、YAML 预览/编辑）
│       └── app.js              #   主应用控制器（事件绑定、状态管理、业务流程）
├── docs/
│   └── yaml-schema.md          # Schema 设计文档（含设计理由、字段说明）
├── sample/
│   └── sample_novel.txt        # 示例武侠小说（3 章）
├── output/                     # 转换结果输出目录
├── data/                       # SQLite 数据库文件（运行时生成）
├── run.py                      # 启动入口
├── start.bat                   # Windows 一键启动脚本
└── requirements.txt
```

## 📦 第三方依赖与原创说明

| 依赖 | 用途 | 是否原创 |
|------|------|:------:|
| FastAPI + Uvicorn | HTTP 服务框架 | 框架 |
| openai | Mimo / Ollama API 调用（OpenAI 兼容） | 框架 |
| PyYAML | YAML 解析与序列化 | 框架 |
| python-multipart | 文件上传解析 | 框架 |
| python-docx | .docx 文档文本提取 | 框架 |
| ebooklib | .epub 电子书文本提取 | 框架 |

**原创核心模块**（`app/` 下除框架调用外的全部逻辑）：

| 模块 | 功能 | 技术思路 |
|------|------|----------|
| `utils/parser.py` | 章节分割 | 12 种正则联合匹配，覆盖中文数字/阿拉伯数字/罗马数字/书信体/卷章，支持超长章节按段落边界分段 |
| `utils/reader.py` | 多格式提取 | 统一接口，自动编码检测（utf-8/gbk/gb2312/latin-1），docx 表格支持，epub HTML 标签剥离 |
| `services/extractor.py` | 人物提取 (Pass 1) | 采样首尾章节 → LLM → JSON → 分配 CHAR_ID → 缓存到 context_cache 表 |
| `services/converter.py` | 场景转换 (Pass 2) | 人物上下文 + 前文摘要注入 System Prompt → YAML → 中文键名自动归一化 |
| `services/merger.py` | 合并去重 (Pass 3) | 同名人物去重合并描述、场景全局重编号、transitions_to 补全、四幕结构按比例推断 |
| `services/importer.py` | 导入流程 | 预览-确认两步模式，章节筛选预览，体裁自动检测 |
| `services/genre.py` | 体裁检测 | 8 种题材关键词匹配 + 英文经典文学标记检测 |
| `schemas/validator.py` | Schema 验证 | 自研 YAML Schema v1.0，含人物 ID 去重、场景完整性、对白字段校验 |
| `schemas/prompts.py` | Prompt 模板 | 人物提取 / 基础转换 / 带上下文转换三套模板，英文键名强制约束 |
| `database.py` | 数据层 | 6 表自动初始化（novels/novel_chapters/scripts/script_chapters/context_cache/users），WAL 模式 + 外键 |
| `auth.py` | 认证系统 | HMAC-SHA256 Token、SHA-256 + Salt 密码、QQ 邮箱 SMTP 验证码、Auth 中间件 |
| `routers/` | API 层 | 25 个端点：上传/导入/转换/合并/仓库管理/剧本管理/模式切换/认证/下载 |
| `config.py` | 配置管理 | .env 自动加载、在线/离线模式运行时切换、LLM 参数集中管理 |
| `frontend/` | 全部前端代码 | 暗色主题粒子背景、拖拽上传、三栏可拖拽布局、章节勾选批量转换、YAML 语法高亮编辑、多剧本切换、产品页+工具页双入口 |

## 📋 YAML Schema

```yaml
meta:         # 元信息（标题、原作者、改编者、来源章节、场景总数、生成时间）
characters:   # 人物表（id + name + role + gender + description + relations）
scenes:       # 场景列表（id + location + time + characters_present + atmosphere + summary + dialogues + transitions_to）
  dialogues:  #   对白（speaker + line + action + emotion + subtext）
acts:         # 分幕结构（四幕：开端·建置 → 发展·对抗 → 高潮·转折 → 结局·收束）
```

详见 [`docs/yaml-schema.md`](docs/yaml-schema.md)

## 🎬 Demo 视频

[待录制]

## 📄 License

MIT
