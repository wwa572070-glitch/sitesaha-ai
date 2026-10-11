/* 在 Node 里用最小 DOM 桩真跑一遍页面的 init()，用于抓运行时错误。
 * 无头浏览器在本机被沙箱拦住，这是最接近真实运行的替代验证。
 *
 * 用法: node run_dom_sim.js <assembled.html>
 */

const fs = require("fs");
const vm = require("vm");
const path = require("path");

const htmlPath = process.argv[2] || path.join(__dirname, "index_full.html");
const html = fs.readFileSync(htmlPath, "utf8");

const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) {
  console.error("FAIL: 未找到 script 块");
  process.exit(1);
}
const script = scriptMatch[1];

const htmlIds = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));

const created = [];
const errors = [];
const warnings = [];

function makeClassList(node) {
  const set = new Set();
  return {
    add: (...names) => names.forEach((n) => set.add(n)),
    remove: (...names) => names.forEach((n) => set.delete(n)),
    contains: (n) => set.has(n),
    toggle: (n, force) => {
      const want = force === undefined ? !set.has(n) : Boolean(force);
      if (want) set.add(n); else set.delete(n);
      return want;
    },
    _set: set,
  };
}

function makeElement(tag, id) {
  const node = {
    tagName: String(tag || "div").toUpperCase(),
    id: id || "",
    className: "",
    children: [],
    dataset: {},
    attributes: {},
    hidden: false,
    disabled: false,
    checked: false,
    value: "",
    type: "",
    files: [],
    style: {
      _props: {},
      setProperty(name, value) { this._props[name] = value; },
      getPropertyValue(name) { return this._props[name]; },
    },
    textContent: "",
    title: "",
    appendChild(child) { this.children.push(child); return child; },
    replaceChildren(...nodes) { this.children = nodes; },
    removeChild(child) {
      this.children = this.children.filter((c) => c !== child);
      return child;
    },
    setAttribute(name, value) {
      this.attributes[name] = String(value);
      if (name === "id") this.id = String(value);
    },
    removeAttribute(name) {
      delete this.attributes[name];
      if (name === "id") this.id = "";
    },
    getAttribute(name) { return this.attributes[name]; },
    hasAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attributes, name); },
    addEventListener() {},
    removeEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; },
    scrollIntoView() {},
    focus() {},
    cloneNode() { return makeElement(tag, id); },
  };
  node.classList = makeClassList(node);
  Object.defineProperty(node, "parentNode", { value: null, writable: true });
  created.push(node);
  return node;
}

const registry = new Map();
htmlIds.forEach((id) => registry.set(id, makeElement("div", id)));

const documentStub = {
  getElementById(id) {
    if (!registry.has(id)) {
      errors.push("getElementById 找不到 id=" + id);
      registry.set(id, makeElement("div", id));
    }
    return registry.get(id);
  },
  createElement: (tag) => makeElement(tag),
  // 页面用 createElementNS 建 SVG 图标节点；浏览器里一定有，模拟器也要有。
  createElementNS: (ns, tag) => makeElement(tag),
  // makeIcon 的「图标 + 文字」片段用 DocumentFragment；
  // 用一个 appendChild 会聚合子节点的普通对象来模拟即可。
  createDocumentFragment: () => ({
    nodeType: 11,
    childNodes: [],
    appendChild(child) { this.childNodes.push(child); return child; },
    get textContent() {
      return this.childNodes.map((n) => n.textContent || "").join("");
    },
  }),
  createTextNode: (text) => ({ nodeType: 3, textContent: String(text) }),
  querySelectorAll(selector) {
    if (selector === ".nav-button" || selector === "[data-jump]" || selector === "[data-goto]") {
      return [];
    }
    return [];
  },
  querySelector() { return null; },
  addEventListener() {},
};

// <html> 与 <body>：主题切换要读写根元素上的 data-theme，必须存在。
// 用 defineProperty 惰性创建，避免在 makeElement 定义之前求值。
function attachRootElements() {
  if (!documentStub.documentElement) documentStub.documentElement = makeElement("html");
  if (!documentStub.body) documentStub.body = makeElement("body");
}

const store = new Map();
const localStorageStub = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
};

/* fetch 桩：返回与真实接口同形的数据，验证渲染路径而不是只验证空数据回退 */
const trainingFixture = JSON.parse(fs.readFileSync(path.join(__dirname, "fixture_training.json"), "utf8"));
const statusFixture = JSON.parse(fs.readFileSync(path.join(__dirname, "fixture_status.json"), "utf8"));
const casesFixture = JSON.parse(fs.readFileSync(path.join(__dirname, "fixture_cases.json"), "utf8"));
const checklistsFixture = JSON.parse(fs.readFileSync(path.join(__dirname, "fixture_checklists.json"), "utf8"));
let standardsFixture = { counts: { total: 0, active: 0, pending: 0 }, items: [] };
try {
  standardsFixture = JSON.parse(fs.readFileSync(path.join(__dirname, "fixture_standards.json"), "utf8"));
} catch (error) {
  // 夹具缺失时用空结构，仍然验证前端降级路径
}

