import { textNode, safeSourceUrl, sourceLink, isRecord, shortText, toolOutput } from "./search-results.js";
import { projectFlowEvent } from "./flow-observations.js";
import { providerNames, comparedProviders } from "./run-labels.js";

const TOOL_LABELS = {
  web: "웹 검색", news: "뉴스 검색", places: "장소 검색", finance: "금융 조회", browse: "페이지 열람",
  images: "이미지 검색", videos: "동영상 검색", sports: "스포츠 정보", sonic: "통합 검색", autosuggest: "검색어 제안",
};
const SEARCH_TITLES = { webiq: "Agent가 WebIQ로 검색한 내용", bing: "Agent가 Bing으로 검색한 내용" };
const SEARCH_WITH = { webiq: "WebIQ로", bing: "Bing으로" };
const STEPS = [["input", "질문"], ["think", "생각"], ["search", "검색"], ["results", "찾은 결과"], ["answer", "답변"]];
const TERMINAL = new Set(["done", "failed", "interrupted", "offline"]);
const MAX_AUDIO_BYTES = 3 * 1024 * 1024;
const PREVIEW_RESULTS = 3;
const seconds = (ms) => `${(Math.max(0, ms) / 1000).toFixed(1)}초`;
const plain = (value) => typeof value === "string" ? value.replace(/<[^<>]{0,80}>/g, " ").replace(/\s+/g, " ").trim() : "";
// Service citation markers and bold marks are for the answer renderer, not for a one-line preview.
const withoutMarks = (value) => value.replace(/【\d+:\d+†[^】]*】/g, "").replace(/\uE200cite\uE202[^\uE201]*\uE201/g, "")
  .replace(/\*\*([^*\n]+)\*\*/g, "$1").replace(/\s+/g, " ").trim();
const firstText = (...values) => values.find((value) => typeof value === "string" && value.trim())?.trim() || "";

