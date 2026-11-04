import { createSettingsView } from "./settings-view.js";
import { createCompareView } from "./compare-view.js";
import { createNewsView, NEWS_DEFAULT_OPTIONS, NEWS_OPTION_FIELDS, NEWS_SCENARIOS, NEWS_QUESTION_TOTAL } from "./news-view.js";
import { createNewsSummary } from "./news-summary.js";
import { createLiveView } from "./live-view.js";
import { textNode, isRecord } from "./search-results.js";
import { providerNames, comparedProviders, modeNames, shortModeNames, routeSummary } from "./labels.js";

const $ = (id) => document.getElementById(id);
const Audio = window.AudioContext || window.webkitAudioContext;
const IDLE_TIMEOUT_MS = 45000;
// A single bufferedAmount sample above this can be a burst of frames queued while the main thread was
// busy (e.g. rendering a large tool result), not real network backpressure: the browser drains it on the
// very next task once the thread is free. Only treat it as a stuck connection once it stays this high for
// BACKPRESSURE_SUSTAIN_MS straight. BACKPRESSURE_HARD_LIMIT_BYTES is an unconditional safety net.
const BACKPRESSURE_LIMIT_BYTES = 96000;
const BACKPRESSURE_SUSTAIN_MS = 1500;
const BACKPRESSURE_HARD_LIMIT_BYTES = 480000;
// The scenario runner leaves a short pause between questions and waits for the briefing audio to finish.
const RUNNER_NEXT_DELAY_MS = 800;
const RUNNER_WAIT_MS = 500;
const LIVE_TEXT_MESSAGE = "GPT-Live는 음성으로만 대화합니다. 말하기를 눌러 주세요.";
const APP_VIEWS = {
  compare: ["엔진 비교", "같은 질문을 WebIQ와 Grounding with Bing에 동시에 보내 결과를 비교합니다"],
  live: ["GPT-Live 음성 대화", "GPT-Live가 듣고 말하고, 정보 질문은 엔진별 Agent 검색에 맡깁니다. 한국어 음성이 돌아오는지 확인합니다"],
  news: ["뉴스 브리핑", "WebIQ 뉴스 검색만으로 브리핑을 만들고, 기존 뉴스 공급을 대체할 수 있는지 시나리오로 평가합니다"],
  summary: ["평가 요약", "뉴스 브리핑 평가 기록을 모아 기준 충족 여부를 정리합니다"],
};
let config = null;
let configState = "loading";
let group = null;
let audio = null;
let workletReady = false;
let liveProvider = "webiq";
let replay = null;
let view = "compare";
let runner = null;
let navState = "";
// Explains why the connection just ended after a settings change, until the next conversation starts.
let restartNotice = "";
// Settings the conversations use. Edits in the panel stay a draft until the user presses Apply.
let applied = null;
let newsApplied = { ...NEWS_DEFAULT_OPTIONS };
let newsDraft = { ...NEWS_DEFAULT_OPTIONS };
const settingsView = createSettingsView();
const compareView = createCompareView({ onReplay: (cell) => toggleReplay(cell, compareView), onLive: setLive });
const liveView = createLiveView({ onReplay: (card) => toggleReplay(card, liveView), compareView });
const newsSummary = createNewsSummary({ onCleared: () => newsView.reload() });
const newsView = createNewsView({
  onReplay: (cell) => toggleReplay(cell, newsView),
  onPick: (question) => {
    $("command-input").value = question;
    $("command-input").focus();
  },
  onRun: (index) => runScenarios([index]),
  onRunAll: () => {
    if (!confirmed(`${NEWS_SCENARIOS.length}개 시나리오의 질문 ${NEWS_QUESTION_TOTAL}개를 차례로 실행할까요? 질문마다 WebIQ 검색과 음성 생성 비용이 듭니다.`)) return;
    runScenarios(NEWS_SCENARIOS.map((_, index) => index));
  },
  onRecords: () => { if (view === "summary") newsSummary.render(); },
  options: () => newsApplied,
});
const syncNewsOptions = settingsView.newsOptions(NEWS_OPTION_FIELDS, (key, value) => {
  newsDraft = { ...newsDraft, [key]: value };
  syncNewsOptions(newsDraft);
  controls();
});
const voiceFields = new Map();
const browserError = !window.isSecureContext
  ? "마이크를 사용하려면 보안 연결 또는 로컬 호스트로 접속하세요."
  : !Audio || !window.AudioWorkletNode || !navigator.mediaDevices?.getUserMedia
    ? "이 브라우저는 필요한 음성 기능을 지원하지 않습니다. 최신 브라우저를 사용하세요." : "";

function error(message = "") {
  $("error").textContent = message;
  $("error").hidden = !message;
}
function setText(id, text) {
  if ($(id).textContent !== text) $(id).textContent = text;
}
const confirmed = (text) => typeof window.confirm !== "function" || window.confirm(text);
const capitalized = (value) => typeof value === "string" && value ? value.charAt(0).toUpperCase() + value.slice(1) : "";
const providerConfig = (provider) => config?.providers.find((item) => item.id === provider);
const configuredProviders = () => comparedProviders.filter((provider) => providerConfig(provider)?.configured);
const liveLanes = () => group ? [...group.lanes.values()].filter((lane) => !lane.closed) : [];
const awaiting = () => liveLanes().some((lane) => lane.awaiting);
const kindFor = (name) => name === "news" ? "news" : applied?.values?.connection_mode === "gpt_live" ? "live" : "compare";
// The summary page has no composer; a scenario run keeps going there in the background.
const activeKind = () => view !== "summary" ? kindFor(view) : group?.kind || (runner ? "news" : kindFor("compare"));
const groupProviders = (kind) => kind === "news" ? configuredProviders().filter((provider) => provider === "webiq") : configuredProviders();
const engines = (kind) => kind === "news" ? "WebIQ 뉴스 검색" : kind === "live" ? "GPT-Live" : "두 엔진";

