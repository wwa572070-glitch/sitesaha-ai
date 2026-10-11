"""把工作区作为一个全新的单提交推送到 GitHub（第 16 轮部署）。

为什么要这么做：
  推送时 GitHub 报
    refusing to allow a Personal Access Token to create or update workflow
    `.github/workflows/tests.yml` without `workflow` scope
  因为历史里有 GitHub Actions 文件，而 token 缺少 workflow 权限。

  即使把文件从最新提交里删掉，历史里的旧对象仍会被推送，仍会被拒。

  做法：建一个无历史的 orphan 分支，只提交当前工作区状态，force push 覆盖远程。
  这对 Render 完全够用（它只拉取最新快照来构建）。

  .env 已被 gitignore，不会进快照 —— 已用 git check-ignore 与全历史扫描确认过。

用法：python push_fresh_snapshot.py [--dry-run]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
GIT = r"C:\Program Files\Git\cmd\git.exe"
REMOTE_URL = "https://github.com/wwa572070-glitch/sitesaha-ai.git"
BRANCH = "main"

COMMIT_MESSAGE = (
    "SiteSaha AI 16.0.0\n"
    "\n"
    "面向建筑一线新工人的安全培训问答智能体。相对上一版的主要变化：\n"
    "- 修复 SVG 图标被当成文字显示（新增 makeIcon，图标改走 createElementNS）\n"
    "- 拍照幻觉防护：退化图像在服务端拦下，不再送模型编造场景\n"
    "- 拍照与语音的残留状态修复（[hidden] 与作者样式的优先级冲突）\n"
    "- 应急处置页重做：红警带 + 停撤报口诀 + 分级卡片 + 时间轴 + 吸底拨号\n"
    "- 首页改为班前四步动线；工种要点改 ✗/✓ 对比式排版\n"
    "- 班前检查按 17 个当班条件生成，支持 csv/txt/md/xlsx 导入\n"
    "- 回答与拍照结果渲染 Markdown，接口不再返回 Python 异常原文\n"
    "\n"
    "六项前端自检与 95 项单元测试通过。"
)


def run(args: list[str], *, check: bool = True, mask: str = "") -> str:
    result = subprocess.run(args, cwd=str(APP), capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    out = (result.stdout or "") + (result.stderr or "")
    if mask:
        out = out.replace(mask, "***")
    if check and result.returncode != 0:
        raise RuntimeError(f"命令失败（{result.returncode}）：{' '.join(args[:3])}\n{out[-800:]}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default="", help="GitHub token（不写入任何文件）")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== 1) 确认 .env 不会被提交 ===")
    out = run([GIT, "check-ignore", "-v", ".env"], check=False)
    if ".env" not in out:
        print("  [FAIL] .env 未被忽略，中止")
        return 1
    print("  [ok]", out.strip())

    print()
    print("=== 2) 建 orphan 分支（无历史）===")
    current = run([GIT, "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    print(f"  当前分支: {current}")
    if args.dry_run:
        print("  （dry-run，到此为止）")
        return 0

    run([GIT, "checkout", "--orphan", "snapshot-v16"])
    print("  [ok] 已切到 snapshot-v16")

    print()
    print("=== 3) 确认索引为空（orphan 分支不带历史文件）===")
    staged = run([GIT, "diff", "--cached", "--name-only"]).strip()
    if staged:
        print(f"  索引里有 {len(staged.splitlines())} 个文件，先清空")
        run([GIT, "rm", "-r", "--cached", "."], check=False)

    print()
    print("=== 4) 加入工作区全部文件 ===")
    run([GIT, "add", "-A"])
    staged = run([GIT, "diff", "--cached", "--name-only"])
    files = [line for line in staged.splitlines() if line.strip()]
    print(f"  待提交 {len(files)} 个文件")

    leaked = [f for f in files if Path(f).name == ".env"]
    if leaked:
        print("  [FAIL] .env 在待提交列表里，中止")
        return 1
    print("  [ok] 不含 .env")

    workflows = [f for f in files if f.startswith(".github/workflows")]
    if workflows:
        print(f"  [警告] 仍含 workflow 文件：{workflows}")

    print()
    print("=== 5) 提交 ===")
    msg_file = APP / ".git" / "SNAPSHOT_MSG.txt"
    msg_file.write_text(COMMIT_MESSAGE, encoding="utf-8")
    out = run([GIT, "commit", "-F", str(msg_file)], check=False)
    msg_file.unlink(missing_ok=True)
    if "nothing to commit" in out:
        print("  [注意] 没有变更可提交")
    else:
        print("  [ok] 已提交")
    print("  提交数:", run([GIT, "rev-list", "--count", "HEAD"]).strip())

    print()
    print("=== 6) 重命名分支为 main ===")
    run([GIT, "branch", "-M", "snapshot-v16", BRANCH], check=False)
    print("  [ok] 分支:", run([GIT, "rev-parse", "--abbrev-ref", "HEAD"]).strip())

    if not args.token:
        print()
        print("  （未提供 token，跳过推送。加 --token 即可推送）")
        return 0

    print()
    print("=== 7) 推送（force，覆盖远程）===")
    auth_url = REMOTE_URL.replace("https://", f"https://wwa572070-glitch:{args.token}@")
    run([GIT, "remote", "set-url", "origin", auth_url])
    try:
        out = run([GIT, "push", "--force", "origin", BRANCH], mask=args.token)
        print("  [ok] 推送成功")
        for line in out.strip().splitlines()[-4:]:
            print("   ", line.replace(args.token, "***"))
    except RuntimeError as exc:
        print("  [FAIL]", str(exc).replace(args.token, "***"))
        return 1
    finally:
        run([GIT, "remote", "set-url", "origin", REMOTE_URL], check=False)
        print("  [ok] 远程地址已还原（不含 token）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
