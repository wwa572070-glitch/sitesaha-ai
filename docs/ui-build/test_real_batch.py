"""批量跑真实工地照片识别（第 24 轮，答辩素材预演）。

把用户提供的 6 张真实工地照片逐张跑一遍真实视觉模型，
汇总成对比表，用于预判答辩演示效果。

用法：python test_real_batch.py
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
BUILD = Path(__file__).resolve().parent
ATTACH = Path(r"C:\Users\sht18\.dsh\attachments\v1\objects")
STORE = BUILD / "evidence" / "real-site"
BASE = "http://127.0.0.1:8504"
BOUNDARY = "----RealBatch7c3"

# 附件对象 id → 便于辨认的名字
PHOTOS = [
    ("69c1e956a25ddd3b28d98d75d7220983", "55/551bc9d2e43a8623d2cd182a2f90b2ce5b03c2f974be124e53005ff0b80864b9",
     "模板支撑架体", "jpg"),
    ("cde825df499e3f587648fd2cf3124031", "25/25e5ef14bead6f827e4653cba8c30530e4d06b693256c7218789b1536ae57510",
     "满堂脚手架（有工人）", "jpg"),
    ("d0708c122ff4097ea972372432b680fe", "3e/3e8707f2927812513ac83ef26c946a9d2a3de134fedcf5102e88e9cb8512aa7a",
     "盘扣架体密集区", "jpg"),
    ("49e60d08ec2ccfcf026cfb8e99ad3ee7", "86/86e7438dac9c37a9cd4c65bb21be92fda3d1479c33cc66542ddced8bdca5a30a",
     "现场全景（塔吊/挖机）", "jpg"),
    ("7ea9a445da1e4978a0bf67f5e6cb0ead", "85/85ccefd64816ba95738b3ba7740942556fb1f13480b9ae58bca503ad0177c6af",
     "电力线路高空作业", "jpg"),
    ("659aa96004db9cc8d44ec63efc44d6d1", "11/1144ad22d907754b8cbe3ee276d638a666ac08578e427971ea9cea26537ef3a3",
     "深基坑（混凝土墙+钢筋）", "jpg"),
]


def collect() -> list[tuple[str, str, Path]]:
    STORE.mkdir(parents=True, exist_ok=True)
    found: list[tuple[str, str, Path]] = []
    for index, (short, tail, name, ext) in enumerate(PHOTOS, 1):
        source = ATTACH / tail
        if not source.is_file():
            print(f"  [缺少] {name}  ({short[:8]})")
            continue
        target = STORE / f"{index:02d}-{short[:8]}.{ext}"
        shutil.copyfile(source, target)
        found.append((name, short[:8], target))
        print(f"  [已存] {name}  {target.stat().st_size // 1024} KB")
    return found


def inspect(path: Path):
    data = path.read_bytes()
    body = b"".join([
        (f"--{BOUNDARY}\r\n"
         f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
         f"Content-Type: image/jpeg\r\n\r\n").encode(),
        data, b"\r\n", f"--{BOUNDARY}--\r\n".encode(),
    ])
    request = urllib.request.Request(
        BASE + "/api/inspect-image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            return json.loads(response.read().decode("utf-8")), time.time() - started, 200
    except urllib.error.HTTPError as exc:
        return {"error": exc.read().decode("utf-8", "replace")[:200]}, time.time() - started, exc.code
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}, time.time() - started, 0


def main() -> int:
    print("=" * 78)
    print("一、收存照片")
    print("=" * 78)
    photos = collect()
    if not photos:
        print("没有可用照片")
        return 1

    results = []
    print()
    print("=" * 78)
    print("二、逐张真实识别")
    print("=" * 78)
    for name, short, path in photos:
        payload, elapsed, status = inspect(path)
        results.append((name, short, payload, elapsed, status))
        print(f"\n--- {name}  [{short}]  HTTP {status}  {elapsed:.1f}s ---")
        if "error" in payload:
            print(f"  失败：{payload['error']}")
            continue
        structured = payload.get("structured") or {}
        print(f"  image_quality = {payload.get('image_quality')}"
              + ("  rejected" if payload.get("rejected") else ""))
        print(f"  作业场景：{structured.get('work_type') or '（未识别）'}")
        risks = structured.get("risks") or []
        print(f"  可见风险 {len(risks)} 条：")
        for item in risks:
            if not isinstance(item, dict):
                continue
            print(f"    · [{item.get('where') or '?'}] {item.get('what') or ''}")
            action = (item.get("action") or "").strip()
            if action:
                print(f"      动作：{action}")
        uncertain = structured.get("uncertain") or []
        if uncertain:
            print(f"  待确认 {len(uncertain)} 项：{str(uncertain[0])[:70]}")

    print()
    print("=" * 78)
    print("三、汇总（答辩演示参考）")
    print("=" * 78)
    print(f"  {'照片':<22}{'耗时':>7}{'风险':>6}  作业场景")
    print("  " + "-" * 68)
    ok = 0
    for name, short, payload, elapsed, status in results:
        if "error" in payload:
            print(f"  {name:<22}{'—':>7}{'—':>6}  失败：{str(payload['error'])[:36]}")
            continue
        structured = payload.get("structured") or {}
        count = len(structured.get("risks") or [])
        work = str(structured.get("work_type") or "（未识别）")
        print(f"  {name:<22}{elapsed:>6.1f}s{count:>6}  {work[:40]}")
        ok += 1
    print("  " + "-" * 68)
    print(f"  成功 {ok}/{len(results)} 张")

    # 存一份完整结果，便于后续比对
    dump = STORE / "_results.json"
    dump.write_text(json.dumps(
        [{"name": n, "short": s, "status": st, "elapsed": round(e, 1),
          "structured": p.get("structured"), "quality": p.get("image_quality"),
          "error": p.get("error")}
         for n, s, p, e, st in results],
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  完整结果已存：{dump.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
