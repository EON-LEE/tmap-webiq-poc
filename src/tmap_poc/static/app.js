import { createSettingsView } from "./settings-view.js";
import { createCompareView } from "./compare-view.js";
import { textNode, isRecord } from "./search-results.js";
import { providerNames, comparedProviders, routeSummary } from "./run-labels.js";

const $ = (id) => document.getElementById(id);
const Audio = window.AudioContext || window.webkitAudioContext;
const IDLE_TIMEOUT_MS = 45000;
let config = null;
let group = null;
let audio = null;
let workletReady = false;
let liveProvider = "webiq";
let replay = null;
let groupSequence = 0;
// Explains why the connection just ended after a settings change, until the next comparison starts.
let restartNotice = "";
const settingsView = createSettingsView();
const compareView = createCompareView({ onReplay: toggleReplay, onLive: setLive });
const voiceFields = new Map();
const unavailableVoiceOptions = [];
const browserError = !window.isSecureContext
  ? "마이크를 사용하려면 보안 연결 또는 로컬 호스트로 접속하세요."
  : !Audio || !window.AudioWorkletNode || !navigator.mediaDevices?.getUserMedia
    ? "이 브라우저는 필요한 음성 기능을 지원하지 않습니다. 최신 브라우저를 사용하세요." : "";

function error(message = "") {
  $("error").textContent = message;
  $("error").hidden = !message;
}
const providerConfig = (provider) => config?.providers.find((item) => item.id === provider);
const configuredProviders = () => comparedProviders.filter((provider) => providerConfig(provider)?.configured);
const liveLanes = () => group ? [...group.lanes.values()].filter((lane) => !lane.closed) : [];
const awaiting = () => liveLanes().some((lane) => lane.awaiting);

