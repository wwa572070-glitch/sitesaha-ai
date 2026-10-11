# 线上部署状态（2026-09-26 已上线）

## GitHub

- Repository: `https://github.com/gaochu996-code/sitesaha-ai`
- Visibility: Private
- Default branch: `main`
- V9.1 功能提交: `b5e5b6c`
- 最新文档提交: `2229a39`
- 当前状态：仓库可正常访问，V9.1 已推送到 `main`。

## Render

- Service name: `sitesaha-ai`
- Service ID: `srv-dar50c3ncjis73c5akpg`
- Blueprint ID: `exs-dar509g473hc739rm0kg`
- URL: `https://sitesaha-ai.onrender.com`
- 当前状态：在线，`GET /healthz` 返回 HTTP 200。
- 当前线上版本：`9.1.0`。
- 当前模型：`deepseek-chat` 已连接。
- 当前知识库：22 个文档，3052 个检索片段。
- 自动部署：GitHub 推送后已由 Render 成功发布。

## V9.1 交付状态

- 本地自动测试：26 项全部通过。
- 公网验收：版本、模型、知识库、案例、语音入口和紧急求助全部通过。
- 源码、部署清单、知识库文本和许可证均已整理。
- API Key 和访问码未写入交付文件。