export function createCompareView({ onReplay, onLive }) {
  const get = (id) => document.getElementById(id);
  const scroll = get("compare-scroll");
  const clock = new Intl.DateTimeFormat("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
  const turns = [];
  const cursors = new Map(comparedProviders.map((provider) => [provider, -1]));
  const available = new Map(comparedProviders.map((provider) => [provider, false]));
  const sessions = new WeakMap();
  let following = true;
  scroll.addEventListener("scroll", () => {
    following = scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 120;
  });
  for (const provider of comparedProviders) get(`lane-${provider}-live`).addEventListener("click", () => onLive(provider));

  function follow() {
    if (following) scroll.scrollTop = scroll.scrollHeight;
  }
  function session(lane) {
    if (!sessions.has(lane)) sessions.set(lane, { items: new Map(), responses: new Map(), echo: [] });
    return sessions.get(lane);
  }
  function current(provider) {
    const cursor = cursors.get(provider);
    return cursor >= 0 ? turns[cursor]?.cells.get(provider) || null : null;
  }
  // Responses belong to the lane's latest question until another question begins.
  function cellFor(lane, responseId) {
    const state = session(lane);
    if (responseId && state.responses.has(responseId)) return state.responses.get(responseId);
    const cell = current(lane.provider);
    if (!cell) return null;
    if (responseId) state.responses.set(responseId, cell);
    cell.mode ??= lane.run.connection_mode;
    return cell;
  }

  function createTurn(kind, question = "") {
    const index = turns.length;
    const element = textNode("li", "", "turn");
    element.dataset.turn = String(index + 1);
    element.dataset.kind = kind;
    const head = textNode("div", "", "turn-head");
    const questionNode = textNode("h2", question ? `“${question}”` : "음성 질문 인식 중…", "turn-question");
    const compareNode = textNode("span", "", "turn-compare");
    compareNode.hidden = true;
    head.append(textNode("span", `Q${index + 1}`, "turn-number"), questionNode,
      textNode("span", kind === "voice" ? "음성" : "텍스트", "turn-kind"), compareNode);
    const lanes = textNode("div", "", "turn-lanes");
    element.append(head, lanes);
    const turn = { index, kind, question, element, questionNode, compareNode, cells: new Map() };
    for (const provider of comparedProviders) {
      const cell = createCell(turn, provider);
      turn.cells.set(provider, cell);
      lanes.append(cell.element);
    }
    turns.push(turn);
    get("turns").append(element);
    get("compare-empty").hidden = true;
    following = true;
    follow();
    return turn;
  }

  function createCell(turn, provider) {
    const element = textNode("article", "", "cell");
    element.dataset.provider = provider;
    const head = textNode("header", "", "cell-head");
    const state = textNode("span", "", "cell-state");
    head.append(textNode("strong", providerNames[provider], "cell-name"), state);
    const steps = textNode("ol", "", "steps");
    steps.setAttribute("aria-label", `${providerNames[provider]} 실행 단계`);
    const stepItems = new Map();
    for (const [key, label] of STEPS) {
      const item = textNode("li", "", "step");
      item.dataset.step = key;
      const dot = textNode("span", "", "step-dot");
      dot.setAttribute("aria-hidden", "true");
      const detail = textNode("small", "", "step-detail");
      item.append(dot, textNode("strong", label, "step-name"), detail);
      steps.append(item);
      stepItems.set(key, { item, detail });
    }
    const recognized = textNode("p", "", "cell-recognized");
    const search = textNode("section", "", "search-box");
    const callList = textNode("ol", "", "search-calls");
    const searchNote = textNode("p", "", "search-note");
    const sources = textNode("div", "", "sources");
    const searchTitle = textNode("h3", SEARCH_TITLES[provider], "search-title");
    search.append(searchTitle, searchNote, callList, sources);
    const answer = textNode("section", "", "answer");
    const fillerText = textNode("p", "", "answer-filler");
    const answerText = textNode("p", "", "answer-text");
    const meta = textNode("div", "", "answer-meta");
    const timing = textNode("span", "", "answer-timing");
    const replay = textNode("button", "", "replay");
    replay.type = "button";
    meta.append(timing, replay);
    const notice = textNode("p", "", "cell-notice");
    // What the engine is doing right now, shown where its answer will appear.
    const activity = textNode("div", "", "cell-activity");
    activity.setAttribute("role", "status");
    const dots = textNode("span", "", "activity-dots");
    dots.setAttribute("aria-hidden", "true");
    dots.append(textNode("span", ""), textNode("span", ""), textNode("span", ""));
    const activityText = textNode("span", "", "activity-text");
    activity.append(dots, activityText);
    answer.append(fillerText, answerText, meta);
    element.append(head, steps, recognized, search, activity, answer, notice);
    const cell = {
      turn, provider, element, state, steps: stepItems, recognized, search, searchTitle, searchNote, callList, sources,
      answer, fillerText, answerText, timing, replay, notice, activity, activityText, mode: null, status: "waiting",
      startedAt: null, speechEndedAt: null, inputFinalAt: null, thinkStartAt: null, thinkEndAt: null,
      outputs: [], fillerResponses: new Set(), audioResponses: new Set(), doneAt: null, responseStarted: false, noticeText: "", playing: false,
      input: { mode: turn.kind, text: turn.question, final: turn.kind === "text", claimed: false },
      calls: new Map(), citations: new Map(), messages: new Map(), audio: { chunks: [], bytes: 0, truncated: false },
    };
    replay.addEventListener("click", () => onReplay(cell));
    if (turn.kind === "voice" && !available.get(provider)) {
      cell.status = "offline";
      cell.noticeText = "이 엔진은 지금 연결되어 있지 않아 질문을 받지 못했습니다.";
    }
    render(cell);
    return cell;
  }

  function call(cell, id) {
    if (!cell.calls.has(id)) {
      const item = textNode("li", "", "search-call");
      cell.callList.append(item);
      cell.calls.set(id, { id, item, kind: null, name: null, args: null, output: undefined, status: null, startedAt: null, settledAt: null });
    }
    return cell.calls.get(id);
  }
  const hidesSearch = (cell) => cell.provider === "bing" && (cell.mode || "agent") === "agent";
  // End-to-end models hear the audio itself; the on-screen caption comes from a separate recognition model.
  const hearsAudio = (cell) => cell.mode === "realtime_agent_tool";
  // A model that talks may say a short filler before it searches; only what follows its last search is the answer.
  // The server also marks a response that ended in a search, since its transcript can arrive after the search starts.
  const lastSearchAt = (cell) => (cell.mode || "agent") === "agent" ? -Infinity
    : Math.max(-Infinity, ...[...cell.calls.values()].map((entry) => entry.startedAt ?? -Infinity));
  const isFiller = (cell, output) => output.at != null
    && (cell.fillerResponses.has(output.responseId) || output.at < lastSearchAt(cell));
  function answerAt(cell) {
    const times = cell.outputs.filter((output) => !isFiller(cell, output)).map((output) => output.at);
    return times.length ? Math.min(...times) : null;
  }
  function fillerAt(cell) {
    const times = cell.outputs.filter((output) => isFiller(cell, output)).map((output) => output.at);
    return times.length ? Math.min(...times) : null;
  }
  function outputStarted(cell, responseId) {
    const output = { at: Date.now(), responseId: responseId || null };
    cell.outputs.push(output);
    markThinkingEnd(cell);
    return output;
  }
  // The Agent is thinking from the moment it has the question until it starts a search or its answer.
  function markThinkingEnd(cell) {
    const now = Date.now();
    cell.thinkStartAt ??= cell.startedAt ?? now;
    cell.thinkEndAt ??= now;
  }
  // Where the engine is in its work, regardless of how the answer ended.
  function progress(cell) {
    if (answerAt(cell) != null) return "answering";
    if (cell.input.mode === "voice" && !cell.input.final && cell.thinkStartAt == null) {
      return cell.speechEndedAt != null ? "transcribing" : cell.input.claimed ? "listening" : "waiting";
    }
    if (cell.thinkStartAt == null) return "waiting";
    if (cell.thinkEndAt == null) return "thinking";
    return [...cell.calls.values()].some((entry) => !settled(entry)) ? "searching" : "writing";
  }
  const phase = (cell) => TERMINAL.has(cell.status) ? cell.status : progress(cell);
  function describeActivity(cell, now) {
    const runningCall = [...cell.calls.values()].find((entry) => !settled(entry));
    const searching = runningCall?.kind === "foundry_agent_call" ? `${providerNames[cell.provider]} Agent에게 검색을 맡기는 중…`
      : runningCall?.kind === "web_search_call" ? "웹 검색 중…"
        : `${SEARCH_WITH[cell.provider]} ${runningCall ? toolLabel(runningCall, cell.provider) : "검색"} 중…`;
    return {
      waiting: cell.input.mode === "text" ? "엔진에 연결하는 중…" : "",
      listening: "말씀을 듣는 중…",
      transcribing: "말씀을 글자로 바꾸는 중…",
      thinking: hidesSearch(cell) ? "Agent가 생각하며 Bing으로 검색하는 중…"
        : hearsAudio(cell) && cell.input.mode === "voice" ? "Realtime 모델이 음성을 직접 듣고 생각하는 중…"
          : "Agent가 질문을 이해하고 무엇을 검색할지 생각하는 중…",
      searching,
      writing: "찾은 결과를 읽고 답변을 준비하는 중…",
    }[now] || "";
  }
  const settled = (entry) => entry.settledAt != null || entry.output !== undefined || ["completed", "failed"].includes(entry.status);
  const hasAnswer = (cell) => [...cell.messages.values()].some((message) => message.text.trim() && !isFiller(cell, message.output));

  function toolLabel(entry, provider) {
    if (entry.kind === "foundry_agent_call") return `${providerNames[provider]} Agent 호출`;
    if (entry.kind === "web_search_call") return "웹 검색";
    const part = String(entry.name || "").toLowerCase().split(/[._:/\s-]+/).find((key) => Object.hasOwn(TOOL_LABELS, key));
    return part ? TOOL_LABELS[part] : entry.name || "검색 도구";
  }
  const isWebSearch = (entry) => ["mcp_call", "function_call"].includes(entry.kind) && entry.name === "web_search";
  // Reads the Toolbox Web Search result: answer text plus url_citation annotations or markdown links.
  function searchAnswer(output) {
    let value = output;
    if (typeof value === "string") {
      try { value = JSON.parse(value); } catch { /* plain answer text */ }
    }
    const texts = [], found = [];
    (function visit(node, depth) {
      if (depth > 6 || node == null) return;
      if (typeof node === "string") { texts.push(node); return; }
      if (Array.isArray(node)) { for (const child of node) visit(child, depth + 1); return; }
      if (!isRecord(node)) return;
      if (node.type === "url_citation") found.push({ url: node.url, title: node.title });
      if (typeof node.text === "string") texts.push(node.text);
      for (const [key, child] of Object.entries(node)) if (key !== "text" && typeof child === "object") visit(child, depth + 1);
    })(value, 0);
    const text = texts.join("\n");
    for (const match of text.matchAll(/\[([^\]\n]{1,120})\]\((https?:\/\/[^)\s]+)\)/g)) found.push({ title: match[1], url: match[2] });
    const links = new Map();
    for (const { url, title } of found) {
      const safe = safeSourceUrl(url);
      if (safe && !links.has(safe.href)) links.set(safe.href, { url: safe, title: firstText(title) });
    }
    const readable = text.replace(/\(\[[^\]\n]*\]\([^)\s]*\)\)/g, "").replace(/\[([^\]\n]*)\]\([^)\s]*\)/g, "$1")
      .replace(/[#*|>`]+/g, " ").replace(/-{3,}/g, " ").replace(/\s+/g, " ").trim();
    return { text: readable, links: [...links.values()] };
  }
  function callQuery(args) {
    if (!isRecord(args)) return null;
    for (const [key, label] of [["query", "검색어"], ["q", "검색어"], ["search_query", "검색어"], ["input", "Agent에 보낸 요청"], ["url", "열어 본 페이지"]]) {
      if (typeof args[key] === "string" && args[key].trim()) return { label, value: args[key].trim() };
    }
    return null;
  }
  function openToday(openHours) {
    const days = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
    const hours = isRecord(openHours) && isRecord(openHours.standard) ? openHours.standard[days[new Date().getDay()]] : null;
    if (!Array.isArray(hours) || !hours.length) return "";
    return hours.every((range) => range === "00:00-23:59") ? "24시간 영업" : `오늘 ${hours.filter((range) => typeof range === "string").join(", ")}`;
  }
  function resultItem({ item }) {
    if (!isRecord(item)) return null;
    const data = isRecord(item.data) ? item.data : {};
    const instrument = isRecord(data.instrument) ? data.instrument : null;
    const url = safeSourceUrl(item.url) || safeSourceUrl(item.businessUrl);
    const title = firstText(instrument?.displayName, item.title, item.name, data.name) || url?.hostname;
    if (!title) return null;
    const facts = [];
    if (instrument) {
      if (Number.isFinite(instrument.price)) {
        facts.push(`${instrument.price.toLocaleString("ko-KR")}${instrument.currency ? ` ${instrument.currency}` : ""}`);
      }
      if (Number.isFinite(instrument.changePercent)) {
        const change = instrument.changePercent;
        facts.push(`${change > 0 ? "▲" : change < 0 ? "▼" : ""}${Math.abs(change).toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%`);
      }
      const traded = typeof instrument.lastTradedAt === "string" ? new Date(instrument.lastTradedAt) : null;
      if (traded && !Number.isNaN(traded.getTime())) facts.push(`${clock.format(traded)} 기준`);
    }
    if (typeof item.category === "string" && item.category.trim()) facts.push(item.category.trim());
    const address = firstText(item.address, isRecord(item.address) ? item.address.text : null, isRecord(item.location) ? item.location.address : null);
    if (address) facts.push(address);
    const hours = openToday(item.openHours);
    if (hours) facts.push(hours);
    const location = isRecord(item.location) ? item.location : null;
    const row = textNode("li", "", "result");
    row.append(textNode("strong", `${shortText(title, 90)}${instrument?.symbol ? ` (${shortText(instrument.symbol, 20)})` : ""}`, "result-title"));
    if (facts.length) row.append(textNode("span", facts.join(" · "), "result-facts"));
    if (location && Number.isFinite(location.latitude) && Number.isFinite(location.longitude)) {
      row.append(textNode("span", `좌표 ${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`, "result-geo"));
    }
    const excerpt = instrument || location ? "" : plain(firstText(item.snippet, item.description, item.content));
    if (excerpt) row.append(textNode("p", shortText(excerpt, 140), "result-excerpt"));
    if (url) row.append(sourceLink(url, url.hostname.replace(/^www\./, "")));
    return row;
  }

  function renderCall(cell, entry) {
    const { item } = entry;
    item.replaceChildren();
    const failed = entry.status === "failed";
    item.dataset.state = failed ? "failed" : settled(entry) ? "done" : "running";
    const time = entry.startedAt != null && entry.settledAt != null ? ` · ${seconds(entry.settledAt - entry.startedAt)}` : "";
    const head = textNode("div", "", "call-head");
    head.append(textNode("strong", toolLabel(entry, cell.provider)),
      textNode("span", failed ? "실패" : settled(entry) ? `완료${time}` : "검색 중…", "call-state"));
    item.append(head);
    const query = callQuery(entry.args);
    if (query) item.append(textNode("p", `${query.label} “${shortText(query.value, 200)}”`, "call-query"));
    if (entry.output === undefined) return;
    if (entry.kind === "foundry_agent_call") {
      item.append(textNode("p", `Agent 답변 “${shortText(withoutMarks(plain(typeof entry.output === "string" ? entry.output : JSON.stringify(entry.output))), 220)}”`, "call-answer"));
    } else if (isWebSearch(entry)) {
      // Web Search returns a grounded summary with source links, not a list of results.
      const answer = searchAnswer(entry.output);
      if (answer.text) item.append(textNode("p", `검색 답변 “${shortText(answer.text, 220)}”`, "call-answer"));
      item.append(textNode("p", `출처 ${answer.links.length}개`, "call-count"));
      if (answer.links.length) {
        const list = textNode("ol", "", "results");
        for (const { url, title } of answer.links.slice(0, PREVIEW_RESULTS)) {
          const row = textNode("li", "", "result");
          row.append(textNode("strong", shortText(title || url.hostname, 90), "result-title"), sourceLink(url, url.hostname.replace(/^www\./, "")));
          list.append(row);
        }
        item.append(list);
      }
    } else {
      const output = toolOutput(entry.output);
      const rows = output.results.map(resultItem).filter(Boolean);
      item.append(textNode("p", output.unreadable && !rows.length ? "결과를 요약할 수 없습니다 · 원본 데이터를 확인하세요."
        : `결과 ${output.results.length}건`, "call-count"));
      if (rows.length) {
        const list = textNode("ol", "", "results");
        list.append(...rows.slice(0, PREVIEW_RESULTS));
        item.append(list);
        if (rows.length > PREVIEW_RESULTS) {
          const more = textNode("details", "", "more-results");
          const rest = textNode("ol", "", "results");
          rest.append(...rows.slice(PREVIEW_RESULTS));
          more.append(textNode("summary", `나머지 ${rows.length - PREVIEW_RESULTS}건 보기`), rest);
          item.append(more);
        }
      }
    }
    const raw = textNode("details", "", "raw");
    const body = typeof entry.output === "string" ? entry.output : JSON.stringify(entry.output, null, 2);
    raw.append(textNode("summary", "원본 데이터"), textNode("pre", body.length > 6000 ? `${body.slice(0, 6000)}…` : body));
    item.append(raw);
  }

  function renderSources(cell) {
    cell.sources.replaceChildren();
    if (!cell.citations.size) return;
    cell.sources.append(textNode("p", `답변 출처 ${cell.citations.size}개`, "sources-title"));
    const list = textNode("ol", "", "results");
    for (const { url, title } of cell.citations.values()) {
      const row = textNode("li", "", "result");
      row.append(textNode("strong", shortText(title, 90), "result-title"), sourceLink(url, url.hostname.replace(/^www\./, "")));
      list.append(row);
    }
    cell.sources.append(list);
  }

  function answerText(cell) {
    // Service citation markers are represented by the source list, not read as text.
    const readable = (messages, separator) => messages.map((message) => message.text.trim()).filter(Boolean).join(separator)
      .replace(/【\d+:\d+†[^】]*】/g, "").replace(/\uE200cite\uE202[^\uE201]*\uE201/g, "").trim();
    const messages = [...cell.messages.values()];
    const filler = readable(messages.filter((message) => isFiller(cell, message.output)), " ");
    const text = readable(messages.filter((message) => !isFiller(cell, message.output)), "\n");
    cell.fillerText.textContent = filler ? `대기 멘트 “${filler}”` : "";
    cell.fillerText.hidden = !filler;
    cell.answerText.replaceChildren();
    for (const part of text.split(/(\*\*[^*\n]+\*\*)/g)) {
      cell.answerText.append(part.startsWith("**") && part.endsWith("**") && part.length > 4 ? textNode("strong", part.slice(2, -2)) : part);
    }
  }

  function setStep(cell, key, state, detail) {
    const step = cell.steps.get(key);
    step.item.dataset.state = state;
    step.detail.textContent = detail;
  }
  function render(cell) {
    const since = (at) => cell.startedAt != null && at != null ? seconds(at - cell.startedAt) : "";
    const calls = [...cell.calls.values()];
    const terminal = TERMINAL.has(cell.status);
    const answered = hasAnswer(cell);
    const voice = cell.input.mode === "voice";
    const direct = voice && hearsAudio(cell);
    const respondedAt = answerAt(cell);
    const now = phase(cell);
    const at = progress(cell);
    const running = calls.some((entry) => !settled(entry));
    const ended = calls.map((entry) => entry.settledAt).filter((time) => time != null);
    const searchEndAt = calls.length && !running && ended.length ? Math.max(...ended) : null;
    const recognition = cell.inputFinalAt != null && cell.speechEndedAt != null ? `인식 ${seconds(cell.inputFinalAt - cell.speechEndedAt)}` : "음성 인식";
    const heard = direct && (cell.speechEndedAt != null || cell.input.final);
    setStep(cell, "input", cell.status === "offline" ? "skipped" : cell.input.final || heard ? "done" : voice && cell.input.claimed ? "active" : "pending",
      !voice ? "텍스트" : heard ? "음성 그대로 전달" : cell.input.final ? recognition
        : at === "listening" ? "듣는 중…" : cell.input.claimed ? "인식 중…" : "음성");
    if (cell.thinkEndAt != null) {
      const thought = seconds(cell.thinkEndAt - cell.thinkStartAt);
      setStep(cell, "think", "done", hidesSearch(cell) && !calls.length ? `검색 포함 ${thought}` : thought);
    } else {
      setStep(cell, "think", at === "thinking" ? "active" : "pending",
        at === "thinking" ? (hidesSearch(cell) ? "생각·검색 중…" : "생각 중…") : "");
    }
    if (calls.length) {
      const failed = calls.every((entry) => entry.status === "failed");
      const labels = [...new Set(calls.map((entry) => toolLabel(entry, cell.provider)))];
      const started = calls.map((entry) => entry.startedAt).filter((time) => time != null);
      const duration = searchEndAt != null && started.length ? ` · ${seconds(searchEndAt - Math.min(...started))}` : "";
      setStep(cell, "search", running ? "active" : failed ? "failed" : "done",
        `${labels[0]}${labels.length > 1 ? ` 외 ${labels.length - 1}` : ""}${calls.length > 1 ? ` · ${calls.length}회` : ""}${duration}`);
    } else if (hidesSearch(cell)) {
      setStep(cell, "search", cell.thinkStartAt != null || cell.responseStarted || answered || terminal ? "hidden" : "pending", "Agent가 Bing 검색");
    } else {
      const skipped = cell.thinkEndAt != null || answered || terminal;
      setStep(cell, "search", skipped ? "skipped" : "pending", skipped ? "검색 안 함" : "");
    }
    const outputs = calls.filter((entry) => entry.output !== undefined);
    const listed = outputs.filter((entry) => entry.kind !== "foundry_agent_call" && !isWebSearch(entry));
    const resultCount = listed.reduce((total, entry) => total + toolOutput(entry.output).results.length, 0);
    const summarized = outputs.filter(isWebSearch);
    const found = [];
    if (listed.length) found.push(`${resultCount}건`);
    if (summarized.length) {
      const sources = new Set(summarized.flatMap((entry) => searchAnswer(entry.output).links.map((link) => link.url.href)));
      found.push(`검색 답변 · 출처 ${sources.size}개`);
    }
    if (outputs.some((entry) => entry.kind === "foundry_agent_call")) found.push("Agent 답변");
    if (cell.citations.size) found.push(`출처 ${cell.citations.size}개`);
    setStep(cell, "results", found.length ? "done" : running ? "active" : terminal ? "skipped" : "pending",
      found.length ? found.join(" · ") : terminal ? (hidesSearch(cell) ? "출처 없음" : "없음") : "");
    // Agent connections report the search result together with the answer start, so a zero gap reads as plain completion.
    const writeMs = searchEndAt != null && respondedAt != null && !hidesSearch(cell) ? respondedAt - searchEndAt : 0;
    const writing = writeMs >= 100 ? `작성 ${seconds(writeMs)}` : "완료";
    setStep(cell, "answer", cell.status === "done" ? "done" : at === "answering" || at === "writing" ? "active" : "pending",
      cell.status === "done" ? writing : at === "answering" ? "답변 중…" : at === "writing" ? "작성 중…" : "");
    if (cell.status === "failed" || cell.status === "interrupted") {
      // The step that was in progress shows why this engine stopped.
      let marked = false;
      for (const step of cell.steps.values()) {
        if (step.item.dataset.state !== "active") continue;
        step.item.dataset.state = cell.status;
        marked = true;
      }
      if (!marked) {
        const lastStep = cell.steps.get("answer");
        lastStep.item.dataset.state = cell.status;
        lastStep.detail.textContent = cell.status === "failed" ? "실패" : "중단";
      }
    }
    cell.element.dataset.status = cell.status;
    cell.element.dataset.phase = now;
    cell.state.textContent = {
      offline: "연결 안 됨", failed: "실패", interrupted: "중단",
      done: respondedAt != null && cell.startedAt != null ? `응답 ${since(respondedAt)}` : "완료",
      waiting: voice ? "대기" : "연결 중…", listening: "듣는 중…", transcribing: "인식 중…", thinking: "생각 중…",
      searching: "검색 중…", writing: "답변 작성 중…", answering: "답변 중…",
    }[now] || "";
    cell.activityText.textContent = describeActivity(cell, now);
    cell.activity.hidden = !cell.activityText.textContent;
    // End-to-end models hear the audio itself, so a caption would only suggest a question they never received.
    const shown = voice && !direct && cell.input.text;
    cell.recognized.hidden = !shown;
    cell.recognized.textContent = shown ? `${(cell.mode || "agent") === "agent" ? "Agent가 받은 질문" : "인식한 질문"} “${cell.input.text}”` : "";
    if (direct && !cell.turn.question) cell.turn.questionNode.textContent = "음성 질문 · 모델이 음성을 직접 들어요";
    const note = !calls.length && hidesSearch(cell) && (cell.responseStarted || answered || terminal)
      ? "Agent가 Bing 검색 결과를 읽고 답변을 작성했어요. 답변에 사용한 출처는 아래 링크에서 확인할 수 있어요."
      : !calls.length && (answered || terminal) && cell.status !== "offline" ? "이번 답변에서는 검색 도구를 사용하지 않았습니다." : "";
    cell.searchNote.textContent = note;
    cell.searchNote.hidden = !note;
    // In End-to-end the realtime model searches by itself; there is no Agent in between.
    cell.searchTitle.textContent = cell.mode === "realtime_agent_tool" && calls.every((entry) => entry.kind !== "foundry_agent_call")
      ? SEARCH_TITLES[cell.provider].replace("Agent가", "모델이") : SEARCH_TITLES[cell.provider];
    cell.callList.hidden = !calls.length;
    cell.sources.hidden = !cell.citations.size;
    cell.search.hidden = !note && !calls.length && !cell.citations.size;
    const timing = [];
    const filler = fillerAt(cell);
    if (cell.startedAt != null && filler != null) timing.push(`대기 멘트 ${since(filler)}`);
    if (cell.startedAt != null && respondedAt != null) timing.push(`응답 시작 ${since(respondedAt)}`);
    if (cell.startedAt != null && cell.doneAt != null) timing.push(`완료 ${since(cell.doneAt)}`);
    cell.timing.textContent = timing.join(" · ");
    cell.replay.hidden = !cell.audio.bytes || !terminal;
    cell.replay.textContent = cell.playing ? "■ 정지" : "▶ 답변 듣기";
    cell.replay.setAttribute("aria-pressed", String(cell.playing));
    cell.replay.setAttribute("aria-label", `${providerNames[cell.provider]} 답변 ${cell.playing ? "재생 정지" : "듣기"}`);
    answerText(cell);
    cell.answer.hidden = !answered && cell.fillerText.hidden && !cell.timing.textContent && cell.replay.hidden;
    cell.notice.textContent = cell.noticeText;
    cell.notice.hidden = !cell.noticeText;
    compareTurn(cell.turn);
  }
  function compareTurn(turn) {
    const cells = comparedProviders.map((provider) => turn.cells.get(provider));
    if (cells.some((cell) => !cell)) return;
    const times = cells.map((cell) => cell.startedAt != null && answerAt(cell) != null
      ? `${providerNames[cell.provider]} ${seconds(answerAt(cell) - cell.startedAt)}` : null);
    turn.compareNode.hidden = times.some((time) => !time);
    turn.compareNode.textContent = times.every(Boolean) ? `응답 시작 · ${times.join(" · ")}` : "";
  }

  function claimVoiceCell(provider) {
    let turn = turns[cursors.get(provider) + 1];
    if (!turn || turn.kind !== "voice" || turn.cells.get(provider).input.claimed) turn = createTurn("voice");
    cursors.set(provider, turn.index);
    const cell = turn.cells.get(provider);
    cell.input.claimed = true;
    if (cell.status === "offline") {
      cell.status = "waiting";
      cell.noticeText = "";
    }
    return cell;
  }
  function userTranscript(lane, event) {
    const state = session(lane);
    let cell = event.item_id ? state.items.get(event.item_id) : null;
    if (!cell) {
      cell = event.input_mode === "text" ? state.echo.shift() || current(lane.provider) : claimVoiceCell(lane.provider);
      if (!cell) return;
      cell.mode ??= lane.run.connection_mode;
      if (event.item_id) state.items.set(event.item_id, cell);
    }
    if (event.input_mode === "text") {
      cell.input = { ...cell.input, mode: cell.input.mode, text: event.text, final: true };
    } else {
      if (cell.input.final && !event.final) return;
      cell.input.mode = "voice";
      cell.input.text = event.final ? event.text : cell.input.text + event.text;
      cell.input.final = Boolean(event.final);
      if (event.final) {
        const now = Date.now();
        cell.startedAt ??= now;
        cell.inputFinalAt ??= now;
        cell.thinkStartAt ??= now;
        if (!cell.turn.question && event.text.trim() && !hearsAudio(cell)) {
          cell.turn.question = event.text.trim();
          cell.turn.questionNode.textContent = `“${cell.turn.question}”`;
        }
        // A new spoken question ends an earlier answer this engine was still waiting to give.
        for (const turn of turns.slice(0, cell.turn.index)) {
          const earlier = turn.cells.get(lane.provider);
          if (!earlier || TERMINAL.has(earlier.status) || earlier.startedAt == null || answerAt(earlier) != null) continue;
          earlier.status = "interrupted";
          earlier.noticeText = "다음 질문이 시작되어 이 답변은 끝나지 않았습니다.";
          earlier.doneAt ??= now;
          render(earlier);
        }
      }
    }
    render(cell);
    follow();
  }
  function assistantTranscript(lane, event) {
    const cell = cellFor(lane, event.response_id);
    if (!cell || cell.status === "offline") return;
    const key = event.item_id || event.response_id || "answer";
    if (!cell.messages.has(key)) cell.messages.set(key, { text: "", final: false, output: {} });
    const message = cell.messages.get(key);
    if (message.final && !event.final) return;
    message.text = event.final ? event.text : message.text + event.text;
    message.final = Boolean(event.final);
    if (message.text.trim() && message.output.at == null) message.output = outputStarted(cell, event.response_id);
    if (!TERMINAL.has(cell.status)) cell.status = "answering";
    render(cell);
    follow();
  }

  return {
    hasTurns: () => turns.length > 0,
    question(text) {
      const turn = createTurn("text", text);
      for (const provider of comparedProviders) cursors.set(provider, turn.index);
      return turn;
    },
    submitted(lane, cell) {
      const now = Date.now();
      cell.startedAt = now;
      cell.inputFinalAt = now;
      cell.thinkStartAt = now;
      cell.mode = lane.run.connection_mode;
      if (cell.status === "offline") cell.status = "waiting";
      cell.noticeText = "";
      session(lane).echo.push(cell);
      render(cell);
    },
    transcript(lane, event) {
      if (event.role === "user") userTranscript(lane, event);
      else if (event.role === "assistant") assistantTranscript(lane, event);
    },
    flow(lane, original) {
      const event = projectFlowEvent(original);
      const { stage, status, data } = event;
      if ((stage === "speech" && status === "stopped") || (stage === "input" && status === "committed")) {
        const cell = event.item_id ? session(lane).items.get(event.item_id) : null;
        if (cell && cell.speechEndedAt == null) {
          const now = Date.now();
          cell.startedAt ??= now;
          cell.speechEndedAt = now;
          // The realtime model starts on the audio itself, without waiting for the caption.
          if (hearsAudio(cell)) cell.thinkStartAt ??= now;
          render(cell);
        }
      } else if (stage === "response" && status === "created" && event.response_id) {
        const cell = cellFor(lane, event.response_id);
        if (cell && !TERMINAL.has(cell.status)) {
          cell.responseStarted = true;
          if (cell.input.final || hearsAudio(cell)) cell.thinkStartAt ??= Date.now();
          render(cell);
        }
      } else if (stage === "tool" && event.tool_id
        && ["mcp_call", "foundry_agent_call", "function_call", "web_search_call"].includes(data.kind)) {
        const cell = cellFor(lane, event.response_id);
        if (!cell || cell.status === "offline") return;
        const entry = call(cell, event.tool_id);
        entry.kind ??= data.kind;
        entry.name ??= data.name || null;
        if (["announced", "in_progress", "searching", "arguments_ready"].includes(status)) entry.startedAt ??= Date.now();
        if (isRecord(data.arguments) && Object.keys(data.arguments).length) entry.args = data.arguments;
        if (["completed", "failed"].includes(status)) {
          entry.status = status;
          entry.settledAt ??= Date.now();
        }
        cell.responseStarted = true;
        markThinkingEnd(cell);
        renderCall(cell, entry);
        render(cell);
      }
    },
    tool(lane, event) {
      const cell = cellFor(lane, event.response_id);
      if (!cell || cell.status === "offline" || event.kind === "navigation_action") return;
      const entry = call(cell, typeof event.id === "string" && event.id ? event.id : `call-${cell.calls.size}`);
      if (typeof event.kind === "string") entry.kind = event.kind;
      if (typeof event.name === "string" && event.name) entry.name = event.name;
      if (isRecord(event.arguments) && Object.keys(event.arguments).length) entry.args = event.arguments;
      entry.startedAt ??= Date.now();
      if (typeof event.status === "string") entry.status = event.status;
      if (event.output != null) {
        entry.output = event.output;
        entry.settledAt ??= Date.now();
      } else if (event.status === "failed") entry.settledAt ??= Date.now();
      markThinkingEnd(cell);
      renderCall(cell, entry);
      render(cell);
      follow();
    },
    citation(lane, event) {
      const url = safeSourceUrl(event.url);
      const cell = url ? cellFor(lane, event.response_id) : null;
      if (!cell || cell.status === "offline") return;
      if (![...cell.citations.values()].some((source) => source.url.href === url.href)) {
        cell.citations.set(url.href, { url, title: firstText(event.title) || url.hostname });
      }
      renderSources(cell);
      render(cell);
    },
    // Returns true when this response ends the lane's answer for the question.
    complete(lane, event) {
      const cell = cellFor(lane, event.response_id);
      if (!cell || TERMINAL.has(cell.status)) return true;
      const answered = hasAnswer(cell);
      if (event.interrupted || event.status === "cancelled") cell.status = "interrupted";
      else if (event.status === "failed" || event.status === "incomplete") {
        cell.status = "failed";
        cell.noticeText = "응답이 끝까지 완료되지 않았습니다.";
      } else if (event.followup) {
        // The server asks for the answer once the search returns; what was said so far came before the search.
        if (event.response_id) cell.fillerResponses.add(event.response_id);
        render(cell);
        return false;
      } else if (!answered && cell.calls.size && lane.run.connection_mode !== "agent") {
        // Model pipelines answer in a follow-up response after a response that ends in a search,
        // even when the model spoke a filler before searching.
        render(cell);
        return false;
      } else {
        cell.status = "done";
        markThinkingEnd(cell);
        if (!answered) cell.noticeText = "서비스가 답변 텍스트를 보내지 않았습니다.";
      }
      cell.doneAt = Date.now();
      render(cell);
      return true;
    },
    audio(lane, event, bytes) {
      const cell = cellFor(lane, event.response_id);
      if (!cell || cell.status === "offline") return;
      if (cell.audio.bytes + bytes.byteLength <= MAX_AUDIO_BYTES) {
        cell.audio.chunks.push(bytes);
        cell.audio.bytes += bytes.byteLength;
      } else cell.audio.truncated = true;
      // Each response's first sound counts once; a filler and the answer can come from different responses.
      const response = event.response_id || "audio";
      if (!cell.audioResponses.has(response)) {
        cell.audioResponses.add(response);
        outputStarted(cell, event.response_id);
        render(cell);
      }
    },
    interrupt(lane, event) {
      const cell = event.response_id ? session(lane).responses.get(event.response_id) : null;
      if (!cell || TERMINAL.has(cell.status)) return;
      cell.status = "interrupted";
      cell.doneAt = Date.now();
      render(cell);
    },
    busy(lane, message) {
      const cell = session(lane).echo.shift();
      if (!cell || TERMINAL.has(cell.status)) return;
      cell.status = "failed";
      cell.noticeText = `이 질문은 전달되지 않았습니다. ${message}`;
      render(cell);
    },
    stalled(lane) {
      const cell = current(lane.provider);
      if (!cell || TERMINAL.has(cell.status)) return;
      cell.status = "failed";
      cell.noticeText = "응답이 오지 않아 기다리기를 멈췄습니다. 다시 질문해 보세요.";
      render(cell);
    },
    // Marks the provider's unfinished answer when its connection ends.
    fail(provider, message) {
      const cell = current(provider);
      if (!cell || TERMINAL.has(cell.status)) return;
      cell.status = "failed";
      cell.noticeText = message;
      render(cell);
    },
    closed(provider) {
      const cell = current(provider);
      if (!cell || TERMINAL.has(cell.status) || (cell.startedAt == null && !cell.responseStarted && !cell.input.claimed)) return;
      cell.status = "interrupted";
      cell.noticeText = "연결이 끝나 답변을 마치지 못했습니다.";
      render(cell);
    },
    laneStatus(provider, state, text) {
      available.set(provider, ["connecting", "ready", "busy"].includes(state));
      get(`lane-${provider}-dot`).dataset.state = state;
      get(`lane-${provider}-status`).textContent = text;
    },
    setLive(provider) {
      for (const name of comparedProviders) {
        const button = get(`lane-${name}-live`);
        const live = name === provider;
        button.setAttribute("aria-pressed", String(live));
        button.textContent = live ? "음성 출력 중" : "이 엔진 음성 듣기";
      }
    },
    replayState(cell, playing) {
      cell.playing = playing;
      render(cell);
    },
    reset() {
      turns.length = 0;
      for (const provider of comparedProviders) cursors.set(provider, -1);
      get("turns").replaceChildren();
      get("compare-empty").hidden = false;
      following = true;
    },
  };
}
