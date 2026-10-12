"""补 ill-emergency 符号 + 接入 ill-scaffold（第 21 轮，第二次尝试）。

上次 patch_illustrations.py 报告插入成功，但文件里实际没有该符号
（可能被后续步骤覆盖）。本次改用「检查-插入-立即复验」的方式，
插入后当场断言文件里确实有，避免再次静默失败。

同时把仍然没人用的 ill-scaffold 接进学习页。

用法：python fix_illustrations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
BODY = BUILD / "index_body.html"

SYMBOL = '''  <symbol id="ill-emergency" viewBox="0 0 240 130">
    <path d="M8 120h224"/>
    <path d="M30 100V70h6V56a4 4 0 0 1 8 0v14h4V52a4 4 0 0 1 8 0v18h4V58a4 4 0 0 1 8 0v16h4V66a4 4 0 0 1 8 0v20a14 14 0 0 1-14 14H44a14 14 0 0 1-14-14z"/>
    <path d="M24 44h44"/>
    <text x="24" y="36" font-size="11" fill="currentColor">1 停手</text>
    <text x="20" y="116" font-size="10" fill="currentColor">停止作业</text>
    <path d="M104 104V82a5 5 0 0 1 10 0v22"/>
    <path d="M109 74a5 5 0 1 0 0-10 5 5 0 0 0 0 10z"/>
    <path d="M104 88l-8 10M114 88l8 10"/>
    <path d="M132 92h34"/>
    <path d="M158 84l10 8-10 8"/>
    <text x="100" y="36" font-size="11" fill="currentColor">2 撤离</text>
    <text x="98" y="116" font-size="10" fill="currentColor">撤到安全区</text>
    <path d="M186 78h30a4 4 0 0 1 4 4v24a4 4 0 0 1-4 4h-30a4 4 0 0 1-4-4V82a4 4 0 0 1 4-4z"/>
    <path d="M192 96h18"/>
    <path d="M196 66c0-6 4-10 9-10s9 4 9 10"/>
    <path d="M205 56v6"/>
    <text x="184" y="36" font-size="11" fill="currentColor">3 报告</text>
    <text x="180" y="116" font-size="10" fill="currentColor">报告负责人</text>
  </symbol>

'''

SCAFFOLD_FIGURE = '''      <figure class="ill-figure ill-scaffold">
        <svg viewBox="0 0 240 130" role="img" aria-labelledby="illScaffoldLabel">
          <title id="illScaffoldLabel">脚手架安全做法：立杆、剪刀撑、扫地杆、作业层防护齐全</title>
          <use href="#ill-scaffold"/>
        </svg>
        <figcaption>脚手架要点：立杆与剪刀撑齐全、设扫地杆、作业层防护完整。搭拆必须由持证人员按方案进行。</figcaption>
      </figure>

'''


def main() -> int:
    body = BODY.read_text(encoding="utf-8")
    changed = 0

    # ---- 1) 补符号 ----
    if 'id="ill-emergency"' in body:
        print("  [跳过] ill-emergency 符号已存在")
    else:
        anchor = '  <symbol id="ill-ppe" viewBox="0 0 240 130">'
        if anchor not in body:
            print("  [FAIL] 找不到 ill-ppe 锚点")
            return 1
        body = body.replace(anchor, SYMBOL + anchor, 1)
        # 立即复验
        if 'id="ill-emergency"' not in body:
            print("  [FAIL] 插入后复验失败")
            return 1
        changed += 1
        print("  [ok] ill-emergency 符号已插入并复验通过")

    # ---- 2) 接入 ill-scaffold 到学习页 ----
    if 'class="ill-figure ill-scaffold"' in body:
        print("  [跳过] ill-scaffold 已接入")
    else:
        # 放在「培训路线」面板之前
        target = None
        for candidate in ('<h2>新人 5 步培训路线</h2>',
                          '<h2>培训路线</h2>',
                          'id="stepList"'):
            if candidate in body:
                target = candidate
                break
        if target:
            index = body.find(target)
            start = body.rfind('<div class="panel"', 0, index)
            if start > 0:
                body = body[:start] + SCAFFOLD_FIGURE + body[start:]
                changed += 1
                print("  [ok] ill-scaffold 已接入学习页")
            else:
                print("  [注意] 找不到 panel 起点")
        else:
            print("  [注意] 找不到学习页接入点")

    if body.count(chr(92)):
        print("[FAIL] body 含反斜杠")
        return 1

    BODY.write_text(body, encoding="utf-8")

    # ---- 3) 写盘后第三次复验 ----
    verify = BODY.read_text(encoding="utf-8")
    print()
    print("  写盘后复验：")
    ok = True
    for sid in ("ill-edge", "ill-scaffold", "ill-ppe", "ill-emergency"):
        defined = verify.count(f'id="{sid}"')
        used = verify.count(f'href="#{sid}"')
        status = "OK" if (defined and used) else "**问题**"
        if not (defined and used):
            ok = False
        print(f"    {sid:<16} 定义 {defined}  引用 {used}  {status}")
    print()
    print(f"[ok] 已写入（{changed} 处），复验{'通过' if ok else '未通过'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