function usable(kind) {
  if (!config || config.errors.length || !applied) return false;
  if (kind === "live" && !config.live.configured) return false;
  return groupProviders(kind).length > 0;
}
function controls() {
  const draft = voiceOptionsState();
  const kind = activeKind();
  const ready = usable(kind);
  $("start").disabled = Boolean(group || runner || !ready || browserError);
  $("start").hidden = Boolean(group || runner);
  $("stop").disabled = !group && !runner;
  $("stop").hidden = !group && !runner;
  $("send-command").disabled = kind === "live" || Boolean(runner) || (group ? awaiting() || !liveLanes().length : !ready);
  const newsBlocked = Boolean(runner) || !usable("news");
  $("news-run").disabled = newsBlocked;
  $("news-run-all").disabled = newsBlocked;
  $("voice-options-defaults").disabled = !voiceFields.size;
  const pending = pendingCount(draft);
  $("voice-options-apply").disabled = !pending || Boolean(draft.message);
  $("voice-options-cancel").disabled = !pending;
  $("voice-options-pending").hidden = !pending;
  $("voice-options-pending-badge").hidden = !pending;
  setText("voice-options-pending-text", pending ? `변경 ${pending}건 · 아직 적용 안 됨` : "변경 사항이 아직 적용되지 않았습니다");
  const label = appliedLabel();
  $("applied-mode").hidden = !label;
  setText("applied-mode", label);
  layoutText(kind);
  navFoot();
}
// Counts the visible settings that differ from the applied ones; hidden companions count with their parent.
function pendingCount(draft) {
  if (!applied) return 0;
  let count = 0;
  for (const [key, field] of voiceFields) {
    if (draft.values[key] !== applied.values[key] && (key === "connection_mode" || !field.wrapper.hidden)) count += 1;
  }
  if (!count && JSON.stringify(draft.values) !== JSON.stringify(applied.values)) count = 1;
  for (const key of Object.keys(NEWS_DEFAULT_OPTIONS)) if (newsDraft[key] !== newsApplied[key]) count += 1;
  return count;
}
function newsChoice(key) {
  return NEWS_OPTION_FIELDS.find((field) => field.key === key)?.options.find(([value]) => value === newsApplied[key])?.[1] || "";
}
function appliedLabel() {
  const values = applied?.values;
  if (!values || view === "summary") return "";
  const mode = values.connection_mode || "agent";
  if (view === "news") {
    // News always runs through Agent or End-to-end; GPT-Live has no text input for scripted questions.
    const newsMode = mode === "gpt_live" ? "agent" : mode;
    return `적용 중: ${[shortModeNames[newsMode] || newsMode, newsMode === "end_to_end" ? values.realtime_model : null,
      newsChoice("freshness"), `기사 ${newsChoice("count")}`, newsChoice("length")].filter(Boolean).join(" · ")}`;
  }
  const detail = mode === "end_to_end" ? values.realtime_model : mode === "gpt_live" ? `음성 ${capitalized(values.live_voice)}` : null;
  return `적용 중: ${[shortModeNames[mode] || modeNames[mode] || mode, detail].filter(Boolean).join(" · ")}`;
}
function layoutText(kind) {
  const page = view === "summary" ? "summary" : kind;
  const [title, desc] = APP_VIEWS[page];
  setText("page-title", title);
  setText("page-desc", desc);
  const input = $("command-input");
  const placeholder = kind === "news" ? "예: 오늘 주요 뉴스 브리핑해줘…" : kind === "live" ? "GPT-Live는 음성으로만 대화합니다" : "예: 삼성전자 주식 찾아줘…";
  if (input.placeholder !== placeholder) input.placeholder = placeholder;
  input.disabled = kind === "live";
  $("start").setAttribute("aria-label", kind === "news" ? "말하기 · WebIQ에 음성으로 뉴스 질문"
    : kind === "live" ? "말하기 · GPT-Live와 음성 대화" : "말하기 · 두 엔진에 음성으로 질문");
  $("send-command").setAttribute("aria-label", kind === "news" ? "WebIQ에 질문 보내기" : "두 엔진에 질문 보내기");
  $("example-prompts").hidden = kind !== "compare";
  $("news-examples").hidden = kind !== "news";
  $("turns").hidden = kind === "live";
  $("live-board").hidden = kind !== "live" || !liveView.hasTurns();
  const note = kind === "live" ? "GPT-Live는 텍스트 질문을 받지 않습니다. 말하기를 눌러 대화하세요."
    : kind === "news" && applied?.values?.connection_mode === "gpt_live" ? "GPT-Live가 적용되어 있어도 뉴스 브리핑은 Agent 연결로 실행합니다." : "";
  setText("composer-note", note);
  $("composer-note").hidden = !note;
}
function voiceLabel(value) {
  const option = voiceFields.get("voice_name")?.definition.options.find((item) => item.value === value);
  return option ? settingsView.optionLabel("voice_name", option) : typeof value === "string" && value ? value : "-";
}
function navFoot() {
  const missing = config ? config.errors.length + config.providers.filter((item) => !item.configured).length : 0;
  const state = !config ? configState : missing ? "warn" : "ok";
  const text = { loading: "서버 확인 중…", error: "서버 연결 실패", warn: "서버 연결됨 · 일부 설정 필요", ok: "서버 연결됨" }[state];
  if (navState !== `${state}|${text}`) {
    navState = `${state}|${text}`;
    const conn = $("nav-conn");
    conn.dataset.state = state;
    const dot = document.createElement("i");
    dot.setAttribute("aria-hidden", "true");
    conn.replaceChildren(dot, textNode("span", text));
  }
  const values = applied?.values;
  const mode = values?.connection_mode || "agent";
  setText("nav-mode", values ? shortModeNames[mode] || mode : "-");
  setText("nav-voice", !values ? "-" : mode === "gpt_live" ? `GPT-Live ${capitalized(values.live_voice)}` : voiceLabel(values.voice_name));
  const agents = config ? config.providers.filter((item) => item.configured && item.agent?.name).map((item) => item.agent.name) : [];
  setText("nav-agents", agents.join(", ") || "-");
}
function status() {
  if (!group) return;
  const lanes = liveLanes();
  const playing = lanes.some((lane) => lane.nodes.size);
  let text;
  if (group.kind === "news") {
    text = lanes.some((lane) => !lane.ready) ? "WebIQ 뉴스 검색에 연결하고 있어요."
      : playing ? "WebIQ 브리핑을 들려주고 있어요."
        : awaiting() ? "WebIQ가 뉴스를 찾아 브리핑을 만드는 중이에요."
          : group.inputMode === "audio" ? "듣고 있어요. 뉴스를 물어보면 WebIQ가 브리핑합니다." : "다음 질문을 입력하세요.";
  } else if (group.kind === "live") {
    text = lanes.some((lane) => !lane.ready) ? "GPT-Live에 연결하고 있어요."
      : playing ? `${providerNames[liveProvider]} 쪽 GPT-Live 음성을 들려주고 있어요.` : "듣고 있어요. GPT-Live에게 말을 걸어 보세요.";
  } else {
    text = lanes.some((lane) => !lane.ready) ? "두 엔진에 연결하고 있어요."
      : playing ? `${providerNames[liveProvider]} 답변을 들려주고 있어요.`
        : awaiting() ? "두 엔진이 검색하고 답하는 중이에요."
          : group.inputMode === "audio" ? "듣고 있어요. 말하면 두 엔진이 동시에 답합니다." : "다음 질문을 입력하세요.";
  }
  $("status").textContent = runner ? `${text} · 시나리오 실행 ${runner.index}/${runner.total}` : text;
}
function idleStatus(kind, problems) {
  if (kind === "news") {
    if (!usable("news")) return "WebIQ 설정이 없어 뉴스 브리핑을 실행할 수 없습니다. 서버 설정을 확인하세요.";
    return restartNotice || (browserError ? `텍스트로 질문할 수 있어요. ${browserError}`
      : "시나리오를 실행하거나, 질문을 입력하거나 말하기를 눌러 WebIQ 뉴스 브리핑을 들어 보세요.");
  }
  if (kind === "live") {
    if (!config.live.configured) return "GPT-Live 배포 설정이 없어 시작할 수 없습니다. 설정에서 다른 음성 처리 방식을 고르세요.";
    if (!configuredProviders().length) return "검색 엔진 설정이 없어 시작할 수 없습니다. 서버 설정을 확인하세요.";
    return browserError ? `${LIVE_TEXT_MESSAGE} ${browserError}`
      : restartNotice || "말하기를 눌러 GPT-Live와 대화해 보세요. 정보 질문은 엔진별 Agent 검색에 맡깁니다.";
  }
  return !configuredProviders().length ? "검색 엔진 설정이 없어 시작할 수 없습니다. 서버 설정을 확인하세요."
    : problems.length ? "설정된 엔진만 비교합니다. 서버 설정을 확인하세요."
      : restartNotice || (browserError ? `텍스트로 질문할 수 있어요. ${browserError}` : "질문을 입력하거나 말하기를 눌러 두 엔진을 비교해 보세요.");
}
function availability() {
  controls();
  if (group || !config) return;
  const kind = activeKind();
  const problems = [...config.errors];
  for (const provider of comparedProviders) {
    const item = providerConfig(provider);
    compareView.laneStatus(provider, item?.configured ? "idle" : "error", item?.configured ? "대기" : "설정 필요");
    if (!item?.configured && (kind !== "news" || provider === "webiq")) {
      problems.push(...(item?.errors?.length ? item.errors : [`${providerNames[provider]} 설정이 없습니다.`]));
    }
  }
  if (kind === "live" && !config.live.configured) {
    problems.push(...(config.live.errors.length ? config.live.errors : ["GPT-Live 배포 설정이 없습니다."]));
  }
  error(problems.join("\n"));
  if (view !== "summary") $("status").textContent = idleStatus(kind, problems);
}

