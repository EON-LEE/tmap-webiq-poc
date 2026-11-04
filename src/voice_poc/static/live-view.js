import { textNode, safeSourceUrl, sourceLink } from "./search-results.js";
import { providerNames } from "./labels.js";

const GLIVE_COMBO_KEY = "voice-poc.live-combos.v1";
const GLIVE_DEFAULT_COMBOS = [["noeul", "korean"], ["marin", "korean"], ["marin", "none"]];
const GLIVE_LANGUAGES = { korean: "항상 한국어", follow_user: "사용자 언어 따라가기", none: "지시 없음" };
const GLIVE_BACKCHANNELS = { none: "맞장구 없음", sometimes: "맞장구 가끔", often: "맞장구 자주" };
const GLIVE_STEPS = [["listen", "듣기"], ["delegate", "위임"], ["search", "Agent 검색"], ["deliver", "결과 전달"], ["speak", "말하기"]];
const GLIVE_VERDICTS = { ok: "정상", warn: "섞임", bad: "한국어 아님", silent: "음성 없음", run: "진행 중", wait: "실행 전" };
// A delta joins the speaker's open bubble when it follows within this gap on the service timeline.
const GLIVE_BUBBLE_GAP_MS = 1200;
const GLIVE_BACKCHANNEL_CHARS = 12;
const GLIVE_MAX_AUDIO_BYTES = 3 * 1024 * 1024;
const gliveSeconds = (ms) => typeof ms === "number" && Number.isFinite(ms) ? `${(Math.max(0, ms) / 1000).toFixed(1)}초` : "—";
const gliveNumber = (value) => typeof value === "number" && Number.isFinite(value) ? value : null;
const gliveVoiceName = (value) => typeof value === "string" && value ? value.charAt(0).toUpperCase() + value.slice(1) : "—";
const gliveLanguage = (value) => Object.hasOwn(GLIVE_LANGUAGES, value) ? GLIVE_LANGUAGES[value] : String(value || "—");