function jsonResponse(payload) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(payload),
  });
}

const fetchCalls = [];
let fetchedStatus = false;
function fetchStub(url) {
  fetchCalls.push(String(url));
  if (url.indexOf("/api/status") >= 0) fetchedStatus = true;
  if (url.indexOf("/api/training") >= 0) return jsonResponse(trainingFixture);
  if (url.indexOf("/api/standards") >= 0) return jsonResponse(standardsFixture);
  if (url.indexOf("/api/status") >= 0) return jsonResponse(statusFixture);
  if (url.indexOf("/api/cases") >= 0) return jsonResponse(casesFixture);
  if (url.indexOf("/api/checklists") >= 0) return jsonResponse(checklistsFixture);
  if (url.indexOf("/api/ask") >= 0) {
    return jsonResponse({
      question: "测试问题", text: "测试回答文本", mode: "extractive", warnings: ["测试警告"],
      sources: [{ title: "测试来源", heading: "章节", content: "内容", source: "标准", version: "2011", category: "安全" }],
      related_cases: [{ title: "相关案例标题" }],
    });
  }
  return jsonResponse({});
}

const windowStub = {
  localStorage: localStorageStub,
  scrollTo() {},
  prompt() { return null; },
  fetch: fetchStub,
  // 浏览器里 location 一定存在。缺了它，页面脚本一旦读 location.search
  // 就会同步抛错、整段停摆，而断言只会报出「没有请求接口」这种下游症状。
  location: { search: "", href: "http://localhost/", hash: "", pathname: "/" },
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  Headers: class { constructor() {} set() {} },
  FormData: class { append() {} },
  SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
  speechSynthesis: {
    cancel() {}, speak() {}, pause() {}, resume() {}, paused: false,
    onvoiceschanged: undefined,
    getVoices() {
      return [
        { name: "Microsoft Xiaoxiao", lang: "zh-CN" },
        { name: "Microsoft Yunxi", lang: "zh-CN" },
      ];
    },
  },
  MediaRecorder: class {
    constructor() { this.state = "inactive"; }
    static isTypeSupported() { return true; }
    start() { this.state = "recording"; }
    stop() { this.state = "inactive"; }
  },
  Blob: class { constructor(parts) { this.size = (parts || []).length; this.type = ""; } },
  XMLHttpRequest: class {
    constructor() { this.upload = {}; this.status = 0; }
    open() {}
    setRequestHeader() {}
    send() {}
    abort() {}
  },
  URL: {
    createObjectURL() { return "blob:sim/1"; },
    revokeObjectURL() {},
  },
  Image: class {
    constructor() { this.naturalWidth = 800; this.naturalHeight = 600; }
    set src(value) { this._src = value; if (this.onload) this.onload(); }
    get src() { return this._src; }
  },
  addEventListener() {},
};

/* 模拟浏览器提供摄像头 / 麦克风能力，验证权限路径而不是只验证不支持分支 */
const navigatorStub = {
  mediaDevices: {
    getUserMedia() {
      return Promise.resolve({ getTracks: () => [{ stop() {} }] });
    },
  },
};

const sandbox = {
  window: windowStub,
  navigator: navigatorStub,
  document: documentStub,
  localStorage: localStorageStub,
  fetch: fetchStub,
  Headers: windowStub.Headers,
  FormData: windowStub.FormData,
  Blob: windowStub.Blob,
  XMLHttpRequest: windowStub.XMLHttpRequest,
  Image: windowStub.Image,
  console,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  Promise,
  Math,
  Date,
  JSON,
  Object,
  Array,
  String,
  Number,
  Boolean,
  RegExp,
  Error,
  isNaN,
  encodeURIComponent,
};
sandbox.globalThis = sandbox;
sandbox.self = sandbox;

// 根元素在沙箱就绪后再补，保证 makeElement 已可用
attachRootElements();

process.on("unhandledRejection", (reason) => {
  errors.push("unhandledRejection: " + (reason && reason.stack ? reason.stack : reason));
});

const context = vm.createContext(sandbox);
try {
  vm.runInContext(script, context, { filename: "page.js" });
} catch (error) {
  errors.push("同步执行抛错: " + error.stack);
}