function voiceOptionValue({ definition, input }) {
  if (definition.type === "boolean") return Boolean(input.checked);
  if (definition.type === "select") {
    const index = Number(input.value);
    return input.value !== "" && Number.isInteger(index) ? definition.options[index]?.value : undefined;
  }
  if (input.validity?.badInput) return undefined;
  return input.value.trim() === "" ? (definition.nullable ? null : undefined) : Number(input.value);
}
function setVoiceOption({ definition, input }, value) {
  if (definition.type === "boolean") input.checked = value === true;
  else if (definition.type === "select") input.value = String(definition.options.findIndex((option) => option.value === value));
  else input.value = value === null || value === undefined ? "" : String(value);
}
function matchesVoiceRequirements(requirements, values) {
  return !requirements || Object.entries(requirements).every(([key, expected]) =>
    Array.isArray(expected) ? expected.includes(values[key]) : expected === values[key]);
}
// GPT-Live stays visible but cannot be chosen when the server has no GPT-Live deployment.
const undeployed = (key, option) => key === "connection_mode" && option.value === "gpt_live" && !config?.live?.configured;
function voiceDefault(key, field, values) {
  const modes = config?.voice_options?.defaults_by_mode;
  const defaults = modes && Object.hasOwn(modes, values.connection_mode) ? modes[values.connection_mode] : null;
  return defaults && Object.hasOwn(defaults, key) ? defaults[key] : field.definition.default;
}
function voiceOptionsState() {
  const values = Object.fromEntries([...voiceFields].map(([key, field]) => [key, voiceOptionValue(field)]));
  let message = "";
  for (const [key, field] of voiceFields) {
    const { definition, input, requirement, wrapper } = field;
    const hiddenByPage = settingsView.hidden(key, values.connection_mode);
    const inactive = !matchesVoiceRequirements(definition.requires, values) || hiddenByPage;
    const defaultValue = voiceDefault(key, field, values);
    let eligible = null;
    if (definition.type === "select") {
      eligible = definition.options.map((option) => matchesVoiceRequirements(option.requires, values) && !undeployed(key, option));
      const eligibleKey = eligible.map(Number).join("");
      const chosenIndex = definition.options.findIndex((option) => option.value === values[key]);
      if (chosenIndex >= 0 && !eligible[chosenIndex] && eligibleKey !== field.eligibleKey) {
        // A dependency changed: replace incompatible choices, not other valid user settings.
        values[key] = defaultValue;
        setVoiceOption(field, defaultValue);
      }
      field.eligibleKey = eligibleKey;
      for (let i = 0; i < eligible.length; i++) {
        input.children[i].disabled = !eligible[i];
        input.children[i].hidden = !eligible[i] && !undeployed(key, definition.options[i]);
      }
    }
    if (inactive) {
      let value = defaultValue;
      // A field the page hides still needs a value that fits the visible choices, e.g. a native voice.
      if (hiddenByPage && eligible && !definition.options.some((option, index) => eligible[index] && option.value === value)) {
        value = definition.options.find((option, index) => eligible[index])?.value ?? value;
      }
      setVoiceOption(field, value);
      values[key] = value;
    }
    input.disabled = inactive;
    wrapper.hidden = inactive;
    requirement.hidden = !inactive;
    const value = values[key];
    const invalid = value === undefined || (value === null && !definition.nullable)
      || (eligible && !inactive && !definition.options.some((option, index) => eligible[index] && option.value === value))
      || (definition.type === "number" && value !== null && (!Number.isFinite(value)
        || (typeof definition.min === "number" && value < definition.min)
        || (typeof definition.max === "number" && value > definition.max)
        || (key === "silence_duration_ms" && !Number.isInteger(value))));
    input.setAttribute("aria-invalid", String(invalid));
    if (invalid && !message) message = `${definition.label} 값을 확인하세요. 안내된 범위 또는 목록에서 선택하세요.`;
  }
  if ($("voice-options-error").textContent !== message) $("voice-options-error").textContent = message;
  $("voice-options-error").hidden = !message;
  const summary = voiceFields.has("connection_mode") ? routeSummary(values.connection_mode) : "";
  $("voice-mode-summary").hidden = !summary;
  if ($("voice-mode-summary").textContent !== summary) $("voice-mode-summary").textContent = summary;
  settingsView.layout(values);
  return {
    values, message,
    // The mode discriminator is always compared with the global default, not with itself.
    overrides: Object.fromEntries([...voiceFields].filter(([key, field]) =>
      values[key] !== (key === "connection_mode" ? field.definition.default : voiceDefault(key, field, values))).map(([key]) => [key, values[key]])),
  };
}
function resetVoiceOptions(mode = null) {
  for (const [key, field] of voiceFields) {
    setVoiceOption(field, mode === null ? field.definition.default : voiceDefault(key, field, { connection_mode: mode }));
  }
}
function restoreVoiceOptions(values) {
  for (const [key, field] of voiceFields) {
    if (Object.hasOwn(values, key)) setVoiceOption(field, values[key]);
  }
}
function configureVoiceOptions(schema) {
  voiceFields.clear();
  settingsView.reset();
  const supported = Array.isArray(schema?.fields);
  $("voice-settings-state").hidden = supported;
  $("voice-settings-state").textContent = supported ? "" : "서버가 선택 가능한 음성 설정을 제공하지 않습니다.";
  if (!supported) return;
  for (const definition of schema.fields) {
    if (!definition || definition.disabled || typeof definition.key !== "string" || !/^[a-z][a-z0-9_]*$/.test(definition.key)
      || ["constructor", "prototype"].includes(definition.key) || voiceFields.has(definition.key)
      || !["select", "boolean", "number"].includes(definition.type)
      || typeof definition.label !== "string" || !Object.hasOwn(definition, "default")
      || (definition.type === "select" && (!Array.isArray(definition.options) || !definition.options.length
        || definition.options.some((option) => !option || typeof option.label !== "string"
          || !(option.value === null || typeof option.value === "string" || typeof option.value === "boolean"
            || (typeof option.value === "number" && Number.isFinite(option.value))))))) continue;
    const wrapper = textNode("div", "", "voice-option");
    const input = document.createElement(definition.type === "select" ? "select" : "input");
    input.id = `voice-option-${definition.key}`;
    input.name = definition.key;
    input.autocomplete = "off";
    const label = textNode("label", settingsView.fieldLabel(definition.key, definition.label));
    label.htmlFor = input.id;
    if (definition.type === "select") {
      definition.options.forEach((option, index) => {
        const item = textNode("option", settingsView.optionLabel(definition.key, option));
        item.value = String(index);
        input.append(item);
      });
    } else {
      input.type = definition.type === "boolean" ? "checkbox" : "number";
      if (definition.type === "number") {
        for (const key of ["min", "max", "step"]) if (Number.isFinite(definition[key])) input[key] = String(definition[key]);
        if (typeof definition.placeholder === "string") input.placeholder = definition.placeholder;
        input.inputMode = "decimal";
      }
    }
    const help = typeof definition.help === "string" && definition.help ? textNode("p", definition.help, "hint") : null;
    if (help) {
      help.id = `${input.id}-help`;
      input.setAttribute("aria-describedby", help.id);
    }
    const requirement = textNode("p", "현재 설정 조합에서는 사용하지 않습니다. 기본 설정을 유지합니다.", "hint voice-option-inactive");
    requirement.hidden = true;
    const field = { definition, input, requirement, wrapper };
    voiceFields.set(definition.key, field);
    setVoiceOption(field, definition.default);
    const changed = () => {
      // An option can require a companion setting, for example an OpenAI voice needs the model to write Bing's answer.
      const chosen = definition.type === "select" ? definition.options[Number(input.value)] : null;
      if (isRecord(chosen?.implies)) {
        for (const [key, value] of Object.entries(chosen.implies)) {
          if (voiceFields.has(key)) setVoiceOption(voiceFields.get(key), value);
        }
      }
      availability();
    };
    input.addEventListener("input", changed);
    input.addEventListener("change", changed);
    wrapper.append(label, input);
    const choices = settingsView.addField(definition.key, wrapper, {
      definition, input, label,
      onPick: (index) => {
        if (input.disabled) return;
        input.value = String(index);
        changed();
      },
    });
    if (choices) wrapper.append(choices);
    wrapper.append(...(help ? [help] : []), requirement);
  }
}
async function loadConfig() {
  try {
    const response = await fetch("/api/config", { cache: "no-store" });
    if (!response.ok) throw new Error();
    const data = await response.json();
    if (!Array.isArray(data.providers) || !Array.isArray(data.errors)
      || data.errors.some((value) => typeof value !== "string")
      || data.providers.some((p) => !p || !Object.hasOwn(providerNames, p.id) || typeof p.configured !== "boolean"
        || (p.errors !== undefined && (!Array.isArray(p.errors) || p.errors.some((value) => typeof value !== "string")))
        || (p.agent != null && (!isRecord(p.agent) || typeof p.agent.name !== "string")))) throw new Error();
    const live = isRecord(data.live) ? data.live : {};
    data.live = {
      configured: live.configured === true,
      deployment: typeof live.deployment === "string" ? live.deployment : "",
      errors: Array.isArray(live.errors) ? live.errors.filter((value) => typeof value === "string") : [],
    };
    config = data;
    configState = "ok";
    configureVoiceOptions(config.voice_options);
    applied = voiceOptionsState();
    availability();
  } catch {
    config = null;
    applied = null;
    configState = "error";
    $("status").textContent = "서버 설정을 불러오지 못했습니다.";
    $("voice-settings-state").hidden = false;
    $("voice-settings-state").textContent = "서버 설정을 불러오지 못했습니다. 연결을 확인한 뒤 페이지를 새로 고쳐 주세요.";
    error("서버가 실행 중인지 확인한 뒤 페이지를 새로 고쳐 주세요.");
    controls();
  }
}

