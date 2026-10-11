"""空仓库 bootstrap：先用 Contents API 建一个初始提交，再用 Git Data API 批量推全部文件。

为什么需要 bootstrap：仓库完全空时，GitHub 的 `POST /git/blobs` 会返回
409 "Git Repository is empty" —— 没有对象数据库可写。必须先有一次提交。

用法：
    set GITHUB_TOKEN=ghp_xxx
    python gh_bootstrap_push.py --repo owner/name [--dry-run]
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
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.github.com"
BUILD = Path(__file__).resolve().parent
REPO_ROOT = BUILD.parent.parent
GIT = r"C:\Program Files\Git\cmd\git.exe"

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


def ensure_bootstrapped(repo: str, token: str) -> tuple[bool, str]:
    """确保仓库至少有一个提交。已初始化则直接返回。"""
    status, _ = call("GET", f"/repos/{repo}/git/ref/heads/main", token)
    if status == 200:
        return True, "已有 main 分支"

    print("  仓库为空，先创建初始提交…")
    payload = {
        "message": "chore: initialize repository",
        "content": base64.b64encode(
            "# sitesaha-ai\n\n筑安智培 SiteSaha AI —— 新工人安全助手。\n".encode("utf-8")
        ).decode("ascii"),
        "branch": "main",
    }
    status, body = call("PUT", f"/repos/{repo}/contents/README.md", token, payload)
    if status in (200, 201):
        return True, "已创建 README.md 初始提交"
    # 409/422 通常表示已存在，再查一次分支
    status2, _ = call("GET", f"/repos/{repo}/git/ref/heads/main", token)
    if status2 == 200:
        return True, "初始提交已存在"
    return False, f"bootstrap 失败 HTTP {status} {body.get('message', body)}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--message", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = local_files()
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

    print("\n[1/5] 确保仓库非空")
    ok, detail = ensure_bootstrapped(args.repo, token)
    print(f"  {detail}")
    if not ok:
        print(f"[FAIL] {detail}")
        return 1

    status, ref = call("GET", f"/repos/{args.repo}/git/ref/heads/main", token)
    parent = ref.get("object", {}).get("sha") if status == 200 else None
    print(f"  当前 main = {str(parent)[:12]}")

    print("\n[2/5] 上传文件对象")
    def upload(item: tuple[str, str]) -> tuple[str, str, str]:
        mode, rel = item
        raw = (REPO_ROOT / rel).read_bytes()
        payload = {"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"}
        code, body = call("POST", f"/repos/{args.repo}/git/blobs", token, payload)
        if code not in (200, 201):
            raise RuntimeError(f"HTTP {code} {body.get('message', body)}")
        return mode, rel, body["sha"]

    tree_items: list[dict] = []
    errors: list[str] = []
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(upload, item): item[1] for item in files}
        for future in concurrent.futures.as_completed(futures):
            rel = futures[future]
            try:
                mode, path, sha = future.result()
                tree_items.append({"path": path, "mode": mode, "type": "blob", "sha": sha})
                done += 1
                if done % 30 == 0 or done == len(files):
                    print(f"  已上传 {done}/{len(files)}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{rel}: {exc}")

    if errors:
        print(f"\n[FAIL] {len(errors)} 个文件上传失败：")
        for item in errors[:8]:
            print("  -", item)
        return 1

    print("\n[3/5] 建 tree")
    status, body = call("POST", f"/repos/{args.repo}/git/trees", token, {"tree": tree_items})
    if status not in (200, 201):
        print(f"[FAIL] HTTP {status} {body.get('message', body)}")
        return 1
    tree_sha = body["sha"]
    print(f"  tree = {tree_sha[:12]}（{len(tree_items)} 项）")

    print("\n[4/5] 建 commit")
    message = args.message or (
        "Release SiteSaha AI V10.0.0\n\n"
        "- 7 个视图 UI/排版重构，正文阅读度量与对比度全部达标\n"
        "- 拍照链路修复（含 multipart 解析缺陷）+ 视觉未配置时的明确降级\n"
        "- 新增服务端 ASR /api/transcribe 与浏览器识别降级\n"
        "- 知识库标准元数据 8 → 28 部，新增 /api/standards\n"
        "- 学习积分与可打印 A4 培训记录单"
    )
    parents = [parent] if parent else []
    status, body = call("POST", f"/repos/{args.repo}/git/commits", token,
                        {"message": message, "tree": tree_sha, "parents": parents})
    if status not in (200, 201):
        print(f"[FAIL] HTTP {status} {body.get('message', body)}")
        return 1
    commit_sha = body["sha"]
    print(f"  commit = {commit_sha[:12]}")

    print("\n[5/5] 更新 refs/heads/main")
    status, body = call("PATCH", f"/repos/{args.repo}/git/refs/heads/main", token,
                        {"sha": commit_sha, "force": True})
    if status not in (200, 201):
        status2, body2 = call("POST", f"/repos/{args.repo}/git/refs", token,
                              {"ref": "refs/heads/main", "sha": commit_sha})
        if status2 not in (200, 201):
            print(f"[FAIL] HTTP {status}/{status2} {body2.get('message', body2)}")
            return 1

    print("\n" + "=" * 54)
    print(f"推送成功：https://github.com/{args.repo}")
    print(f"commit：{commit_sha}")
    print(f"文件数：{len(tree_items)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
