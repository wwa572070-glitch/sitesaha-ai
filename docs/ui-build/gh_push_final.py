"""把本地仓库推到 GitHub（分批建 tree + 完整错误输出）。

要点：
  · 用 base_tree 增量建 tree，避免一次性 158 条 payload 出错时无从定位
  · 每批失败都打印 GitHub 的原始响应体，不再吞掉原因
  · 支持把失败的批次递归拆小，定位到具体是哪一条 entry 有问题

用法：
    set GITHUB_TOKEN=ghp_xxx
    python gh_push_final.py --repo owner/name [--batch 40] [--dry-run]
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

SKIP_PREFIXES = (".git/", "tmp", "__pycache__/")
SKIP_SUFFIXES = (".pyc", ".db", ".db-wal", ".db-shm")
# GitHub 规定写入 workflow 文件需要令牌带 `workflow` 权限。
# 只有 `repo` 权限时该文件会被拒（HTTP 404），因此默认跳过并单独提示。
SKIP_WORKFLOWS = True


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
                parsed = {"raw": body[:400]}
            # 4xx 不重试，避免掩盖真实错误
            if exc.code < 500 and exc.code != 429:
                return exc.code, parsed
            last = (exc.code, parsed)
        except Exception as exc:  # noqa: BLE001
            last = (0, {"message": f"{type(exc).__name__}: {exc}"})
        time.sleep(1.5 * (attempt + 1))
    return last


def local_files() -> tuple[list[tuple[str, str]], list[str]]:
    result = subprocess.run(
        [GIT, "ls-files", "--stage"], cwd=str(REPO_ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"git ls-files 失败：{result.stderr.strip()[:200]}")
    out: list[tuple[str, str]] = []
    skipped: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) < 3:
            continue
        if path.startswith(SKIP_PREFIXES) or path.endswith(SKIP_SUFFIXES):
            continue
        if SKIP_WORKFLOWS and path.startswith(".github/workflows/"):
            skipped.append(path)
            continue
        out.append(("100755" if parts[0] == "100755" else "100644", path))
    return out, skipped


def upload_blobs(repo: str, token: str, files: list[tuple[str, str]]) -> tuple[list[dict], list[str]]:
    def one(item: tuple[str, str]) -> tuple[str, str, str]:
        mode, rel = item
        raw = (REPO_ROOT / rel).read_bytes()
        code, body = call("POST", f"/repos/{repo}/git/blobs", token,
                          {"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"})
        if code not in (200, 201):
            raise RuntimeError(f"HTTP {code} {json.dumps(body, ensure_ascii=False)[:200]}")
        return mode, rel, body["sha"]

    items: list[dict] = []
    errors: list[str] = []
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(one, item): item[1] for item in files}
        for future in concurrent.futures.as_completed(futures):
            rel = futures[future]
            try:
                mode, path, sha = future.result()
                items.append({"path": path, "mode": mode, "type": "blob", "sha": sha})
                done += 1
                if done % 40 == 0 or done == len(files):
                    print(f"  已上传 {done}/{len(files)}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{rel}: {exc}")
    return items, errors


def build_tree(repo: str, token: str, entries: list[dict], base_tree: str | None,
               *, depth: int = 0) -> tuple[str | None, str]:
    """增量建 tree；失败时二分拆小以定位问题 entry。"""
    payload: dict = {"tree": entries}
    if base_tree:
        payload["base_tree"] = base_tree
    status, body = call("POST", f"/repos/{repo}/git/trees", token, payload)
    if status in (200, 201):
        return body["sha"], ""
    reason = f"HTTP {status} {json.dumps(body, ensure_ascii=False)[:300]}"

    if len(entries) == 1:
        return None, f"单条 entry 被拒：{entries[0]['path']} → {reason}"
    if depth >= 6:
        return None, f"拆分过深仍失败：{reason}"

    print(f"  {len(entries)} 条被拒（{reason[:80]}…），拆成两半重试")
    mid = len(entries) // 2
    left, left_err = build_tree(repo, token, entries[:mid], base_tree, depth=depth + 1)
    if left is None:
        return None, left_err
    right, right_err = build_tree(repo, token, entries[mid:], left, depth=depth + 1)
    if right is None:
        return None, right_err
    return right, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--message", default="")
    parser.add_argument("--batch", type=int, default=40)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files, skipped = local_files()
    size = sum((REPO_ROOT / rel).stat().st_size for _m, rel in files if (REPO_ROOT / rel).is_file())
    print(f"待推送：{len(files)} 个文件，{size / 1024 / 1024:.2f} MB")
    if skipped:
        print(f"跳过 {len(skipped)} 个 workflow 文件（需要令牌带 workflow 权限）：")
        for item in skipped:
            print("  -", item)
    if args.dry_run:
        return 0

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[FAIL] 未设置 GITHUB_TOKEN")
        return 1

    status, data = call("GET", f"/repos/{args.repo}", token)
    if status != 200:
        print(f"[FAIL] 仓库不可访问 HTTP {status}")
        return 1
    print(f"仓库：{data.get('full_name')}")

    status, ref = call("GET", f"/repos/{args.repo}/git/ref/heads/main", token)
    if status != 200:
        print(f"[FAIL] 读不到 main 分支 HTTP {status}（请先让仓库有一个初始提交）")
        return 1
    parent = ref["object"]["sha"]
    status, commit = call("GET", f"/repos/{args.repo}/git/commits/{parent}", token)
    base_tree = commit["tree"]["sha"]
    print(f"main = {parent[:12]}，base tree = {base_tree[:12]}")

    print(f"\n[1/4] 上传 {len(files)} 个文件对象")
    blob_items, blob_errors = upload_blobs(args.repo, token, files)
    if blob_errors:
        print(f"[FAIL] {len(blob_errors)} 个文件上传失败：")
        for item in blob_errors[:8]:
            print("  -", item)
        return 1
    print(f"  完成：{len(blob_items)} 个 blob")

    print(f"\n[2/4] 分批建 tree（每批 {args.batch} 条，基于 base_tree 增量）")
    current_tree = base_tree
    for start in range(0, len(blob_items), args.batch):
        chunk = blob_items[start:start + args.batch]
        new_tree, err = build_tree(args.repo, token, chunk, current_tree)
        if new_tree is None:
            print(f"[FAIL] 第 {start // args.batch + 1} 批失败：{err}")
            return 1
        current_tree = new_tree
        print(f"  第 {start // args.batch + 1} 批 OK（{len(chunk)} 条）→ {current_tree[:12]}")
    print(f"  最终 tree = {current_tree}")

    print("\n[3/4] 建 commit")
    message = args.message or (
        "Release SiteSaha AI V10.0.0\n\n"
        "- 7 视图 UI/排版重构：正文行宽 40 字、行高 1.78、对比度全部达 WCAG AA\n"
        "- 修复拍照链路（含 multipart 字段解析在 CPython 3.12 下不可用的缺陷）\n"
        "- 新增服务端 ASR /api/transcribe，未配置时降级浏览器识别\n"
        "- 知识库标准元数据 8 → 28 部，新增 GET /api/standards\n"
        "- 学习积分与可打印 A4 培训记录单；知识库检索高亮"
    )
    status, body = call("POST", f"/repos/{args.repo}/git/commits", token,
                        {"message": message, "tree": current_tree, "parents": [parent]})
    if status not in (200, 201):
        print(f"[FAIL] HTTP {status} {json.dumps(body, ensure_ascii=False)[:300]}")
        return 1
    commit_sha = body["sha"]
    print(f"  commit = {commit_sha}")

    print("\n[4/4] 更新 refs/heads/main")
    status, body = call("PATCH", f"/repos/{args.repo}/git/refs/heads/main", token,
                        {"sha": commit_sha, "force": False})
    if status not in (200, 201):
        print(f"[FAIL] HTTP {status} {json.dumps(body, ensure_ascii=False)[:300]}")
        return 1

    print("\n" + "=" * 56)
    print(f"推送成功：https://github.com/{args.repo}")
    print(f"commit：{commit_sha}")
    print(f"文件数：{len(blob_items)}")
    print("\n下一步：Render 若已连接此仓库会自动重建；否则在 Render 里连接它。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