async function ensureAudio() {
  if (!Audio) return null;
  if (!audio || audio.state === "closed") {
    const context = new Audio({ sampleRate: 24000 });
    if (context.sampleRate !== 24000) {
      context.close().catch(() => {});
      throw new Error("이 브라우저는 필요한 24,000헤르츠 음성을 지원하지 않습니다.");
    }
    context.onstatechange = () => {
      if (group && !group.closed && context.state !== "running" && liveLanes().some((lane) => lane.ready)) {
        failGroup(group, "브라우저의 음성 처리가 중단되었습니다. 다시 시작해 주세요.");
      }
    };
    audio = context;
    workletReady = false;
  }
  if (audio.state !== "running") await audio.resume();
  return audio;
}
function idle() {
  if (!group && !replay && audio?.state === "running") audio.suspend().catch(() => {});
}
function mediaError(cause) {
  return cause?.name === "NotAllowedError" ? "마이크 권한이 거부되었습니다. 브라우저의 사이트 권한을 확인하세요."
    : cause?.name === "NotFoundError" ? "사용할 수 있는 마이크가 없습니다."
      : cause?.name === "NotReadableError" ? "마이크를 열 수 없습니다. 다른 앱에서 사용 중인지 확인하세요."
        : cause?.message?.startsWith("이 브라우저") ? cause.message : "음성 기능을 준비하지 못했습니다. 브라우저와 마이크를 확인하세요.";
}

