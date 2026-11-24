# Glyphbridge

**面向所有文字的免费、离线、开源翻译——从现代语言到奥斯曼土耳其语、埃及象形文字和楔形文字。**

🌐 [English](../../README.md) · [Türkçe](README.tr.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md) · **中文** · [日本語](README.ja.md)

> ⚠️ **状态：早期开发中。** Glyphbridge 正在公开开发。标记为*计划中*的功能尚未实现——欢迎你一起来建设。

## 为什么选择 Glyphbridge？

- **永久免费**——基于 Apache 2.0 许可证开源，无需注册；只有在开放自己的服务器时才需要 API 密钥。
- **私密离线**——一切都在你自己的电脑上运行，文档永远不会离开你的设备。
- **轻量**——专为 **8 GB 内存**的普通电脑设计，无需显卡。
- **如实呈现质量**——每条译文都附带**置信度分数**，并公布每个语言对的实测质量（COMET / chrF）。
- **适用于所有文字**——文本、图片、文档、语音以及历史文字系统。

## 功能与路线图

| 版本 | 功能 | 状态 |
|---|---|---|
| **v0.1** | 文本翻译，首批 10–20 种语言，命令行 + 简洁界面，量化模型（int8） | 🚧 进行中 |
| **v0.2** | 翻译**图片**（OCR）和**文档**（PDF、DOCX）中的文字并保留排版；置信度过滤 | 📋 计划中 |
| **v0.3** | **语音**翻译：语音 → 文本 → 翻译 → 语音 | 📋 计划中 |
| **v0.4** | **奥斯曼土耳其语**：印刷体与手写体（Rika、Divani）OCR、转写、现代土耳其语 | 📋 计划中 |
| **实验性** | **埃及象形文字**与**楔形文字**（阿卡德语、苏美尔语）——与研究人员合作 | 🔬 研究 |

## 随处可用（计划中）

| 接口 | 示例 |
|---|---|
| Python 库 | `glyphbridge.translate("Merhaba", to="en")` |
| 命令行 | `glyphbridge translate file.pdf --to de` |
| REST API | `glyphbridge serve` → `POST /v1/translate` (可选 API 密钥) |
| AI 智能体（MCP） | 在 Claude 及其他 AI 助手中作为工具调用 |
| OpenAI 兼容接口 | 无需改代码即可接入现有 AI 工具 |

全部自托管且免费。当你把服务器开放到网络时，API 密钥用于保护它。

## 参与贡献

- 🌍 把这份 README 翻译成你的语言——最理想的第一次贡献
- 🧪 用你的母语测试译文并报告错误
- 🐍 编写代码（Python）——查看带有 `good first issue` 标签的问题
- 📜 如果你是语言学家、历史学家或埃及学家，欢迎协助历史文字部分

请参阅 [CONTRIBUTING.md](../../CONTRIBUTING.md) 开始。

## 许可证

[Apache 2.0](../../LICENSE) — 可自由使用、修改和分享，包括商业用途。
