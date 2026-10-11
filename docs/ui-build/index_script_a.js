  <script>
  (function () {
    "use strict";

    /* ===== THEME BOOT BEGIN ===== */
    /* 主题：默认白天（方案 C：纯白 + 单一蓝），可切夜间（方案 B：深蓝黑 + 明黄）。
       这段必须在 <head> 里同步执行——放到文件末尾的话，
       夜间用户会先看到一帧亮色界面再被切暗（闪白）。 */
    (function () {
      var KEY = "sitesaha-theme-v1";

      /* URL 上的 ?theme=dark / ?theme=light 只影响本次访问，不写入 localStorage。
         用于演示、截图核对和排查配色问题。
         注意：这里刻意不用正则，也不用任何反斜杠转义——
         分片文件必须保持零反斜杠，否则 inject.py 无法安全地写入 Python 字符串。 */
      function fromQuery() {
        try {
          var query = String(window.location.search || "");
          if (query.charAt(0) === "?") query = query.slice(1);
          if (!query) return "";
          var parts = query.split("&");
          for (var i = 0; i < parts.length; i += 1) {
            var pair = parts[i].split("=");
            if (decodeURIComponent(pair[0] || "") !== "theme") continue;
            var value = decodeURIComponent(pair[1] || "").toLowerCase();
            if (value === "dark" || value === "light") return value;
          }
          return "";
        } catch (e) {
          return "";
        }
      }

      function preferred() {
        var forced = fromQuery();
        if (forced) return forced;
        var saved = "";
        try { saved = window.localStorage.getItem(KEY) || ""; } catch (e) { saved = ""; }
        if (saved === "dark" || saved === "light") return saved;
        try {
          if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
            return "dark";
          }
        } catch (e) { /* 不支持 matchMedia 时按白天处理 */ }
        return "light";
      }

      function paint(theme) {
        var root = document.documentElement;
        if (theme === "dark") root.setAttribute("data-theme", "dark");
        else root.removeAttribute("data-theme");
        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.setAttribute("content", theme === "dark" ? "#0e1c28" : "#17385c");
        var button = document.getElementById("themeToggle");
        if (button) {
          button.replaceChildren(iconText("i-clock", theme === "dark" ? "白天" : "夜间"));
          button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
        }
      }

      window.__sitesahaTheme = {
        preferred: preferred,
        paint: paint,
        toggle: function () {
          var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
          paint(next);
          try { window.localStorage.setItem(KEY, next); } catch (e) { /* 隐私模式忽略 */ }
        },
      };

      // 立即上色，不等 DOMContentLoaded
      paint(preferred());
      // 顶栏按钮在页面主体里，解析到之后补一次文案
      // （注意：注释里不要写尖括号标签，assemble.py 的标签计数会把它算进去）
      document.addEventListener("DOMContentLoaded", function () {
        paint(preferred());
      });
    })();
    /* ===== THEME BOOT END ===== */

    /* ==================================================================
       1. 常量与本地存储
       ================================================================== */
    var ACCESS_CODE_KEY = "sitesaha-access-code";
    var PROFILE_KEY = "sitesaha-profile-v1";
    var CHECKLIST_KEY = "sitesaha-checklist-v1";
    var QUIZ_KEY = "sitesaha-quiz-v1";
    var PRACTICAL_KEY = "sitesaha-practical-v1";
    var EMPTY_QUIZ = { attempts: 0, bestPercent: 0, bestCorrect: 0, total: 20, lastCorrect: 0, lastAt: "", wrongDomains: {}, seen: {} };

    /* 今天上工前的三件事（第一条为入场三件事合并项，共 5 条） */
    var PRACTICAL_ITEMS = [
      { id: "entry", step: 1, label: "入口三件事已完成", hint: "实名进场、安全教育、班前交底都确认过" },
      { id: "ppe", step: 1, label: "安全帽下颚带、防护鞋和必要防护用品已到位", hint: "按当天作业风险选用，破损失效立即更换" },
      { id: "hazard", step: 2, label: "知道今天的风险点、禁区和撤离路线", hint: "临边洞口、吊装区、配电区、基坑边在哪里" },
      { id: "machine", step: 3, label: "设备和工具开机前检查过防护、限位和急停", hint: "有异常先停机断电挂牌，不自己拆修" },
      { id: "stop", step: 4, label: "不确定的事不硬上，先停工问负责人", hint: "赶工和评分不能替代安全底线" },
    ];

    /* 班前动线的四步（§7 方向 2）。
       分组参照旧版手册：进门 → 风险 → 机具 → 停。
       注意：勾选项一条都没减少（用户要求"不合并"），只是按步骤归位。 */
    var PRACTICAL_STEPS = [
      { n: 1, title: "进门先过关", note: "没交底、没防护，不上岗" },
      { n: 2, title: "先弄清风险", note: "知道哪里危险、往哪撤" },
      { n: 3, title: "再检查机具", note: "设备带病不上手" },
      { n: 4, title: "不确定就停", note: "停下来问，比硬上便宜" },
    ];

    /* 现场问答快捷问题：带工种标签，按工种高亮 */
    /* 快捷提问按场景分组（第 16 轮 §6：每组 ≤4 个，超出折叠）。
       分组按新工人实际会遇到的场景，不是按专业分类。 */
    var QUICK_GROUPS = [
      {
        title: "第一天上工",
        hint: "刚进场，先弄清这几件",
        items: [
          { text: "我是第一次上工地，入场后先做什么？", roles: [] },
          { text: "进入施工现场必须做哪些防护？", roles: [] },
        ],
      },
      {
        title: "常见高风险",
        hint: "这些场景出事最多",
        items: [
          { text: "高处作业前要检查什么？", roles: ["架子工", "钢筋工", "木工", "焊工", "电工", "普工/杂工"] },
          { text: "吊物下方为什么不能站人？", roles: [] },
          { text: "基坑出现裂缝和渗水怎么处理？", roles: ["普工/杂工", "钢筋工"] },
          { text: "动火作业前要做哪些确认？", roles: ["焊工"] },
        ],
      },
      {
        title: "本工种专项",
        hint: "按你选的工种出题",
        collapsed: true,
        items: [
          { text: "脚手架验收牌有什么作用？", roles: ["架子工"] },
          { text: "发现配电箱进水怎么办？", roles: ["电工"] },
          { text: "钢筋加工机械清理前要做什么？", roles: ["钢筋工"] },
          { text: "圆盘锯的防护罩能拆掉吗？", roles: ["木工"] },
        ],
      },
    ];


    var QUIZ_OPTION_KEYS = ["A", "B", "C", "D", "E"];

    /* ==================================================================
       2. 应急场景数据
       ================================================================== */
    var EMERGENCY_DATA = [
      {
        key: "受伤", icon: "i-firstaid", label: "有人受伤",
        headline: "先确认自己安全，再呼救，不随意搬动重伤人员。",
        steps: [
          "立即停止相关作业，先确认自己不会进入二次危险区域。",
          "立即通知现场负责人和安全员，说明位置、人数和伤情。",
          "需要急救时拨打 120；现场有急救器材的按交底取用。",
          "重伤人员不要随意搬动，除非现场仍有立即危险。",
        ],
        never: "不要为了把人拖出来而让自己进入危险区域，也不要围在伤者周围影响救援和通风。",
        calls: ["120"],
      },
      {
        key: "火灾", icon: "i-fire", label: "发生火灾",
        headline: "先撤离、再报警，未受训练不返回火场。",
        steps: [
          "立即停止作业，远离烟气和火源，沿疏散路线撤离。",
          "在安全位置拨打 119，说清项目名称、位置和燃烧物。",
          "通知现场负责人，按现场要求启动疏散和清点人员。",
          "在集合点等待清点，听从现场应急指挥。",
        ],
        never: "未受过训练不要返回火场救人或取物；不要乘坐施工升降机逃生。",
        calls: ["119"],
      },
      {
        key: "触电", icon: "i-shock", label: "触电了",
        headline: "先断电、再救人，绝不徒手拉触电者。",
        steps: [
          "不要直接用手拉触电者，避免自己一起触电。",
          "能安全断电就立即切断电源或用绝缘物分离电源。",
          "远离带电设备并呼叫现场负责人和安全员。",
          "拨打 120；只有受过急救训练的人按现场要求实施救护。",
        ],
        never: "不要徒手接触触电者和带电设备，不要用水去浇电气火灾。",
        calls: ["120"],
      },
      {
        key: "坍塌", icon: "i-collapse", label: "坍塌 / 被困",
        headline: "立即撤离到安全区，不进入坍塌体盲目施救。",
        steps: [
          "马上撤离危险区域，撤到稳定地面和上方无堆载的位置。",
          "不要进入坍塌体内部或坑边盲目救人，避免二次坍塌。",
          "设置警戒并劝阻其他人员靠近，通知项目负责人。",
          "需要救援时拨打 119，等待专业救援力量到场。",
        ],
        never: "不要在不稳定的边坡、堆载或结构物下方停留和施救。",
        calls: ["119"],
      },
      {
        key: "高处坠落", icon: "i-fall", label: "高处坠落",
        headline: "先控制现场、防止二次坠落，再呼救。",
        steps: [
          "停止相关作业，防止其他人继续靠近临边和洞口。",
          "通知现场负责人和安全员，拨打 120。",
          "在专业人员指导下设置警戒，避免二次坠落和落物伤人。",
          "未受训练不要随意搬动重伤人员。",
        ],
        never: "不要为了查看伤情而自己站到没有防护的临边或洞口。",
        calls: ["120"],
      },
      {
        key: "其他危险", icon: "i-alert", label: "其他危险",
        headline: "不确定怎么处理时，先停下来、先离开、先报告。",
        steps: [
          "立即离开危险区域，站到稳定安全的位置。",
          "提醒附近工友，避免更多人进入。",
          "通知班组长、安全员或项目值班人员说明情况。",
          "紧急情况拨打 119 或 120，听现场指挥行动。",
        ],
        never: "不要为了赶工继续试、继续干，也不要自己拆改或维修不熟悉的设备。",
        calls: ["119", "120"],
      },
    ];

    var VIEW_ALIAS = { cases: "cases", voice: "ask", photo: "ask" };

    /* ==================================================================
       3. 存储与通用工具
       ================================================================== */
    function readStore(key, fallback) {
      try {
        var raw = window.localStorage.getItem(key);
        if (!raw) return fallback;
        var parsed = JSON.parse(raw);
        return parsed === null || parsed === undefined ? fallback : parsed;
      } catch (error) {
        return fallback;
      }
    }

    function writeStore(key, value) {
      try {
        window.localStorage.setItem(key, JSON.stringify(value));
      } catch (error) {
        /* 隐私模式或存储已满时静默降级，不影响本次使用 */
      }
    }

    function $(id) { return document.getElementById(id); }

    function make(tag, className, value) {
      var node = document.createElement(tag);
      if (className) node.className = className;
      if (value !== undefined && value !== null) node.textContent = String(value);
      return node;
    }

    /* 建一个真实的 svg/use 图标节点。
       为什么单独一个函数：make() 用 textContent，传 HTML 字符串会被转义成
       可见文本（页面上直接显示 <svg ...>）。图标必须走这里，契约才清楚。 */
    function makeIcon(symbolId, className) {
      var NS = "http://www.w3.org/2000/svg";
      var svg = document.createElementNS(NS, "svg");
      svg.setAttribute("class", className || "ico");
      svg.setAttribute("aria-hidden", "true");
      var use = document.createElementNS(NS, "use");
      use.setAttribute("href", "#" + symbolId);
      svg.appendChild(use);
      return svg;
    }

    /* 图标 + 文字的片段：返回 DocumentFragment，便于 appendChild 一次挂上 */
    function iconText(symbolId, text, className) {
      var frag = document.createDocumentFragment();
      frag.appendChild(makeIcon(symbolId, className));
      frag.appendChild(document.createTextNode(" " + text));
      return frag;
    }

    /* make() 的图标版：建 div/button 并把「图标 + 文字」一次性挂上 */
    function makeIconText(tag, className, symbolId, iconClass, text) {
      var node = make(tag, className);
      node.appendChild(makeIcon(symbolId, iconClass));
      node.appendChild(document.createTextNode(" " + text));
      return node;
    }

    function makeButtonWithIcon(className, symbolId, text) {
      var button = make("button", className);
      button.type = "button";
      button.appendChild(makeIcon(symbolId));
      button.appendChild(document.createTextNode(" " + text));
      return button;
    }

    /* ==================================================================
       回答正文的极简 Markdown 渲染
       ------------------------------------------------------------------
       只支持回答里真实出现的三种标记：**加粗**、无序列表、有序列表。
       安全前提：先把 HTML 全转义，再替换白名单标记 ——
       模型输出属于不可信内容，绝不能直接 innerHTML。

       注意：分片里不能写反斜杠，所以正则都用 RegExp 构造器拼。
       ================================================================== */
    /* 分片禁止出现反斜杠字符，所以正则里的转义用 fromCharCode(92) 拼出来。
       星号在正则里是量词，必须转义成「反斜杠 + 星号」才能匹配字面量。 */
    var ESC = String.fromCharCode(92);
    var STAR = String.fromCharCode(42);
    var RE_BOLD = new RegExp(ESC + STAR + ESC + STAR + "([^" + STAR + "]+)" +
      ESC + STAR + ESC + STAR, "g");
    var RE_BULLET = new RegExp("^[" + String.fromCharCode(45, 42, 8226) + "]" +
      String.fromCharCode(32) + "+(.*)$");
    var RE_SPACE = new RegExp("^" + String.fromCharCode(32) + "+");

    /* 有序列表手写解析，不用正则 —— 数字类会引入反斜杠 d。 */
    function matchNumbered(line) {
      var index = 0;
      while (index < line.length) {
        var code = line.charCodeAt(index);
        if (code < 48 || code > 57) break;
        index += 1;
      }
      if (index === 0 || index >= line.length) return null;
      var sep = line.charAt(index);
      if (sep !== "." && sep !== ")" && sep !== String.fromCharCode(12289)) return null;
      var rest = line.slice(index + 1);
      if (!rest.length) return null;
      if (rest.charAt(0) !== String.fromCharCode(32)) return null;
      return [rest.replace(RE_SPACE, "")];
    }

    function escapeHtml(text) {
      return String(text == null ? "" : text)
        .split("&").join("&amp;")
        .split("<").join("&lt;")
        .split(">").join("&gt;")
        .split(String.fromCharCode(34)).join("&quot;");
    }

    function stripTrailingSpaces(line) {
      var end = line.length;
      while (end > 0) {
        var code = line.charCodeAt(end - 1);
        if (code === 32 || code === 9 || code === 13 || code === 160) end -= 1;
        else break;
      }
      return line.slice(0, end);
    }

    function renderAnswerBody(text) {
      var host = document.createDocumentFragment();
      var lines = String(text == null ? "" : text).split(String.fromCharCode(10));
      var list = null;
      var listKind = "";

      function closeList() {
        if (list) {
          host.appendChild(list);
          list = null;
          listKind = "";
        }
      }

      function inline(raw) {
        /* 先转义，再把 **x** 换成 strong。顺序不能反。 */
        return escapeHtml(raw).replace(RE_BOLD, "<strong>$1</strong>");
      }

      lines.forEach(function (rawLine) {
        var line = stripTrailingSpaces(rawLine);
        if (!line.trim()) {
          closeList();
          return;
        }
        var bullet = line.match(RE_BULLET);
        var numbered = bullet ? null : matchNumbered(line);
        var kind = bullet ? "ul" : (numbered ? "ol" : "");

        if (kind) {
          if (listKind !== kind) {
            closeList();
            list = document.createElement(kind);
            list.className = "answer-list";
            listKind = kind;
          }
          var item = document.createElement("li");
          item.innerHTML = inline(bullet ? bullet[1] : numbered[1]);
          list.appendChild(item);
          return;
        }

        closeList();
        var para = document.createElement("p");
        para.className = "answer-line";
        para.innerHTML = inline(line);
        host.appendChild(para);
      });

      closeList();
      return host;
    }

    function clear(node) {
      if (node) node.replaceChildren();
      return node;
    }

    /* 访问码：兼容服务端可选的访问码保护 */
    function accessCode() {
      try { return window.localStorage.getItem(ACCESS_CODE_KEY) || ""; }
      catch (error) { return ""; }
    }

    async function apiFetch(url, options) {
      var opts = Object.assign({}, options || {});
      var headers = new Headers(opts.headers || {});
      var code = accessCode();
      if (code) headers.set("X-Access-Code", code);
      opts.headers = headers;
      var response = await fetch(url, opts);
      if (response.status === 401) {
        var entered = window.prompt("请输入管理员提供的访问码：", "");
        if (entered && entered.trim()) {
          try { window.localStorage.setItem(ACCESS_CODE_KEY, entered.trim()); } catch (error) { /* 忽略 */ }
          headers.set("X-Access-Code", entered.trim());
          response = await fetch(url, opts);
        }
      }
      return response;
    }

    async function getJson(url) {
      var response = await apiFetch(url, { method: "GET" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }

    /* POST JSON。走 apiFetch 而不是裸 fetch —— 它带访问码重试逻辑。 */
    async function postJson(url, body) {
      var response = await apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }

    function modeLabel(mode) {
      if (mode === "local-llm") return "在线大模型生成";
      if (mode === "extractive") return "SQLite 检索摘要";
      if (mode === "error") return "查询失败";
      return mode || "未知模式";
    }

    function fmtTime(value) {
      if (!value) return "";
      var date = new Date(value);
      if (isNaN(date.getTime())) return String(value);
      function pad(n) { return n < 10 ? "0" + n : String(n); }
      return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate())
        + " " + pad(date.getHours()) + ":" + pad(date.getMinutes());
    }

    /* ==================================================================
       4. 视图切换
       ================================================================== */
    function showView(name) {
      var target = VIEW_ALIAS[name] || name;
      var buttons = document.querySelectorAll(".nav-button");
      var known = false;
      for (var i = 0; i < buttons.length; i += 1) {
        if (buttons[i].dataset.view === target) known = true;
      }
      if (!known) target = "home";

      var views = document.querySelectorAll(".view");
      for (var j = 0; j < views.length; j += 1) {
        views[j].classList.toggle("active", views[j].id === target);
      }
      for (var k = 0; k < buttons.length; k += 1) {
        buttons[k].classList.toggle("active", buttons[k].dataset.view === target);
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    document.querySelectorAll(".nav-button").forEach(function (button) {
      button.addEventListener("click", function () { showView(button.dataset.view); });
    });

    /* 视图深链：?view=ask 之类的链接直接打开对应页。
       用途：现场分享某个页面的链接；截图脚本也依赖它（外部拿不到 IIFE 里的 showView）。
       放在这里同步执行 —— 脚本在 body 末尾，此时 DOM 已解析完，切页会先于首帧绘制。
       注意：必须逐层判断存在性。run_dom_sim.js 的沙箱没有 window.location，
       直接取 .search 会抛错并中断整个脚本（踩过，且模拟器当时静默吞掉了异常）。 */
    (function deepLinkView() {
      var loc = window.location;
      if (!loc || typeof loc.search !== "string") return;
      var query = loc.search;
      var found = null;
      var parts = query.replace(/^[?]/, "").split("&");
      for (var i = 0; i < parts.length; i += 1) {
        var pair = parts[i].split("=");
        if (decodeURIComponent(pair[0] || "") === "view") {
          found = decodeURIComponent(pair[1] || "");
          break;
        }
      }
      if (!found) return;
      var name = found.toLowerCase();
      var known = ["home", "ask", "sos", "pre", "learn"];
      if (known.indexOf(name) < 0) return;
      showView(name);
    })();

    /* 支持 data-jump（滚动到页内区域）与 data-goto（切换模块） */
    document.querySelectorAll("[data-jump]").forEach(function (button) {
      button.addEventListener("click", function () {
        var name = button.dataset.jump;
        if (name === "voice") {
          showView("ask");
          var input = $("question");
          if (input) input.focus();
          return;
        }
        if (name === "photo") {
          showView("ask");
          var file = $("sitePhoto");
          if (file) file.scrollIntoView({ behavior: "smooth", block: "center" });
          return;
        }
        showView(name);
      });
    });

    document.querySelectorAll("[data-goto]").forEach(function (button) {
      button.addEventListener("click", function () {
        var view = button.dataset.goto;
        showView(view);
        var train = button.dataset.train;
        if (!train) return;
        if (train === "quiz") {
          var panel = $("trainQuizPanel");
          if (panel) panel.scrollIntoView({ behavior: "smooth", block: "start" });
        } else {
          var target = $("trainPathPanel");
          if (train === "check") target = $("pre");
          if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });

    /* ==================================================================
       5. 首页：班前 5 分钟四步动线（§7 方向 2）
       ------------------------------------------------------------------
       勾选项一条都没减少（用户要求"不合并"），只是按步骤归位：
       进门过关 → 弄清风险 → 检查机具 → 不确定就停。
       ================================================================== */
    function renderPractical() {
      var done = readStore(PRACTICAL_KEY, {});
      var host = clear($("todoList"));
      if (!host) return;

      PRACTICAL_STEPS.forEach(function (group) {
        var items = PRACTICAL_ITEMS.filter(function (item) { return item.step === group.n; });
        if (!items.length) return;

        var bucket = make("section", "flow-step");
        var head = make("div", "flow-step-head");
        head.appendChild(make("span", "flow-step-num", String(group.n)));
        var titles = make("div", "flow-step-titles");
        titles.appendChild(make("b", "flow-step-title", group.title));
        if (group.note) titles.appendChild(make("span", "flow-step-note", group.note));
        head.appendChild(titles);
        bucket.appendChild(head);

        var list = make("div", "todo-list");
        items.forEach(function (item) {
          var label = make("label", "todo-item" + (done[item.id] ? " done" : ""));
          var input = document.createElement("input");
          input.type = "checkbox";
          input.checked = Boolean(done[item.id]);
          input.setAttribute("aria-label", item.label);
          input.addEventListener("change", function () {
            var state = readStore(PRACTICAL_KEY, {});
            state[item.id] = input.checked;
            writeStore(PRACTICAL_KEY, state);
            label.classList.toggle("done", input.checked);
            if (input.checked) logActivity();
            updatePracticalProgress();
          });
          label.appendChild(input);
          var text = make("span");
          text.appendChild(make("b", "", item.label));
          text.appendChild(make("span", "", item.hint));
          label.appendChild(text);
          list.appendChild(label);
        });
        bucket.appendChild(list);
        host.appendChild(bucket);
      });
      updatePracticalProgress();
    }
    function updatePracticalProgress() {
      var done = readStore(PRACTICAL_KEY, {});
      var count = PRACTICAL_ITEMS.filter(function (item) { return Boolean(done[item.id]); }).length;
      var percent = Math.round((count / PRACTICAL_ITEMS.length) * 100);
      var fill = $("todoFill");
      if (fill) fill.style.width = percent + "%";
      var label = $("todoLabel");
      if (label) label.textContent = count + " / " + PRACTICAL_ITEMS.length;
    }

    var todoReset = $("todoReset");
    if (todoReset) {
      todoReset.addEventListener("click", function () {
        writeStore(PRACTICAL_KEY, {});
        renderPractical();
      });
    }

    /* ==================================================================
       6. 工种选择（贯穿问答与培训）
       ================================================================== */
    var profile = readStore(PROFILE_KEY, { role: "" });
    var roleHosts = [$("homeRoleChips"), $("assistantRoleChips"), $("roleChips")];
    var trainingData = { roles: [], worker_roles: {}, questions: [], quiz: {}, training_steps: [] };

    function currentRole() { return profile.role || ""; }

    function setRole(role) {
      profile.role = role || "";
      writeStore(PROFILE_KEY, profile);
      renderRoleChips();
      renderRoleDetail();
      renderQuickQuestions();
      renderProfileMeta();
    }

    function renderRoleChips() {
      roleHosts.forEach(function (host) {
        if (!host) return;
        clear(host);
        var roles = (trainingData.roles && trainingData.roles.length)
          ? trainingData.roles
          : Object.keys(trainingData.worker_roles || {});
        roles.forEach(function (role) {
          var chip = make("button", "role-chip" + (role === currentRole() ? " active" : ""), role);
          chip.type = "button";
          chip.setAttribute("aria-pressed", role === currentRole() ? "true" : "false");
          chip.addEventListener("click", function () { setRole(role === currentRole() ? "" : role); });
          host.appendChild(chip);
        });
      });
    }

    function renderRoleDetail() {
      var host = clear($("roleDetail"));
      if (!host) return;
      var role = currentRole();
      var data = (trainingData.worker_roles || {})[role];
      if (!role || !data) {
        host.appendChild(make("p", "empty-state", "先选一个工种，这里会显示该工种的常见风险、必守规矩和典型违规。"));
        return;
      }
      var head = make("h3");
      head.appendChild(make("span", "", role));
      head.appendChild(make("span", "q-role-tag", "专项要点"));
      host.appendChild(head);
      host.appendChild(make("p", "role-summary", data.summary || ""));

      /* ---- 常见风险：背景资料，独立一行 ---- */
      var haz = make("div", "role-block is-danger role-block-wide");
      haz.appendChild(iconText("i-alert", "常见风险"));
      var hazList = make("ul", "role-chip-list");
      var hazards = data.hazards || [];
      if (hazards.length) {
        hazards.forEach(function (text) {
          hazList.appendChild(make("li", "role-chip", text));
        });
      } else {
        hazList.appendChild(make("li", "role-chip", "本工种暂无单独列出的风险条目。"));
      }
      haz.appendChild(hazList);
      host.appendChild(haz);

      /* ---- ✗ 典型违规 / ✓ 必守规矩：左右对照（§7 方向 5）----
         这两块讲的是同一件事的两面，并排才看得出对应关系。
         左边红底、右边绿底，视觉上直接对撞。 */
      var compare = make("div", "role-compare");
      var wrong = make("div", "role-compare-col is-wrong");
      wrong.appendChild(make("b", "role-compare-head", "✗ 典型违规"));
      var wrongList = make("ul");
      var violations = data.violations || [];
      if (violations.length) {
        violations.forEach(function (text) { wrongList.appendChild(make("li", "", text)); });
      } else {
        wrongList.appendChild(make("li", "", "本工种暂无单独列出的典型违规。"));
      }
      wrong.appendChild(wrongList);
      compare.appendChild(wrong);

      var right = make("div", "role-compare-col is-right");
      right.appendChild(make("b", "role-compare-head", "✓ 必守规矩"));
      var rightList = make("ul");
      var rules = data.rules || [];
      if (rules.length) {
        rules.forEach(function (text) { rightList.appendChild(make("li", "", text)); });
      } else {
        rightList.appendChild(make("li", "", "本工种暂无单独列出的必守规矩。"));
      }
      right.appendChild(rightList);
      compare.appendChild(right);
      host.appendChild(compare);

      /* ---- 防护用品：清单，独立一行 ---- */
      var ppe = make("div", "role-block role-block-wide");
      ppe.appendChild(iconText("i-helmet", "防护用品"));
      var ppeList = make("ul", "role-chip-list");
      var ppeItems = data.ppe || [];
      if (ppeItems.length) {
        ppeItems.forEach(function (text) {
          ppeList.appendChild(make("li", "role-chip", text));
        });
      } else {
        ppeList.appendChild(make("li", "role-chip", "按项目交底配备，以现场要求为准。"));
      }
      ppe.appendChild(ppeList);
      host.appendChild(ppe);

      if (data.questions && data.questions.length) {
        var box = make("div", "related-row");
        data.questions.forEach(function (text) {
          var button = make("button", "quick-button", "问：" + text);
          button.type = "button";
          button.addEventListener("click", function () {
            showView("ask");
            var input = $("question");
            if (input) { input.value = text; input.focus(); }
          });
          box.appendChild(button);
        });
        host.appendChild(box);
      }
    }

    function renderQuickQuestions() {
      var host = clear($("quickList"));
      if (!host) return;
      var role = currentRole();

      function buildButtons(group, container) {
        var shown = 0;
        group.items.forEach(function (item) {
          var matched = !!(role && item.roles.indexOf(role) >= 0);
          /* 折叠组只显示命中当前工种的题；未选工种时先不展开 */
          if (group.collapsed && role && !matched) return;
          var button = make("button", "quick-button", item.text);
          button.type = "button";
          if (matched) button.classList.add("is-role-match");
          button.addEventListener("click", function () {
            var input = $("question");
            if (!input) return;
            input.value = item.text;
            input.focus();
            setVoiceHint("");
          });
          container.appendChild(button);
          shown += 1;
        });
        return shown;
      }

      QUICK_GROUPS.forEach(function (group) {
        /* collapsed 组的内容完全依赖工种：没选工种时整块不渲染。
           注意要在**循环这一层**跳过 —— 只在 buildButtons 里 return 的话，
           外层 details 与占位文案仍会渲染出一个空壳。 */
        if (group.collapsed && !role) return;

        var bucket = make("div", "quick-group");
        var head = make("div", "quick-group-head");
        head.appendChild(make("span", "quick-group-title", group.title));
        if (group.hint) head.appendChild(make("span", "quick-group-hint", group.hint));
        bucket.appendChild(head);

        var list = make("div", "quick-list");

        if (group.collapsed) {
          var details = make("details", "quick-group-more");
          details.appendChild(make("summary", "", "本工种专项问题"));
          var count = buildButtons(group, list);
          if (!count) {
            list.appendChild(make(
              "span", "answer-meta",
              "当前工种没有专属问题，可以从上面两组里挑一个问。"
            ));
          }
          details.appendChild(list);
          bucket.appendChild(details);
        } else {
          buildButtons(group, list);
          bucket.appendChild(list);
        }
        host.appendChild(bucket);
      });
    }
    function renderProfileMeta() {
      var role = currentRole();
      var head = $("headerRole");
      if (head) {
        /* 未选工种时不显示"工种未选择"——空状态不该做成常驻标签（§5 第 5 条） */
        head.hidden = !role;
        head.textContent = role ? "当前工种：" + role : "";
        head.classList.toggle("offline", !role);
        head.setAttribute("style", role
          ? "background:var(--brand);color:#fff;border-color:var(--brand)"
          : "");
      }
      var hint = $("homeRoleHint");
      if (hint) {
        clear(hint);
        var data = (trainingData.worker_roles || {})[role];
        if (role && data) {
          hint.appendChild(make("b", "", "已选择：" + role));
          hint.appendChild(document.createTextNode((data.summary || "") + " 提问时会自动带上这个工种的要点。"));
        } else {
          hint.appendChild(make("b", "", "还没有选择工种"));
          hint.appendChild(document.createTextNode("未选择时按通用要点回答，选择后会自动带上本工种的主要风险与必守规矩。"));
        }
      }
      var kvRole = $("kvRole");
      if (kvRole) kvRole.textContent = role || "未选择";
    }

    /* ==================================================================
       7. 首页：知识领域分布与警示案例
       ================================================================== */
    var DOMAIN_TOKENS = [
      { name: "高处作业", tokens: ["高处", "坠落", "安全带", "临边", "洞口", "脚手架", "攀登"] },
      { name: "起重吊装", tokens: ["吊装", "起重", "塔吊", "吊索", "钢丝绳", "升降机", "物料提升"] },
      { name: "临时用电", tokens: ["用电", "配电", "电气", "漏电", "接地", "电缆"] },
      { name: "基坑与边坡", tokens: ["基坑", "支护", "边坡", "土方", "降水"] },
      { name: "模板支架", tokens: ["模板", "支架", "浇筑", "支撑"] },
      { name: "施工机具", tokens: ["机具", "机械", "焊机", "气瓶", "搅拌", "钢筋机械", "木工"] },
      { name: "动火消防", tokens: ["消防", "动火", "火灾", "灭火", "燃烧"] },
      { name: "应急与急救", tokens: ["应急", "急救", "撤离", "救援", "事故"] },
      { name: "安全管理", tokens: ["管理", "制度", "交底", "教育", "检查", "责任"] },
      { name: "文明施工", tokens: ["文明", "围挡", "场地", "材料堆放", "标牌", "住宿"] },
    ];

    function renderDomainDistribution(documents) {
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
        host.appendChild(make("li", "", "知识库中还没有可归类的文档"));
        return;
      }
      rows.slice(0, 6).forEach(function (row) {
        var li = make("li");
        li.appendChild(make("span", "", row.name));
        li.appendChild(make("span", "hot-count", row.docs + " 篇 / " + row.count + " 段"));
        host.appendChild(li);
      });
    }

    function caseCard(item, compact) {
      var card = make("article", "case-card");
      card.dataset.category = item.category || "";
      card.appendChild(make("span", "case-tag", item.category || "未分类"));
      card.appendChild(make("h3", "", item.title || ""));
      var pairs = [
        ["事故 / 隐患经过", item.what_happened],
        ["主要致险因素", item.why_dangerous],
      ];
      pairs.forEach(function (pair) {
        if (!pair[1]) return;
        var p = make("p");
        p.appendChild(make("span", "case-label", pair[0] + "："));
        p.appendChild(document.createTextNode(pair[1]));
        card.appendChild(p);
      });
      if (!compact) {
        var detail = make("div", "case-detail");
        if (item.consequence) {
          var p1 = make("p");
          p1.appendChild(make("span", "case-label", "后果与影响："));
          p1.appendChild(document.createTextNode(item.consequence));
          detail.appendChild(p1);
        }
        if (item.lesson) detail.appendChild(make("p", "case-lesson", "防控要点：" + item.lesson));
        detail.appendChild(make("div", "case-source", "来源：" + (item.source_name || "未标注") + " · " + (item.date || "")));
        card.appendChild(detail);
      }
      return card;
    }

    function renderSteps() {
      var host = clear($("stepList"));
      if (!host) return;
      var steps = trainingData.training_steps || [];
      if (!steps.length) {
        host.appendChild(make("p", "empty-state", "培训路线数据未读取到。"));
        return;
      }
      steps.forEach(function (step) {
        var item = make("section", "step-item");
        item.appendChild(make("div", "step-order", String(step.order)));
        var main = make("div");
        var head = make("h3");
        head.appendChild(make("span", "", step.title));
        head.appendChild(make("span", "step-meta", step.duration || ""));
        main.appendChild(head);
        main.appendChild(make("p", "role-summary", step.summary || ""));
        var points = make("ul", "step-points");
        (step.key_points || []).forEach(function (text) { points.appendChild(make("li", "", text)); });
        main.appendChild(points);
        if (step.checkpoint) main.appendChild(make("div", "step-check", "自检标准：" + step.checkpoint));
        item.appendChild(main);

        var side = make("div", "step-side");
        var done = readStore("sitesaha-steps-v1", {});
        var label = make("label", "check-item" + (done[step.order] ? " checked" : ""));
        var box = document.createElement("input");
        box.type = "checkbox";
        box.checked = Boolean(done[step.order]);
        box.setAttribute("aria-label", "标记“" + step.title + "”已完成");
        box.addEventListener("change", function () {
          var state = readStore("sitesaha-steps-v1", {});
          state[step.order] = box.checked;
          writeStore("sitesaha-steps-v1", state); if (box.checked) logActivity();
          label.classList.toggle("checked", box.checked);
          item.classList.toggle("is-done", box.checked);
          renderTrainingProgress();
        });
        label.appendChild(box);
        label.appendChild(make("span", "", "已完成"));
        side.appendChild(label);
        if (step.link_view) {
          var jump = make("button", "ghost-button", "去看相关模块");
          jump.type = "button";
          jump.addEventListener("click", function () { showView(step.link_view); });
          side.appendChild(jump);
        }
        item.appendChild(side);
        item.classList.toggle("is-done", Boolean(done[step.order]));
        if (done[step.order]) {
          label.classList.add("checked");
          item.querySelector(".step-order").replaceChildren(makeIcon("i-check", "ico ico-sm"));
        }
        host.appendChild(item);
      });
      renderTrainingProgress();
    }

    function renderTrainingProgress() {
      var steps = (trainingData.training_steps || []).length || 5;      var done = readStore("sitesaha-steps-v1", {});
      var count = 0;
      Object.keys(done).forEach(function (key) { if (done[key]) count += 1; });
      if (count > steps) count = steps;
      var percent = Math.round((count / steps) * 100);
      var fill = $("trainFill");
      if (fill) fill.style.width = percent + "%";
      var label = $("trainLabel");
      if (label) label.textContent = percent + "%";
      var stat = $("trainStepDone");
      if (stat) stat.textContent = count + "/" + steps;
      var kv = $("kvSteps");
      if (kv) kv.textContent = count + " / " + steps;
      var kpiQuiz = $("kpiQuiz");
      if (kpiQuiz) {
        var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
        kpiQuiz.textContent = quiz.bestCorrect + "/" + (quiz.total || 20);
        var note = $("kpiQuizNote");
        if (note) note.textContent = quiz.attempts ? ("已测 " + quiz.attempts + " 次 · 历史最佳") : "本地保存，仅自己可见";
      }
    }

    /* ==================================================================
       9. 测验引擎
       ================================================================== */
    var quizState = { active: false, index: 0, order: [], answered: false, correct: 0, wrong: [] };

    function shuffledIndexes(total) {
      var list = [];
      for (var i = 0; i < total; i += 1) list.push(i);
      for (var j = list.length - 1; j > 0; j -= 1) {
        var k = Math.floor(Math.random() * (j + 1));
        var tmp = list[j]; list[j] = list[k]; list[k] = tmp;
      }
      return list;
    }

    function renderQuizIntro() {
      var meta = trainingData.quiz || {};
      var intro = $("quizIntro");
      if (intro) intro.textContent = meta.intro || "答一遍看看哪些风险域还没掌握，结果只保存在你自己的浏览器里。";
      var note = $("quizHomeNote");
      var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
      if (note && quiz.attempts) {
        note.textContent = "已测验 " + quiz.attempts + " 次，最近一次 "
          + quiz.lastCorrect + " / " + (quiz.total || 20) + " 题（" + fmtTime(quiz.lastAt) + "）。薄弱项见下方分布。";
      }
    }

    function renderRing(percent) {
      var ring = $("ringFg");
      if (ring) {
        var offset = 345.58 * (1 - Math.min(100, Math.max(0, percent)) / 100);
        ring.style.setProperty("--ring-offset", offset.toFixed(2));
        ring.setAttribute("stroke", percent >= 80 ? "var(--risk-low)" : (percent >= 60 ? "var(--risk-mid)" : "var(--risk-high)"));
      }
      var num = $("ringNum");
      if (num) num.textContent = percent + "%";
    }

    /* ==================================================================
       §7 图形语言：近 7 天学习热力格 + 测验正确率趋势
       ------------------------------------------------------------------
       数据全部来自本机 localStorage，不上传。
       没有数据就画空状态 —— 不编造趋势线。
       ================================================================== */
    var ACTIVITY_KEY = "sitesaha-activity-v1";

    function dayKey(date) {
      function pad(n) { return n < 10 ? "0" + n : String(n); }
      return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
    }

    /* 记一次学习动作。renderStudyHeat 会读它画热力格。 */
    function logActivity() {
      var store = readStore(ACTIVITY_KEY, {});
      var key = dayKey(new Date());
      store[key] = (store[key] || 0) + 1;
      /* 只留最近 30 天，避免无限增长 */
      var cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - 30);
      var kept = {};
      Object.keys(store).forEach(function (item) {
        if (item >= dayKey(cutoff)) kept[item] = store[item];
      });
      writeStore(ACTIVITY_KEY, kept);
    }

    function renderStudyHeat() {
      var host = clear($("studyHeat"));
      if (!host) return;
      var store = readStore(ACTIVITY_KEY, {});
      var today = new Date();
      var values = [];
      for (var back = 6; back >= 0; back -= 1) {
        var day = new Date(today.getTime());
        day.setDate(day.getDate() - back);
        values.push({ key: dayKey(day), count: store[dayKey(day)] || 0, back: back });
      }
      var max = 1;
      values.forEach(function (item) { if (item.count > max) max = item.count; });

      values.forEach(function (item) {
        var level = item.count === 0 ? 0 : Math.min(4, Math.ceil((item.count / max) * 4));
        var cell = make("span", "heat-cell");
        cell.setAttribute("data-level", String(level));
        cell.setAttribute("title", item.key + "：" + item.count + " 次学习动作");
        cell.textContent = item.back === 0 ? "今" : String(item.back + 1);
        host.appendChild(cell);
      });

      var note = $("studyHeatNote");
      if (note) {
        var total = values.reduce(function (sum, item) { return sum + item.count; }, 0);
        note.textContent = total
          ? ("近 7 天共 " + total + " 次学习动作")
          : "还没有记录。完成培训步骤、做测验或班前确认后会出现在这里。";
      }
    }

    function renderQuizTrend() {
      var host = clear($("quizTrend"));
      if (!host) return;
      var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
      var history = (quiz.history || []).filter(function (item) {
        return item && typeof item.percent === "number";
      });

      if (history.length < 2) {
        host.appendChild(make(
          "p", "trend-empty",
          history.length === 1
            ? "目前只有 1 次记录（" + history[0].percent + "%）。再做一次就能看到趋势线。"
            : "还没有测验记录。点上面的「开始测验」做一遍，这里会画出正确率变化。"
        ));
        return;
      }

      var recent = history.slice(-8);
      var width = 420;
      var height = 108;
      var padX = 26;
      var padY = 18;
      var stepX = recent.length > 1 ? (width - padX * 2) / (recent.length - 1) : 0;

      function pointX(index) { return padX + index * stepX; }
      function pointY(percent) {
        return height - padY - (Math.max(0, Math.min(100, percent)) / 100) * (height - padY * 2);
      }

      var points = recent.map(function (item, index) {
        return pointX(index) + "," + pointY(item.percent).toFixed(1);
      });
      var areaPath = "M" + pointX(0) + "," + (height - padY)
        + " L" + points.join(" L")
        + " L" + pointX(recent.length - 1) + "," + (height - padY) + " Z";

      var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("class", "trend-figure");
      svg.setAttribute("viewBox", "0 0 " + width + " " + height);
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label",
        "最近 " + recent.length + " 次测验正确率趋势，最新 " + recent[recent.length - 1].percent + "%");

      function add(tag, attrs, text) {
        var node = document.createElementNS("http://www.w3.org/2000/svg", tag);
        Object.keys(attrs).forEach(function (key) { node.setAttribute(key, attrs[key]); });
        if (text) node.textContent = text;
        svg.appendChild(node);
        return node;
      }

      add("line", { class: "axis", x1: padX, y1: height - padY, x2: width - padX, y2: height - padY });
      add("path", { class: "area", d: areaPath });
      add("polyline", { class: "line", points: points.join(" ") });

      recent.forEach(function (item, index) {
        add("circle", { class: "pt", cx: pointX(index), cy: pointY(item.percent).toFixed(1), r: 3.5 });
      });
      add("text", { class: "pt-label", x: padX, y: height - 4 }, "60%");
      add("text", { class: "pt-label", x: width - padX - 26, y: height - 4 },
        recent[recent.length - 1].percent + "%");

      host.appendChild(svg);
      host.appendChild(make(
        "p", "answer-meta",
        "最近 " + recent.length + " 次记录，最新 " + recent[recent.length - 1].percent + "%（及格线 80%）。"
      ));
    }

    function renderDomainBars() {
      var host = clear($("domainBars"));
      if (!host) return;
      var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
      var wrong = quiz.wrongDomains || {};
      var seen = quiz.seen || {};
      var domains = (trainingData.quiz && trainingData.quiz.domains) || [];
      if (!domains.length) {
        (trainingData.questions || []).forEach(function (q) {
          if (domains.indexOf(q.domain) < 0) domains.push(q.domain);
        });
      }
      var shown = 0;
      domains.forEach(function (name) {
        var total = seen[name] || 0;
        if (!total) return;
        var bad = wrong[name] || 0;
        var rate = Math.round(((total - bad) / total) * 100);
        var row = make("div", "domain-bar" + (rate >= 80 ? "" : (rate >= 60 ? " warn" : " bad")));
        row.appendChild(make("span", "dname", name));
        var track = make("div", "dtrack");
        var fill = make("div", "dfill");
        fill.style.width = rate + "%";
        track.appendChild(fill);
        row.appendChild(track);
        row.appendChild(make("span", "dval", rate + "%"));
        host.appendChild(row);
        shown += 1;
      });
      if (!shown) {
        host.appendChild(make("p", "empty-state", "测验后这里会按风险域显示你的掌握情况。"));
      }
    }

    function renderHomeQuiz() {
      var quiz = readStore(QUIZ_KEY, EMPTY_QUIZ);
      renderRing(quiz.bestPercent || 0);
      renderDomainBars(); renderStudyHeat(); renderQuizTrend();
      renderQuizIntro();
      var stat = $("trainQuizScore");
      if (stat) stat.textContent = quiz.attempts ? (quiz.lastCorrect + " / " + (quiz.total || 20)) : "未测";
      var kv = $("kvQuiz");
      if (kv) kv.textContent = quiz.attempts ? (quiz.bestPercent + "%（历史最佳）") : "无记录";
      // 积分依赖测验与路线进度，测验任何变化都要刷新
      renderPoints();
      renderTrainingProgress();
    }

    function startQuiz() {
      var total = (trainingData.questions || []).length;
      if (!total) return;
      quizState = { active: true, index: 0, order: shuffledIndexes(total), answered: false, correct: 0, wrong: [] };
      $("quizHome").hidden = true;
      $("quizResult").hidden = true;
      $("quizPlay").hidden = false;
      renderQuizQuestion();
    }

    function renderQuizQuestion() {
      var host = clear($("quizPlay"));
      var questions = trainingData.questions || [];
      var qIndex = quizState.order[quizState.index];
      var item = questions[qIndex];
      if (!item) return;

      var bar = make("div", "quiz-progress");
      bar.appendChild(make("span", "qcount", "第 " + (quizState.index + 1) + " / " + quizState.order.length + " 题"));
      var tags = make("span");
      tags.appendChild(make("span", "q-role-tag", item.domain || item.category || "安全知识"));
      tags.appendChild(document.createTextNode(" "));
      tags.appendChild(make("span", "answer-meta", "适用：" + (item.role || "全部工种")));
      bar.appendChild(tags);
      host.appendChild(bar);

      var track = make("div", "progress-track");
      var fill = make("div", "progress-fill");
      fill.style.width = Math.round((quizState.index / quizState.order.length) * 100) + "%";
      track.appendChild(fill);
      host.appendChild(track);

      host.appendChild(make("h3", "q-head", item.q || ""));
      var options = make("div", "options");
      var buttons = [];
      (item.options || []).forEach(function (text, idx) {
        var button = make("button", "option");
        button.type = "button";
        button.appendChild(make("span", "opt-key", QUIZ_OPTION_KEYS[idx] || String(idx + 1)));
        button.appendChild(make("span", "", text));
        button.addEventListener("click", function () { answerQuiz(idx, buttons, item); });
        buttons.push(button);
        options.appendChild(button);
      });
      host.appendChild(options);

      var foot = make("div", "quiz-actions");
      foot.style.marginTop = "14px";
      var next = make("button", "amber-button", quizState.index + 1 >= quizState.order.length ? "提交并看结果" : "下一题");
      next.type = "button";
      next.id = "quizNext";
      next.disabled = true;
      next.addEventListener("click", function () { nextQuizQuestion(); });
      foot.appendChild(next);
      var quit = make("button", "secondary-button", "退出测验");
      quit.type = "button";
      quit.addEventListener("click", function () {
        quizState.active = false;
        $("quizPlay").hidden = true;
        $("quizHome").hidden = false;
        renderHomeQuiz();
      });
      foot.appendChild(quit);
      host.appendChild(foot);
    }

    function answerQuiz(choice, buttons, item) {
      if (quizState.answered) return;
      quizState.answered = true;
      var correct = item.answer;
      buttons.forEach(function (button, idx) {
        button.disabled = true;
        if (idx === correct) button.classList.add("is-correct");
        else if (idx === choice) button.classList.add("is-wrong");
        else button.classList.add("is-dim");
      });
      var isRight = choice === correct;
      if (isRight) {
        quizState.correct += 1;
      } else {
        quizState.wrong.push({ q: item.q, domain: item.domain || item.category || "综合", chose: (item.options || [])[choice] || "", right: (item.options || [])[correct] || "", why: item.why || "" });
      }
      var box = make("div", "explain");
      box.appendChild(make("b", "", isRight ? "回答正确。" : "回答错误。"));
      box.appendChild(document.createTextNode((item.why || "") + (isRight ? "" : " 正确答案是 " + (QUIZ_OPTION_KEYS[correct] || "") + "。")));
      $("quizPlay").appendChild(box);
      var next = $("quizNext");
      if (next) next.disabled = false;
    }

    function nextQuizQuestion() {
      quizState.answered = false;
      quizState.index += 1;
      if (quizState.index >= quizState.order.length) {
        finishQuiz();
        return;
      }
      renderQuizQuestion();
      var host = $("quizPlay");
      if (host) host.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function finishQuiz() {
      var total = quizState.order.length;
      var percent = Math.round((quizState.correct / total) * 100);
      var stored = readStore(QUIZ_KEY, EMPTY_QUIZ);
      var wrong = stored.wrongDomains || {};
      var seen = stored.seen || {};
      quizState.wrong.forEach(function (row) {
        wrong[row.domain] = (wrong[row.domain] || 0) + 1;
      });
      var questions = trainingData.questions || [];
      var touched = {};
      quizState.order.forEach(function (qIndex) {
        var item = questions[qIndex];
        if (!item) return;
        var name = item.domain || item.category || "综合";
        touched[name] = (touched[name] || 0) + 1;
      });
      Object.keys(touched).forEach(function (name) {
        seen[name] = (seen[name] || 0) + touched[name];
      });
      var record = {
        attempts: (stored.attempts || 0) + 1,
        bestPercent: Math.max(stored.bestPercent || 0, percent),
        bestCorrect: Math.max(stored.bestCorrect || 0, quizState.correct),
        total: total,
        lastCorrect: quizState.correct,
        lastAt: new Date().toISOString(),
        wrongDomains: wrong,
        seen: seen,
      };
      writeStore(QUIZ_KEY, record);

      logActivity();

      var host = clear($("quizResult"));
      $("quizPlay").hidden = true;
      $("quizHome").hidden = true;
      host.hidden = false;
      var pass = (trainingData.quiz && trainingData.quiz.pass_score) || Math.ceil(total * 0.8);
      var card = make("div", "quiz-result");
      card.appendChild(make("h3", "", quizState.correct >= pass ? "完成测验：掌握情况良好" : "完成测验：还有需要补的地方"));
      var score = make("div", "score-big " + (quizState.correct >= pass ? "pass" : "fail"), quizState.correct + " / " + total);
      card.appendChild(score);
      card.appendChild(make("p", "lead", "正确率 " + percent + "%。参考达标线 " + pass + " / " + total + " 题。成绩与薄弱项已保存在本机浏览器。"));
      card.appendChild(make("p", "lead", (trainingData.quiz && trainingData.quiz.notice) || ""));

      var actions = make("div", "quiz-actions");
      actions.style.marginTop = "13px";
      var again = make("button", "amber-button", "再测一次");
      again.type = "button";
      again.addEventListener("click", function () { startQuiz(); });
      actions.appendChild(again);
      var back = make("button", "secondary-button", "返回掌握情况");
      back.type = "button";
      back.addEventListener("click", function () {
        host.hidden = true;
        $("quizHome").hidden = false;
        renderHomeQuiz();
      });
      actions.appendChild(back);
      card.appendChild(actions);

      if (quizState.wrong.length) {
        card.appendChild(make("h3", "sec-title", "错题与解析（" + quizState.wrong.length + " 题）"));
        var list = make("div", "wrong-list");
        quizState.wrong.forEach(function (row) {
          var box = make("div", "wrong-item");
          box.appendChild(make("b", "", row.q));
          box.appendChild(make("p", "", "你的选择：" + row.chose + "　|　正确答案：" + row.right));
          box.appendChild(make("p", "", "解析：" + row.why));
          list.appendChild(box);
        });
        card.appendChild(list);
      } else {
        card.appendChild(make("p", "lead", "全部答对，没有错题。建议再做一遍其他工种的专项要点，或者去开工前检查走一遍班前确认。"));
      }
      host.appendChild(card);
      renderHomeQuiz();
    }

    var quizStart = $("quizStart");
    if (quizStart) quizStart.addEventListener("click", function () { startQuiz(); });
    var quizReset = $("quizReset");
    if (quizReset) {
      quizReset.addEventListener("click", function () {
        writeStore(QUIZ_KEY, EMPTY_QUIZ);
        writeStore("sitesaha-steps-v1", {});
        renderSteps();
        renderHomeQuiz();
      });
    }
