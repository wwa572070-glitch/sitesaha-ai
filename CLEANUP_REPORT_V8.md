# V8 整理与改动报告

## 输入包情况

原始 ZIP 大小约 145 MB。主要体积来自随包携带的 `.venv`，其中的 Python
解释器路径仍指向另一台电脑和另一个用户目录，复制后不能直接运行。

原包 `.env` 与 `.env.example` 的 SHA-256 完全相同，说明压缩包没有保留真实
API Key，只有 `sk-your-key-here` 占位值。原模型配置也指向 OpenAI Responses
接口和 `gpt-5.6-luna`，不是 DeepSeek 配置。

## 本版本处理

已移除：

- 失效的 `.venv`
- `__pycache__` 和 `.pyc`
- `data/sitesaha.db` 及 WAL/SHM 文件
- 27 MB 已下载原始附件
- 无法正常显示中文的 Streamlit 备用脚本
- 重复和过期的发布清单内容

已保留：

- 完整应用源码和测试
- `data/knowledge/` 演示摘要
- `data/sources/normalized/` 标准化标准文本
- 公开来源清单和采集脚本
- 第三方许可证和来源说明

已新增：

- DeepSeek 文字模型配置
- 独立多模态模型配置
- 云端 `PORT` 自动识别
- Render、Railway、Cloud Run 和 Docker 部署配置
- 按 IP 限流、并发限制和可选访问码
- 安全响应头、健康检查和请求超时
- 在线部署与验证测试

## 目录整理

标准化文件已改为稳定的 ASCII 文件名，避免 ZIP 在不同 Windows 语言环境中
再次出现中文乱码。文件正文中的中文内容没有改动。

## 仍需项目提供

1. 一份已获授权、额度可控的 DeepSeek API Key。
2. 一个 GitHub 仓库、Render/Railway 账号或云服务器权限。
3. 正式公开前的项目访问码和额度上限策略。
4. 如启用照片分析，另需一个支持视觉的 OpenAI 兼容模型服务。
5. 正式使用前，由项目安全负责人复核标准版本和知识文本适用范围。
