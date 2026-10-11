"""修复「知识领域分布」永远为空的问题。

根因：函数用「类别名」当关键词 haystack，而类别只有「公开标准 / 演示摘要」两个词，
一个风险领域关键词都命中不了，于是永远走 "暂无分类统计" 分支。
改法：改用「文档标题 + 来源文件名」匹配，并显示「N 篇 / N 段」。

用法：python fix_domain_distribution.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent
SCRIPT_A = BUILD / "index_script_a.js"
SCRIPT_B = BUILD / "index_script_b.js"

OLD = '''    function renderDomainDistribution(categories) {
      var host = clear($("sideDomains"));
      if (!host) return;
      host.setAttribute("aria-busy", "false");
      var counts = categories || {};
      var rows = DOMAIN_TOKENS.map(function (item) {
        var total = 0;
        Object.keys(counts).forEach(function (key) {
          for (var i = 0; i < item.tokens.length; i += 1) {
            if (key.indexOf(item.tokens[i]) >= 0) { total += counts[key]; return; }
          }
        });
        return { name: item.name, count: total };
      }).filter(function (row) { return row.count > 0; });
      rows.sort(function (a, b) { return b.count - a.count; });
      if (!rows.length) {
        host.appendChild(make("li", "", "\u6682\u65e0\u5206\u7c7b\u7edf\u8ba1"));
        return;
      }
      rows.slice(0, 6).forEach(function (row) {
        var li = make("li");
        li.appendChild(make("span", "", row.name));
        li.appendChild(make("span", "hot-count", row.count + " \u6bb5"));
        host.appendChild(li);
      });
    }'''

NEW = '''    function renderDomainDistribution(documents) {
      var host = clear($("sideDomains"));
      if (!host) return;
      host.setAttribute("aria-busy", "false");

      // 按「文档标题 + 来源文件名」匹配风险领域。
      // 早先版本拿"类别名"当 haystack，而类别只有「公开标准 / 演示摘要」两个词，
      // 一个领域关键词都命中不了，导致这一栏永远显示空态。
      var list = documents || [];
      var rows = DOMAIN_TOKENS.map(function (item) {
        var total = 0;
        var docs = 0;
        list.forEach(function (document) {
          var haystack = ((document.title || "") + " " + (document.source || "")).toLowerCase();
          for (var i = 0; i < item.tokens.length; i += 1) {
            if (haystack.indexOf(item.tokens[i].toLowerCase()) >= 0) {
              total += (document.chunk_count || 0);
              docs += 1;
              return;
            }
          }
        });
        return { name: item.name, count: total, docs: docs };
      }).filter(function (row) { return row.docs > 0; });

      rows.sort(function (a, b) {
        if (b.docs !== a.docs) return b.docs - a.docs;
        return b.count - a.count;
      });

      if (!rows.length) {
        host.appendChild(make("li", "", "\u77e5\u8bc6\u5e93\u4e2d\u8fd8\u6ca1\u6709\u53ef\u5f52\u7c7b\u7684\u6587\u6863"));
        return;
      }
      rows.slice(0, 6).forEach(function (row) {
        var li = make("li");
        li.appendChild(make("span", "", row.name));
        li.appendChild(make("span", "hot-count", row.docs + " \u7bc7 / " + row.count + " \u6bb5"));
        host.appendChild(li);
      });
    }'''


def main() -> int:
    a = SCRIPT_A.read_text(encoding="utf-8")
    if NEW.split("\n")[0] in a:
        print("[跳过] 已经修过了")
        return 0
    if OLD not in a:
        print("[FAIL] 未找到待替换的原函数，可能行内容有差异")
        return 1
    a = a.replace(OLD, NEW)
    SCRIPT_A.write_text(a, encoding="utf-8")
    print("[ok] renderDomainDistribution 已改为按标题匹配")

    b = SCRIPT_B.read_text(encoding="utf-8")
    if "renderDomainDistribution(categories);" in b:
        b = b.replace("renderDomainDistribution(categories);", "renderDomainDistribution(documents);")
        SCRIPT_B.write_text(b, encoding="utf-8")
        print("[ok] 调用处已改为传入 documents")
    else:
        print("[注意] 未找到调用处，请手工确认")

    # 顺手把侧栏文档清单补上来源文件名
    if "metaParts.push(document.source)" not in b:
        old_meta = '''        li.appendChild(make("div", "source-meta",
          (document.category || "\u672a\u5206\u7c7b") + " \u00b7 " + (document.chunk_count || 0) + " \u4e2a\u7247\u6bb5"));'''
        new_meta = '''        // 带上来源文件名，便于核对入库的是哪份文件
        var metaParts = [document.category || "\u672a\u5206\u7c7b"];
        if (document.source) metaParts.push(document.source);
        metaParts.push((document.chunk_count || 0) + " \u4e2a\u7247\u6bb5");
        li.appendChild(make("div", "source-meta", metaParts.join(" \u00b7 ")));'''
        if old_meta in b:
            b = b.replace(old_meta, new_meta)
            SCRIPT_B.write_text(b, encoding="utf-8")
            print("[ok] 侧栏文档清单已补来源文件名")
        else:
            print("[注意] 未找到侧栏 source-meta 代码，跳过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