async function start(inputMode, pending = null, kind = activeKind()) {
  if (group) return;
  const voice = applied;
  const providers = groupProviders(kind);
  if (!voice || !usable(kind) || (inputMode === "audio" && browserError) || (kind === "live" && inputMode !== "audio")) {
    controls();
    return;
  }
  const ui = kind === "news" ? newsView : kind === "live" ? liveView : compareView;
  const g = {
    kind, ui, providers, closed: false, inputMode, lanes: new Map(), voice, capturing: false,
    news: kind === "news" ? { ...newsApplied } : null,
  };
  group = g;
  restartNotice = "";
  stopReplay();
  error();
  if (kind === "live") liveView.start({ values: voice.values, deployment: config.live.deployment, providers });
  for (const provider of providers) ui.laneStatus(provider, "connecting", "연결 준비");
  $("status").textContent = inputMode === "audio" ? "마이크를 준비하고 있습니다." : `${engines(kind)}에 연결하고 있어요.`;
  controls();
  try {
    await ensureAudio();
    if (g.closed) return;
    if (inputMode === "audio") {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 24000, echoCancellation: true, noiseSuppression: true }, video: false,
      });
      if (g.closed) { stream.getTracks().forEach((track) => track.stop()); return; }
      g.stream = stream;
      stream.getAudioTracks().forEach((track) => track.addEventListener("ended", () => failGroup(g, "마이크 연결이 끊어졌습니다.")));
      if (!workletReady) {
        await audio.audioWorklet.addModule("/static/pcm-worklet.js");
        workletReady = true;
      }
      if (g.closed) return;
    }
    for (const provider of providers) connectLane(g, provider, pending);
    status();
  } catch (cause) {
    failGroup(g, mediaError(cause));
  }
}
// News runs through Agent or End-to-end; with GPT-Live applied it falls back to the default Agent route.
function startOptions(g) {
  return g.kind === "news" && g.voice.values.connection_mode === "gpt_live" ? {} : g.voice.overrides;
}
function connectLane(g, provider, pending) {
  const options = startOptions(g);
  const lane = {
    provider, group: g, closed: false, ready: false, awaiting: false, failed: false, idleTimer: null,
    nodes: new Set(), nextTime: 0, cancelled: new Set(),
    pending: pending ? { text: pending.text, cell: pending.turn.cells.get(provider) } : null,
    run: { connection_mode: options.connection_mode || "agent" },
  };
  g.lanes.set(provider, lane);
  g.ui.laneStatus(provider, "connecting", "연결 중…");
  lane.socket = new WebSocket(`${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/voice`);
  lane.socket.onopen = () => {
    if (lane.closed) return;
    try {
      lane.socket.send(JSON.stringify({ type: "start", provider, context: "",
        ...(voiceFields.size ? { voice_options: options } : {}), ...(g.news ? { news: g.news } : {}) }));
    } catch { failLane(lane, "대화 시작 요청을 보내지 못했습니다."); }
  };
  lane.socket.onmessage = ({ data }) => {
    if (lane.closed) return;
    try { receive(lane, JSON.parse(data)); } catch { failLane(lane, "서버 응답을 처리하지 못했습니다."); }
  };
  lane.socket.onerror = () => failLane(lane, "서버 연결에 실패했습니다. 서버와 네트워크 설정을 확인하세요.");
  lane.socket.onclose = () => { if (!lane.closed) failLane(lane, "서버 연결이 종료되었습니다."); };
}
function laneReady(lane) {
  if (lane.ready) return;
  lane.ready = true;
  lane.group.ui.laneStatus(lane.provider, "ready", lane.group.inputMode === "audio" ? "듣는 중" : "연결됨");
  if (lane.group.inputMode === "audio") capture(lane.group);
  if (lane.pending && !lane.closed) {
    const { text, cell } = lane.pending;
    lane.pending = null;
    submit(lane, text, cell);
  }
  status();
  controls();
}
function capture(g) {
  if (g.capturing || g.closed || !g.stream) return;
  if (!audio || audio.state !== "running") { failGroup(g, "브라우저의 음성 처리가 중단되었습니다. 다시 시작해 주세요."); return; }
  g.source = audio.createMediaStreamSource(g.stream);
  g.worklet = new AudioWorkletNode(audio, "pcm-capture", {
    numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1], channelCount: 1, channelCountMode: "explicit",
  });
  g.mute = audio.createGain();
  g.mute.gain.value = 0;
  g.worklet.onprocessorerror = () => failGroup(g, "마이크 음성을 처리하지 못했습니다. 다시 시작해 주세요.");
  // One microphone feeds every lane so each engine hears exactly the same question.
  g.worklet.port.onmessage = ({ data }) => {
    if (g.closed) return;
    for (const lane of g.lanes.values()) {
      if (lane.closed || !lane.ready || lane.socket.readyState !== WebSocket.OPEN) continue;
      if (backpressured(lane)) { failLane(lane, "음성 전송이 지연되어 이 엔진의 연결을 중단했습니다."); continue; }
      try { lane.socket.send(data); } catch { failLane(lane, "음성을 서버로 보내지 못했습니다."); }
    }
  };
  g.source.connect(g.worklet).connect(g.mute).connect(audio.destination);
  g.capturing = true;
}
// A brief main-thread stall (e.g. rendering a large tool result) queues worklet frames; once the thread
// frees up they are sent in one burst and bufferedAmount spikes even though the socket drains it right
// after. Require the spike to persist across BACKPRESSURE_SUSTAIN_MS of real elapsed time before treating
// it as a stuck connection, with a hard cap as an unconditional safety net.
function backpressured(lane) {
  const amount = lane.socket.bufferedAmount;
  if (amount > BACKPRESSURE_HARD_LIMIT_BYTES) return true;
  if (amount <= BACKPRESSURE_LIMIT_BYTES) { lane.backpressureSince = null; return false; }
  lane.backpressureSince ??= Date.now();
  return Date.now() - lane.backpressureSince >= BACKPRESSURE_SUSTAIN_MS;
}
function watch(lane) {
  clearTimeout(lane.idleTimer);
  if (!lane.awaiting || lane.closed) return;
  lane.idleTimer = setTimeout(() => {
    if (lane.closed || !lane.awaiting) return;
    lane.group.ui.stalled(lane);
    settle(lane);
  }, IDLE_TIMEOUT_MS);
}
function settle(lane) {
  lane.awaiting = false;
  clearTimeout(lane.idleTimer);
  if (!lane.closed) lane.group.ui.laneStatus(lane.provider, "ready", lane.group.inputMode === "audio" ? "듣는 중" : "연결됨");
  if (runner && !runner.timer && lane.group === group && group.kind === "news") runner.timer = setTimeout(runNext, RUNNER_NEXT_DELAY_MS);
  status();
  controls();
}
function submit(lane, text, cell) {
  try {
    lane.socket.send(JSON.stringify({ type: "text", text }));
  } catch { failLane(lane, "질문을 서버로 보내지 못했습니다."); return; }
  lane.awaiting = true;
  watch(lane);
  lane.group.ui.submitted(lane, cell);
  lane.group.ui.laneStatus(lane.provider, "busy", "검색·답변 중…");
}
function receive(lane, event) {
  if (lane.closed) return;
  watch(lane);
  const ui = lane.group.ui;
  const cancelled = event.response_id && lane.cancelled.has(event.response_id);
  switch (event.type) {
    case "status":
      if (event.state === "ready") laneReady(lane);
      else if (event.state === "connecting") ui.laneStatus(lane.provider, "connecting", "음성 서비스 연결 중…");
      break;
    case "activity":
      if (event.state === "thinking") {
        lane.awaiting = true;
        watch(lane);
        ui.laneStatus(lane.provider, "busy", "검색·답변 중…");
        controls();
      }
      break;
    case "transcript": if (!cancelled || event.role === "user") ui.transcript?.(lane, event); break;
    case "flow": if (!cancelled) ui.flow?.(lane, event); break;
    case "tool": if (!cancelled) ui.tool?.(lane, event); break;
    case "citation": if (!cancelled) ui.citation?.(lane, event); break;
    case "audio": if (!cancelled) playAudio(lane, event); break;
    case "response_done":
      if (event.response_id && (event.interrupted || event.status === "cancelled")) lane.cancelled.add(event.response_id);
      if (ui.complete?.(lane, event)) settle(lane);
      break;
    case "interrupt":
      if (event.response_id) lane.cancelled.add(event.response_id);
      stopLive(lane);
      stopReplay();
      ui.interrupt?.(lane, event);
      break;
    case "live_session":
    case "live_transcript":
    case "delegation":
    case "live_usage":
    case "live_closed":
      ui.live?.(lane, event);
      break;
    case "error": {
      const message = event.message || "서버에서 오류가 발생했습니다.";
      if (event.code === "response_busy") {
        ui.busy(lane, message);
        settle(lane);
      } else if (event.terminal === false) {
        // The session keeps running; GPT-Live shows these on its session card.
        if (ui.live) ui.live(lane, event);
        else error(message);
      } else failLane(lane, message);
      break;
    }
    case "done": finishLane(lane, "종료", false); break;
  }
}

