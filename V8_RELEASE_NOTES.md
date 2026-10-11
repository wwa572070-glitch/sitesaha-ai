# 筑安智培 V8 发布说明

本压缩包沿用 V7 的目录形式：

```text
sitesaha-ai-new-worker-safety-assistant-v8/
└── sitesaha_v3/
```

## 线上地址

```text
https://sitesaha-ai.onrender.com
```

网站名称：

```text
筑安智培
面向建筑一线新员工的AI安全培训智能体
```

GitHub：

```text
https://github.com/gaochu996-code/sitesaha-ai
```

## 本版本包含

- DeepSeek OpenAI 兼容接口配置。
- Render、Railway、Docker 和 Cloud Run 部署文件。
- 在线限流、并发限制、请求超时和可选访问码。
- 安全响应头、健康检查和浏览器端问答页面。
- 标准化建筑安全知识文本和检索测试。
- 线上部署状态、清理说明和验证脚本。
- 已在 Render 配置并验证 DeepSeek 文字模型。

## 未包含

- 原 V7 中已经失效的 `.venv`。
- DeepSeek API Key。
- 运行时 SQLite 数据库、上传文件和缓存。

API Key 和访问码已经配置在 Render 的环境变量中，不会写入源码或压缩包。
