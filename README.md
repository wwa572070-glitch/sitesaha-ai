# 筑安智培 V10.0.0 在线部署版

面向建筑新入职工人的安全问答服务。后端使用 Python 标准库 HTTP 服务，
知识检索使用 SQLite FTS5 和本地混合检索，回答模型通过服务端环境变量接入
DeepSeek 或其他 OpenAI 兼容接口。

## V10 主要变化

V10 在 V9.1 的在线加固基线上完成界面重构、拍照与语音链路修复、知识库扩充：

- **界面**：7 个模块统一骨架，首页改为「大屏指标条 + 主行动卡 + 今日三件事」，
  正文阅读度量与行高收敛，对比度全部达到 WCAG AA，可点击元素 ≥44px 触控区。
- **拍照**：支持摄像头拍照、本机压缩、预览重拍、上传进度与取消；
  失败原因分类提示；未配置视觉模型时返回可操作提示而不是 HTTP 500。
  同时修复了 multipart 字段解析在 CPython 3.12 下不可用的缺陷。
- **语音**：新增服务端 ASR（`POST /api/transcribe`，MediaRecorder 录音），
  未配置时自动降级到浏览器识别，错误码如实展示；朗读支持音色选择与暂停。
- **知识库**：国家标准元数据 8 → 28 部，新增 `GET /api/standards` 与
  「标准现行状态」检索表格，支持关键词高亮。
- **培训**：5 步培训路线、6 个工种专项、20 题知识测验、学习积分与
  可打印 A4 培训记录单（数据均在浏览器本地）。
- 新增 `<meta name="sitesaha-version">` 标记，线上与本地一眼可辨。

完整变更与已知限制见 `V10_RELEASE_NOTES.md`；标准缺口见 `data/sources/PENDING_STANDARDS.md`。

这个版本同时保留 V8 以来的可部署能力与公网运行加固：

- 自动识别云平台的 `PORT` 环境变量，兼容 Render、Railway、Cloud Run 等平台。
- 默认按 DeepSeek 的 OpenAI 兼容接口配置，也保留 Responses API 兼容能力。
- API Key 只从服务端环境变量读取，不写入 HTML、JavaScript 或数据库。
- 增加按 IP 限流、全局并发限制、请求超时和可选访问码。
- 部署在 Render 等反向代理后，可按真实访客 IP 限流，避免所有用户共用同一额度。
- 增加安全响应头、健康检查、Docker 非 root 运行和多平台部署清单。
- 移除失效的 `.venv`、数据库、缓存和 27 MB 原始附件，保留可检索的标准化文本。
- 包含真实案例、语音问答、回答朗读和应急求助入口。

## 当前公网状态

当前已经部署并可公开访问的地址是：

```text
https://sitesaha-ai.onrender.com
```

V9.1 部署时该地址的健康检查返回 `9.1.0`、22 个知识文档与 3052 个检索片段。
**V10.0.0 推送后应以 `.\VERIFY_ONLINE.ps1 -ExpectedVersion 10.0.0` 复核**，
预期为 42 个知识文档与 3092 个检索片段（标准元数据扩充后）。

## 前端界面维护

`webapp.py` 里的 `INDEX_HTML` 是内嵌单文件页面，**不要直接编辑那个字面量**。
改界面要编辑 `docs/ui-build/` 下的分片，再跑拼装与自检流水线，
详见 `docs/ui-build/README.md`。


## 先明确一件事

本目录不包含任何可用的第三方 API Key。原压缩包中的 `.env` 与
`.env.example` 完全相同，里面的 `sk-your-key-here` 只是占位符。

正式上线时必须由项目负责人提供一份已授权的 DeepSeek Key，并把它配置到
云平台的 Secret/Environment Variables。不要提交到 Git，也不要发给工人。

## 本地运行

要求 Python 3.10 或更高版本。

```powershell
Copy-Item .env.example .env
python webapp.py --open
```

浏览器打开 `http://127.0.0.1:8501`。如果只测试离线检索，把 `.env` 中的
`SITESHAHA_LLM_MODE` 改为 `off`。

## 配置 DeepSeek

在 `.env` 或云平台环境变量中填写：

```dotenv
SITESHAHA_LLM_MODE=on
SITESHAHA_LLM_BASE_URL=https://api.deepseek.com/v1
SITESHAHA_LLM_API_KEY=你的已授权Key
SITESHAHA_LLM_MODEL=deepseek-chat
SITESHAHA_LLM_API_STYLE=chat
```

DeepSeek 文字模型不能直接分析图片。若要启用“拍照问安全”，需要另外配置一个
支持视觉的 OpenAI 兼容模型：

```dotenv
SITESHAHA_VISION_BASE_URL=https://你的视觉服务/v1
SITESHAHA_VISION_API_KEY=你的视觉服务Key
SITESHAHA_VISION_MODEL=你的多模态模型名
SITESHAHA_VISION_API_STYLE=chat
```

未配置视觉模型时，文字问答正常，照片入口会返回明确的未配置提示。

## 上线到 Render

Render 适合快速获得公开网址：