// Share of Hangul among the letters GPT-Live spoke; null until there is something to measure.
export function hangulRatio(text) {
  const letters = typeof text === "string" ? text.match(/\p{L}/gu) || [] : [];
  if (!letters.length) return null;
  return letters.filter((letter) => /\p{Script=Hangul}/u.test(letter)).length / letters.length;
}
export function hangulState(ratio) {
  return ratio == null ? "info" : ratio >= 0.8 ? "ok" : ratio >= 0.3 ? "warn" : "bad";
}
function gliveStorage() {
  try { return window.localStorage || null; } catch { return null; }
}
function loadCombos() {
  try {
    const parsed = JSON.parse(gliveStorage()?.getItem(GLIVE_COMBO_KEY) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch { return {}; }
}
function saveCombos(combos) {
  try { gliveStorage()?.setItem(GLIVE_COMBO_KEY, JSON.stringify(combos)); } catch { /* Storage is optional. */ }
}

export function createLiveView({ onReplay, compareView }) {
  const get = (id) => document.getElementById(id);
  const board = get("live-board");
  const scroll = get("compare-scroll");
  const sessions = [];
  const combos = loadCombos();
  let comboBody = null;
  let following = true;
  scroll.addEventListener("scroll", () => {
    following = scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 120;
  });
  const follow = () => { if (following) scroll.scrollTop = scroll.scrollHeight; };
  const current = () => sessions.at(-1) || null;
  const cardFor = (provider) => current()?.lanes.get(provider) || null;

  function chip(text, className = "chip") {
    return textNode("span", text, className);
  }
  function comboCard() {
    const card = textNode("section", "", "card combo-card");
    const title = textNode("h3", "음성·언어 지시 조합별 기록", "section-title");
    title.append(textNode("small", "한국어 음성이 돌아오는지 조합마다 확인합니다 · 이 브라우저에만 저장"));
    const table = textNode("table", "", "combo");
    const head = textNode("thead", "");
    const row = textNode("tr", "");
    for (const label of ["음성", "언어 지시", "음성 수신", "답변 한글 비율", "상태", "최근 실행"]) {
      const cell = textNode("th", label);
      cell.scope = "col";
      row.append(cell);
    }
    head.append(row);
    comboBody = textNode("tbody", "");
    const caption = textNode("caption", "설정에서 음성과 언어 지시를 바꿔 같은 질문을 말하면 한 줄씩 채워집니다. ‘Marin + 지시 없음’은 한국어 음성이 나오지 않는 상황을 재현하는 비교용 조합입니다.");
    table.append(caption, head, comboBody);
    const wrap = textNode("div", "", "table-wrap");
    wrap.append(table);
    card.append(title, wrap);
    renderCombos();
    return card;
  }
  function renderCombos() {
    if (!comboBody) return;
    const keys = GLIVE_DEFAULT_COMBOS.map(([voice, language]) => `${voice}|${language}`);
    for (const key of Object.keys(combos)) if (!keys.includes(key)) keys.push(key);
    const active = current();
    const activeKey = active ? `${active.voice}|${active.language}` : "";
    comboBody.replaceChildren(...keys.map((key) => {
      const [voice, language] = key.split("|");
      const entry = combos[key];
      const row = textNode("tr", "", key === activeKey ? "current" : "");
      const verdict = entry?.verdict || "wait";
      const state = textNode("td", "");
      state.append(textNode("span", GLIVE_VERDICTS[verdict] || verdict, `verdict ${verdict}`));
      row.append(textNode("td", gliveVoiceName(voice)), textNode("td", gliveLanguage(language)),
        textNode("td", entry ? entry.audio ? `예 · ${entry.audioSeconds.toFixed(1)}초` : "아니요" : "—"),
        textNode("td", entry?.hangul == null ? "—" : `${Math.round(entry.hangul * 100)}%`), state,
        textNode("td", entry?.at ? new Date(entry.at).toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"));
      return row;
    }));
  }
  // The combination's verdict covers both lanes of the latest session that used it.
  function recordCombo(session) {
    const cards = [...session.lanes.values()];
    const spoken = cards.map((card) => card.assistantText).join(" ");
    const audioBytes = cards.reduce((total, card) => total + card.audio.total, 0);
    if (!audioBytes && !spoken.trim()) return;
    const hangul = hangulRatio(spoken);
    const verdict = !audioBytes ? "silent" : hangul == null ? "run" : ({ ok: "ok", warn: "warn", bad: "bad" })[hangulState(hangul)];
    combos[`${session.voice}|${session.language}`] = {
      audio: audioBytes > 0, audioSeconds: audioBytes / 48000, hangul, verdict, at: new Date().toISOString(),
    };
    saveCombos(combos);
    renderCombos();
  }

  function laneCard(session, provider) {
    const element = textNode("article", "", `card lane ${provider}`);
    element.dataset.provider = provider;
    const head = textNode("header", "", "lane-head");
    const state = textNode("span", "대기", "state");
    const latency = textNode("span", "", "lane-latency");
    head.append(textNode("b", providerNames[provider]), chip("GPT-Live 음성", "chip live"), latency, state);
    const body = textNode("div", "", "lane-body");
    const timeline = textNode("ol", "", "tl");
    timeline.setAttribute("aria-label", `${providerNames[provider]} GPT-Live 진행 단계`);
    const steps = new Map();
    for (const [key, label] of GLIVE_STEPS) {
      const item = textNode("li", "");
      item.dataset.step = key;
      const dot = textNode("span", "", "dot");
      dot.setAttribute("aria-hidden", "true");
      const detail = textNode("small", "");
      item.append(dot, textNode("b", label), detail);
      timeline.append(item);
      steps.set(key, { item, detail });
    }
    const convo = textNode("div", "", "convo");
    convo.setAttribute("aria-label", "대화 전사");
    const empty = textNode("p", "말하면 사용자와 GPT-Live의 전사가 여기에 표시됩니다.", "muted");
    convo.append(empty);
    const delegations = textNode("div", "", "delegations");
    const checks = textNode("ul", "", "checks");
    const diag = textNode("section", "", "lane-diag");
    diag.append(textNode("h3", "한국어 음성 진단", "section-title"), checks);
    const player = textNode("div", "", "player");
    const replay = textNode("button", "다시 듣기", "btn sm");
    replay.type = "button";
    replay.disabled = true;
    const length = textNode("span", "음성 없음", "muted");
    player.append(replay, length);
    body.append(timeline, convo, delegations, diag, player);
    element.append(head, body);
    const card = {
      session, provider, element, state, latency, steps, convo, empty, delegations, checks, replay, length,
      bubbles: [], open: { user: null, assistant: null }, assistantText: "", info: null,
      delegationCards: new Map(), created: 0, delivered: 0, failed: 0, errors: [], closed: null, usage: null,
      cycle: null, audio: { chunks: [], bytes: 0, total: 0 }, playing: false,
    };
    replay.addEventListener("click", () => onReplay(card));
    step(card, "listen", "active", "");
    diagnose(card);
    return card;
  }
  function step(card, key, state, detail) {
    const { item, detail: node } = card.steps.get(key);
    item.dataset.state = state;
    item.className = state;
    if (detail !== undefined) node.textContent = detail;
  }

  function bubbleFor(card, role, startMs) {
    const open = card.open[role];
    const last = card.bubbles.at(-1);
    const joins = open && (startMs != null && open.endMs != null ? startMs - open.endMs < GLIVE_BUBBLE_GAP_MS : last === open);
    if (joins) return open;
    card.empty.hidden = true;
    const node = textNode("div", "", `bubble ${role === "user" ? "user" : "ai"}`);
    const text = textNode("span", "");
    const note = textNode("small", "");
    note.hidden = true;
    node.append(text, note);
    const bubble = { role, node, text, note, value: "", startMs, endMs: null, overlap: false, answer: false };
    if (role === "assistant" && card.cycle?.deliveredAt && !card.cycle.answered) {
      bubble.answer = true;
      card.cycle.answered = true;
    }
    card.bubbles.push(bubble);
    card.open[role] = bubble;
    card.convo.append(node);
    return bubble;
  }
  // Assistant speech that starts before the user's open utterance ends overlaps it; a short one reads as a backchannel.
  function classify(card, bubble) {
    if (bubble.role !== "assistant") return;
    const user = card.open.user;
    bubble.overlap = Boolean(user && bubble.startMs != null && user.endMs != null && bubble.startMs < user.endMs);
    const back = bubble.overlap && !bubble.answer && bubble.value.trim().length <= GLIVE_BACKCHANNEL_CHARS;
    bubble.node.className = `bubble ${back ? "back" : "ai"}`;
    const note = bubble.answer ? "검색 결과로 답변" : back ? "맞장구 · 사용자 발화와 겹침" : bubble.overlap ? "사용자 발화와 겹침" : "";
    bubble.note.textContent = note;
    bubble.note.className = bubble.overlap ? "overlap" : "";
    bubble.note.hidden = !note;
  }
  function transcript(card, event) {
    const role = event.role === "user" ? "user" : event.role === "assistant" ? "assistant" : null;
    if (!role || typeof event.delta !== "string" || !event.delta) return;
    const startMs = gliveNumber(event.start_ms);
    const endMs = gliveNumber(event.end_ms);
    const bubble = bubbleFor(card, role, startMs);
    const fresh = !bubble.value;
    bubble.value += event.delta;
    bubble.text.textContent = bubble.value;
    if (endMs != null) bubble.endMs = Math.max(bubble.endMs ?? endMs, endMs);
    else if (startMs != null) bubble.endMs = Math.max(bubble.endMs ?? startMs, startMs);
    if (role === "user") {
      // A new utterance starts a new cycle; later words of the same utterance only move its end.
      if (fresh || !card.cycle) {
        card.cycle = { userAt: Date.now(), userEndMs: bubble.endMs, firstAudioAt: null, answerAudioAt: null };
        for (const key of ["delegate", "search", "deliver", "speak"]) step(card, key, "", "");
      } else {
        card.cycle.userEndMs = bubble.endMs;
        if (!card.cycle.firstAudioAt && !card.cycle.delegatedAt) card.cycle.userAt = Date.now();
      }
      step(card, "listen", "done", "말하는 중에도");
      for (const item of card.bubbles) classify(card, item);
    } else {
      card.assistantText += event.delta;
      classify(card, bubble);
      if (card.cycle?.deliveredAt) step(card, "speak", "active", "");
    }
    diagnose(card);
    follow();
  }

  function delegation(card, event) {
    if (typeof event.id !== "string" || !event.id) return;
    const now = Date.now();
    let entry = card.delegationCards.get(event.id);
    if (!entry) {
      const node = textNode("div", "", "delegate");
      const title = textNode("h3", `${providerNames[card.provider]} Agent에 맡긴 검색`, "section-title");
      const elapsed = textNode("small", "검색 중…");
      title.append(elapsed);
      const request = textNode("p", "");
      const answer = textNode("p", "", "muted");
      answer.hidden = true;
      const sources = textNode("div", "", "sources");
      sources.hidden = true;
      node.append(title, request, answer, sources);
      card.delegations.append(node);
      entry = { node, elapsed, request, answer, sources, createdAt: now, completedAt: null, status: "created" };
      card.delegationCards.set(event.id, entry);
    }
    card.cycle ??= { userAt: null, userEndMs: null, firstAudioAt: null, answerAudioAt: null };
    if (event.status === "created") {
      card.created += 1;
      const request = typeof event.request === "string" ? event.request : "";
      entry.request.textContent = request ? `요청 “${request}”` : "요청 내용을 확인하지 못했습니다";
      const offset = gliveNumber(event.offset_ms);
      const wait = offset != null && card.cycle.userEndMs != null ? offset - card.cycle.userEndMs : null;
      card.cycle.delegatedAt = now;
      step(card, "listen", "done", "말하는 중에도");
      step(card, "delegate", "done", wait != null && wait >= 0 && wait < 60000 ? gliveSeconds(wait) : "");
      step(card, "search", "active", `${providerNames[card.provider]} 검색 중`);
      step(card, "deliver", "", "");
      step(card, "speak", "", "");
    } else if (event.status === "completed") {
      entry.status = "completed";
      entry.completedAt = now;
      card.cycle.completedAt = now;
      const elapsed = gliveNumber(event.elapsed_ms);
      entry.elapsed.textContent = gliveSeconds(elapsed);
      const spoken = typeof event.spoken === "string" && event.spoken ? event.spoken : typeof event.answer === "string" ? event.answer : "";
      entry.answer.textContent = spoken ? `답변 “${spoken.length > 160 ? `${spoken.slice(0, 160)}…` : spoken}”` : "";
      entry.answer.hidden = !spoken;
      const links = (Array.isArray(event.citations) ? event.citations : [])
        .map((item) => ({ url: safeSourceUrl(item?.url), title: typeof item?.title === "string" ? item.title : "" }))
        .filter((item) => item.url).slice(0, 4);
      entry.sources.replaceChildren(...links.map((item) => sourceLink(item.url, item.title || item.url.hostname)));
      entry.sources.hidden = !links.length;
      step(card, "search", "done", `${providerNames[card.provider]} ${gliveSeconds(elapsed)}`);
      step(card, "deliver", "active", "");
    } else if (event.status === "failed") {
      entry.status = "failed";
      card.failed += 1;
      entry.elapsed.textContent = `실패 · ${gliveSeconds(gliveNumber(event.elapsed_ms))}`;
      entry.answer.textContent = typeof event.message === "string" ? event.message : "Agent 검색을 완료하지 못했습니다.";
      entry.answer.hidden = false;
      entry.node.dataset.state = "failed";
      step(card, "search", "failed", "실패");
    } else if (event.status === "delivered") {
      card.delivered += 1;
      card.cycle.deliveredAt = now;
      card.cycle.answered = false;
      step(card, "deliver", "done", entry.completedAt ? gliveSeconds(now - entry.completedAt) : "");
      step(card, "speak", "active", "");
    }
    diagnose(card);
    follow();
  }

  function latency(card) {
    const cycle = card.cycle;
    const parts = [];
    if (cycle?.userAt && cycle.firstAudioAt) parts.push(`첫 반응 ${gliveSeconds(cycle.firstAudioAt - cycle.userAt)}`);
    if (cycle?.userAt && cycle.answerAudioAt) parts.push(`검색 답변 ${gliveSeconds(cycle.answerAudioAt - cycle.userAt)}`);
    card.latency.textContent = parts.join(" · ");
    card.latency.hidden = !parts.length;
  }
  function diagnose(card) {
    const rows = [];
    const info = card.info;
    const requested = card.session.voice;
    if (info) {
      const voiceMatches = !info.voice || info.voice === requested;
      rows.push({
        state: voiceMatches ? "ok" : "warn",
        text: voiceMatches ? `세션 시작 · 음성 ${gliveVoiceName(info.voice || requested)} · ${gliveLanguage(info.language)}`
          : `요청한 음성(${gliveVoiceName(requested)})과 다른 음성(${gliveVoiceName(info.voice)})으로 시작`,
        value: info.model || "",
      });
    } else rows.push({ state: "info", text: "세션 시작 대기", value: "" });
    const seconds = card.audio.total / 48000;
    rows.push(card.audio.total
      ? { state: "ok", text: "출력 음성 수신 · 24kHz PCM16", value: `${seconds.toFixed(1)}초` }
      : card.assistantText.trim()
        ? { state: "bad", text: "답변 전사는 있지만 음성이 오지 않음", value: "음성 없음" }
        : { state: "info", text: "출력 음성 수신", value: "아직 없음" });
    const ratio = hangulRatio(card.assistantText);
    rows.push({ state: hangulState(ratio), text: "답변 전사의 한글 비율", value: ratio == null ? "—" : `${Math.round(ratio * 100)}%` });
    rows.push({
      state: card.failed ? "warn" : card.delivered ? "ok" : "info",
      text: `검색 위임 ${card.created}회 · 결과 전달 ${card.delivered}회`,
      value: card.failed ? `실패 ${card.failed}회` : card.created ? "오류 없음" : "",
    });
    for (const message of card.errors.slice(-3)) rows.push({ state: "warn", text: message, value: "" });
    if (card.closed) rows.push({ state: "info", text: `세션 종료${card.closed.reason ? ` · ${card.closed.reason}` : ""}`, value: card.closed.seconds != null ? `${card.closed.seconds.toFixed(0)}초 사용` : "" });
    card.checks.replaceChildren(...rows.map((row) => {
      const item = textNode("li", "", "check");
      item.dataset.state = row.state;
      const icon = textNode("span", row.state === "ok" ? "✓" : row.state === "bad" ? "✕" : row.state === "warn" ? "!" : "·", "ic");
      icon.setAttribute("aria-hidden", "true");
      item.append(icon, textNode("span", row.text), textNode("em", row.value));
      return item;
    }));
    card.length.textContent = card.audio.total ? `음성 ${seconds.toFixed(1)}초${card.audio.total > card.audio.bytes ? " · 최근 부분만 다시 듣기" : ""}` : "음성 없음";
    card.replay.disabled = !card.audio.bytes;
    card.replay.textContent = card.playing ? "멈추기" : "다시 듣기";
    card.replay.setAttribute("aria-pressed", String(card.playing));
    latency(card);
    recordCombo(card.session);
  }

  return {
    hasTurns: () => sessions.length > 0,
    // One session card per connection; GPT-Live fixes the voice and instructions when the session starts.
    start({ values, deployment, providers }) {
      if (!comboBody) board.append(comboCard());
      board.hidden = false;
      const session = {
        voice: values.live_voice || "noeul", language: values.live_language || "korean",
        backchannel: values.live_backchannel || "sometimes", lanes: new Map(),
      };
      const element = textNode("section", "", "live-session");
      element.dataset.session = String(sessions.length + 1);
      const head = textNode("div", "", "card q-card");
      const chips = textNode("div", "", "chips");
      chips.append(chip(`음성 ${gliveVoiceName(session.voice)}`, "chip live"), chip(gliveLanguage(session.language)),
        chip(Object.hasOwn(GLIVE_BACKCHANNELS, session.backchannel) ? GLIVE_BACKCHANNELS[session.backchannel] : session.backchannel));
      if (deployment) chips.append(chip(deployment));
      head.append(textNode("span", `S${sessions.length + 1}`, "q-badge"),
        textNode("p", "GPT-Live 음성 세션 · 말하는 중에도 끼어들 수 있습니다", "q-text"), chips);
      const lanes = textNode("div", "", "lanes");
      session.element = element;
      sessions.push(session);
      for (const provider of providers) {
        const card = laneCard(session, provider);
        session.lanes.set(provider, card);
        lanes.append(card.element);
      }
      element.append(head, lanes);
      board.append(element);
      renderCombos();
      following = true;
      follow();
      return session;
    },
    live(lane, event) {
      const card = cardFor(lane.provider);
      if (!card) return;
      if (event.type === "live_session") {
        card.info = {
          model: typeof event.model === "string" ? event.model : "", voice: typeof event.voice === "string" ? event.voice : "",
          language: typeof event.language === "string" ? event.language : card.session.language,
        };
        diagnose(card);
      } else if (event.type === "live_transcript") transcript(card, event);
      else if (event.type === "delegation") delegation(card, event);
      else if (event.type === "live_usage") card.usage = gliveNumber(event.seconds);
      else if (event.type === "live_closed") {
        card.closed = { reason: typeof event.reason === "string" ? event.reason : "", seconds: gliveNumber(event.seconds) };
        diagnose(card);
      } else if (event.type === "error") {
        card.errors.push(typeof event.message === "string" && event.message ? event.message : "GPT-Live 서비스 오류가 발생했습니다.");
        diagnose(card);
      }
    },
    audio(lane, event, bytes) {
      const card = cardFor(lane.provider);
      if (!card) return;
      const now = Date.now();
      let changed = !card.audio.total;
      // The session can run for minutes; replay keeps the most recent audio.
      card.audio.total += bytes.byteLength;
      card.audio.chunks.push(bytes);
      card.audio.bytes += bytes.byteLength;
      while (card.audio.bytes > GLIVE_MAX_AUDIO_BYTES && card.audio.chunks.length > 1) {
        card.audio.bytes -= card.audio.chunks.shift().byteLength;
      }
      if (card.cycle?.userAt) {
        if (!card.cycle.firstAudioAt) {
          card.cycle.firstAudioAt = now;
          changed = true;
        }
        if (card.cycle.deliveredAt && !card.cycle.answerAudioAt) {
          card.cycle.answerAudioAt = now;
          step(card, "speak", "done", gliveSeconds(now - card.cycle.userAt));
          changed = true;
        }
      }
      if (changed) diagnose(card);
      else {
        card.length.textContent = `음성 ${(card.audio.total / 48000).toFixed(1)}초`;
        card.replay.disabled = false;
      }
    },
    laneStatus(provider, state, text) {
      compareView.laneStatus(provider, state, text);
      const card = cardFor(provider);
      if (!card) return;
      card.state.textContent = text;
      card.element.dataset.state = state;
    },
    setLive: (provider) => compareView.setLive(provider),
    fail(provider, message) {
      const card = cardFor(provider);
      if (!card || card.closed) return;
      card.errors.push(message);
      card.closed = { reason: "", seconds: card.usage };
      diagnose(card);
    },
    closed(provider) {
      const card = cardFor(provider);
      if (!card) return;
      for (const [key, { item }] of card.steps) if (item.dataset.state === "active") step(card, key, "", undefined);
      diagnose(card);
    },
    replayState(card, playing) {
      card.playing = playing;
      card.replay.textContent = playing ? "멈추기" : "다시 듣기";
      card.replay.setAttribute("aria-pressed", String(playing));
    },
    submitted() {},
    busy() {},
    stalled() {},
    reset() {
      sessions.length = 0;
      comboBody = null;
      board.replaceChildren();
      board.hidden = true;
      following = true;
    },
  };
}
