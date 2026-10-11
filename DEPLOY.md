# 上线操作说明

## 1. 上线前检查

必须准备：

- 一个 GitHub 仓库，或一台安装 Docker 的云服务器。
- 一份由 Key 所有者明确授权给本项目使用的 DeepSeek API Key。
- 一个公开域名来源，例如 Render/Railway 自动域名或自己的域名。

不要准备：

- 不要把 Key 写进 `webapp.py`、HTML、JavaScript、截图或 Git。
- 不要把另一个成员的 Key 当作公共资源无限开放。应确认额度、账单和使用范围。
- 不要省略访问码和限流，否则公开网址可能被陌生人消耗 API 额度。

## 2. Render 蓝图部署

项目根目录已经包含 `render.yaml`：

```yaml
services:
  - type: web
    runtime: docker
    healthCheckPath: /healthz
    envVars:
      - key: SITESHAHA_LLM_API_KEY
        sync: false
```

操作步骤：

1. 在 GitHub 新建仓库并上传本目录。
2. Render 中选择 `New > Blueprint`，连接该仓库。
3. Render 读取 `render.yaml` 后要求填写 `SITESHAHA_LLM_API_KEY` 和
   `SITESHAHA_ACCESS_CODE`。
4. 点击部署。健康检查通过后，服务会获得类似
   `https://sitesaha-ai.onrender.com` 的网址。

免费实例会休眠。演示可使用，正式项目建议至少使用常驻实例。

## 3. Railway 部署

项目根目录已经包含 `railway.json` 和 `Procfile`。

1. Railway 中选择 `New Project > Deploy from GitHub repo`。
2. 设置以下 Variables：

```dotenv
SITESHAHA_LLM_MODE=on
SITESHAHA_LLM_BASE_URL=https://api.deepseek.com/v1
SITESHAHA_LLM_API_KEY=已授权Key
SITESHAHA_LLM_MODEL=deepseek-chat
SITESHAHA_LLM_API_STYLE=chat
SITESHAHA_ACCESS_CODE=项目访问码
SITESHAHA_RATE_LIMIT_PER_MINUTE=60
SITESHAHA_MAX_CONCURRENT_REQUESTS=4
```

3. 在 Networking 中生成公开域名。
4. 打开域名检查 `/healthz` 和首页。

## 4. Google Cloud Run 部署

要求已安装 Google Cloud CLI，并已启用 Cloud Run 和 Cloud Build。

```powershell
gcloud auth login
$env:SITESHAHA_LLM_API_KEY="已授权Key"
$env:SITESHAHA_ACCESS_CODE="项目访问码"
.\deploy\cloud-run.ps1 -ProjectId "你的项目ID" -Region "asia-east1"
```

Cloud Run 注入 `PORT`，服务会监听 `0.0.0.0:$PORT`。如需控制成本，可在控制台
设置最大实例数 1，并设置预算告警。

## 5. Docker/VPS 部署

```powershell
Copy-Item .env.example .env

# 编辑 .env，至少填写以下三项
# SITESHAHA_LLM_API_KEY=已授权Key
# SITESHAHA_ACCESS_CODE=项目访问码
# SITESHAHA_LLM_BASE_URL=https://api.deepseek.com/v1

docker compose up -d --build
docker compose ps
```

服务默认监听 `0.0.0.0:8501`。建议前面部署 Caddy 或 Nginx：

- Caddy 自动申请 HTTPS 证书。
- Nginx 需要配置证书并反向代理到 `127.0.0.1:8501`。
- 防火墙不要直接向公网开放 8501。

Docker Compose 使用命名卷 `sitesaha-data` 持久化 SQLite。删除命名卷会重置
运行时数据库，但镜像中的标准化知识文件不会丢失。

## 6. 验证上线结果

```powershell
Invoke-RestMethod "https://你的域名/healthz"
```

正常结果：

```json
{
  "status": "ok",
  "version": "9.1.0",
  "model_configured": true,
  "vision_configured": false
}
```

然后依次验证：

1. 首页可以打开。
2. 输入访问码后可以提问。
3. 回答中的“依据编号”有对应来源。
4. 断开 DeepSeek 或填错 Key 后，系统回退到检索摘要而不是崩溃。
5. 连续快速请求超过限制时返回 HTTP 429。

## 7. 当前线上地址

当前已经部署并通过验证：

```text
https://sitesaha-ai.onrender.com
```

GitHub 仓库收到 `main` 分支更新后，Render 会自动部署。部署完成后运行
`DELIVERY_VERIFY.ps1` 或交付目录中的 `VERIFY_ONLINE.ps1` 完成验收。
