"""§11 接口验收（第 16 轮）。

覆盖：
  · /api/checklists 未被破坏（原有接口回归）
  · /api/checklists/conditions 返回全部条件
  · /api/checklists/generate 按条件生成（验收：动火+高温）
  · /api/checklists/import 接受 csv 与 xlsx，并标出错误行

用法：python verify_checklist_api.py
"""

from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8504"
BOUNDARY = "----VerifyChecklist9c2f"


def get(path: str):
    try:
        with urllib.request.urlopen(BASE + path, timeout=30) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:200]
    except Exception as exc:  # noqa: BLE001
        return 0, json.dumps({"client_error": f"{type(exc).__name__}: {exc}"})


def post_json(path: str, body: dict):
    request = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:300]
    except Exception as exc:  # noqa: BLE001
        return 0, json.dumps({"client_error": f"{type(exc).__name__}: {exc}"})


def post_file(path: str, filename: str, data: bytes, mime: str):
    body = (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + data + f"\r\n--{BOUNDARY}--\r\n".encode()
    request = urllib.request.Request(
        BASE + path, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:300]
    except Exception as exc:  # noqa: BLE001
        return 0, json.dumps({"client_error": f"{type(exc).__name__}: {exc}"})


def main() -> int:
    results: list[tuple[str, bool]] = []

    print("=" * 78)
    print("一、原有接口回归")
    print("=" * 78)
    status, body = get("/api/checklists")
    data = json.loads(body) if status == 200 and body.startswith("{") else {}
    ok = status == 200 and len(data.get("categories") or []) == 9
    print(f"  /api/checklists  HTTP {status}  必查 {len(data.get('priority_checks') or [])} "
          f"/ 类别 {len(data.get('categories') or [])}")
    results.append(("原有 /api/checklists 未破坏", ok))

    print()
    print("=" * 78)
    print("二、条件清单")
    print("=" * 78)
    status, body = get("/api/checklists/conditions")
    data = json.loads(body) if status == 200 and body.startswith("{") else {}
    weather = data.get("weather") or []
    work = data.get("work") or []
    print(f"  HTTP {status}  天气环境 {len(weather)} 项 / 当班作业 {len(work)} 项")
    if weather:
        print("   " + "、".join(item["label"] for item in weather))
    if work:
        print("   " + "、".join(item["label"] for item in work))
    results.append(("conditions 返回全部条件", status == 200 and len(weather) + len(work) == 17))

    print()
    print("=" * 78)
    print("三、按条件生成（§11.D 验收：动火 + 高温）")
    print("=" * 78)
    status, body = post_json("/api/checklists/generate", {"conditions": ["hotwork", "heat"]})
    data = json.loads(body) if status == 200 and body.startswith("{") else {}
    required = data.get("required") or []
    blob = " ".join(item.get("content", "") for item in required)
    print(f"  HTTP {status}  必查 {len(required)} 条")
    for item in required:
        print(f"   {item['code']} [{item['source']}] {item['content'][:44]}")
    need = ["动火许可证", "看火人", "灭火器材", "防暑"]
    missing = [word for word in need if word not in blob]
    has_reason = all(item.get("source") for item in required)
    results.append(("动火+高温出现许可/看火人/灭火器/防暑",
                    status == 200 and not missing))
    results.append(("每条必查都带命中理由", has_reason))

    print()
    print("=" * 78)
    print("四、不选条件")
    print("=" * 78)
    status, body = post_json("/api/checklists/generate", {"conditions": []})
    data = json.loads(body) if status == 200 and body.startswith("{") else {}
    routine = data.get("routine") or []
    print(f"  HTTP {status}  必查 {len(data.get('required') or [])} / 常规 {len(routine)}")
    results.append(("不选条件退回基础清单", status == 200 and len(routine) > 0
                    and not (data.get("required") or [])))

    print()
    print("=" * 78)
    print("五、导入文件（§11.D 验收：6 行含 1 行错）")
    print("=" * 78)
    csv_text = (
        "类别,检查内容,判定要点,依据\n"
        "临时设施,宿舍内是否使用大功率电器,无电炉热得快,项目制度\n"
        "消防,灭火器压力表是否在绿区,指针在绿区,项目制度\n"
        "塔吊,塔吊基础是否有积水,无积水,项目制度\n"
        ",乙,,\n"
        "高处,高处作业平台是否设置防坠栏杆,栏杆齐全,项目制度\n"
    ).encode("utf-8")
    status, body = post_file("/api/checklists/import", "check.csv", csv_text, "text/csv")
    data = json.loads(body) if status == 200 and body.startswith("{") else {}
    accepted = data.get("accepted") or []
    rejected = data.get("rejected") or []
    print(f"  csv  HTTP {status}  通过 {len(accepted)} / 拒绝 {len(rejected)}")
    for item in rejected:
        print(f"    [错误行 {item.get('row')}] {item.get('content')!r} → {item.get('error')}")
    for item in accepted:
        print(f"    {item['code']} {item['content'][:40]}  ({item['origin']})")
    ok_csv = status == 200 and len(rejected) == 1 and len(accepted) == 4
    results.append(("csv 导入：标错误行 + 正确行入库", ok_csv))
    results.append(("导入内容标注为项目自有文件",
                    all(item.get("origin") == "项目自有文件" for item in accepted)))

    # xlsx
    try:
        from openpyxl import Workbook
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["类别", "检查内容", "判定要点", "依据"])
        sheet.append(["消防", "消火栓是否被遮挡", "无遮挡", "项目制度"])
        buffer = io.BytesIO()
        workbook.save(buffer)
        status, body = post_file(
            "/api/checklists/import", "check.xlsx", buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        data = json.loads(body) if status == 200 and body.startswith("{") else {}
        print(f"  xlsx HTTP {status}  通过 {len(data.get('accepted') or [])} "
              f"/ 文件 {data.get('filename')}")
        results.append(("xlsx 导入可用", status == 200 and len(data.get("accepted") or []) == 1))
    except ImportError:
        print("  (没有 openpyxl，跳过 xlsx)")

    print()
    print("=" * 78)
    for name, ok in results:
        print(f"  [{'pass' if ok else 'FAIL'}] {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"\n通过 {passed}/{len(results)}")
    print("=" * 78)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