function pcmBuffer(bytes) {
  const data = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const buffer = audio.createBuffer(1, bytes.byteLength / 2, 24000);
  const samples = buffer.getChannelData(0);
  for (let i = 0; i < samples.length; i++) samples[i] = data.getInt16(i * 2, true) / 32768;
  return buffer;
}
function playAudio(lane, event) {
  const raw = atob(event.data);
  if (!raw.length) return;
  if (raw.length % 2) throw new Error("잘못된 음성 데이터입니다.");
  const bytes = Uint8Array.from(raw, (char) => char.charCodeAt(0));
  lane.group.ui.audio(lane, event, bytes);
  // Every answer is kept for replay; only the selected engine speaks live. News has only WebIQ.
  const speaker = lane.group.kind === "news" ? "webiq" : liveProvider;
  if (lane.provider !== speaker || replay || !lane.ready || audio?.state !== "running") return;
  const node = audio.createBufferSource();
  node.buffer = pcmBuffer(bytes);
  node.connect(audio.destination);
  node.onended = () => {
    lane.nodes.delete(node);
    node.disconnect();
    if (!lane.nodes.size) status();
  };
  const when = Math.max(lane.nextTime, audio.currentTime);
  lane.nextTime = when + node.buffer.duration;
  lane.nodes.add(node);
  node.start(when);
  status();
}
function stopLive(lane) {
  for (const node of lane.nodes) {
    node.onended = null;
    try { node.stop(); } catch { /* A finished source cannot be stopped again. */ }
    node.disconnect();
  }
  lane.nodes.clear();
  lane.nextTime = audio?.currentTime || 0;
}
function setLive(provider) {
  if (provider === liveProvider || !comparedProviders.includes(provider)) return;
  const previous = group?.kind !== "news" ? group?.lanes.get(liveProvider) : null;
  if (previous) stopLive(previous);
  liveProvider = provider;
  compareView.setLive(provider);
  status();
}
function stopReplay() {
  if (!replay) return;
  const { cell, node, ui } = replay;
  replay = null;
  node.onended = null;
  try { node.stop(); } catch { /* Already ended. */ }
  node.disconnect();
  ui.replayState(cell, false);
}
async function toggleReplay(cell, ui) {
  if (replay?.cell === cell) { stopReplay(); idle(); return; }
  stopReplay();
  if (!cell.audio.bytes) return;
  try {
    if (!await ensureAudio()) { error("이 브라우저에서는 음성을 재생할 수 없습니다."); return; }
  } catch (cause) { error(mediaError(cause)); return; }
  for (const lane of liveLanes()) stopLive(lane);
  const merged = new Uint8Array(cell.audio.bytes);
  let offset = 0;
  for (const chunk of cell.audio.chunks) { merged.set(chunk, offset); offset += chunk.byteLength; }
  const node = audio.createBufferSource();
  node.buffer = pcmBuffer(merged);
  node.connect(audio.destination);
  replay = { cell, node, ui };
  node.onended = () => {
    node.disconnect();
    if (replay?.node !== node) return;
    replay = null;
    ui.replayState(cell, false);
    idle();
  };
  node.start();
  ui.replayState(cell, true);
}

