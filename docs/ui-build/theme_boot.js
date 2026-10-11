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
      button.textContent = theme === "dark" ? "☀️ 白天" : "🌙 夜间";
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