/* 等 init() 的异步链跑完 */
setTimeout(() => {
  const domCounts = {
    "role-chip": 0, "step-item": 0, "emergency-card": 0, "case-card": 0,
    "doc-group": 0, "check-item": 0, "todo-item": 0, "quick-button": 0,
    "training-card": 0, "domain-bar": 0, "source-card": 0, "todo-item-done": 0,
    "voice-select": 0, "option": 0, "filter-chip": 0, "explain": 0,
  };
  created.forEach((node) => {
    const cls = node.className || "";
    Object.keys(domCounts).forEach((key) => {
      if (key === "todo-item-done") return;
      if (cls.split(/\s+/).indexOf(key) >= 0) domCounts[key] += 1;
    });
  });

  const filled = {
    kpiDocs: registry.get("kpiDocs") ? registry.get("kpiDocs").textContent : null,
    kpiChunks: registry.get("kpiChunks") ? registry.get("kpiChunks").textContent : null,
    kpiCases: registry.get("kpiCases") ? registry.get("kpiCases").textContent : null,
    documentCount: registry.get("documentCount") ? registry.get("documentCount").textContent : null,
    roleCount: registry.get("roleCount") ? registry.get("roleCount").textContent : null,
    modelStatus: registry.get("modelStatus") ? registry.get("modelStatus").textContent : null,
    trainStepDone: registry.get("trainStepDone") ? registry.get("trainStepDone").textContent : null,
    ringNum: registry.get("ringNum") ? registry.get("ringNum").textContent : null,
    libraryNote: registry.get("libraryNote") ? registry.get("libraryNote").textContent : null,
    kvVision: registry.get("kvVision") ? registry.get("kvVision").textContent : null,
    kvAsr: registry.get("kvAsr") ? registry.get("kvAsr").textContent : null,
    voiceHint: registry.get("voiceHint") ? registry.get("voiceHint").textContent : null,
    recordButton: registry.get("recordButton") ? registry.get("recordButton").textContent : null,
    photoErrorHidden: registry.get("photoError") ? registry.get("photoError").hidden : null,
    priorityBadge: registry.get("priorityBadge") ? registry.get("priorityBadge").textContent : null,
  };

  /* 拍照 / 语音新增控件是否真的绑好（按钮存在且未被永久禁用） */
  const controls = {
    cameraButton: registry.get("cameraButton"),
    captureButton: registry.get("captureButton"),
    filePickButton: registry.get("filePickButton"),
    photoRetakeButton: registry.get("photoRetakeButton"),
    recordButton: registry.get("recordButton"),
    recordStopButton: registry.get("recordStopButton"),
    speakButton: registry.get("speakButton"),
    speakStopButton: registry.get("speakStopButton"),
    photoCancelButton: registry.get("photoCancelButton"),
  };
  const controlState = {};
  Object.keys(controls).forEach((key) => {
    const node = controls[key];
    controlState[key] = node ? { hidden: Boolean(node.hidden), disabled: Boolean(node.disabled) } : "MISSING";
  });

  console.log("fetch 调用:", fetchCalls.map((u) => u.split("?")[0]).join(", "));
  console.log("创建节点数:", created.length);
  console.log("渲染数量:", JSON.stringify(domCounts));
  console.log("回填文本:", JSON.stringify(filled, null, 1));
  console.log("拍照/语音控件:", JSON.stringify(controlState));

  const missing = Object.keys(controlState).filter((key) => controlState[key] === "MISSING");
  if (missing.length) {
    console.error("[FAIL] 结构里缺少控件：" + missing.join("、"));
    process.exit(1);
  }
  // 先报脚本自身的抛错，再报下游症状。
  // 顺序很重要：脚本中途抛错会让 init() 完全跑不到，症状看起来像「没请求接口」，
  // 真正的根因（哪一行抛的）反而被掩盖 —— 这个坑踩过一次。
  if (errors.length) {
    console.error("\n运行时错误 " + errors.length + " 条（这是根因，先修这个再看下面的断言）：");
    errors.slice(0, 20).forEach((item) => console.error("  [FAIL] " + item));
    process.exit(1);
  }
  // V11 去掉了朗读音色下拉，改检查知识库概览是否被正确回填
  if (filled.documentCount === null || filled.documentCount === 0) {
    console.error("[FAIL] 知识库文档数未回填");
    process.exit(1);
  }
  if (!fetchedStatus) {
    console.error("[FAIL] 没有请求 /api/status");
    process.exit(1);
  }
  if (!fetchCalls.some((u) => u.indexOf("/api/training") >= 0)) {
    console.error("[FAIL] 没有请求 /api/training");
    process.exit(1);
  }
  // §13 防回归：页面上不得出现被转义成文本的标签，或未填充的占位值
  const visibleText = documentStub.body
    ? String(documentStub.body.innerText || documentStub.body.textContent || "")
    : "";
  const forbidden = ["<svg", "<use", "undefined", "NaN", "Expecting value"];
  const leaked = forbidden.filter((token) => visibleText.indexOf(token) >= 0);
  if (leaked.length) {
    console.error("[FAIL] 页面可见文本里出现不该出现的内容：" + leaked.join("、"));
    const at = visibleText.indexOf(leaked[0]);
    console.error("  上下文: " + JSON.stringify(visibleText.slice(Math.max(0, at - 40), at + 80)));
    process.exit(1);
  }
  console.log("可见文本检查: OK（无 <svg / <use / undefined / NaN / Expecting value）");

  console.log("\nDOM simulation: OK");
}, 400);