function finishLane(lane, message, notify = true) {
  if (lane.closed) return;
  lane.closed = true;
  lane.ready = false;
  lane.pending = null;
  lane.awaiting = false;
  clearTimeout(lane.idleTimer);
  if (lane.socket) {
    try {
      if (notify && lane.socket.readyState === WebSocket.OPEN) lane.socket.send(JSON.stringify({ type: "stop" }));
      lane.socket.close();
    } catch { /* The socket is already unusable. */ }
  }
  stopLive(lane);
  const g = lane.group;
  g.ui.closed(lane.provider);
  g.ui.laneStatus(lane.provider, lane.failed ? "error" : "idle", lane.failed ? "오류" : message);
  if (!g.closed && [...g.lanes.values()].every((item) => item.closed)) {
    const lost = g.kind === "news" ? "WebIQ 연결이 중단되었습니다." : g.kind === "live" ? "GPT-Live 연결이 모두 중단되었습니다." : "두 엔진의 연결이 모두 중단되었습니다.";
    finishGroup(g, [...g.lanes.values()].every((item) => item.failed) ? `${lost} 확인 후 다시 시작해 주세요.` : "대화를 마쳤습니다.");
  } else {
    status();
    controls();
  }
}
function failLane(lane, message) {
  if (lane.closed) return;
  lane.failed = true;
  lane.group.ui.fail(lane.provider, message);
  finishLane(lane, "오류");
}
function finishGroup(g, message) {
  if (g.closed) return;
  g.closed = true;
  if (runner && !runner.advancing && g.kind === "news") stopRunner();
  for (const lane of g.lanes.values()) finishLane(lane, "종료");
  if (g.worklet) {
    g.worklet.onprocessorerror = null;
    g.worklet.port.onmessage = null;
    g.worklet.port.close();
    g.worklet.disconnect();
  }
  g.source?.disconnect();
  g.mute?.disconnect();
  g.stream?.getTracks().forEach((track) => track.stop());
  if (group === g) group = null;
  idle();
  controls();
  if (message) $("status").textContent = message;
}
function failGroup(g, message) {
  if (!g || g.closed) return;
  error(message);
  for (const provider of g.kind === "compare" ? comparedProviders : g.providers) g.ui.fail(provider, message);
  for (const lane of g.lanes.values()) lane.failed = true;
  finishGroup(g, "대화가 중단되었습니다. 확인 후 다시 시작해 주세요.");
}

// Asks the active group, connecting first when needed; a group of another kind ends first.
async function ask(text, meta = null, kind = activeKind()) {
  if (kind === "live") { error(LIVE_TEXT_MESSAGE); return; }
  if (group && group.kind !== kind) finishGroup(group, "");
  error();
  const turn = kind === "news" ? newsView.question(text, meta) : compareView.question(text);
  if (!group) { await start("text", { text, turn }, kind); return; }
  for (const provider of group.providers) {
    const lane = group.lanes.get(provider);
    if (!lane || lane.closed) connectLane(group, provider, { text, turn });
    else if (!lane.ready) lane.pending = { text, cell: turn.cells.get(provider) };
    else submit(lane, text, turn.cells.get(provider));
  }
  status();
  controls();
}
async function sendCommand(event) {
  event?.preventDefault();
  if (activeKind() === "live") { error(LIVE_TEXT_MESSAGE); return; }
  const text = $("command-input").value.trim();
  if (!text || text.length > 4000) { error("1~4,000자 이내의 질문을 입력해 주세요."); return; }
  if (awaiting()) { error(group?.kind === "news" ? "WebIQ 브리핑이 끝난 뒤 다음 질문을 보내세요." : "두 엔진의 답변이 끝난 뒤 다음 질문을 보내세요."); return; }
  if ($("send-command").disabled) return;
  $("command-input").value = "";
  await ask(text);
}

