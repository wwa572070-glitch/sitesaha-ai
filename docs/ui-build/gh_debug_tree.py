"""调试：为什么 POST /git/trees 返回 404。只读取与最小化试验，不改动仓库内容。

用法：set GITHUB_TOKEN=ghp_xxx && python gh_debug_tree.py --repo owner/name
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"


def call(method: str, path: str, token: str, payload: dict | None = None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "sitesaha-debug",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            body = response.read().decode("utf-8", "replace")
            return response.status, (json.loads(body) if body else {}), dict(response.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        return exc.code, {"raw_body": body[:500]}, dict(exc.headers or {})
    except Exception as exc:  # noqa: BLE001
        return 0, {"exception": f"{type(exc).__name__}: {exc}"}, {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[FAIL] 未设置 GITHUB_TOKEN")
        return 1
        # 1) 仓库与限流
    status, data, headers = call("GET", f"/repos/{args.repo}", token)
    print(f"1) GET /repos -> {status}")
    print(f"   限流剩余 {headers.get('X-RateLimit-Remaining')} / 上限 {headers.get('X-RateLimit-Limit')}")
    if status != 200:
        print("   ", data)
        return 1

    # 2) 现有分支
    status, data, _ = call("GET", f"/repos/{args.repo}/git/ref/heads/main", token)
    print(f"2) GET ref/heads/main -> {status}")
    parent = None
    if status == 200:
        parent = data.get("object", {}).get("sha")
        print(f"   main = {parent}")

    # 3) 读已有提交的 tree（验证 tree 接口本身通路）
    if parent:
        status, data, _ = call("GET", f"/repos/{args.repo}/git/commits/{parent}", token)
        print(f"3) GET commit -> {status}")
        base_tree = data.get("tree", {}).get("sha") if status == 200 else None
        print(f"   base tree = {base_tree}")
    else:
        base_tree = None

    # 4) 建一个只有单条目的 tree，分别测 带/不带 base_tree
    status, blob, _ = call("POST", f"/repos/{args.repo}/git/blobs", token,
                           {"content": base64.b64encode(b"debug").decode(), "encoding": "base64"})
    print(f"4) POST blob -> {status}")
    if status not in (200, 201):
        print("   ", blob)
        return 1
    blob_sha = blob["sha"]
    print(f"   blob = {blob_sha[:12]}")

    for label, payload in [
        ("最小 tree（1 项，无 base_tree）", {"tree": [{"path": "_debug.txt", "mode": "100644", "type": "blob", "sha": blob_sha}]}),
    ]:
        status, body, _ = call("POST", f"/repos/{args.repo}/git/trees", token, payload)
        print(f"5) POST /git/trees [{label}] -> {status}")
        if status not in (200, 201):
            print("   响应体:", json.dumps(body, ensure_ascii=False)[:400])

    if base_tree:
        status, body, _ = call("POST", f"/repos/{args.repo}/git/trees", token,
                               {"base_tree": base_tree,
                                "tree": [{"path": "_debug2.txt", "mode": "100644", "type": "blob", "sha": blob_sha}]})
        print(f"6) POST /git/trees [带 base_tree] -> {status}")
        if status not in (200, 201):
            print("   响应体:", json.dumps(body, ensure_ascii=False)[:400])

    return 0


if __name__ == "__main__":
    sys.exit(main())