function controls() {
  const voice = voiceOptionsState();
  const usable = Boolean(config) && configuredProviders().length > 0 && !config.errors.length && !voice.message;
  $("start").disabled = Boolean(group || !usable || browserError);
  $("start").hidden = Boolean(group);
  $("stop").disabled = !group;
  $("stop").hidden = !group;
  $("send-command").disabled = group ? awaiting() || !liveLanes().length : !usable;
  $("voice-options-defaults").disabled = !voiceFields.size;
}
function status() {
  const lanes = liveLanes();
  $("status").textContent = !group ? $("status").textContent
    : lanes.some((lane) => !lane.ready) ? "두 엔진에 연결하고 있어요."
      : lanes.some((lane) => lane.nodes.size) ? `${providerNames[liveProvider]} 답변을 들려주고 있어요.`
        : awaiting() ? "두 엔진이 검색하고 답하는 중이에요."
          : group.inputMode === "audio" ? "듣고 있어요. 말하면 두 엔진이 동시에 답합니다." : "다음 질문을 입력하세요.";
}
function availability() {
  controls();
  if (group || !config) return;
  const problems = [...config.errors];
  for (const provider of comparedProviders) {
    const item = providerConfig(provider);
    compareView.laneStatus(provider, item?.configured ? "idle" : "error", item?.configured ? "대기" : "설정 필요");
    if (!item?.configured) problems.push(...(item?.errors?.length ? item.errors : [`${providerNames[provider]} 설정이 없습니다.`]));
  }
  error(problems.join("\n"));
  $("status").textContent = !configuredProviders().length ? "검색 엔진 설정이 없어 시작할 수 없습니다. 서버 설정을 확인하세요."
    : problems.length ? "설정된 엔진만 비교합니다. 서버 설정을 확인하세요."
      : restartNotice || (browserError ? `텍스트로 질문할 수 있어요. ${browserError}` : "질문을 입력하거나 말하기를 눌러 두 엔진을 비교해 보세요.");
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
      eligible = definition.options.map((option) => !settingsView.excluded(key, option) && matchesVoiceRequirements(option.requires, values));
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
        input.children[i].hidden = !eligible[i];
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
  for (const item of unavailableVoiceOptions) item.element.hidden = !matchesVoiceRequirements(item.definition.requires, values);
  const summary = voiceFields.has("connection_mode") ? routeSummary(values.connection_mode) : "";
  $("voice-mode-summary").hidden = !summary;
  if ($("voice-mode-summary").textContent !== summary) $("voice-mode-summary").textContent = summary;
  settingsView.layout();
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
function configureVoiceOptions(schema) {
  voiceFields.clear();
  unavailableVoiceOptions.length = 0;
  settingsView.reset();
  for (const id of ["voice-options-unavailable", "voice-options-limitations"]) $(id).replaceChildren();
  const supported = schema?.mode === "foundry_agent" && Array.isArray(schema.fields);
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
    const help = textNode("p", typeof definition.help === "string" ? definition.help : "", "hint");
    help.id = `${input.id}-help`;
    input.setAttribute("aria-describedby", help.id);
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
      if (group) {
        finishGroup(group, "");
        restartNotice = "설정을 바꿨습니다. 다음 질문부터 새 설정으로 비교합니다.";
      }
      availability();
    };
    input.addEventListener("input", changed);
    input.addEventListener("change", changed);
    wrapper.append(label, input, help, requirement);
    settingsView.addField(definition.key, wrapper);
  }
  for (const option of Array.isArray(schema.unavailable_options) ? schema.unavailable_options : []) {
    if (!option || typeof option.label !== "string") continue;
    const wrapper = textNode("div", "", "voice-option-unavailable");
    wrapper.append(textNode("strong", option.label));
    if (typeof option.help === "string") wrapper.append(textNode("p", option.help, "hint"));
    unavailableVoiceOptions.push({ definition: option, element: wrapper });
    $("voice-options-unavailable").append(wrapper);
  }
  for (const limitation of Array.isArray(schema.limitations) ? schema.limitations : []) {
    if (typeof limitation === "string") $("voice-options-limitations").append(textNode("li", limitation));
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
    config = data;
    configureVoiceOptions(config.voice_options);
    availability();
  } catch {
    config = null;
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

async function start(inputMode, pending = null) {
  if (group) return;
  const voice = voiceOptionsState();
  const providers = configuredProviders();
  if (!config || voice.message || !providers.length || (inputMode === "audio" && browserError)) { controls(); return; }
  const g = { closed: false, inputMode, sequence: ++groupSequence, lanes: new Map(), voice, capturing: false };
  group = g;
  restartNotice = "";
  stopReplay();
  error();
  for (const provider of providers) compareView.laneStatus(provider, "connecting", "연결 준비");
  $("status").textContent = inputMode === "audio" ? "마이크를 준비하고 있습니다." : "두 엔진에 연결하고 있어요.";
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
function connectLane(g, provider, pending) {
  const lane = {
    provider, group: g, closed: false, ready: false, awaiting: false, failed: false, idleTimer: null,
    nodes: new Set(), nextTime: 0, cancelled: new Set(),
    pending: pending ? { text: pending.text, cell: pending.turn.cells.get(provider) } : null,
    run: { provider, input_mode: g.inputMode, sequence: g.sequence, connection_mode: g.voice.values.connection_mode || "agent",
      ...(voiceFields.size ? { voice_options: g.voice.values } : {}) },
  };
  g.lanes.set(provider, lane);
  compareView.laneStatus(provider, "connecting", "연결 중…");
  lane.socket = new WebSocket(`${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/voice`);
  lane.socket.onopen = () => {
    if (lane.closed) return;
    try {
      lane.socket.send(JSON.stringify({ type: "start", provider, context: "",
        ...(voiceFields.size ? { voice_options: g.voice.overrides } : {}) }));
    } catch { failLane(lane, "대화 시작 요청을 보내지 못했습니다."); }
  };
  lane.socket.onmessage = ({ data }) => {
    if (lane.closed) return;
    try { receive(lane, JSON.parse(data)); } catch { failLane(lane, "서버 응답을 처리하지 못했습니다."); }
  };
  lane.socket.onerror = () => failLane(lane, "서버 연결에 실패했습니다. 서버와 네트워크 설정을 확인하세요.");
  lane.socket.onclose = () => { if (!lane.closed) failLane(lane, "서버 연결이 종료되었습니다."); };
  return lane;
}
function laneReady(lane) {
  if (lane.ready) return;
  lane.ready = true;
  compareView.laneStatus(lane.provider, "ready", lane.group.inputMode === "audio" ? "듣는 중" : "연결됨");
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
  // One microphone feeds both engines so they hear exactly the same question.
  g.worklet.port.onmessage = ({ data }) => {
    if (g.closed) return;
    for (const lane of g.lanes.values()) {
      if (lane.closed || !lane.ready || lane.socket.readyState !== WebSocket.OPEN) continue;
      if (lane.socket.bufferedAmount > 96000) { failLane(lane, "음성 전송이 지연되어 이 엔진의 연결을 중단했습니다."); continue; }
      try { lane.socket.send(data); } catch { failLane(lane, "음성을 서버로 보내지 못했습니다."); }
    }
  };
  g.source.connect(g.worklet).connect(g.mute).connect(audio.destination);
  g.capturing = true;
}
function watch(lane) {
  clearTimeout(lane.idleTimer);
  if (!lane.awaiting || lane.closed) return;
  lane.idleTimer = setTimeout(() => {
    if (lane.closed || !lane.awaiting) return;
    compareView.stalled(lane);
    settle(lane);
  }, IDLE_TIMEOUT_MS);
}
function settle(lane) {
  lane.awaiting = false;
  clearTimeout(lane.idleTimer);
  if (!lane.closed) compareView.laneStatus(lane.provider, "ready", lane.group.inputMode === "audio" ? "듣는 중" : "연결됨");
  status();
  controls();
}
function submit(lane, text, cell) {
  try {
    lane.socket.send(JSON.stringify({ type: "text", text }));
  } catch { failLane(lane, "질문을 서버로 보내지 못했습니다."); return; }
  lane.awaiting = true;
  watch(lane);
  compareView.submitted(lane, cell);
  compareView.laneStatus(lane.provider, "busy", "검색·답변 중…");
}
function receive(lane, event) {
  if (lane.closed) return;
  watch(lane);
  const cancelled = event.response_id && lane.cancelled.has(event.response_id);
  switch (event.type) {
    case "status":
      if (event.state === "ready") laneReady(lane);
      else if (event.state === "connecting") compareView.laneStatus(lane.provider, "connecting", "음성 서비스 연결 중…");
      else if (event.state === "stopped") finishLane(lane, "종료", false);
      break;
    case "activity":
      if (event.state === "thinking") {
        lane.awaiting = true;
        watch(lane);
        compareView.laneStatus(lane.provider, "busy", "검색·답변 중…");
        controls();
      }
      break;
    case "transcript": if (!cancelled || event.role === "user") compareView.transcript(lane, event); break;
    case "flow": if (!cancelled) compareView.flow(lane, event); break;
    case "tool": if (!cancelled) compareView.tool(lane, event); break;
    case "citation": if (!cancelled) compareView.citation(lane, event); break;
    case "audio": if (!cancelled) playAudio(lane, event); break;
    case "response_done":
      if (event.response_id && (event.interrupted || event.status === "cancelled")) lane.cancelled.add(event.response_id);
      if (compareView.complete(lane, event)) settle(lane);
      break;
    case "interrupt":
      if (event.response_id) lane.cancelled.add(event.response_id);
      stopLive(lane);
      stopReplay();
      compareView.interrupt(lane, event);
      break;
    case "error": {
      const message = event.message || "서버에서 오류가 발생했습니다.";
      if (event.code === "response_busy") {
        compareView.busy(lane, message);
        settle(lane);
      } else failLane(lane, message);
      break;
    }
    case "done": finishLane(lane, "종료", false); break;
  }
}

function pcmBuffer(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const buffer = audio.createBuffer(1, bytes.byteLength / 2, 24000);
  const samples = buffer.getChannelData(0);
  for (let i = 0; i < samples.length; i++) samples[i] = view.getInt16(i * 2, true) / 32768;
  return buffer;
}
function playAudio(lane, event) {
  const raw = atob(event.data);
  if (!raw.length) return;
  if (raw.length % 2) throw new Error("잘못된 음성 데이터입니다.");
  const bytes = Uint8Array.from(raw, (char) => char.charCodeAt(0));
  compareView.audio(lane, event, bytes);
  // Both answers are kept for replay; only the selected engine speaks live.
  if (lane.provider !== liveProvider || replay || !lane.ready || audio?.state !== "running") return;
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
  const previous = group?.lanes.get(liveProvider);
  if (previous) stopLive(previous);
  liveProvider = provider;
  compareView.setLive(provider);
  status();
}
function stopReplay() {
  if (!replay) return;
  const { cell, node } = replay;
  replay = null;
  node.onended = null;
  try { node.stop(); } catch { /* Already ended. */ }
  node.disconnect();
  compareView.replayState(cell, false);
}
async function toggleReplay(cell) {
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
  replay = { cell, node };
  node.onended = () => {
    node.disconnect();
    if (replay?.node !== node) return;
    replay = null;
    compareView.replayState(cell, false);
    idle();
  };
  node.start();
  compareView.replayState(cell, true);
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
  compareView.closed(lane.provider);
  compareView.laneStatus(lane.provider, lane.failed ? "error" : "idle", lane.failed ? "오류" : message);
  const g = lane.group;
  if (!g.closed && [...g.lanes.values()].every((item) => item.closed)) {
    finishGroup(g, [...g.lanes.values()].every((item) => item.failed)
      ? "두 엔진의 연결이 모두 중단되었습니다. 확인 후 다시 시작해 주세요." : "대화를 마쳤습니다.");
  } else {
    status();
    controls();
  }
}
function failLane(lane, message) {
  if (lane.closed) return;
  lane.failed = true;
  compareView.fail(lane.provider, message);
  finishLane(lane, "오류");
}
function finishGroup(g, message) {
  if (g.closed) return;
  g.closed = true;
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
  for (const provider of comparedProviders) compareView.fail(provider, message);
  for (const lane of g.lanes.values()) lane.failed = true;
  finishGroup(g, "대화가 중단되었습니다. 확인 후 다시 시작해 주세요.");
}

async function sendCommand(event) {
  event?.preventDefault();
  const text = $("command-input").value.trim();
  if (!text || text.length > 4000) { error("1~4,000자 이내의 질문을 입력해 주세요."); return; }
  if (awaiting()) { error("두 엔진의 답변이 끝난 뒤 다음 질문을 보내세요."); return; }
  if ($("send-command").disabled) return;
  error();
  $("command-input").value = "";
  const turn = compareView.question(text);
  if (!group) { await start("text", { text, turn }); return; }
  for (const provider of configuredProviders()) {
    const lane = group.lanes.get(provider);
    if (!lane || lane.closed) connectLane(group, provider, { text, turn });
    else if (!lane.ready) lane.pending = { text, cell: turn.cells.get(provider) };
    else submit(lane, text, turn.cells.get(provider));
  }
  status();
  controls();
}
function resetConversation() {
  if ((group || compareView.hasTurns()) && !window.confirm("현재 연결을 종료하고 화면의 비교 결과를 비울까요? 서버에 남은 기록은 삭제하지 않습니다.")) return;
  stopReplay();
  if (group) finishGroup(group, "대화를 초기화했습니다.");
  restartNotice = "";
  compareView.reset();
  resetVoiceOptions();
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
$("stop").addEventListener("click", () => { if (group) finishGroup(group, "대화를 중지했습니다."); });
$("reset").addEventListener("click", resetConversation);
$("skip-to-content").addEventListener("click", (event) => {
  event.preventDefault();
  $("command-input").focus();
});
$("voice-options-defaults").addEventListener("click", () => {
  if (group) {
    finishGroup(group, "");
    restartNotice = "설정을 기본값으로 되돌렸습니다. 다음 질문부터 새 설정으로 비교합니다.";
  }
  const mode = voiceFields.get("connection_mode");
  resetVoiceOptions(mode ? voiceOptionValue(mode) : null);
  availability();
});
window.addEventListener("pagehide", () => {
  stopReplay();
  if (group) finishGroup(group, "");
  audio?.close().catch(() => {});
});
compareView.setLive(liveProvider);
loadConfig();
