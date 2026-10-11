"""把本地仓库推到 GitHub（多路径自动尝试，绕开 git 子进程限制）。

背景：本机沙箱禁止 git 启动凭据助手子进程，`git push` 无法完成认证。
本脚本用 Python 标准库直接调 GitHub REST API，能正常走系统代理。

按顺序尝试三条写入路径，哪条通就用哪条：
  A. Contents API（PUT /contents/<path>）—— 逐文件写，最少用 2 次请求
  B. Git Data API（blobs + tree + commit + refs）—— 整批提交，效率高
  C. 都不通时报告具体原因与所需令牌权限

用法：
    set GITHUB_TOKEN=ghp_xxx
    python gh_api_push.py --repo owner/name [--dry-run] [--method contents|gitdata|auto]

安全：不打印令牌；失败时打印 GitHub 的响应体（不会回显令牌）。
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
BUILD = Path(__file__).resolve().parent
REPO_ROOT = BUILD.parent.parent
GIT = r"C:\Program Files\Git\cmd\git.exe"

# 明显不该上传的东西（.gitignore 已覆盖，这里再兜一道）
SKIP_PREFIXES = (".git/", "tmp", "__pycache__/")
SKIP_SUFFIXES = (".pyc", ".db", ".db-wal", ".db-shm")


def call(method: str, path: str, token: str, payload: dict | None = None,
         *, retries: int = 3) -> tuple[int, dict]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "sitesaha-push",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    last: tuple[int, dict] = (0, {"message": "not attempted"})
    for attempt in range(retries):
        request = urllib.request.Request(API + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read().decode("utf-8", "replace")
                return response.status, (json.loads(body) if body else {})
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(body or "{}")
            except json.JSONDecodeError:
                parsed = {"message": body[:300]}
            if exc.code < 500 and exc.code != 429:
                return exc.code, parsed
            last = (exc.code, parsed)
        except Exception as exc:  # noqa: BLE001
            last = (0, {"message": f"{type(exc).__name__}: {exc}"})
        time.sleep(1.5 * (attempt + 1))
    return last


def local_files() -> list[tuple[str, str]]:
    result = subprocess.run(
        [GIT, "ls-files", "--stage"], cwd=str(REPO_ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"git ls-files 失败：{result.stderr.strip()[:200]}")

    out: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) < 3:
            continue
        if path.startswith(SKIP_PREFIXES) or path.endswith(SKIP_SUFFIXES):
            continue
        out.append(("100755" if parts[0] == "100755" else "100644", path))
    return out


def try_gitdata(repo: str, token: str, files: list[tuple[str, str]], message: str) -> tuple[bool, str]:
    print("\n[路径 B] Git Data API：blobs → tree → commit → refs")

    status, data = call("GET", f"/repos/{repo}/git/ref/heads/main", token)
    parents: list[str] = []
    if status == 200 and isinstance(data.get("object"), dict):
        parents = [data["object"]["sha"]]
        print(f"  现有 main 分支：{parents[0][:12]}")
    elif status == 409:
        print("  仓库为空，将创建首个提交")
    else:
        print(f"  读取分支返回 HTTP {status}（继续尝试）")

    def upload(item: tuple[str, str]) -> tuple[str, str, str]:
        mode, rel = item
        raw = (REPO_ROOT / rel).read_bytes()
        payload = {"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"}
        code, body = call("POST", f"/repos/{repo}/git/blobs", token, payload)
        if code not in (200, 201):
            raise RuntimeError(f"HTTP {code} {body.get('message', body)}")
        return mode, rel, body["sha"]

    tree_items: list[dict] = []
    first_error = ""
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(upload, item): item[1] for item in files}
        for future in concurrent.futures.as_completed(futures):
            rel = futures[future]
            try:
                mode, path, sha = future.result()
                tree_items.append({"path": path, "mode": mode, "type": "blob", "sha": sha})
                done += 1
                if done % 25 == 0 or done == len(files):
                    print(f"  已上传 {done}/{len(files)}")
            except Exception as exc:  # noqa: BLE001
                if not first_error:
                    first_error = f"{rel}: {exc}"

    if first_error:
        return False, f"blob 上传失败（示例）{first_error}"
    if len(tree_items) != len(files):
        return False, f"只有 {len(tree_items)}/{len(files)} 个文件上传成功"

    status, body = call("POST", f"/repos/{repo}/git/trees", token, {"tree": tree_items})
    if status not in (200, 201):
        return False, f"建 tree 失败 HTTP {status} {body.get('message', body)}"
    tree_sha = body["sha"]

    status, body = call("POST", f"/repos/{repo}/git/commits", token,
                        {"message": message, "tree": tree_sha, "parents": parents})
    if status not in (200, 201):
        return False, f"建 commit 失败 HTTP {status} {body.get('message', body)}"
    commit_sha = body["sha"]

    status, body = call("POST", f"/repos/{repo}/git/refs", token,
                        {"ref": "refs/heads/main", "sha": commit_sha})
    if status not in (200, 201):
        # 分支可能已存在，改用 PATCH 更新
        status2, body2 = call("PATCH", f"/repos/{repo}/git/refs/heads/main", token,
                              {"sha": commit_sha, "force": False})
        if status2 not in (200, 201):
            return False, f"更新分支失败 HTTP {status}/{status2} {body2.get('message', body2)}"

    return True, f"commit {commit_sha[:12]}，{len(tree_items)} 个文件"


def try_contents(repo: str, token: str, files: list[tuple[str, str]], message: str) -> tuple[bool, str]:
    print("\n[路径 A] Contents API：逐文件 PUT /contents/<path>")
    failed: list[str] = []
    done = 0
    for _mode, rel in files:
        raw = (REPO_ROOT / rel).read_bytes()
        payload = {
            "message": f"{message} :: {rel}",
            "content": base64.b64encode(raw).decode("ascii"),
            "branch": "main",
        }
        code, body = call("PUT", f"/repos/{repo}/contents/{urllib.parse.quote(rel)}", token, payload)
        if code not in (200, 201):
            # 第二次尝试：不带 branch（某些空仓库状态下 branch 参数会被拒）
            code2, body2 = call("PUT", f"/repos/{repo}/contents/{urllib.parse.quote(rel)}", token,
                                {"message": payload["message"], "content": payload["content"]})
            if code2 not in (200, 201):
                failed.append(f"{rel}: HTTP {code}/{code2} {body2.get('message', body2)}")
                if len(failed) >= 3:
                    return False, "；".join(failed[:3])
                continue
        done += 1
        if done % 25 == 0 or done == len(files):
            print(f"  已写入 {done}/{len(files)}")
    if failed:
        return False, "；".join(failed[:3])
    return True, f"{done} 个文件"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--message", default="Release SiteSaha AI V10.0.0")
    parser.add_argument("--method", choices=["auto", "contents", "gitdata"], default="auto")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = local_files()
    if not files:
        print("[FAIL] git 索引里没有文件")
        return 1
    size = sum((REPO_ROOT / rel).stat().st_size for _m, rel in files if (REPO_ROOT / rel).is_file())
    print(f"待推送：{len(files)} 个文件，{size / 1024 / 1024:.2f} MB")
    if args.dry_run:
        return 0

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[FAIL] 未设置 GITHUB_TOKEN")
        return 1

    status, data = call("GET", f"/repos/{args.repo}", token)
    if status != 200:
        print(f"[FAIL] 仓库不可访问 HTTP {status} {data.get('message', data)}")
        return 1
    print(f"仓库：{data.get('full_name')}（私有={data.get('private')}）")

    order = {
        "auto": [try_contents, try_gitdata],
        "contents": [try_contents],
        "gitdata": [try_gitdata],
    }[args.method]

    reasons: list[str] = []
    for attempt in order:
        ok, detail = attempt(args.repo, token, files, args.message)
        if ok:
            print("\n" + "=" * 52)
            print(f"推送成功：https://github.com/{args.repo}")
            print(f"方式：{attempt.__name__}　{detail}")
            return 0
        reasons.append(f"{attempt.__name__}: {detail}")
        print(f"  该路径失败：{detail}")

    print("\n[FAIL] 所有写入路径都不通：")
    for item in reasons:
        print("  -", item)
    print("\n所需令牌权限：classic PAT 勾选 `repo`；fine-grained PAT 需要")
    print("  · Repository permissions → Contents: Read and write")
    print("  · Repository permissions → Workflows: Read and write（仓库内有 .github/workflows）")
    return 1


if __name__ == "__main__":
    import urllib.parse  # 供 try_contents 使用
    sys.exit(main())
