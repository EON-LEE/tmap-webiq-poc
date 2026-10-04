const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const vm = require("node:vm");

const staticRoot = join(process.cwd(), "src", "tmap_poc", "static");
const readStaticFile = (fileName) => readFileSync(join(staticRoot, fileName), "utf8");

const htmlSource = readStaticFile("index.html");
const appSource = readStaticFile("app.js");
const compareSource = readStaticFile("compare-view.js");
const clientModuleOrder = [
  "search-results.js",
  "run-labels.js",
  "flow-observations.js",
  "settings-view.js",
  "compare-view.js",
  "app.js",
];
const tick = () => new Promise(setImmediate);

function createElement(tagName = "div") {
  let ownText = "";
  const node = {
    tagName,
    value: "",
    disabled: false,
    hidden: false,
    checked: false,
    open: false,
    children: [],
    listeners: {},
    scrollHeight: 100,
    scrollTop: 0,
    clientHeight: 100,
    style: {},
    dataset: {},
    attributes: {},
    parentNode: null,
    className: "",
    id: "",
    href: "",
    target: "",
    rel: "",
    type: "",
    validity: { badInput: false },

    get textContent() {
      return ownText + this.children.map((child) => (
        typeof child === "string" ? child : child.textContent
      )).join("");
    },

    set textContent(value) {
      this.replaceChildren();
      ownText = String(value);
    },

    append(...children) {
      for (const child of children) {
        if (typeof child !== "string") child.parentNode = this;
        this.children.push(child);
      }
    },

    replaceChildren(...children) {
      for (const child of this.children) {
        if (typeof child !== "string") child.parentNode = null;
      }
      this.children = [];
      ownText = "";
      this.append(...children);
    },

    addEventListener(name, fn) {
      this.listeners[name] = fn;
    },

    setAttribute(name, value) {
      this.attributes[name] = String(value);
      if (name === "class") this.className = String(value);
      else if (name === "id") this.id = String(value);
      else if (name === "href") this.href = String(value);
      else if (name === "type") this.type = String(value);
      else if (name.startsWith("data-")) {
        this.dataset[name.slice(5).replace(/-([a-z])/g, (_, char) => char.toUpperCase())] = String(value);
      } else if (["hidden", "disabled", "checked", "open"].includes(name)) {
        this[name] = true;
      } else {
        this[name] = String(value);
      }
    },

    getAttribute(name) {
      return this.attributes[name] ?? null;
    },

    contains(descendant) {
      for (let current = descendant; current; current = current.parentNode) {
        if (current === this) return true;
      }
      return false;
    },

    focus() {
      this.focused = true;
      if (this.ownerDocument) this.ownerDocument.activeElement = this;
    },

    connect(other) {
      this.connected = other;
      return other;
    },

    disconnect() {
      this.disconnected = true;
    },

    classList: {
      toggle() {},
      add() {},
      remove() {},
      contains: (className) => hasClass(node, className),
    },

    set innerHTML(_) {
      throw new Error("Unsafe HTML insertion");
    },
  };
  return node;
}

function staticDocument(html) {
  const elements = {};
  const document = {
    getElementById: (id) => elements[id],
    createElement(tagName) {
      return Object.assign(createElement(tagName), { ownerDocument: document });
    },
    createElementNS(_namespace, tagName) {
      return document.createElement(tagName);
    },
  };
  const root = document.createElement("document");
  const stack = [root];
  const voidTags = new Set("area base br col embed hr img input link meta param source track wbr".split(" "));

  for (const [token] of html.matchAll(/<!--[\s\S]*?-->|<![^>]*>|<\/?[\w:-]+\b[^>]*>|[^<]+/g)) {
    if (token.startsWith("<!")) continue;
    if (token.startsWith("</")) {
      stack.pop();
      continue;
    }
    if (!token.startsWith("<")) {
      if (token.trim()) stack.at(-1).append(token);
      continue;
    }

    const [, tagName, attributes] = token.match(/^<([\w:-]+)\b([^>]*)>/);
    const node = document.createElement(tagName);
    for (const [, name, quoted, bare] of attributes.matchAll(/([:\w-]+)(?:="([^"]*)"|=([^\s>]+))?/g)) {
      node.setAttribute(name, quoted ?? bare ?? "");
    }
    if (node.id) elements[node.id] = node;
    if (tagName === "body") document.body = node;
    stack.at(-1).append(node);
    if (!voidTags.has(tagName) && !token.endsWith("/>")) stack.push(node);
  }

  document.activeElement = document.body;
  return { document, elements, root };
}

function descendants(node, tagName) {
  return (node?.children || [])
    .filter((child) => typeof child !== "string")
    .flatMap((child) => [
      ...(!tagName || child.tagName === tagName ? [child] : []),
      ...descendants(child, tagName),
    ]);
}

const hasClass = (node, className) => node.className?.split(/\s+/).includes(className);
const findByClass = (node, className) => descendants(node).filter((candidate) => hasClass(candidate, className));

function isVisible(node) {
  if (!node) return false;
  for (let current = node; current; current = current.parentNode) {
    if (current.hidden) return false;
    if (current.parentNode?.tagName === "details" && !current.parentNode.open
      && current !== current.parentNode.children.find((child) => child.tagName === "summary")) {
      return false;
    }
  }
  return true;
}

function sentMessages(socket) {
  return socket.sent.filter((value) => typeof value === "string").map(JSON.parse);
}

function providerCell(env, provider, turnIndex = 0) {
  return descendants(env.elements.turns.children[turnIndex]).find((node) => (
    hasClass(node, "cell") && node.dataset.provider === provider
  ));
}

function stepNode(cellNode, stepName) {
  return descendants(cellNode).find((node) => hasClass(node, "step") && node.dataset.step === stepName);
}

function classText(node, className) {
  return findByClass(node, className)[0]?.textContent || "";
}

const validPcmBase64 = Buffer.from([0, 128, 255, 127]).toString("base64");
const oddLengthPcmBase64 = Buffer.from([1, 2, 3]).toString("base64");
function voiceOptionsSchema() {
  const option = (value, label, requires) => ({ value, label, ...(requires ? { requires } : {}) });
  const selectField = (key, label, defaultValue, options, extra = {}) => ({
    key,
    label,
    type: "select",
    default: defaultValue,
    options,
    ...extra,
  });
  const defaults = {
    connection_mode: "agent",
    llm_model: null,
    realtime_model: null,
    transcription_model: "azure-speech",
    voice_name: "ko-KR-SunHiNeural",
    turn_detection: "azure_semantic_vad_multilingual",
    speech_rate: null,
    silence_duration_ms: null,
    return_agent_response_directly: true,
  };

  return {
    mode: "foundry_agent",
    defaults,
    defaults_by_mode: {
      agent: { ...defaults },
      model_search: {
        ...defaults,
        connection_mode: "model_search",
        llm_model: "gpt-4.1-mini",
        return_agent_response_directly: true,
      },
      realtime_agent_tool: {
        ...defaults,
        connection_mode: "realtime_agent_tool",
        realtime_model: "gpt-realtime-mini",
      },
      model_tools: {
        ...defaults,
        connection_mode: "model_tools",
        llm_model: "gpt-4.1-mini",
      },
    },
    supported_modes: ["agent", "model_search", "realtime_agent_tool", "model_tools"],
    fields: [
      selectField("connection_mode", "실행 구조", "agent", [
        option("agent", "Agent"),
        option("model_search", "STT → LLM → TTS"),
        option("realtime_agent_tool", "Realtime"),
        option("model_tools", "Model tools"),
      ]),
      selectField("llm_model", "텍스트 모델", null, [
        option(null, "Agent", { connection_mode: ["agent", "realtime_agent_tool"] }),
        option("gpt-4.1-mini", "gpt-4.1-mini", { connection_mode: ["model_search", "model_tools"] }),
        option("gpt-5-mini", "gpt-5-mini", { connection_mode: ["model_search", "model_tools"] }),
      ], { nullable: true, requires: { connection_mode: ["model_search", "model_tools"] } }),
      selectField("realtime_model", "Realtime 모델", null, [
        option(null, "없음", { connection_mode: ["agent", "model_search", "model_tools"] }),
        option("gpt-realtime-mini", "gpt-realtime-mini", { connection_mode: "realtime_agent_tool" }),
      ], { nullable: true, requires: { connection_mode: "realtime_agent_tool" } }),
      selectField("return_agent_response_directly", "Bing Agent 답변 전달", true, [
        option(true, "직접", { voice_name: ["ko-KR-SunHiNeural", "ko-KR-SunHi:DragonHDLatestNeural"] }),
        option(false, "재작성"),
      ], { requires: { connection_mode: ["model_search", "realtime_agent_tool"] } }),
      selectField("transcription_model", "STT", "azure-speech", [
        option("azure-speech", "azure-speech"),
        option("mai-transcribe", "mai-transcribe"),
      ]),
      selectField("voice_name", "TTS", "ko-KR-SunHiNeural", [
        option("ko-KR-SunHiNeural", "SunHi"),
        option("ko-KR-SunHi:DragonHDLatestNeural", "Dragon"),
        {
          ...option("openai:marin", "OpenAI native · marin", { connection_mode: "realtime_agent_tool" }),
          implies: { return_agent_response_directly: false },
        },
      ]),
      selectField("turn_detection", "VAD", "azure_semantic_vad_multilingual", [
        option("azure_semantic_vad_multilingual", "semantic"),
        option("server_vad", "server"),
      ]),
      {
        key: "speech_rate",
        label: "속도",
        type: "number",
        default: null,
        nullable: true,
        min: 0.5,
        max: 1.5,
        step: 0.05,
      },
      {
        key: "silence_duration_ms",
        label: "무음",
        type: "number",
        default: null,
        nullable: true,
        min: 100,
        max: 2000,
        step: 50,
      },
    ],
    unavailable_options: [{ label: "모델 도구", help: "숨김", requires: { connection_mode: "model_tools" } }],
    limitations: ["demo"],
  };
}

