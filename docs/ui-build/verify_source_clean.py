"""验证 cleanSourceText 能清掉真实条文里的碎片（第 16 轮线上乱码修复）。

用线上实际返回的 5 条来源正文做输入，看清理结果。

用法：python verify_source_clean.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

BUILD = Path(__file__).resolve().parent
NODE = r"C:\Users\sht18\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"
BASE = "https://sitesaha-ai-v16.onrender.com"

# 从真实返回里取来源（内置一份兜底样本，避免线上抖动）
FALLBACK_SOURCES = [
    {
        "title": "建筑施工安全检查标准 JGJ59-2011",
        "heading": "建筑施工安全检查标准 JGJ59-2011 / 第 92 页",
        "content": (
            "91\n"
            "起重吊装作业前应结合施工实际， 编制专项施工方案， 并应给单位技术负责人进行审核。\n"
            "采用起重拔杆等非常规起重设备且单件起重量超过100kN 时，专项施工方案应经专家论证。\n"
            "2 起重机械\n荷载限制器：当荷载达到额定起重量的95%时，限制器宜发出警报；"
            "当荷载达到额定起重量的100%～110%时，限制器应切断起升动力主电路。"
        ),
    },
    {
        "title": "建筑施工安全检查标准 JGJ59-2011",
        "heading": "建筑施工安全检查标准 JGJ59-2011 / 第 67 页",
        "content": (
            "物从人的正上方\n通过，扣10 分\n起重机吊具载运人员，扣10 分\n"
            "吊运易散落物件不使用吊笼，扣6 分\n10\n8\n高处\n作业\n"
            "未按规定设置高处作业平台，扣10 分\n"
            "高处作业平台设置不符合规范要求，扣5～10 分\n"
            "未按规定设置安全带悬挂点，扣8 分\n10"
        ),
    },
    {
        "title": "现场工友安全问答摘要",
        "heading": "现场工友安全问答摘要 / 高处作业 / 开始前",
        "content": "确认作业平台、脚手架、临边和洞口防护完整。安全带应检查外观，"
                   "可靠挂点应能承受坠落冲击，使用时优先高挂低用。"
                   "作业下方应设置警戒，避免交叉作业落物伤人。",
    },
]


def fetch_sources() -> list[dict]:
    request = urllib.request.Request(
        BASE + "/api/ask",
        data=json.dumps({"question": "我没有挂安全带"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=150) as response:
            data = json.loads(response.read().decode("utf-8"))
        sources = data.get("sources") or []
        return sources if sources else FALLBACK_SOURCES
    except Exception as exc:  # noqa: BLE001
        print(f"  （线上取源失败：{type(exc).__name__}，用内置样本）")
        return FALLBACK_SOURCES


def extract_js_function() -> str:
    """从分片里把 cleanSourceText 及其正则依赖抽出来，交给 node 跑。"""
    script = (BUILD / "index_script_b.js").read_text(encoding="utf-8")
    start = script.find("    var RE_ONLY_DIGITS")
    end = script.find("    function sourceBlock(answer) {")
    if start < 0 or end < 0:
        raise RuntimeError("分片里找不到清理函数")
    return script[start:end]


def main() -> int:
    sources = fetch_sources()
    print("=" * 78)
    print(f"用 {len(sources)} 条真实来源测试清理函数")
    print("=" * 78)

    body: list[dict] = []
    for index, source in enumerate(sources, 1):
        content = source.get("content") or ""
        body.append({"index": index, "title": source.get("title") or "",
                     "heading": source.get("heading") or "", "content": content})
        print(f"\n--- 依据 [{index}] {body[-1]['title'][:44]}（原文 {len(content)} 字符）---")
        print("  原文前 130 字:")
        print("    " + content[:130].replace("\n", " / "))

    js = extract_js_function()
    payload = json.dumps(body, ensure_ascii=False)

    driver = f"""
{js}
const sources = {payload};
const out = [];
sources.forEach((s) => {{
  const cleaned = cleanSourceText(s.content);
  out.push({{ index: s.index, original: s.content.length, cleaned: cleaned.length,
              text: cleaned }});
}});
console.log(JSON.stringify(out));
"""
    path = Path(tempfile.gettempdir()) / "_clean_test.js"
    path.write_text(driver, encoding="utf-8")
    result = subprocess.run([NODE, str(path)], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60)
    if result.returncode != 0:
        print("\n[FAIL] node 执行失败:", (result.stderr or "")[-300:])
        return 1

    cleaned_list = json.loads(result.stdout.strip())

    print()
    print("=" * 78)
    print("清理结果")
    print("=" * 78)

    bad_markers = ["扣10", "扣6", "扣8", "扣5", "应得", "实得"]
    leftovers: list[str] = []

    for item in cleaned_list:
        print(f"\n--- 依据 [{item['index']}] ---")
        print(f"  原文 {item['original']} 字符 → 清理后 {item['cleaned']} 字符")
        print(f"  结果: {item['text']!r}")
        for marker in bad_markers:
            if marker in item["text"]:
                leftovers.append(f"[{item['index']}] {marker}")

    print()
    print("=" * 78)
    if leftovers:
        print(f"  ❌ 仍有碎片: {sorted(set(leftovers))}")
        return 1
    print("  ✅ 评分表碎片已全部清除")
    total_before = sum(i["original"] for i in cleaned_list)
    total_after = sum(i["cleaned"] for i in cleaned_list)
    print(f"  页面文字量: {total_before} → {total_after} 字符"
          f"（减少 {100 - round(total_after / max(total_before, 1) * 100)}%）")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
