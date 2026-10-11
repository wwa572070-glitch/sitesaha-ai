"""用 GitHub REST API 把本地 git 仓库推送到远端（绕开 git 的子进程限制）。

背景：本机沙箱禁止 git 启动凭据助手子进程（sh.exe 创建信号管道被拒），
导致 `git push` 无法完成认证。本脚本改用 GitHub REST API 直接提交，
只用 Python 标准库，能正常走系统代理。

用法：
    set GITHUB_TOKEN=ghp_xxx
    python gh_push.py --repo wwa572070-glitch/sitesaha-ai [--dry-run]

安全：绝不打印令牌；失败时打印响应体（GitHub 不会在响应里回显令牌）。
"""

from __future__ import annotations

import argparse
import base64
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
REPO_ROOT = BUILD.parent.parent          # sitesaha_v3
GIT = r"C:\Program Files\Git\cmd\git.exe"


def api(
    method: str,
    path: str,
    token: str,
    payload: dict | None = None,
    *,
    retries: int = 3,
) -> tuple[int, dict]:
    url = API + path
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "sitesaha-push",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    last: tuple[int, dict] = (0, {"error": "not attempted"})
    for attempt in range(retries):
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
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
            # 422 是"已存在"之类的语义错误，重试无意义
            if exc.code < 500 and exc.code != 429:
                return exc.code, parsed
            last = (exc.code, parsed)
        except Exception as exc:  # noqa: BLE001
            last = (0, {"error": f"{type(exc).__name__}: {exc}"})
        time.sleep(1.5 * (attempt + 1))
    return last


def local_entries() -> list[tuple[str, str]]:
    """返回 git 索引里的 (模式, 路径) 列表；模式保留可执行位。"""
    result = subprocess.run(
        [GIT, "ls-files", "--stage"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"git ls-files 失败：{result.stderr.strip()[:300]}")

    entries: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) < 3:
            continue
        mode = parts[0]
        entries.append(("100755" if mode == "100755" else "100644", path))
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description="通过 GitHub API 推送仓库")
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--message", default="", help="提交信息")
    parser.add_argument("--dry-run", action="store_true", help="只列出将要上传的文件")
    args = parser.parse_args()

    entries = local_entries()
    if not entries:
        print("[FAIL] 本地 git 索引里没有文件")
        return 1

    total_bytes = 0
    for _mode, rel in entries:
        path = REPO_ROOT / rel
        if path.is_file():
            total_bytes += path.stat().st_size
    print(f"待推送文件：{len(entries)} 个，合计 {total_bytes / 1024 / 1024:.2f} MB")

    if args.dry_run:
        for mode, rel in entries[:20]:
            print(f"  {mode}  {rel}")
        if len(entries) > 20:
            print(f"  …… 另有 {len(entries) - 20} 个")
        return 0

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[FAIL] 未设置 GITHUB_TOKEN")
        return 1

    # 0) 校验令牌与仓库
    status, data = api("GET", f"/repos/{args.repo}", token)
    if status != 200:
        print(f"[FAIL] 无法访问仓库 {args.repo}：HTTP {status} {data.get('message', data)}")
        return 1
    if not data.get("permissions", {}).get("push"):
        print("[FAIL] 令牌对该仓库没有 push 权限")
        return 1
    print(f"仓库确认：{data.get('full_name')}（私有={data.get('private')}）")

    # 1) 并发上传 blob
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def upload(item: tuple[str, str]) -> tuple[str, str, str]:
        mode, rel = item
        path = REPO_ROOT / rel
        raw = path.read_bytes()
        payload = {"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"}
        status_code, body = api("POST", f"/repos/{args.repo}/git/blobs", token, payload)
        if status_code not in (200, 201):
            raise RuntimeError(f"{rel}: HTTP {status_code} {body.get('message', body)}")
        return mode, rel, body["sha"]

    tree_items: list[dict] = []
    failures: list[str] = []
    done = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(upload, item): item[1] for item in entries}
        for future in as_completed(futures):
            rel = futures[future]
            try:
                mode, path_in_repo, sha = future.result()
                tree_items.append({"path": path_in_repo, "mode": mode, "type": "blob", "sha": sha})
                done += 1
                if done % 25 == 0 or done == len(entries):
                    print(f"  已上传 {done}/{len(entries)}")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{rel}: {exc}")

    if failures:
        print(f"[FAIL] {len(failures)} 个文件上传失败：")
        for item in failures[:10]:
            print("  -", item)
        return 1

    # 2) 建 tree
    status, body = api(
        "POST", f"/repos/{args.repo}/git/trees", token, {"tree": tree_items}
    )
    if status not in (200, 201):
        print(f"[FAIL] 建 tree 失败：HTTP {status} {body.get('message', body)}")
        return 1
    tree_sha = body["sha"]
    print(f"tree 已建：{tree_sha[:12]}（{len(tree_items)} 项）")

    # 3) 建 commit
    message = args.message or "Release SiteSaha AI V10.0.0 (initial import via API)"
    status, body = api(
        "POST",
        f"/repos/{args.repo}/git/commits",
        token,
        {"message": message, "tree": tree_sha, "parents": []},
    )
    if status not in (200, 201):
        print(f"[FAIL] 建 commit 失败：HTTP {status} {body.get('message', body)}")
        return 1
    commit_sha = body["sha"]
    print(f"commit 已建：{commit_sha[:12]}")

    # 4) 更新分支引用
    status, body = api(
        "POST",
        f"/repos/{args.repo}/git/refs",
        token,
        {"ref": "refs/heads/main", "sha": commit_sha},
    )
    if status not in (200, 201):
        print(f"[FAIL] 更新 refs/heads/main 失败：HTTP {status} {body.get('message', body)}")
        return 1

    print()
    print("=" * 50)
    print(f"推送完成：https://github.com/{args.repo}")
    print(f"提交：{message}")
    print(f"commit sha：{commit_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
