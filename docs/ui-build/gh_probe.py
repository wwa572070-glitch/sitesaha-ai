"""用 GitHub REST API 探测令牌权限与仓库状态（只读，不改动任何东西）。

用法：set GITHUB_TOKEN=ghp_xxx 然后 python gh_probe.py

安全约定：绝不打印令牌本身，只打印它的属性和探测结果。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"


def call(path: str, token: str) -> tuple[int, dict, dict]:
    request = urllib.request.Request(
        API + path,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "sitesaha-push-check",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8", "replace")
            return response.status, json.loads(body or "{}"), dict(response.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body or "{}")
        except json.JSONDecodeError:
            parsed = {"raw": body[:200]}
        return exc.code, parsed, dict(exc.headers or {})
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": f"{type(exc).__name__}: {exc}"}, {}


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[FAIL] 未设置 GITHUB_TOKEN 环境变量")
        return 1
    print(f"令牌长度 {len(token)}，前缀 {token[:4]}…（不打印完整内容）")

    status, data, headers = call("/user", token)
    print(f"\n1) 令牌身份 /user -> HTTP {status}")
    if status == 200:
        print(f"   登录账号: {data.get('login')}")
        print(f"   账号类型: {data.get('type')}")
        scopes = headers.get("X-OAuth-Scopes", "(未返回)")
        print(f"   令牌权限: {scopes}")
    else:
        print(f"   {data}")
        print("   令牌无效或已过期，后面的检查没意义。")
        return 1

    status, data, _ = call("/repos/gaochu996-code/sitesaha-ai", token)
    print(f"\n2) 目标仓库 gaochu996-code/sitesaha-ai -> HTTP {status}")
    if status == 200:
        print(f"   名称: {data.get('full_name')}")
        print(f"   私有: {data.get('private')}")
        print(f"   默认分支: {data.get('default_branch')}")
        print(f"   是否为空仓库: {data.get('size') == 0}")
        perms = data.get("permissions", {})
        print(f"   当前令牌权限: push={perms.get('push')} admin={perms.get('admin')}")
        if not perms.get("push"):
            print("   [问题] 该令牌对这个仓库没有 push 权限，推送会 403")
    elif status == 404:
        print("   404：仓库不存在，或令牌账号无权看到它。")
    else:
        print(f"   {data}")

    status, data, _ = call("/user/repos?per_page=100&sort=updated", token)
    print(f"\n3) 令牌可访问的仓库 -> HTTP {status}")
    if status == 200 and isinstance(data, list):
        print(f"   共 {len(data)} 个：")
        for repo in data[:12]:
            print(f"     - {repo.get('full_name')}  (私有={repo.get('private')})")
    else:
        print(f"   {data}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
