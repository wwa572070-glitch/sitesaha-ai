# 清理与后续维护

## 需要保留

- `sitesaha_v3/`
- `发布包/sitesaha-ai-new-worker-safety-assistant-v9-online-source.zip`
- `发布包/筑安智培V9.1源码与Git.bundle`
- 本文件夹中的部署和校验文档

## 可以清理

- `.env`
- `data/sitesaha.db`、WAL 和 SHM 文件
- `data/uploads/`
- `__pycache__/`
- `*.pyc`
- `*.log`
- 本地预览进程和测试数据库

`DELIVERY_CLEANUP.ps1` 默认只预览，不删除。确认后使用：

```powershell
.\DELIVERY_CLEANUP.ps1 -Apply
```

脚本只处理当前交付目录内的运行时文件，不会删除源码、发布包或 Git 历史包。

## 后续开发方式

1. 在 GitHub 仓库中创建分支。
2. 每个成员使用 Pull Request 合并，不再互相传 ZIP。
3. 所有人从同一个 `main` 分支拉取更新。
4. 每次发布重新生成源码 ZIP，并更新 `SHA256SUMS.txt`。
5. API Key、访问码和云平台账号由项目团队管理，不绑定个人开发机。

## 版本状态

- 应用版本：`9.1.0`
- V9.1 功能提交：`b5e5b6c`
- GitHub 最新文档提交：`2229a39`
- 线上平台：Render Free
- 线上地址：https://sitesaha-ai.onrender.com
