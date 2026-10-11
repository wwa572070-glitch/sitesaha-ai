"""校验拼装后模板里的 JavaScript 语法，并检查关键实现是否真的落地。

用法：python check_js.py
产物：_build/index_script_check.js（仅供 node --check 使用，可随时重建）
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
FULL = BUILD / "index_full.html"
CHECK_FILE = BUILD / "index_script_check.js"

NODE_CANDIDATES = [
    Path(r"C:\Users\sht18\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"),
    Path("node"),
]

# 关键实现标记：缺失说明功能没真正接上
REQUIRED_MARKERS = {
    "问答会话流": "appendAnswer",
    "工种上下文": "worker_role",
    "培训数据接口": "/api/training",
    "案例接口": "/api/cases",
    "检查清单接口": "/api/checklists",
    "测验判分": "finishQuiz",
    "掌握度环": "ring-offset",    "本地学习记录": "sitesaha-quiz-v1",
    "开工检查持久化": "sitesaha-checklist-v1",
    "应急处置步骤": "showEmergencyGuide",
    "知识库分组": "renderDocumentGroups",
    "文档检索高亮": "appendHighlighted",
    "三件事进度": "updatePracticalProgress",
    "学习积分": "computePoints",
    "培训记录单": "buildCertificate",
    "拍照压缩": "compressImage",
    "语音转写": "/api/transcribe",
    "访问码兼容": "X-Access-Code",
}


def main() -> int:
    full = FULL.read_text(encoding="utf-8")
    match = re.search(r"<script>(.*?)</script>", full, re.S)
    if not match:
        print("[FAIL] 未找到 script 块")
        return 1
    script = match.group(1)
    CHECK_FILE.write_text(script, encoding="utf-8")

    node = next((str(path) for path in NODE_CANDIDATES if path.is_file()), None)
    problems: list[str] = []

    if node:
        result = subprocess.run(
            [node, "--check", str(CHECK_FILE)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            print("JS syntax (node --check): OK")
        else:
            print("JS syntax: FAILED")
            print((result.stdout or "") + (result.stderr or ""))
            problems.append("JS 语法错误")
    else:
        print("node 未找到，跳过 node --check")

    for label, marker in REQUIRED_MARKERS.items():
        if marker not in script:
            problems.append(f"缺少关键实现：{label}（{marker}）")

    print(f"script lines={script.count(chr(10))} chars={len(script)}")
    print(f"IIFE wrap: {'OK' if script.strip().startswith('(function ()') else 'FAIL'}")
    print(f"init 调用: {'OK' if 'init();' in script else 'FAIL'}")

    if problems:
        for item in problems:
            print("  [FAIL]", item)
        return 1
    print("JS check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
