"""验证回退答案的评分表碎片过滤（第 16 轮线上问题修复）。

修复前：问「我没有挂安全带」时模型失败，回退答案堆出
   物从人的正上方通过，扣10 分
   起重机吊具载运人员，扣10 分
   10
   8
   高处
   作业
修复后：这些碎片应被过滤掉，只留能读的句子。

用法：python verify_answer_fallback.py
"""

from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(APP))

from sitesaha.rag import RAGEngine, _looks_like_table_fragment  # noqa: E402

FRAGMENTS = [
    "物从人的正上方通过，扣10 分",
    "起重机吊具载运人员，扣10 分",
    "吊运易散落物件不使用吊笼，扣6 分",
    "10",
    "8",
    "高处",
    "作业",
    "未按规定设置高处作业平台",
    "应得 分",
]

REAL_SENTENCES = [
    "安全带应悬挂在牢固的结构或专用固定构件上，并应高挂低用。",
    "作业人员必须按规定正确佩戴和使用安全带。",
    "立即停止相关作业，先确认自己不会进入二次危险区域。",
    "发现配电箱进水时，应停止使用并通知持证电工处理。",
]


def main() -> int:
    print("=" * 74)
    print("一、过滤器：评分表碎片应被剔除")
    print("=" * 74)
    bad_pass = 0
    for text in FRAGMENTS:
        hit = _looks_like_table_fragment(text)
        mark = "剔除" if hit else "**漏过**"
        if not hit:
            bad_pass += 1
        print(f"  [{mark}] {text[:44]!r}")

    print()
    print("=" * 74)
    print("二、过滤器：正常句子应保留")
    print("=" * 74)
    good_pass = 0
    for text in REAL_SENTENCES:
        hit = _looks_like_table_fragment(text)
        mark = "**误杀**" if hit else "保留"
        if not hit:
            good_pass += 1
        print(f"  [{mark}] {text[:44]!r}")

    print()
    print("=" * 74)
    print("三、真实回退答案（模拟模型失败）")
    print("=" * 74)
    import webapp

    services = webapp.build_services()
    engine = services.engine
    question = "我没有挂安全带"
    sources = engine.retriever.search(question, top_k=services.config.top_k, worker_role="")
    answer = engine._extractive_answer(question, sources, "普通咨询", "绿色")
    print(answer)
    print()
    print(f"  长度 {len(answer)} 字符")
    print(f"  含『扣' + '分』字样: {'扣' in answer and '分' in answer and '扣10' in answer}")

    print()
    print("=" * 74)
    total_bad = len(FRAGMENTS)
    print(f"  碎片剔除 {total_bad - bad_pass}/{total_bad}")
    print(f"  正常句保留 {good_pass}/{len(REAL_SENTENCES)}")
    ok = bad_pass == 0 and good_pass == len(REAL_SENTENCES)
    print(f"  结论: {'通过' if ok else '有问题'}")
    print("=" * 74)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