function configuredResponse(overrides = {}) {
  return {
    providers: [
      {
        id: "webiq",
        label: "WebIQ",
        configured: true,
        errors: [],
        warnings: [],
        agent: { name: "webiq-agent", version: "1.2", pinned: true },
      },
      {
        id: "bing",
        label: "Grounding with Bing",
        configured: true,
        errors: [],
        warnings: [],
        agent: { name: "bing-agent", version: "2.3", pinned: true },
      },
    ],
    errors: [],
    voice_options: voiceOptionsSchema(),
    observability: { flow_schema_version: 1 },
    ...overrides,
  };
}

function oneProviderUnavailableResponse() {
  return configuredResponse({
    providers: [
      { id: "webiq", label: "WebIQ", configured: true, errors: [] },
      {
        id: "bing",
        label: "Grounding with Bing",
        configured: false,
        errors: ["Bing Agent 키가 없습니다."],
      },
    ],
  });
}

function fakeTimers() {
  let now = 1000;
  let nextId = 1;
  const timeouts = new Map();
  return {
    now: () => now,
    setTimeout(fn, ms) {
      const id = nextId++;
      timeouts.set(id, { fn, at: now + ms });
      return id;
    },
    clearTimeout(id) {
      timeouts.delete(id);
    },
    advance(ms) {
      now += ms;
      const due = [...timeouts]
        .filter(([, timeout]) => timeout.at <= now)
        .sort((left, right) => left[1].at - right[1].at);
      for (const [id, timeout] of due) {
        if (timeouts.delete(id)) timeout.fn();
      }
    },
  };
}
async function createHarness(options = {}) {
  const { document, elements, root } = staticDocument(htmlSource);
  const timer = fakeTimers();
  const sockets = [];
  const audioContexts = [];
  const worklets = [];
  const confirmations = [];
  let getUserMediaCalls = 0;
  const track = {
    stopped: false,
    listeners: {},
    stop() {
      this.stopped = true;
    },
    addEventListener(name, fn) {
      this.listeners[name] = fn;
    },
  };
  const stream = {
    getTracks: () => [track],
    getAudioTracks: () => [track],
  };

  class FakeAudioNode {
    connect(other) {
      this.connected = other;
      return other;
    }

    disconnect() {
      this.disconnected = true;
    }
  }

  class FakeAudioContext {
    constructor(init) {
      this.sampleRate = options.sampleRate || init.sampleRate;
      this.requested = init.sampleRate;
      this.state = "suspended";
      this.currentTime = 10;
      this.destination = {};
      this.played = [];
      this.audioWorklet = {
        addModule: async (path) => {
          this.module = path;
        },
      };
      audioContexts.push(this);
    }

    async resume() {
      this.state = "running";
    }

    async suspend() {
      this.state = "suspended";
    }

    async close() {
      this.state = "closed";
    }

    createBuffer(channels, length, rate) {
      const data = new Float32Array(length);
      return {
        channels,
        length,
        rate,
        duration: length / rate,
        getChannelData: () => data,
      };
    }

    createBufferSource() {
      const node = new FakeAudioNode();
      node.start = (when = 0) => {
        node.when = when;
        this.played.push(node);
      };
      node.stop = () => {
        node.stopped = true;
      };
      return node;
    }

    createGain() {
      const node = new FakeAudioNode();
      node.gain = { value: 1 };
      return node;
    }

    createMediaStreamSource() {
      this.source = new FakeAudioNode();
      return this.source;
    }
  }

  class FakeWorklet extends FakeAudioNode {
    constructor() {
      super();
      this.port = {
        closed: false,
        close() {
          this.closed = true;
        },
      };
      worklets.push(this);
    }
  }

  class FakeSocket {
    static OPEN = 1;

    constructor(url) {
      this.url = url;
      this.readyState = 0;
      this.bufferedAmount = 0;
      this.sent = [];
      sockets.push(this);
    }

    send(value) {
      if (this.readyState !== 1) throw new Error("closed");
      this.sent.push(value);
    }

    close() {
      this.readyState = 3;
      this.closed = true;
    }

    open() {
      this.readyState = 1;
      this.onopen?.();
    }

    event(json) {
      this.onmessage?.({ data: JSON.stringify(json) });
    }
  }

  const location = { protocol: options.protocol || "http:", host: "localhost:8080" };
  const windowListeners = {};
  const window = {
    isSecureContext: options.secure !== false,
    AudioContext: FakeAudioContext,
    AudioWorkletNode: FakeWorklet,
    location,
    confirm(message) {
      confirmations.push(message);
      return options.confirm !== false;
    },
    addEventListener(name, fn) {
      const previous = windowListeners[name];
      windowListeners[name] = previous ? (event) => {
        previous(event);
        fn(event);
      } : fn;
    },
    dispatchEvent(event) {
      windowListeners[event.type]?.(event);
    },
  };

  const sandbox = {
    window,
    document,
    navigator: {
      mediaDevices: {
        getUserMedia: () => {
          getUserMediaCalls++;
          if (options.permissionError) return Promise.reject({ name: options.permissionError });
          return Promise.resolve(stream);
        },
      },
    },
    WebSocket: FakeSocket,
    AudioWorkletNode: FakeWorklet,
    location,
    fetch: async (url) => {
      if (url !== "/api/config") throw new Error(url);
      if (options.fetchFail) throw new Error("offline");
      return {
        ok: !options.fetchNotOk,
        json: async () => options.config || configuredResponse(),
      };
    },
    atob: (value) => Buffer.from(value, "base64").toString("binary"),
    URL,
    console,
    setTimeout: timer.setTimeout,
    clearTimeout: timer.clearTimeout,
  };
  const context = vm.createContext(sandbox);
  context.Date = class extends Date {
    constructor(...args) {
      super(...(args.length ? args : [timer.now()]));
    }
    static now() {
      return timer.now();
    }
  };

  for (const fileName of clientModuleOrder) {
    const code = readStaticFile(fileName)
      .replace(/^import .* from "[^"]+";\r?\n/gm, "")
      .replace(/^export /gm, "");
    vm.runInContext(code, context);
  }
  await tick();
  for (const node of descendants(root)) {
    if (node.id) elements[node.id] = node;
  }

  return {
    root,
    document,
    elements,
    sockets,
    audioContexts,
    worklets,
    confirmations,
    track,
    stream,
    context,
    visible: (id) => isVisible(elements[id]),
    getUserMediaCalls: () => getUserMediaCalls,
    advance: async (ms) => {
      timer.advance(ms);
      await tick();
    },
    submit: async (text) => {
      elements["command-input"].value = text;
      elements["command-form"].listeners.submit({ preventDefault() {} });
      await tick();
    },
    click: async (id) => {
      elements[id].listeners.click?.({ preventDefault() {} });
      await tick();
    },
    key: async (overrides = {}) => {
      const event = {
        key: "Enter",
        keyCode: 13,
        shiftKey: false,
        isComposing: false,
        defaultPrevented: false,
        preventDefault() {
          this.defaultPrevented = true;
        },
        ...overrides,
      };
      elements["command-input"].listeners.keydown(event);
      await tick();
      return event;
    },
    changeVoiceOption(key, value) {
      const input = descendants(root).find((node) => node.id === `voice-option-${key}`);
      const definition = vm.runInContext("config.voice_options", context).fields.find((field) => field.key === key);
      input.value = definition.type === "select"
        ? String(definition.options.findIndex((option) => option.value === value))
        : String(value ?? "");
      input.listeners.change?.();
      input.listeners.input?.();
    },
    voiceOptionValue(key) {
      const input = descendants(root).find((node) => node.id === `voice-option-${key}`);
      const definition = vm.runInContext("config.voice_options", context).fields.find((field) => field.key === key);
      return definition.type === "select"
        ? definition.options[Number(input.value)]?.value
        : input.value === "" ? null : Number(input.value);
    },
  };
}