1. 把本目录提交到项目自己的 GitHub 仓库。
2. 登录 Render，选择 `New > Blueprint` 或 `New > Web Service`。
3. 选择该仓库。仓库根目录的 `render.yaml` 和 `Dockerfile` 会被自动识别。
4. 设置 `SITESHAHA_LLM_API_KEY`，以及建议设置的 `SITESHAHA_ACCESS_CODE`。
5. 等待部署完成，Render 会给出 `https://...onrender.com` 网址。

免费实例在一段时间无请求后可能休眠，首次访问需要等待重新启动。需要稳定在线时，
应升级实例规格或改用 Railway、Cloud Run、云服务器等常驻方案。

## 上线到 Railway

1. 把本目录提交到 GitHub。
2. 在 Railway 选择 `Deploy from GitHub repo`。
3. Railway 会根据 `Dockerfile` 构建，并根据 `railway.json` 做健康检查。
4. 在 Variables 中添加 DeepSeek Key 和可选访问码。
5. 在 Networking 中生成公开域名。

## 上线到 Google Cloud Run

先安装并登录 `gcloud`，然后在项目根目录运行：

```powershell
$env:SITESHAHA_LLM_API_KEY="你的已授权Key"
$env:SITESHAHA_ACCESS_CODE="给项目成员使用的访问码"
.\deploy\cloud-run.ps1 -ProjectId "你的GCP项目ID" -Region "asia-east1"
```

Cloud Run 会注入 `PORT`，服务会自动使用该端口。完成后命令行会输出公开网址。

## 部署到自己的服务器

安装 Docker 后，在项目根目录运行：

```powershell
Copy-Item .env.example .env
# 编辑 .env，填写 API Key 和访问码
docker compose up -d --build
```

访问 `http://服务器IP:8501`。生产环境应再配置 Nginx/Caddy HTTPS 反向代理，
只向公网开放 80/443，并限制 8501 端口的防火墙访问。

## 公网安全设置

```dotenv
# 每个 IP 每分钟最多 60 次问答或照片请求
SITESHAHA_RATE_LIMIT_PER_MINUTE=60

# 同时处理的模型请求数，避免突发流量耗尽额度
SITESHAHA_MAX_CONCURRENT_REQUESTS=4

# Render 等受信任反向代理后设为 true，限流会使用真实访客 IP。
# 若服务端口直接暴露公网，应保持 false，避免请求伪造转发头绕过限流。
SITESHAHA_TRUST_PROXY_HEADERS=true

# 可选访问码。公开投用前建议设置。
SITESHAHA_ACCESS_CODE=请设置一段不易猜到的访问码
```

若设置访问码，第一次回答前页面会提示输入，之后保存在浏览器本地。访问码只是
轻量入口保护，不等同于正式账号体系。面向较大用户群时应接入统一身份认证。

## 接口

- `GET /healthz`：健康检查（含 `version`、`model_configured`、`vision_configured`、`asr_configured`）
- `GET /api/status`：模型与知识库状态
- `GET /api/checklists`：开工检查清单
- `GET /api/training`：培训数据（培训路线、工种专项、知识测验题库）
- `GET /api/standards`：标准元数据（编号、名称、状态、实施日期、官方入口）
- `GET /api/cases`：真实案例检索
- `POST /api/ask`：文字安全问答
- `POST /api/inspect-image`：照片安全辅助检查
- `POST /api/transcribe`：服务端语音识别（未配置 ASR 时返回 503 + `asr_not_configured`）

### 培训数据与工种上下文

`GET /api/training` 是只读接口，返回 `sitesaha/training.py` 中的纯数据：

```json
{
  "training_path": [["入场第一课", "……"]],
  "training_steps": [{"order": 1, "title": "入场第一课", "key_points": ["……"]}],
  "worker_roles": {"电工": {"summary": "……", "hazards": [], "rules": [], "violations": [], "ppe": []}},
  "roles": ["普工/杂工", "钢筋工", "木工", "电工", "焊工", "架子工"],
  "questions": [{"id": "q01", "domain": "入场与交底", "options": [], "answer": 1, "why": "……"}],
  "quiz": {"pass_score": 16, "domains": []}
}
```

`POST /api/ask` 新增两个**可选**字段，不传时行为与接入前完全一致：

| 字段 | 说明 |
| --- | --- |
| `worker_role` | 工种名，必须是 `roles` 中的值；非法值自动忽略 |
| `training_context` | 服务端根据 `worker_role` 自动生成的培训上下文，前端无需传 |

传入合法 `worker_role` 时，响应会额外带一个 `worker_role` 字段用于前端标注；
工种要点通过 `RAGEngine.answer(worker_role=..., training_context=...)` 进入模型提示词。

前端的测验成绩、培训路线勾选、班前确认清单全部保存在浏览器 `localStorage`，
不上传服务端，因此不需要账号体系，也不采集工友个人数据。

## 数据与合规

`data/knowledge/` 是演示摘要，`data/sources/normalized/` 是已标准化文本。
标准化内容仍应在正式使用前核对现行版本、项目适用性和授权范围。

高后果安全决策必须由现场安全员、项目交底、作业许可和应急指挥确认。模型输出
仅作辅助，不替代正式规范、项目制度和现场判断。

## 测试

```powershell
python -m unittest discover -s tests -v
```

更多部署说明见 `DEPLOY.md`，当前维护事项见 `CLEANUP_AND_NEXT.md`，
V8 历史改动记录见 `CLEANUP_REPORT_V8.md`。
