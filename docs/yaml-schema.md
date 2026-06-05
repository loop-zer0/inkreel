# Novel2Script YAML Schema v1.0

## 设计理念

此 Schema 专为 **AI 辅助小说→剧本改编** 设计，兼顾三个目标：

1. **可读性** — 人类编剧可直接阅读、编辑、打磨
2. **结构化** — 机器可解析、可校验、可导入其他编剧工具
3. **忠实度** — 保留原著叙事信息的同时适配剧本格式

相对于业界已有的格式（Final Draft XML、Fountain、CELTX），本 Schema 选择 YAML 的原因：
- 层级清晰，嵌套结构天然支持场景→对话→动作的树形关系
- 比 JSON 可读性更好（多行字符串、注释），比 XML 简洁
- 版本控制友好（纯文本、diff 友好）
- 便于 AI 生成和解析

---

## Schema 结构

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `meta` | object | ✅ | 剧本元信息 |
| `characters` | list | ✅ | 人物表 |
| `scenes` | list | ✅ | 场景列表（核心） |
| `acts` | list | | 分幕结构（可选，AI 自动推断） |

---

### meta — 元信息

```yaml
meta:
  title: "作品名"
  original_author: "原作者"
  adapter: "AI 辅助改编"
  source_chapters: [1, 2, 3]
  genre: "武侠"
  total_scenes: 12
  schema_version: "1.0"
  generated_at: "2026-06-05T22:00:00"
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `title` | string | ✅ | 剧本名称 |
| `original_author` | string | | 原著作者 |
| `adapter` | string | | 改编者/工具名 |
| `source_chapters` | list[int] | | 改编来源章节号 |
| `genre` | string | | 类型（武侠/科幻/现代…） |
| `total_scenes` | int | | 总场景数 |
| `schema_version` | string | | Schema 版本号 |
| `generated_at` | string | | 生成时间（ISO 8601） |

---

### characters — 人物表

```yaml
characters:
  - id: CHAR_01
    name: "张三"
    role: 主角
    gender: 男
    age: 25
    description: "年轻剑客，性格冲动但心地善良，自幼父母双亡"
    relations:
      - target: CHAR_02
        relation: 师父
      - target: CHAR_03
        relation: 暗恋对象
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `id` | string | ✅ | 全局唯一，CHAR_XX 格式 |
| `name` | string | ✅ | 人物姓名 |
| `role` | string | | 主角/配角/反派/龙套 |
| `gender` | string | | 男/女 |
| `age` | int/string | | 年龄或年龄段 |
| `description` | string | | 一句话人物介绍 |
| `relations` | list | | 人物关系表 |
| `relations[].target` | string | | 关联人物 ID |
| `relations[].relation` | string | | 关系描述（父子/师徒/恋人…） |

**设计原因**：
- `id` 用 `CHAR_XX` 而非数字，场景中引用一目了然
- `relations` 内嵌而非外键表，避免跨文件引用，一个 YAML 自包含
- `role` 用中文枚举而非英文，降低编剧阅读门槛

---

### scenes — 场景列表

```yaml
scenes:
  - id: SCENE_01
    source_chapter: 1
    location: "华山·论剑台"
    time: "清晨·外景"
    characters_present: [CHAR_01, CHAR_02]
    atmosphere: "紧张肃杀，薄雾笼罩"
    summary: "张三在论剑台上向师父告别。师父虽有不舍，但尊重弟子的决定。"
    dialogues:
      - speaker: CHAR_01
        line: "师父，弟子去意已决。"
        action: "单膝跪地，双手抱拳"
        emotion: 坚定
        subtext: "内心其实不舍，但必须走"
      - speaker: CHAR_02
        line: "江湖险恶，万事小心。"
        action: "缓步上前，扶起徒弟，拍了拍他的肩"
        emotion: 担忧
    transitions_to: SCENE_02
    notes: "建议加一段剑鸣声的远景音效来渲染氛围"
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `id` | string | ✅ | 全局唯一，SCENE_XX 格式 |
| `source_chapter` | int/string | ✅ | 改编来源章节号 |
| `location` | string | | 场景地点 |
| `time` | string | | 时间描述（清晨/深夜 + 内景/外景） |
| `characters_present` | list[string] | | 出场人物 ID 列表 |
| `atmosphere` | string | | 场景氛围 |
| `summary` | string | | 场景概要（非对话的叙述部分） |
| `dialogues` | list | | 对话列表 |
| `transitions_to` | string | | 转场目标场景 ID |
| `notes` | string | | 导演/编剧备注 |

**对话字段（dialogues[]）**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `speaker` | string | ✅ | 说话人 CHAR_ID |
| `line` | string | ✅ | 台词正文 |
| `action` | string | | 舞台动作/表情/走位 |
| `emotion` | string | | 情绪标注 |
| `subtext` | string | | 潜台词/内心活动 |

**设计原因**：
- 将 `action` 和 `emotion` 从台词中分离，方便编剧独立调整表演指导
- `subtext` 是 AI 独特价值——传统剧本格式不含潜台词，但 AI 可以推断角色"言外之意"，帮助演员理解
- `transitions_to` 显式声明转场，使得场景间逻辑关系明确（AI 生成时默认为下一场景）
- `summary` 收纳小说中纯粹描写的段落，与对话分离

---

### acts — 分幕结构

```yaml
acts:
  - act: 1
    title: "开端 / 建置"
    scenes: [SCENE_01, SCENE_02, SCENE_03]
    summary: "主角登场，建立世界观，冲突萌芽"
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| `act` | int | ✅ | 幕序号 |
| `title` | string | | 幕标题 |
| `scenes` | list[string] | ✅ | 该幕包含的场景 ID |
| `summary` | string | | 该幕剧情概要 |

默认分幕策略：场景数 ≥4 时按四幕结构（开端→发展→高潮→结局）均分。

---

## 完整示例

见 `sample/` 目录下的示例小说及转换结果。

---

## 扩展性

Schema 设计为可向后兼容扩展：
- 新增字段对旧解析器透明（YAML 天然容许多余字段）
- 未来可增加 `locations`（场景地点表）、`props`（道具表）等顶层字段
- 对话可扩展 `voice_type`（画外音/内心独白）、`overlap`（两人同时说话标记）

---

## 与业界格式对比

| 特性 | YAML Schema | Final Draft XML | Fountain |
|------|:-----------:|:---------------:|:--------:|
| 可读性 | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 结构化 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| AI 生成友好 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 工具生态 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 版本控制 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |

本 Schema 选择以可读性和 AI 友好性优先，而非工具兼容性——因为目标用户是"小说作者→编剧"的创作者，改编初稿后续可导入专业工具进一步打磨。
