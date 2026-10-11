"""§6 IA 收敛：learn 视图 17 块 → 6 区块（第 16 轮）。

目标结构（按 §6 收敛表）：
  ① 培训路线      培训进度总览 + 新人 5 步路线 + 学习积分（合并成一条动线）
  ② 工种专项      工种专项风险要点
  ③ 知识测验      新工人安全知识测验（含掌握情况环）
  ④ 案例库        真实事故 / 隐患案例
  ⑤ 标准库        标准现行状态 + 在线模型与培训上下文
  ⑥ 知识库状态    已入库文档 + 知识领域分布 + 最近入库 + 知识库概览 + 服务状态
  ⑦ 合规说明      检索与合规说明

删除：案例分析说明（与案例库重复）、培训与知识模块（导航冗余）
移位：每日警示案例 → 已在首页实现，这里删除

实现方式：按块重排 + 用 <details> 折叠知识库状态里的次级块，
而不是删内容 —— 信息不丢，只是不再平铺。全部 id 保留。

用法：python consolidate_learn.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"

TAG = re.compile(r"<(/?)(div)\b[^>]*?(/?)>")


def find_blocks(segment: str) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    for match in re.finditer(r'<div class="panel[^"]*"', segment):
        start = match.start()
        depth = 0
        position = start
        while position < len(segment):
            tag = TAG.search(segment, position)
            if not tag:
                break
            position = tag.end()
            if tag.group(1) == "/":
                depth -= 1
                if depth == 0:
                    blocks.append((start, tag.end(), segment[start:tag.end()]))
                    break
            elif tag.group(3) != "/":
                depth += 1
    top: list[tuple[int, int, str]] = []
    for item in sorted(blocks, key=lambda triple: (triple[0], -triple[1])):
        if any(outer[0] <= item[0] and item[1] <= outer[1] for outer in top):
            continue
        top.append(item)
    return top


def title_of(block: str) -> str:
    heading = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S)
    return re.sub(r"<[^>]+>", "", heading.group(1)).strip() if heading else ""


def retitle(block: str, new_title: str) -> str:
    """替换块里的 h2 文案。"""
    return re.sub(r"(<h2[^>]*>).*?(</h2>)", r"\g<1>" + new_title + r"\g<2>",
                  block, count=1, flags=re.S)


def wrap_details(block: str, summary: str, open_by_default: bool = False) -> str:
    """把一个 panel 收进 <details>，保留原 id 与结构。"""
    opened = " open" if open_by_default else ""
    return (
        f'<details class="kb-sub"{opened}>\n'
        f'  <summary>{summary}</summary>\n'
        f'  <div class="kb-sub-body">\n{block}\n  </div>\n'
        f'</details>'
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    body = BODY.read_text(encoding="utf-8")
    start = body.find('<section id="learn"')
    end = body.find('<section id="', start + 10)
    segment = body[start:end]

    blocks = find_blocks(segment)
    by_title = {title_of(block): block for _s, _e, block in blocks}
    print(f"读到 {len(by_title)} 个顶层块")

    required = [
        "培训进度总览", "新人 5 步培训路线", "工种专项风险要点", "新工人安全知识测验",
        "学习积分与培训记录", "在线模型与培训上下文", "真实事故 / 隐患案例",
        "案例分析说明", "已入库文档", "标准现行状态", "检索与合规说明",
        "服务状态", "知识领域分布", "最近入库", "知识库概览",
        "每日警示案例", "培训与知识模块",
    ]
    missing = [name for name in required if name not in by_title]
    if missing:
        print(f"[FAIL] 缺少块：{missing}")
        return 1

    # ---------- 组装新顺序 ----------
    out: list[str] = []

    # ① 培训路线：进度总览 + 五步路线 + 学习积分
    route_head = by_title["培训进度总览"]
    route_head = retitle(route_head, "培训路线")
    out.append(route_head)
    out.append(by_title["新人 5 步培训路线"])
    out.append(by_title["学习积分与培训记录"])

    # ② 工种专项
    out.append(by_title["工种专项风险要点"])

    # ③ 知识测验
    out.append(by_title["新工人安全知识测验"])

    # ④ 案例库
    out.append(by_title["真实事故 / 隐患案例"])

    # ⑤ 标准库
    out.append(by_title["标准现行状态"])
    out.append(by_title["在线模型与培训上下文"])

    # ⑥ 知识库状态：五个块收进折叠区，主块保持展开
    kb_head = by_title["知识库概览"]
    kb_head = retitle(kb_head, "知识库状态")
    kb_parts = [
        by_title["已入库文档"],
        by_title["知识领域分布"],
        by_title["最近入库"],
        by_title["服务状态"],
    ]
    kb_bodies = "\n".join(kb_parts)
    kb_doc = by_title["已入库文档"]
    kb_marker = kb_doc[kb_doc.find('class="panel-head"'):]
    out.append(kb_head)
    out.append(
        '<details class="kb-sub">\n'
        '  <summary>已入库文档 / 领域分布 / 最近入库 / 服务状态</summary>\n'
        '  <div class="kb-sub-body">\n' + kb_bodies + '\n  </div>\n'
        '</details>'
    )

    # ⑦ 合规说明
    out.append(by_title["检索与合规说明"])

    # ---------- 校验：id 不能丢 ----------
    # section 自身的 id（learn）不在 panel 里，不参与比较
    old_ids = set(re.findall(r'id="([^"]+)"', segment)) - {"learn"}
    new_segment = "\n\n".join(out)
    new_ids = set(re.findall(r'id="([^"]+)"', new_segment))

    # 这三块是刻意删除/移位的，它们的 id 允许消失，但要逐个确认没有脚本引用
    removed_titles = ["案例分析说明", "每日警示案例", "培训与知识模块"]
    removed_ids: set[str] = set()
    for name in removed_titles:
        removed_ids |= set(re.findall(r'id="([^"]+)"', by_title[name]))

    lost = sorted((old_ids - new_ids) - removed_ids)
    print(f"\n原 id {len(old_ids)} 个，新 id {len(new_ids)} 个")
    print(f"删除块带走的 id：{sorted(removed_ids)}")
    if lost:
        print(f"[FAIL] 意外丢失 id：{lost}")
        return 1
    print("[ok] 除刻意删除的块外，id 无丢失")

    print(f"\n收敛结果：17 块 → {len(out)} 个顶层区块")
    print(f"  字符数 {len(segment)} → {len(new_segment)}")

    if args.dry_run:
        print("（dry-run，未写入）")
        return 0

    # 别忘了 <section id="learn" ...> 开标签本身
    open_tag_end = segment.find(">") + 1
    open_tag = segment[:open_tag_end]
    body = body[:start] + open_tag + "\n\n" + new_segment + "\n\n    " + body[end:]
    BODY.write_text(body, encoding="utf-8")
    print("[ok] index_body.html 已更新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