async function startTextComparison(env, text = "삼성전자 주식 찾아줘.") {
  await env.submit(text);
  assert.equal(env.sockets.length, 2);
  for (const socket of env.sockets) socket.open();
  return env;
}

function readyProviderLane(env, provider) {
  const socket = env.sockets.find((candidate) => JSON.parse(candidate.sent[0]).provider === provider);
  socket.event({ type: "status", state: "ready" });
  return socket;
}

function completeResponse(socket, responseId, text = "답변입니다.") {
  socket.event({
    type: "transcript",
    role: "assistant",
    item_id: `answer-${responseId}`,
    response_id: responseId,
    text,
    final: true,
  });
  socket.event({
    type: "response_done",
    response_id: responseId,
    status: "completed",
    interrupted: false,
  });
}

function stockToolOutput() {
  return {
    financeResults: [{
      url: "https://example.com/stock",
      title: "삼성전자",
      data: {
        instrument: {
          displayName: "삼성전자",
          symbol: "005930",
          price: 273000,
          currency: "KRW",
          changePercent: -4.3783,
          lastTradedAt: "2026-09-28T14:26:48+09:00",
        },
      },
    }],
  };
}
test("static contract: comparison DOM, examples, settings and no unsafe sinks", async () => {
  const { elements } = staticDocument(htmlSource);
  for (const id of [
    "turns",
    "compare-empty",
    "command-input",
    "send-command",
    "start",
    "stop",
    "reset",
    "connection-settings",
    "voice-options-fields",
    "voice-options-defaults",
    "lane-webiq-dot",
    "lane-bing-dot",
    "lane-webiq-live",
    "lane-bing-live",
  ]) {
    assert.ok(elements[id], id);
  }
  for (const id of ["provider", "agent-flow-panel", "navigation-demo", "trace-panel", "scenario-control"]) {
    assert.equal(elements[id], undefined, id);
  }
  assert.equal(elements["connection-settings"].tagName, "details");
  assert.equal(elements["connection-settings"].open, false);
  assert.equal(elements["example-prompts"].children.length, 4);
  assert.deepEqual(elements["example-prompts"].children.map((button) => button.dataset.prompt), [
    "삼성전자 주식 찾아줘.",
    "서울역 근처 충전소 찾아줘.",
    "인천공항 주차비 얼마야?",
    "오늘 주요 뉴스 알려줘.",
  ]);
  assert.doesNotMatch(appSource, /\binnerHTML\b|\beval\s*\(/);
  assert.doesNotMatch(compareSource, /\binnerHTML\b|\beval\s*\(/);

  const env = await createHarness();
  for (const id of ["voice-group-pipeline", "voice-group-stt", "voice-group-tts"]) {
    assert.equal(env.elements[id].tagName, "fieldset");
  }
  assert.equal(env.elements["lane-webiq-live"].getAttribute("aria-pressed"), "true");
});

test("configuration: both providers, one unconfigured, fetch failure and insecure context", async () => {
  const ok = await createHarness();
  assert.equal(ok.elements["send-command"].disabled, false);
  assert.equal(ok.elements.start.disabled, false);
  assert.equal(ok.elements["lane-webiq-status"].textContent, "대기");

  const partial = await createHarness({ config: oneProviderUnavailableResponse() });
  assert.equal(partial.elements["send-command"].disabled, false);
  assert.equal(partial.elements["lane-bing-status"].textContent, "설정 필요");
  assert.match(partial.elements.error.textContent, /Bing Agent 키/);
  await partial.submit("질문");
  assert.equal(partial.sockets.length, 1);
  partial.sockets[0].open();
  assert.equal(JSON.parse(partial.sockets[0].sent[0]).provider, "webiq");

  const failed = await createHarness({ fetchFail: true });
  assert.equal(failed.elements["send-command"].disabled, true);
  assert.equal(failed.elements.start.disabled, true);
  assert.match(failed.elements.error.textContent, /서버가 실행/);

  const insecure = await createHarness({ secure: false });
  assert.equal(insecure.elements.start.disabled, true);
  assert.equal(insecure.elements["send-command"].disabled, false);
  assert.match(insecure.elements.status.textContent, /텍스트로 질문/);
});

test("text question opens two lanes and queues text until each lane is ready", async () => {
  const env = await createHarness();
  await startTextComparison(env, "삼성전자 주식 찾아줘.");
  assert.equal(env.elements.turns.children.length, 1);
  assert.equal(findByClass(env.elements.turns.children[0], "cell").length, 2);
  assert.equal(env.getUserMediaCalls(), 0);
  assert.equal(env.elements["command-input"].value, "");
  assert.equal(env.elements["send-command"].disabled, true);

  for (const socket of env.sockets) {
    assert.equal(socket.url, "ws://localhost:8080/ws/voice");
    assert.deepEqual(JSON.parse(socket.sent[0]), {
      type: "start",
      provider: JSON.parse(socket.sent[0]).provider,
      context: "",
      voice_options: {},
    });
    assert.equal(sentMessages(socket).filter((message) => message.type === "text").length, 0);
  }

  const webiq = readyProviderLane(env, "webiq");
  assert.deepEqual(sentMessages(webiq).at(-1), { type: "text", text: "삼성전자 주식 찾아줘." });
  const bing = readyProviderLane(env, "bing");
  assert.deepEqual(sentMessages(bing).at(-1), { type: "text", text: "삼성전자 주식 찾아줘." });

  completeResponse(webiq, "webiq-response", "WebIQ 답변");
  assert.equal(env.elements["send-command"].disabled, true);
  completeResponse(bing, "bing-response", "Bing 답변");
  assert.equal(env.elements["send-command"].disabled, false);
  assert.match(classText(env.elements.turns.children[0], "turn-compare"), /응답 시작 · WebIQ .*Grounding with Bing/);
});

test("follow-up reuses ready sockets and reconnects only a closed failed lane", async () => {
  const env = await createHarness();
  await startTextComparison(env, "첫 질문");
  const webiq = readyProviderLane(env, "webiq");
  const bing = readyProviderLane(env, "bing");
  completeResponse(webiq, "webiq-1", "첫 W");
  completeResponse(bing, "bing-1", "첫 B");

  await env.submit("둘째 질문");
  assert.equal(env.sockets.length, 2);
  assert.deepEqual(sentMessages(webiq).filter((message) => message.type === "text").map((message) => message.text), [
    "첫 질문",
    "둘째 질문",
  ]);

  completeResponse(webiq, "webiq-2", "둘째 W");
  bing.event({ type: "error", message: "Bing 장애" });
  assert.equal(providerCell(env, "bing", 1).dataset.status, "failed");
  assert.equal(env.elements["lane-bing-dot"].dataset.state, "error");

  await env.submit("셋째 질문");
  assert.equal(env.sockets.length, 3);
  env.sockets[2].open();
  env.sockets[2].event({ type: "status", state: "ready" });
  assert.equal(JSON.parse(env.sockets[2].sent[0]).provider, "bing");
  assert.equal(sentMessages(webiq).at(-1).text, "셋째 질문");
  assert.equal(sentMessages(env.sockets[2]).at(-1).text, "셋째 질문");
});
test("WebIQ finance rendering covers lifecycle, facts, raw JSON and answer formatting", async () => {
  const env = await createHarness();
  await startTextComparison(env, "삼성전자 주식 찾아줘.");
  const webiq = readyProviderLane(env, "webiq");
  const bing = readyProviderLane(env, "bing");

  webiq.event({
    type: "flow",
    stage: "tool",
    status: "arguments_ready",
    tool_id: "finance-tool",
    response_id: "webiq-response",
    data: { kind: "mcp_call", name: "finance", arguments: { query: "삼성전자 주가" } },
  });
  assert.equal(stepNode(providerCell(env, "webiq"), "search").dataset.state, "active");

  webiq.event({
    type: "tool",
    id: "finance-tool",
    kind: "mcp_call",
    name: "finance",
    arguments: { query: "삼성전자 주가" },
    output: stockToolOutput(),
    status: "completed",
    response_id: "webiq-response",
  });
  webiq.event({
    type: "transcript",
    role: "assistant",
    item_id: "webiq-answer",
    response_id: "webiq-response",
    text: "**삼성전자**는 현재 273,000원입니다. ",
    final: true,
  });
  webiq.event({ type: "response_done", response_id: "webiq-response", status: "completed", interrupted: false });

  const webiqCell = providerCell(env, "webiq");
  assert.equal(webiqCell.dataset.status, "done");
  assert.match(stepNode(webiqCell, "search").textContent, /금융 조회 · \d\.\d초/);
  assert.match(stepNode(webiqCell, "results").textContent, /1건/);
  assert.match(classText(webiqCell, "call-query"), /검색어 “삼성전자 주가”/);
  assert.match(webiqCell.textContent, /273,000 KRW/);
  assert.match(webiqCell.textContent, /▼4\.38%/);
  assert.ok(descendants(webiqCell, "details").find((node) => hasClass(node, "raw")).textContent.includes("financeResults"));
  assert.equal(findByClass(webiqCell, "answer-text")[0].textContent, "삼성전자는 현재 273,000원입니다.");
  assert.equal(descendants(findByClass(webiqCell, "answer-text")[0], "strong")[0].textContent, "삼성전자");

  completeResponse(bing, "bing-response", "Bing 완료");
  assert.match(classText(env.elements.turns.children[0], "turn-compare"), /WebIQ .*Grounding with Bing/);
});

test("Bing agent mode hides tool internals and dedupes safe citations", async () => {
  const env = await createHarness();
  await startTextComparison(env, "인천공항 주차비");
  readyProviderLane(env, "webiq");
  const bing = readyProviderLane(env, "bing");

  bing.event({ type: "flow", stage: "response", status: "created", response_id: "bing-response", data: {} });
  const bingCell = providerCell(env, "bing");
  assert.equal(stepNode(bingCell, "think").dataset.state, "active");
  assert.match(stepNode(bingCell, "think").textContent, /생각·검색 중…/);
  assert.equal(stepNode(bingCell, "search").dataset.state, "hidden");
  assert.equal(classText(bingCell, "activity-text"), "Agent가 생각하며 Bing으로 검색하는 중…");
  assert.equal(isVisible(findByClass(bingCell, "cell-activity")[0]), true);

  await env.advance(4200);
  bing.event({ type: "citation", response_id: "bing-response", url: "https://example.com/source", title: "출처" });
  bing.event({ type: "citation", response_id: "bing-response", url: "HTTPS://EXAMPLE.COM/source", title: "중복" });
  bing.event({ type: "citation", response_id: "bing-response", url: "javascript:alert(1)", title: "unsafe" });
  completeResponse(bing, "bing-response", "Bing 답변");

  assert.equal(stepNode(bingCell, "search").dataset.state, "hidden");
  assert.match(stepNode(bingCell, "search").textContent, /Agent가 Bing 검색/);
  assert.equal(stepNode(bingCell, "think").dataset.state, "done");
  assert.match(stepNode(bingCell, "think").textContent, /검색 포함 4\.2초/, "Bing's search happens inside the Agent's thinking");
  assert.match(stepNode(bingCell, "answer").textContent, /완료/);
  assert.match(classText(bingCell, "search-note"), /Bing 검색 결과를 읽고 답변을 작성했어요/);
  assert.doesNotMatch(bingCell.textContent, /비공개|공개하지|미공개/, "no wording about hidden results");
  assert.match(classText(bingCell, "sources"), /답변 출처 1개/);
  assert.equal(descendants(bingCell, "a").length, 1);
  assert.equal(isVisible(findByClass(bingCell, "cell-activity")[0]), false);
});

test("places, web and news results render facts and strip HTML; unsafe URLs stay unlinked", async () => {
  const env = await createHarness();
  await startTextComparison(env, "서울역 충전소");
  const webiq = readyProviderLane(env, "webiq");
  readyProviderLane(env, "bing");
  const output = {
    placeResults: [{
      name: "서울역 E-pit",
      category: "EV 충전 스테이션",
      url: "https://www.e-pit.co.kr/",
      location: { latitude: 37.55552, longitude: 126.96962 },
      openHours: {
        standard: {
          sun: ["00:00-23:59"],
          mon: ["00:00-23:59"],
          tue: ["00:00-23:59"],
          wed: ["00:00-23:59"],
          thu: ["00:00-23:59"],
          fri: ["00:00-23:59"],
          sat: ["00:00-23:59"],
        },
      },
    }],
    webResults: [{ title: "공항", url: "https://example.com/web", content: "<I>Airport Guide</I><BR>주차 요금" }],
    newsResults: [{ title: "뉴스", url: "file:///bad", content: "<b>속보</b> 내용" }],
  };

  webiq.event({
    type: "tool",
    id: "places-tool",
    kind: "mcp_call",
    name: "places",
    arguments: { query: "서울역 충전소" },
    output,
    status: "completed",
    response_id: "places-response",
  });

  const webiqCell = providerCell(env, "webiq");
  assert.match(webiqCell.textContent, /EV 충전 스테이션/);
  assert.match(webiqCell.textContent, /24시간 영업/);
  assert.match(webiqCell.textContent, /좌표 37\.5555, 126\.9696/);
  assert.match(webiqCell.textContent, /Airport Guide 주차 요금/);
  assert.match(webiqCell.textContent, /속보 내용/);
  assert.equal(descendants(webiqCell, "a").some((link) => link.href.startsWith("file:")), false);
});

test("End-to-end waits on tool-only completion and then settles on follow-up text", async () => {
  const env = await createHarness();
  env.changeVoiceOption("connection_mode", "realtime_agent_tool");
  await startTextComparison(env, "삼성전자");
  const bing = readyProviderLane(env, "bing");
  readyProviderLane(env, "webiq");
  assert.equal(JSON.parse(bing.sent[0]).voice_options.connection_mode, "realtime_agent_tool");

  bing.event({
    type: "tool",
    id: "agent-tool",
    kind: "foundry_agent_call",
    name: "bing-agent",
    arguments: { input: "삼성전자 주식 가격" },
    output: "**Agent** 답변【5:0†source】",
    status: "completed",
    response_id: "tool-response",
  });
  bing.event({ type: "response_done", response_id: "tool-response", status: "completed", interrupted: false });
  assert.equal(env.elements["send-command"].disabled, true);

  const bingCell = providerCell(env, "bing");
  assert.match(bingCell.textContent, /Grounding with Bing Agent 호출/);
  assert.match(bingCell.textContent, /Agent에 보낸 요청 “삼성전자 주식 가격”/);
  assert.match(bingCell.textContent, /Agent 답변 “Agent 답변”/);

  bing.event({
    type: "transcript",
    role: "assistant",
    item_id: "answer",
    response_id: "answer-response",
    text: "최종 답변",
    final: true,
  });
  bing.event({ type: "response_done", response_id: "answer-response", status: "completed", interrupted: false });
  assert.equal(providerCell(env, "bing").dataset.status, "done");
});
test("interrupt stops playback and ignores late cancelled response events", async () => {
  const env = await createHarness();
  await startTextComparison(env, "오류");
  const webiq = readyProviderLane(env, "webiq");
  readyProviderLane(env, "bing");

  webiq.event({ type: "transcript", role: "assistant", item_id: "answer", response_id: "response", text: "초기", final: false });
  webiq.event({ type: "audio", response_id: "response", data: validPcmBase64 });
  webiq.event({ type: "interrupt", response_id: "response" });
  webiq.event({ type: "response_done", response_id: "response", status: "cancelled", interrupted: true });
  const before = providerCell(env, "webiq").textContent;

  assert.equal(providerCell(env, "webiq").dataset.status, "interrupted");
  assert.equal(env.audioContexts[0].played[0].stopped, true);
  for (const lateEvent of [
    { type: "transcript", role: "assistant", item_id: "answer", response_id: "response", text: "late", final: true },
    { type: "tool", id: "late", name: "web", response_id: "response", output: { webResults: [{ title: "late" }] } },
    { type: "citation", response_id: "response", url: "https://example.com/late" },
    { type: "audio", response_id: "response", data: validPcmBase64 },
  ]) {
    webiq.event(lateEvent);
  }
  assert.equal(providerCell(env, "webiq").textContent, before);
});

test("response_busy fails only the echoed cell and leaves the lane connected", async () => {
  const env = await createHarness();
  await startTextComparison(env, "오류");
  readyProviderLane(env, "webiq");
  const bing = readyProviderLane(env, "bing");

  bing.event({ type: "error", code: "response_busy", message: "busy" });
  assert.equal(providerCell(env, "bing").dataset.status, "failed");
  assert.equal(env.elements["lane-bing-dot"].dataset.state, "ready");
});

test("idle watchdog fails an awaiting lane after 45 seconds", async () => {
  const env = await createHarness();
  await startTextComparison(env, "응답 없음");
  const webiq = readyProviderLane(env, "webiq");
  const bing = readyProviderLane(env, "bing");
  completeResponse(bing, "bing-response", "Bing 완료");

  await env.advance(45001);
  assert.match(classText(providerCell(env, "webiq"), "cell-notice"), /응답이 오지 않아/);
  assert.equal(env.elements["send-command"].disabled, false);
  webiq.event({ type: "error", message: "terminal" });
  assert.equal(env.elements["lane-webiq-dot"].dataset.state, "error");
});

test("audio live switching, replay and odd PCM failure", async () => {
  const env = await createHarness();
  await startTextComparison(env, "오디오");
  const webiq = readyProviderLane(env, "webiq");
  const bing = readyProviderLane(env, "bing");

  webiq.event({ type: "audio", response_id: "webiq-response", data: validPcmBase64 });
  webiq.event({ type: "audio", response_id: "webiq-response", data: validPcmBase64 });
  assert.equal(env.audioContexts[0].played.length, 2);
  assert.equal(
    env.audioContexts[0].played[1].when,
    env.audioContexts[0].played[0].when + env.audioContexts[0].played[0].buffer.duration,
  );

  bing.event({ type: "audio", response_id: "bing-response", data: validPcmBase64 });
  assert.equal(env.audioContexts[0].played.length, 2);
  await env.click("lane-bing-live");
  assert.equal(env.elements["lane-bing-live"].getAttribute("aria-pressed"), "true");
  assert.equal(env.audioContexts[0].played[0].stopped, true);
  bing.event({ type: "audio", response_id: "bing-response", data: validPcmBase64 });
  assert.equal(env.audioContexts[0].played.length, 3);

  completeResponse(bing, "bing-response", "Bing audio");
  const replayButton = findByClass(providerCell(env, "bing"), "replay")[0];
  assert.equal(isVisible(replayButton), true);
  replayButton.listeners.click();
  await tick();
  assert.equal(env.audioContexts[0].played.length, 4);
  assert.equal(replayButton.getAttribute("aria-pressed"), "true");
  replayButton.listeners.click();
  await tick();
  assert.equal(env.audioContexts[0].played[3].stopped, true);

  webiq.event({ type: "audio", response_id: "bad-response", data: oddLengthPcmBase64 });
  assert.equal(providerCell(env, "webiq").dataset.status, "failed");
});

test("voice mode shares microphone/worklet and broadcasts only to ready lanes", async () => {
  const env = await createHarness();
  await env.click("start");
  assert.equal(env.getUserMediaCalls(), 1);
  assert.equal(env.audioContexts[0].module, "/static/pcm-worklet.js");
  assert.equal(env.sockets.length, 2);
  for (const socket of env.sockets) socket.open();
  const webiq = readyProviderLane(env, "webiq");
  const bing = env.sockets.find((socket) => socket !== webiq);
  const frame = new ArrayBuffer(4800);
  assert.equal(env.worklets.length, 1);

  env.worklets[0].port.onmessage({ data: frame });
  assert.equal(webiq.sent.at(-1), frame);
  assert.notEqual(bing.sent.at(-1), frame);

  bing.event({ type: "status", state: "ready" });
  // A single spike right after a main-thread stall is not real backpressure: the browser drains it on the
  // very next task, so the lane must only fail once the spike is sustained for BACKPRESSURE_SUSTAIN_MS.
  bing.bufferedAmount = 96001;
  env.worklets[0].port.onmessage({ data: frame });
  assert.notEqual(env.elements["lane-bing-dot"].dataset.state, "error");
  await env.advance(1500);
  env.worklets[0].port.onmessage({ data: frame });
  assert.equal(env.elements["lane-bing-dot"].dataset.state, "error");

  webiq.event({ type: "transcript", role: "user", input_mode: "audio", item_id: "user", text: "삼성", final: false });
  webiq.event({ type: "transcript", role: "user", input_mode: "audio", item_id: "user", text: "삼성전자 주식", final: true });
  assert.equal(env.elements.turns.children.length, 1);
  assert.match(classText(env.elements.turns.children[0], "turn-question"), /삼성전자 주식/);
  assert.match(classText(providerCell(env, "webiq"), "cell-recognized"), /삼성/);

  env.track.listeners.ended();
  assert.match(env.elements.error.textContent, /마이크 연결/);
});
test("a transient bufferedAmount spike that drains before the sustain window clears the lane", async () => {
  const env = await createHarness();
  await env.click("start");
  for (const socket of env.sockets) socket.open();
  const webiq = readyProviderLane(env, "webiq");
  const bing = env.sockets.find((socket) => socket !== webiq);
  bing.event({ type: "status", state: "ready" });
  const frame = new ArrayBuffer(4800);

  bing.bufferedAmount = 96001;
  env.worklets[0].port.onmessage({ data: frame });
  await env.advance(500);
  // The browser caught up and drained the burst well within the sustain window.
  bing.bufferedAmount = 0;
  env.worklets[0].port.onmessage({ data: frame });
  await env.advance(2000);
  env.worklets[0].port.onmessage({ data: frame });
  assert.notEqual(env.elements["lane-bing-dot"].dataset.state, "error");
});
test("bufferedAmount above the hard cap fails the lane immediately", async () => {
  const env = await createHarness();
  await env.click("start");
  for (const socket of env.sockets) socket.open();
  const webiq = readyProviderLane(env, "webiq");
  const bing = env.sockets.find((socket) => socket !== webiq);
  bing.event({ type: "status", state: "ready" });
  bing.bufferedAmount = 480001;
  env.worklets[0].port.onmessage({ data: new ArrayBuffer(4800) });
  assert.equal(env.elements["lane-bing-dot"].dataset.state, "error");
});
test("permission denial starts no sockets", async () => {
  const env = await createHarness({ permissionError: "NotAllowedError" });
  await env.click("start");
  assert.equal(env.sockets.length, 0);
  assert.match(env.elements.error.textContent, /권한/);
});

test("stop releases sockets tracks worklet and suspends AudioContext", async () => {
  const env = await createHarness();
  await env.click("start");
  for (const socket of env.sockets) socket.open();
  readyProviderLane(env, "webiq");
  readyProviderLane(env, "bing");
  env.sockets[0].event({
    type: "transcript",
    role: "user",
    input_mode: "audio",
    item_id: "user",
    text: "음성 질문",
    final: true,
  });

  await env.click("stop");
  for (const socket of env.sockets) assert.deepEqual(sentMessages(socket).at(-1), { type: "stop" });
  assert.equal(env.track.stopped, true);
  assert.equal(env.worklets[0].port.closed, true);
  assert.equal(env.worklets[0].disconnected, true);
  assert.equal(env.audioContexts[0].state, "suspended");
  assert.equal(providerCell(env, "webiq").dataset.status, "interrupted");

  const sentCount = env.sockets[0].sent.length;
  env.worklets[0].port.onmessage?.({ data: new ArrayBuffer(4) });
  env.sockets[0].event({ type: "transcript", role: "assistant", text: "late", final: true });
  assert.equal(env.sockets[0].sent.length, sentCount);
});

test("settings offer only Agent and End-to-end, stay editable while connected and restart on any change", async () => {
  const env = await createHarness();
  const modeSelect = descendants(env.root).find((node) => node.id === "voice-option-connection_mode");
  const offered = modeSelect.children.filter((option) => !option.hidden && !option.disabled).map((option) => option.textContent);
  assert.deepEqual(offered, ["Agent 연결 (기본)", "End-to-end (Realtime)"]);
  assert.ok(modeSelect.children[1].hidden && modeSelect.children[1].disabled, "STT → LLM → TTS is not offered");
  assert.ok(modeSelect.children[3].hidden && modeSelect.children[3].disabled, "the app-control scenario is not offered");

  await startTextComparison(env, "설정 전");
  readyProviderLane(env, "webiq");
  readyProviderLane(env, "bing");
  env.changeVoiceOption("connection_mode", "realtime_agent_tool");
  assert.equal(env.audioContexts[0].state, "suspended");
  assert.equal(env.sockets.every((socket) => socket.closed), true);

  await env.submit("설정 후");
  assert.equal(env.sockets.length, 4);
  env.sockets[2].open();
  assert.equal(JSON.parse(env.sockets[2].sent[0]).voice_options.connection_mode, "realtime_agent_tool");
  const sttInput = descendants(env.root).find((node) => node.id === "voice-option-transcription_model");
  const vadInput = descendants(env.root).find((node) => node.id === "voice-option-turn_detection");
  assert.equal(vadInput.disabled, false, "every setting stays editable while connected");
  assert.equal(env.elements["voice-options-defaults"].disabled, false);
  env.changeVoiceOption("turn_detection", "server_vad");
  assert.equal(env.sockets.every((socket) => socket.closed), true, "a change ends the connection");
  assert.match(env.elements.status.textContent, /설정을 바꿨습니다/);

  await env.submit("설정 변경 후");
  assert.equal(env.sockets.length, 6);
  env.sockets[4].open();
  assert.equal(JSON.parse(env.sockets[4].sent[0]).voice_options.turn_detection, "server_vad");
  await env.click("voice-options-defaults");
  assert.equal(env.sockets.every((socket) => socket.closed), true, "restoring defaults also ends the connection");
  assert.match(env.elements.status.textContent, /기본값으로 되돌렸습니다/);
  assert.equal(env.voiceOptionValue("connection_mode"), "realtime_agent_tool");
  assert.equal(env.voiceOptionValue("return_agent_response_directly"), true);
  assert.equal(env.voiceOptionValue("realtime_model"), "gpt-realtime-mini");
  assert.equal(env.voiceOptionValue("turn_detection"), "azure_semantic_vad_multilingual");
  assert.equal(sttInput.parentNode.hidden, true, "End-to-end has no caption model to choose");
});

test("End-to-end offers the model's own voice directly and switches Bing's delivery with it", async () => {
  const env = await createHarness();
  const voiceSelect = descendants(env.root).find((node) => node.id === "voice-option-voice_name");
  const native = voiceSelect.children[2];
  assert.equal(native.hidden, true, "Agent mode keeps Azure voices");
  env.changeVoiceOption("connection_mode", "realtime_agent_tool");
  assert.equal(native.hidden, false, "offered without changing Bing's delivery first");
  const sttWrapper = descendants(env.root).find((node) => node.id === "voice-option-transcription_model").parentNode;
  assert.equal(sttWrapper.hidden, true, "End-to-end has no caption model to choose");

  env.changeVoiceOption("voice_name", "openai:marin");
  assert.equal(env.voiceOptionValue("return_agent_response_directly"), false);
  assert.equal(env.elements["voice-options-error"].hidden, true);
  await env.submit("질문");
  env.sockets[0].open();
  const options = JSON.parse(env.sockets[0].sent[0]).voice_options;
  assert.equal(options.voice_name, "openai:marin");
  assert.equal(options.return_agent_response_directly, false);

  env.changeVoiceOption("connection_mode", "agent");
  assert.equal(env.voiceOptionValue("voice_name"), "ko-KR-SunHiNeural");
  assert.equal(sttWrapper.hidden, false, "Agent mode keeps its speech recognition choice");
});

test("reset confirmation clears only after approval", async () => {
  const cancelEnv = await createHarness({ confirm: false });
  await startTextComparison(cancelEnv, "보존");
  for (const socket of cancelEnv.sockets) socket.open();
  readyProviderLane(cancelEnv, "webiq");
  readyProviderLane(cancelEnv, "bing");
  await cancelEnv.click("reset");
  assert.equal(cancelEnv.elements.turns.children.length, 1);

  const confirmEnv = await createHarness({ confirm: true });
  await startTextComparison(confirmEnv, "삭제");
  for (const socket of confirmEnv.sockets) socket.open();
  readyProviderLane(confirmEnv, "webiq");
  readyProviderLane(confirmEnv, "bing");
  await confirmEnv.click("reset");
  assert.equal(confirmEnv.elements.turns.children.length, 0);
  assert.equal(confirmEnv.elements["compare-empty"].hidden, false);
  assert.equal(confirmEnv.sockets.every((socket) => socket.closed), true);
});

test("composer respects IME, Shift+Enter and normal Enter", async () => {
  const env = await createHarness();
  for (const keyOptions of [{ isComposing: true }, { shiftKey: true }, { keyCode: 229 }]) {
    env.elements["command-input"].value = "조합";
    const event = await env.key(keyOptions);
    assert.equal(event.defaultPrevented, false);
    assert.equal(env.sockets.length, 0);
  }

  env.elements["command-input"].value = "엔터 질문";
  const event = await env.key();
  assert.equal(event.defaultPrevented, true);
  assert.equal(env.sockets.length, 2);
  assert.equal(env.elements["command-input"].value, "");
});

test("example prompts only fill and focus the composer", async () => {
  const env = await createHarness();
  await env.submit("엔터 질문");
  const socketCount = env.sockets.length;
  env.elements["example-prompts"].children[1].listeners.click();
  assert.equal(env.elements["command-input"].value, "서울역 근처 충전소 찾아줘.");
  assert.equal(env.document.activeElement, env.elements["command-input"]);
  assert.equal(env.sockets.length, socketCount);
});

test("pagehide finishes active group and closes the page AudioContext", async () => {
  const env = await createHarness();
  await startTextComparison(env, "나가기");
  for (const socket of env.sockets) socket.open();
  readyProviderLane(env, "webiq");
  readyProviderLane(env, "bing");

  env.context.window.dispatchEvent({ type: "pagehide" });
  await tick();
  assert.equal(env.sockets.every((socket) => socket.closed), true);
  assert.equal(env.audioContexts[0].state, "closed");
});

test("voice turns align both engines in one row and a new utterance starts the next row", async () => {
  const env = await createHarness();
  await env.click("start");
  for (const socket of env.sockets) socket.open();
  const webiq = readyProviderLane(env, "webiq");
  const bing = readyProviderLane(env, "bing");
  const speak = (socket, itemId, text) => {
    socket.event({ type: "transcript", role: "user", input_mode: "audio", item_id: itemId, text: "", final: false });
    socket.event({ type: "transcript", role: "user", input_mode: "audio", item_id: itemId, text, final: true });
  };

  speak(webiq, "webiq-user-1", "서울역 근처 충전소 찾아줘.");
  speak(bing, "bing-user-1", "서울역 근처 충전소 찾아줘");
  assert.equal(env.elements.turns.children.length, 1, "both engines hear one utterance and share its row");
  const firstRow = env.elements.turns.children[0];
  assert.equal(firstRow.dataset.kind, "voice");
  assert.match(classText(firstRow, "turn-question"), /서울역 근처 충전소 찾아줘\./);
  assert.match(classText(providerCell(env, "webiq"), "cell-recognized"), /찾아줘\./);
  assert.match(classText(providerCell(env, "bing"), "cell-recognized"), /찾아줘”/, "each engine shows its own recognition");

  completeResponse(webiq, "webiq-response-1", "WebIQ 첫 답변");
  completeResponse(bing, "bing-response-1", "Bing 첫 답변");
  speak(bing, "bing-user-2", "오늘 주요 뉴스 알려줘.");
  speak(webiq, "webiq-user-2", "오늘 주요 뉴스 알려줘.");
  assert.equal(env.elements.turns.children.length, 2);
  completeResponse(webiq, "webiq-response-2", "WebIQ 둘째 답변");
  assert.match(classText(providerCell(env, "webiq", 1), "answer-text"), /WebIQ 둘째 답변/);
  assert.match(classText(providerCell(env, "webiq", 0), "answer-text"), /WebIQ 첫 답변/, "earlier answers stay in their row");
  await env.click("stop");
});

test("one engine failing leaves the other running; both failing ends the comparison", async () => {
  const env = await createHarness();
  await startTextComparison(env, "삼성전자 주식 찾아줘.");
  const webiq = readyProviderLane(env, "webiq");
  const bing = readyProviderLane(env, "bing");

  bing.event({ type: "error", code: "VoiceServiceError", message: "Bing 연결 오류", terminal: true });
  assert.equal(providerCell(env, "bing").dataset.status, "failed");
  assert.equal(stepNode(providerCell(env, "bing"), "think").dataset.state, "failed", "the step in progress shows where it stopped");
  assert.match(classText(providerCell(env, "bing"), "cell-notice"), /Bing 연결 오류/);
  assert.equal(env.elements.stop.hidden, false, "the comparison keeps running with WebIQ");
  completeResponse(webiq, "webiq-response", "WebIQ 답변");
  assert.equal(providerCell(env, "webiq").dataset.status, "done");

  webiq.onclose();
  assert.equal(env.elements.stop.hidden, true, "no engine is left, so the comparison ends");
  assert.equal(env.elements.start.hidden, false);
  assert.match(env.elements.status.textContent, /두 엔진의 연결이 모두 중단/);
  assert.equal(env.audioContexts[0].state, "suspended");
});

test("text turns show the Agent thinking, searching and writing with each step's time", async () => {
  const env = await createHarness();
  await startTextComparison(env, "삼성전자 주식 찾아줘.");
  const cell = providerCell(env, "webiq");
  const activity = () => findByClass(cell, "cell-activity")[0];
  assert.equal(classText(cell, "activity-text"), "엔진에 연결하는 중…");
  assert.equal(classText(cell, "cell-state"), "연결 중…");

  const webiq = readyProviderLane(env, "webiq");
  readyProviderLane(env, "bing");
  assert.equal(cell.dataset.phase, "thinking");
  assert.equal(stepNode(cell, "input").dataset.state, "done");
  assert.equal(stepNode(cell, "think").dataset.state, "active");
  assert.match(stepNode(cell, "think").textContent, /생각 중…/);
  assert.equal(classText(cell, "cell-state"), "생각 중…");
  assert.equal(classText(cell, "activity-text"), "Agent가 질문을 이해하고 무엇을 검색할지 생각하는 중…");
  assert.equal(isVisible(activity()), true, "thinking is visible before any search or answer arrives");

  await env.advance(1200);
  webiq.event({
    type: "flow",
    stage: "tool",
    status: "arguments_ready",
    tool_id: "finance-tool",
    response_id: "webiq-response",
    data: { kind: "mcp_call", name: "finance", arguments: { query: "삼성전자 주가" } },
  });
  assert.equal(stepNode(cell, "think").dataset.state, "done");
  assert.match(stepNode(cell, "think").textContent, /1\.2초/);
  assert.equal(stepNode(cell, "search").dataset.state, "active");
  assert.equal(classText(cell, "cell-state"), "검색 중…");
  assert.equal(classText(cell, "activity-text"), "WebIQ로 금융 조회 중…");

  await env.advance(800);
  webiq.event({
    type: "tool",
    id: "finance-tool",
    kind: "mcp_call",
    name: "finance",
    arguments: { query: "삼성전자 주가" },
    output: stockToolOutput(),
    status: "completed",
    response_id: "webiq-response",
  });
  assert.match(stepNode(cell, "search").textContent, /금융 조회 · 0\.8초/);
  assert.equal(stepNode(cell, "answer").dataset.state, "active");
  assert.match(stepNode(cell, "answer").textContent, /작성 중…/);
  assert.equal(classText(cell, "cell-state"), "답변 작성 중…");
  assert.equal(classText(cell, "activity-text"), "찾은 결과를 읽고 답변을 준비하는 중…");

  await env.advance(1500);
  webiq.event({
    type: "transcript", role: "assistant", item_id: "webiq-answer", response_id: "webiq-response",
    text: "삼성전자는 ", final: false,
  });
  assert.equal(classText(cell, "cell-state"), "답변 중…");
  assert.equal(isVisible(activity()), false, "the answer itself replaces the activity bubble");
  completeResponse(webiq, "webiq-response", "삼성전자는 273,000원입니다.");
  assert.equal(stepNode(cell, "answer").dataset.state, "done");
  assert.match(stepNode(cell, "answer").textContent, /작성 1\.5초/);
  assert.equal(classText(cell, "cell-state"), "응답 3.5초");
});

test("voice turns show listening, recognition time and thinking before the answer", async () => {
  const env = await createHarness();
  await env.click("start");
  for (const socket of env.sockets) socket.open();
  const webiq = readyProviderLane(env, "webiq");
  readyProviderLane(env, "bing");

  webiq.event({ type: "flow", stage: "speech", status: "started", item_id: "user-1", data: {} });
  webiq.event({ type: "transcript", role: "user", input_mode: "audio", item_id: "user-1", text: "", final: false });
  const cell = providerCell(env, "webiq");
  assert.equal(cell.dataset.phase, "listening");
  assert.equal(classText(cell, "activity-text"), "말씀을 듣는 중…");
  assert.match(stepNode(cell, "input").textContent, /듣는 중…/);

  await env.advance(2000);
  webiq.event({ type: "flow", stage: "speech", status: "stopped", item_id: "user-1", data: {} });
  assert.equal(classText(cell, "cell-state"), "인식 중…");
  assert.equal(classText(cell, "activity-text"), "말씀을 글자로 바꾸는 중…");

  await env.advance(700);
  webiq.event({ type: "transcript", role: "user", input_mode: "audio", item_id: "user-1", text: "삼성전자 주식 찾아줘.", final: true });
  assert.match(stepNode(cell, "input").textContent, /인식 0\.7초/);
  assert.equal(classText(cell, "cell-recognized"), "Agent가 받은 질문 “삼성전자 주식 찾아줘.”", "the Agent gets exactly this text");
  assert.equal(stepNode(cell, "think").dataset.state, "active");
  assert.equal(classText(cell, "cell-state"), "생각 중…");

  await env.advance(1000);
  completeResponse(webiq, "webiq-response", "삼성전자 답변");
  assert.match(stepNode(cell, "think").textContent, /1\.0초/);
  assert.equal(stepNode(cell, "search").dataset.state, "skipped");
  assert.match(stepNode(cell, "search").textContent, /검색 안 함/);
  assert.equal(classText(cell, "cell-state"), "응답 1.7초", "response time counts from the end of speech");
  await env.click("stop");
});

test("End-to-end shows no caption, starts thinking at the end of speech and separates a spoken filler", async () => {
  const env = await createHarness();
  env.changeVoiceOption("connection_mode", "realtime_agent_tool");
  await env.click("start");
  for (const socket of env.sockets) socket.open();
  const webiq = readyProviderLane(env, "webiq");
  readyProviderLane(env, "bing");
  webiq.event({ type: "flow", stage: "speech", status: "started", item_id: "user-1", data: {} });
  webiq.event({ type: "transcript", role: "user", input_mode: "audio", item_id: "user-1", text: "", final: false });
  const cell = providerCell(env, "webiq");

  await env.advance(1500);
  webiq.event({ type: "flow", stage: "speech", status: "stopped", item_id: "user-1", data: {} });
  assert.equal(cell.dataset.phase, "thinking", "the realtime model starts on the audio, not on the caption");
  assert.equal(stepNode(cell, "input").dataset.state, "done");
  assert.match(stepNode(cell, "input").textContent, /음성 그대로 전달/);
  assert.equal(classText(cell, "activity-text"), "Realtime 모델이 음성을 직접 듣고 생각하는 중…");

  await env.advance(300);
  webiq.event({
    type: "flow", stage: "tool", status: "arguments_ready", tool_id: "t1", response_id: "r1",
    data: { kind: "mcp_call", name: "finance", arguments: { query: "하이닉스 주식 가격" } },
  });
  assert.equal(cell.dataset.phase, "searching");
  assert.equal(classText(cell, "activity-text"), "WebIQ로 금융 조회 중…");
  // With an Azure voice the spoken filler's transcript can arrive after the search has started.
  await env.advance(300);
  webiq.event({ type: "transcript", role: "assistant", item_id: "filler", response_id: "r1", text: "잠시만요, 확인해 볼게요.", final: true });
  webiq.event({ type: "response_done", response_id: "r1", status: "completed", interrupted: false, followup: true });
  assert.notEqual(cell.dataset.status, "done", "the answer comes in the follow-up response");
  assert.equal(cell.dataset.phase, "searching", "talk before the search is not the answer");
  assert.equal(classText(cell, "answer-filler"), "대기 멘트 “잠시만요, 확인해 볼게요.”");
  assert.equal(classText(cell, "answer-text"), "");

  webiq.event({ type: "transcript", role: "user", input_mode: "audio", item_id: "user-1", text: "하이브 주식 종가 알려줘.", final: true });
  assert.equal(isVisible(findByClass(cell, "cell-recognized")[0]), false, "no separate caption for a model that hears the audio");
  assert.equal(classText(env.elements.turns.children[0], "turn-question"), "음성 질문 · 모델이 음성을 직접 들어요");
  assert.match(classText(cell, "call-query"), /하이닉스 주식 가격/, "what the model understood shows in its search");

  await env.advance(500);
  webiq.event({
    type: "tool", id: "t1", kind: "mcp_call", name: "finance", arguments: { query: "하이닉스 주식 가격" },
    output: stockToolOutput(), status: "completed", response_id: "r1",
  });
  assert.equal(classText(cell, "activity-text"), "찾은 결과를 읽고 답변을 준비하는 중…");

  await env.advance(900);
  completeResponse(webiq, "r2", "SK하이닉스는 1,756,000원입니다.");
  assert.equal(cell.dataset.status, "done");
  assert.equal(classText(cell, "answer-text"), "SK하이닉스는 1,756,000원입니다.");
  assert.match(stepNode(cell, "think").textContent, /0\.3초/);
  assert.match(stepNode(cell, "answer").textContent, /작성 0\.9초/);
  assert.equal(classText(cell, "answer-timing"), "대기 멘트 0.6초 · 응답 시작 2.0초 · 완료 2.0초");
  assert.equal(classText(cell, "cell-state"), "응답 2.0초", "the filler does not count as the answer");
  await env.click("stop");
});

test("a new spoken question ends an earlier answer that was still waiting for its search", async () => {
  const env = await createHarness();
  env.changeVoiceOption("connection_mode", "realtime_agent_tool");
  await env.click("start");
  for (const socket of env.sockets) socket.open();
  const webiq = readyProviderLane(env, "webiq");
  readyProviderLane(env, "bing");
  const ask = (itemId, text) => {
    webiq.event({ type: "transcript", role: "user", input_mode: "audio", item_id: itemId, text: "", final: false });
    webiq.event({ type: "flow", stage: "speech", status: "stopped", item_id: itemId, data: {} });
    webiq.event({ type: "transcript", role: "user", input_mode: "audio", item_id: itemId, text, final: true });
  };
  ask("user-1", "첫 질문");
  webiq.event({ type: "flow", stage: "tool", status: "arguments_ready", tool_id: "t1", response_id: "r1", data: { kind: "mcp_call", name: "web" } });
  webiq.event({ type: "response_done", response_id: "r1", status: "completed", interrupted: false, followup: true });
  assert.equal(providerCell(env, "webiq", 0).dataset.phase, "searching");
  ask("user-2", "둘째 질문");
  assert.equal(providerCell(env, "webiq", 0).dataset.status, "interrupted");
  assert.match(classText(providerCell(env, "webiq", 0), "cell-notice"), /다음 질문이 시작되어/);
  await env.click("stop");
});

test("End-to-end Bing shows its web search answer and sources without an Agent", async () => {
  const env = await createHarness();
  env.changeVoiceOption("connection_mode", "realtime_agent_tool");
  const delivery = descendants(env.root).find((node) => node.id === "voice-option-return_agent_response_directly").parentNode;
  assert.equal(delivery.hidden, true, "Bing's Agent delivery setting does not apply without an Agent");
  await startTextComparison(env, "삼성전자 주가 알려줘.");
  readyProviderLane(env, "webiq");
  const bing = readyProviderLane(env, "bing");
  const cell = providerCell(env, "bing");

  bing.event({
    type: "flow", stage: "tool", status: "arguments_ready", tool_id: "item1", response_id: "r1",
    data: { kind: "function_call", name: "web_search", arguments: { search_query: "삼성전자 주가" } },
  });
  assert.equal(classText(cell, "activity-text"), "Bing으로 웹 검색 중…");
  assert.match(classText(cell, "call-query"), /검색어 “삼성전자 주가”/);
  bing.event({ type: "response_done", response_id: "r1", status: "completed", interrupted: false, followup: true });
  await env.advance(10800);
  bing.event({
    type: "tool", kind: "function_call", id: "item1", name: "web_search", status: "completed", response_id: "r1",
    arguments: { search_query: "삼성전자 주가" },
    output: {
      text: "## 요약\n- **종가**: 272,500원 ([finance.example](https://finance.example/quote))\n| 항목 | 수치 |",
      citations: [
        { type: "url_citation", url: "https://finance.example/quote", title: "Quote" },
        { type: "url_citation", url: "https://news.example/a", title: "News" },
        { type: "url_citation", url: "javascript:alert(1)", title: "unsafe" },
      ],
    },
  });
  assert.equal(classText(cell, "search-title"), "모델이 Bing으로 검색한 내용");
  assert.match(stepNode(cell, "search").textContent, /웹 검색 · 10\.8초/);
  assert.match(stepNode(cell, "results").textContent, /검색 답변 · 출처 2개/);
  assert.equal(classText(cell, "call-answer"), "검색 답변 “요약 - 종가 : 272,500원 항목 수치”");
  assert.equal(classText(cell, "call-count"), "출처 2개");
  assert.equal(descendants(findByClass(cell, "search-call")[0], "a").length, 2, "only safe source links");

  completeResponse(bing, "r2", "삼성전자 종가는 272,500원입니다.");
  assert.equal(cell.dataset.status, "done");
  assert.equal(classText(cell, "answer-text"), "삼성전자 종가는 272,500원입니다.");
});