// Scenarios 1-5 ask each question on a fresh connection; the follow-up scenario keeps one conversation.
function runScenarios(indices) {
  if (runner || !usable("news")) return;
  const queue = [];
  for (const scenario of indices) {
    const item = NEWS_SCENARIOS[scenario];
    if (!item) continue;
    if (item.seed) queue.push({ text: item.seed, meta: { scenario, q: null, seed: true }, fresh: true });
    item.questions.forEach((text, q) => queue.push({ text, meta: { scenario, q }, fresh: !item.seed }));
  }
  if (!queue.length) return;
  stopReplay();
  runner = { queue, index: 0, total: queue.length, timer: null, advancing: false };
  newsView.running(true);
  runNext();
}
function runNext() {
  if (!runner) return;
  clearTimeout(runner.timer);
  runner.timer = null;
  if (group && liveLanes().some((lane) => lane.awaiting || lane.nodes.size)) {
    runner.timer = setTimeout(runNext, RUNNER_WAIT_MS);
    return;
  }
  const item = runner.queue[runner.index];
  if (!item) {
    stopRunner();
    if (group) finishGroup(group, "");
    $("status").textContent = "시나리오 실행을 마쳤습니다. 평가 요약에서 결과를 확인하세요.";
    return;
  }
  runner.index += 1;
  if (view === "news") newsView.select(item.meta.scenario);
  if (item.fresh && group) {
    runner.advancing = true;
    finishGroup(group, "");
    runner.advancing = false;
  }
  ask(item.text, item.meta, "news");
  if (runner && !group) stopRunner("뉴스 브리핑을 시작하지 못해 시나리오 실행을 멈췄습니다.");
}
function stopRunner(message = "") {
  if (!runner) return;
  clearTimeout(runner.timer);
  runner = null;
  newsView.running(false);
  controls();
  if (message) $("status").textContent = message;
}

function openSettings() {
  const dialog = $("connection-settings");
  if (dialog.open) return;
  if (typeof dialog.showModal === "function") {
    try { dialog.showModal(); return; } catch { /* Fall back to a non-modal panel. */ }
  }
  dialog.open = true;
}
function closeSettings() {
  const dialog = $("connection-settings");
  if (typeof dialog.close === "function") {
    try { dialog.close(); } catch { /* Already closed. */ }
  }
  dialog.open = false;
}
function showView(name) {
  if (!Object.hasOwn(APP_VIEWS, name) || name === "live") return;
  if (name !== view && name !== "summary") {
    if (runner) stopRunner();
    if (group && group.kind !== kindFor(name)) finishGroup(group, "");
  }
  view = name;
  for (const key of ["compare", "news", "summary"]) {
    $(`nav-${key}`).setAttribute("aria-current", key === name ? "page" : "false");
    $(`view-${key}`).hidden = key !== name;
  }
  $("composer").hidden = name === "summary";
  $("reset").hidden = name === "summary";
  if (name === "summary") newsSummary.render();
  if (name === "news") newsView.refresh();
  availability();
}
function resetConversation() {
  if (view === "summary") return;
  const news = view === "news";
  const shown = news ? newsView.hasTurns() : compareView.hasTurns() || liveView.hasTurns();
  const prompt = news ? "현재 연결을 종료하고 화면의 뉴스 브리핑 결과를 비울까요? 평가 기록은 그대로 남습니다."
    : "현재 연결을 종료하고 화면의 비교 결과를 비울까요? 서버에 남은 기록은 삭제하지 않습니다.";
  if ((group || runner || shown) && !confirmed(prompt)) return;
  stopRunner();
  stopReplay();
  if (group) finishGroup(group, "대화를 초기화했습니다.");
  restartNotice = "";
  if (news) newsView.reset();
  else {
    compareView.reset();
    liveView.reset();
  }
  $("command-input").value = "";
  error();
  availability();
}

for (const button of $("example-prompts").children) {
  button.addEventListener("click", () => {
    $("command-input").value = button.dataset.prompt;
    $("command-input").focus();
  });
}
for (const key of ["compare", "news", "summary"]) $(`nav-${key}`).addEventListener("click", () => showView(key));
let composing = false;
$("command-input").addEventListener("compositionstart", () => { composing = true; });
$("command-input").addEventListener("compositionend", () => { composing = false; });
$("command-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing && !composing && event.keyCode !== 229) {
    event.preventDefault();
    sendCommand();
  }
});
$("command-form").addEventListener("submit", sendCommand);
$("start").addEventListener("click", () => start("audio"));
$("stop").addEventListener("click", () => {
  const running = Boolean(runner);
  stopRunner();
  if (group) finishGroup(group, running ? "시나리오 실행을 중지했습니다." : "대화를 중지했습니다.");
  else if (running) $("status").textContent = "시나리오 실행을 중지했습니다.";
});
$("reset").addEventListener("click", resetConversation);
$("skip-to-content").addEventListener("click", (event) => {
  event.preventDefault();
  $("command-input").focus();
});
$("open-settings").addEventListener("click", openSettings);
$("nav-settings").addEventListener("click", openSettings);
$("settings-close").addEventListener("click", closeSettings);
$("connection-settings").addEventListener("click", (event) => {
  if (event.target === $("connection-settings")) closeSettings();
});
$("voice-options-defaults").addEventListener("click", () => {
  const mode = voiceFields.get("connection_mode");
  resetVoiceOptions(mode ? voiceOptionValue(mode) : null);
  newsDraft = { ...NEWS_DEFAULT_OPTIONS };
  syncNewsOptions(newsDraft);
  availability();
});
$("voice-options-cancel").addEventListener("click", () => {
  if (applied) restoreVoiceOptions(applied.values);
  newsDraft = { ...newsApplied };
  syncNewsOptions(newsDraft);
  availability();
});
$("voice-options-apply").addEventListener("click", () => {
  const draft = voiceOptionsState();
  if (draft.message || !pendingCount(draft)) return;
  const voiceChanged = JSON.stringify(draft.values) !== JSON.stringify(applied.values);
  const newsChanged = JSON.stringify(newsDraft) !== JSON.stringify(newsApplied);
  applied = draft;
  newsApplied = { ...newsDraft };
  stopRunner();
  if (group && (voiceChanged || (newsChanged && group.kind === "news"))) finishGroup(group, "");
  const kind = activeKind();
  restartNotice = kind === "news" ? "설정을 적용했습니다. 다음 질문부터 새 설정으로 브리핑합니다."
    : kind === "live" ? "설정을 적용했습니다. 말하기를 누르면 새 설정으로 GPT-Live 세션을 시작합니다."
      : "설정을 적용했습니다. 다음 질문부터 새 설정으로 비교합니다.";
  closeSettings();
  availability();
});
window.addEventListener("pagehide", () => {
  stopRunner();
  stopReplay();
  if (group) finishGroup(group, "");
  audio?.close().catch(() => {});
});
compareView.setLive(liveProvider);
syncNewsOptions(newsDraft);
controls();
loadConfig();
