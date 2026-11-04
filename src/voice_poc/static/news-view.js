import { textNode, isRecord, shortText, toolOutput, safeSourceUrl, sourceLink } from "./search-results.js";
import { createCompareView } from "./compare-view.js";

export const NEWS_DEFAULT_OPTIONS = Object.freeze({ freshness: "day", count: 5, length: "60s", cite: true, group_events: true });
export const NEWS_OPTION_FIELDS = [
  { key: "freshness", label: "기사 기간", options: [["day", "최근 24시간"], ["week", "최근 7일"], ["any", "기간 제한 없음"]] },
  { key: "count", label: "브리핑 기사 수", options: [[3, "3건"], [5, "5건"], [10, "10건"]] },
  { key: "length", label: "답변 길이", options: [["30s", "30초 이내"], ["60s", "1분 이내"], ["free", "제한 없음"]] },
  { key: "cite", label: "언론사·게시 시각 말하기", options: [[true, "말하기"], [false, "생략"]] },
  { key: "group_events", label: "같은 사건 기사 묶기", options: [[true, "묶기"], [false, "따로"]] },
];
export const NEWS_SCENARIOS = [
  {
    title: "헤드라인 브리핑",
    desc: "주요 뉴스 몇 건을 1분 안에 듣는 상황입니다. 기존 뉴스 공급사의 헤드라인 낭독을 대체할 수 있는지 봅니다.",
    crit: ["최신성", "분야 다양성", "답변 길이", "출처 말하기"],
    questions: ["오늘 주요 뉴스 브리핑해줘", "아침 뉴스 1분 요약해줘", "지금 가장 많이 보도되는 뉴스 뭐야?"],
  },
  {
    title: "분야별 뉴스",
    desc: "경제·IT·스포츠처럼 분야를 지정해 묻습니다. 요청한 분야의 최신 기사를 요청한 수만큼 고르는지 봅니다.",
    crit: ["분야 일치", "최신성", "기사 수 지키기"],
    questions: ["오늘 경제 뉴스 3개 알려줘", "IT·AI 최신 소식 알려줘", "어젯밤 프로야구 결과 기사 알려줘"],
  },
  {
    title: "관심 주제 추적",
    desc: "특정 주제를 기간과 함께 묻습니다. 주제에 맞는 기사를 기간 안에서 여러 언론사로 찾는지 봅니다.",
    crit: ["주제 일치", "기간 지키기", "언론사 다양성"],
    questions: ["지난 일주일 전기차 보조금 기사 찾아줘", "반도체 수출 관련 최신 소식 있어?", "이번 달 유가 전망 기사 알려줘"],
  },
  {
    title: "경로·지역 소식",
    desc: "이동할 지역이나 도로의 소식을 묻습니다. 지역에 맞고 이동에 도움이 되는 기사를 고르는지 봅니다.",
    crit: ["지역 일치", "최신성", "이동 관련성"],
    questions: ["부산 가는 길에 경부고속도로 관련 소식 있어?", "오늘 서울 도심 교통 통제 기사 알려줘", "강릉 이번 주말 축제 소식 있어?"],
  },
  {
    title: "속보·방금 발표",
    desc: "방금 나온 소식을 묻습니다. 게시 시각을 확인하고, 발표 전 예상 기사와 발표 결과 기사를 구분하는지 봅니다.",
    crit: ["1시간 이내", "게시 시각", "예상·결과 구분"],
    questions: ["지금 속보 있어?", "오늘 기준금리 결정 결과 나왔어?", "방금 발표된 정부 발표 내용 알려줘"],
  },
  {
    title: "이어지는 대화",
    desc: "브리핑을 들은 뒤 이어서 묻습니다. 앞 답변의 기사를 기억하고 같은 기사를 다시 찾는지 봅니다.",
    crit: ["문맥 유지", "같은 기사 찾기", "언론사 비교"],
    questions: ["방금 두 번째 기사 더 자세히", "그 뉴스 다른 언론사는 뭐라고 해?", "그거 언제부터 시행된대?"],
    seed: "오늘 주요 뉴스 브리핑해줘",
  },
];
export const NEWS_QUESTION_TOTAL = NEWS_SCENARIOS.reduce((total, scenario) => total + scenario.questions.length, 0);
const NEWS_RECORDS_KEY = "voice-poc.news.v1";
const NEWS_WINDOW_MINUTES = { day: 1440, week: 10080, any: null };
const NEWS_TARGET_SECONDS = { "30s": 30, "60s": 60, free: null };
const NEWS_WINDOW_LABELS = { day: "24시간", week: "7일", any: "" };
// The service streams 24 kHz, 16-bit mono audio.
const NEWS_AUDIO_BYTES_PER_SECOND = 48000;
export const NEWS_RATINGS = {
  accuracy: { label: "기사 내용과 일치", options: [["match", "일치"], ["partial", "일부 다름"], ["wrong", "틀림"]] },
  length: { label: "듣기 길이", options: [["ok", "적당"], ["long", "너무 김"], ["short", "너무 짧음"]] },
};
const NEWS_DONE = new Set(["done", "failed", "interrupted", "offline"]);
export const newsScenarioNumber = (index) => "①②③④⑤⑥⑦⑧⑨"[index] || String(index + 1);
const newsNormalize = (text) => String(text || "").replace(/[\s.,!?·~]/g, "");
const newsFilled = (value) => typeof value === "string" && value.trim();

export function newsAge(minutes) {
  if (minutes == null || !Number.isFinite(minutes)) return "—";
  if (minutes < 1) return "방금";
  if (minutes < 60) return `${Math.round(minutes)}분 전`;
  if (minutes < 1440) return `${Math.round(minutes / 60)}시간 전`;
  return `${Math.round(minutes / 1440)}일 전`;
}
export const newsSeconds = (ms) => ms == null || !Number.isFinite(ms) ? "—" : `${(Math.max(0, ms) / 1000).toFixed(1)}초`;

function newsStorage() {
  try { return window.localStorage || null; } catch { return null; }
}
export function loadNewsRecords() {
  try {
    const parsed = JSON.parse(newsStorage()?.getItem(NEWS_RECORDS_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter(isRecord) : [];
  } catch { return []; }
}
export function saveNewsRecords(records) {
  try { newsStorage()?.setItem(NEWS_RECORDS_KEY, JSON.stringify(records.slice(-300))); } catch { /* Storage is optional. */ }
}
// The latest finished record for every scenario question; free questions are not part of the progress.
export function latestNewsRecords(records = loadNewsRecords()) {
  const latest = new Map();
  for (const record of records) {
    if (!Number.isInteger(record.scenario) || !Number.isInteger(record.q) || record.status !== "done") continue;
    latest.set(`${record.scenario}:${record.q}`, record);
  }
  return latest;
}

function newsProviderName(item, url) {
  const value = item.provider ?? item.source ?? item.publisher ?? item.siteName;
  const names = (Array.isArray(value) ? value : [value]).map((entry) => isRecord(entry) ? entry.name : entry).filter(newsFilled);
  return names[0]?.trim() || url?.hostname.replace(/^www\./, "") || "";
}
function newsPublished(item) {
  for (const key of ["datePublished", "publishedAt", "published", "date", "pubDate"]) {
    if (typeof item[key] !== "string" && typeof item[key] !== "number") continue;
    const date = new Date(item[key]);
    if (!Number.isNaN(date.getTime())) return date;
  }
  return null;
}
export function newsArticles(cell) {
  const list = [], seen = new Set();
  for (const entry of cell.calls.values()) {
    if (entry.output === undefined || entry.kind === "foundry_agent_call") continue;
    for (const { item } of toolOutput(entry.output).results) {
      if (!isRecord(item)) continue;
      const url = safeSourceUrl(item.url);
      const title = [item.title, item.name, item.headline].find(newsFilled)?.trim();
      if (!title) continue;
      const key = url?.href || title;
      if (seen.has(key)) continue;
      seen.add(key);
      list.push({ title, url, provider: newsProviderName(item, url), published: newsPublished(item),
        category: newsFilled(item.category) ? item.category.trim() : "" });
    }
  }
  return list;
}
// Rough, automatic signals only. People still judge whether the briefing matches the articles.
export function newsMeasure(cell, info, options) {
  const articles = newsArticles(cell);
  const now = cell.doneAt || Date.now();
  const ages = articles.map((article) => article.published ? (now - article.published.getTime()) / 60000 : null)
    .filter((age) => age != null && age > -60).map((age) => Math.max(0, age));
  const providers = [...new Set(articles.map((article) => article.provider).filter(Boolean))];
  const categories = new Set(articles.map((article) => article.category).filter(Boolean));
  const windowMinutes = NEWS_WINDOW_MINUTES[options.freshness] ?? null;
  const answer = info.answer || "";
  const calls = [...cell.calls.values()];
  const starts = calls.map((entry) => entry.startedAt).filter((time) => time != null);
  const ends = calls.map((entry) => entry.settledAt).filter((time) => time != null);
  return {
    articles: articles.length,
    providers: providers.length,
    categories: categories.size,
    dated: ages.length,
    newestMinutes: ages.length ? Math.min(...ages) : null,
    withinCount: windowMinutes ? ages.filter((age) => age <= windowMinutes).length : null,
    within: windowMinutes && ages.length ? ages.filter((age) => age <= windowMinutes).length / ages.length : null,
    mentioned: providers.filter((name) => answer.includes(name)).length,
    timeMentioned: /\d+\s*(분|시간)\s*전|방금|오늘\s*(오전|오후|아침|새벽)?\s*\d{1,2}시|\d{1,2}시\s*\d{0,2}분?에?\s*(보도|발표|게시)/.test(answer),
    answerSeconds: cell.audio.total ? cell.audio.total / NEWS_AUDIO_BYTES_PER_SECOND : null,
    firstAudioMs: info.answerAt != null && cell.startedAt != null ? info.answerAt - cell.startedAt : null,
    searchMs: starts.length && ends.length ? Math.max(...ends) - Math.min(...starts) : null,
    answerChars: answer.length,
  };
}
export function newsChecks(metrics, options) {
  const checks = [];
  const period = NEWS_WINDOW_LABELS[options.freshness];
  if (!period) checks.push({ state: "info", text: "기사 기간 제한 없음", value: `날짜 확인 ${metrics.dated}건` });
  else if (!metrics.dated) checks.push({ state: metrics.articles ? "warn" : "bad", text: `${period} 이내 기사`, value: "게시 시각 없음" });
  else {
    const ratio = metrics.within ?? 0;
    checks.push({ state: ratio === 1 ? "ok" : ratio >= 0.8 ? "warn" : "bad", text: `${period} 이내 기사`, value: `${metrics.withinCount}/${metrics.dated}` });
  }
  checks.push({ state: metrics.articles >= options.count ? "ok" : metrics.articles ? "warn" : "bad",
    text: "받은 기사 수", value: `${metrics.articles}건 / 요청 ${options.count}건` });
  if (options.cite) {
    const both = metrics.mentioned > 0 && metrics.timeMentioned;
    checks.push({ state: both ? "ok" : metrics.mentioned > 0 || metrics.timeMentioned ? "warn" : "bad",
      text: "언론사와 게시 시각을 말함", value: `언론사 ${metrics.mentioned}곳 · 시각 ${metrics.timeMentioned ? "있음" : "없음"}` });
  } else checks.push({ state: "info", text: "언론사·게시 시각 말하기", value: "생략 설정" });
  const target = NEWS_TARGET_SECONDS[options.length] ?? null;
  if (metrics.answerSeconds == null) checks.push({ state: "info", text: "답변 길이", value: "음성 없음" });
  else {
    const spoken = `${Math.round(metrics.answerSeconds)}초`;
    checks.push(target ? {
      state: metrics.answerSeconds <= target ? "ok" : metrics.answerSeconds <= target * 1.25 ? "warn" : "bad",
      text: "답변 길이 목표 이내", value: `${spoken} / ${target}초`,
    } : { state: "info", text: "답변 길이", value: spoken });
  }
  checks.push({ state: "info", text: "언론사·분야", value: `${metrics.providers}곳 · ${metrics.categories}개 분야` });
  return checks;
}

export function createNewsView({ onReplay, onPick, onRun, onRunAll, onRecords, options }) {
  const get = (id) => document.getElementById(id);
  const clock = new Intl.DateTimeFormat("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
  let selected = 0;
  let pendingMeta = null;
  let records = loadNewsRecords();
  const inner = createCompareView({
    onReplay, providers: ["webiq"], scrollId: "news-scroll", listId: "news-turns", onTurn: attach, onUpdate: update,
  });

  function attach(turn) {
    const meta = pendingMeta || { scenario: selected, q: null };
    turn.news = { ...meta, id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`,
      options: { ...options() }, recorded: false, outputs: -1, rating: { accuracy: null, length: null } };
    turn.element.dataset.news = "true";
    const badge = textNode("span", "", "turn-scenario");
    turn.head.append(badge);
    const brief = textNode("section", "", "brief");
    brief.setAttribute("aria-label", "뉴스 브리핑 점검");
    const metrics = textNode("div", "", "brief-metrics");
    const articlesPanel = textNode("section", "", "panel brief-articles");
    const articlesTitle = textNode("h3", "WebIQ 뉴스 검색", "section-title");
    const articlesCount = textNode("small", "검색 대기");
    articlesTitle.append(articlesCount);
    const articleList = textNode("ol", "", "arts");
    articlesPanel.append(articlesTitle, articleList);
    const checksPanel = textNode("section", "", "panel brief-checks");
    const checksTitle = textNode("h3", "자동 점검", "section-title");
    checksTitle.append(textNode("small", "참고용 · 사람 평가가 최종"));
    const checkList = textNode("ul", "", "checks");
    checkList.append(textNode("li", "답변이 끝나면 점검합니다.", "check-wait"));
    const rateTitle = textNode("h3", "사람 평가", "section-title");
    checksPanel.append(checksTitle, checkList, rateTitle);
    const rateButtons = new Map();
    for (const [key, { label, options: choices }] of Object.entries(NEWS_RATINGS)) {
      const row = textNode("div", "", "rate-row");
      const name = textNode("span", label);
      name.id = `${turn.news.id}-${key}-label`;
      const seg = textNode("div", "", "seg");
      seg.setAttribute("role", "radiogroup");
      seg.setAttribute("aria-labelledby", name.id);
      const buttons = choices.map(([value, text]) => {
        const button = textNode("button", text);
        button.type = "button";
        button.setAttribute("role", "radio");
        button.setAttribute("aria-checked", "false");
        button.id = `${turn.news.id}-${key}-${value}`;
        button.addEventListener("click", () => rate(turn, key, value));
        seg.append(button);
        return { button, value };
      });
      rateButtons.set(key, buttons);
      row.append(name, seg);
      checksPanel.append(row);
    }
    const grid = textNode("div", "", "brief-grid");
    grid.append(articlesPanel, checksPanel);
    brief.append(metrics, grid);
    turn.element.append(brief);
    turn.brief = { badge, brief, metrics, articleList, articlesCount, checkList, rateButtons };
    describe(turn);
    syncRating(turn);
    get("news-empty").hidden = true;
  }
  function describe(turn) {
    const scenario = NEWS_SCENARIOS[turn.news.scenario];
    turn.brief.badge.textContent = scenario
      ? `${newsScenarioNumber(turn.news.scenario)} ${scenario.title}${turn.news.q != null ? ` · 문항 ${turn.news.q + 1}` : turn.news.seed ? " · 앞선 브리핑" : " · 자유 질문"}`
      : "자유 질문";
  }
  function matchQuestion(text, scenarioIndex = null) {
    const wanted = newsNormalize(text);
    const order = scenarioIndex == null ? NEWS_SCENARIOS.map((_, index) => index)
      : [scenarioIndex, ...NEWS_SCENARIOS.map((_, index) => index).filter((index) => index !== scenarioIndex)];
    for (const index of order) {
      const q = NEWS_SCENARIOS[index].questions.findIndex((question) => newsNormalize(question) === wanted);
      if (q >= 0) return { scenario: index, q };
    }
    return null;
  }
  function chip(text, className = "") {
    return textNode("span", text, `chip${className ? ` ${className}` : ""}`);
  }
  function update(cell, info) {
    const turn = cell.turn;
    if (!turn.news) return;
    if (turn.news.q == null && !turn.news.seed && !turn.news.recorded && turn.question) {
      const match = matchQuestion(turn.question, turn.news.scenario);
      if (match && match.scenario === turn.news.scenario) { turn.news.q = match.q; describe(turn); }
    }
    const outputs = [...cell.calls.values()].filter((entry) => entry.output !== undefined).length;
    const finished = NEWS_DONE.has(cell.status);
    if (outputs !== turn.news.outputs) {
      turn.news.outputs = outputs;
      renderArticles(turn, cell);
    }
    if (!finished || turn.news.recorded) return;
    turn.news.recorded = true;
    const metrics = newsMeasure(cell, info, turn.news.options);
    const checks = newsChecks(metrics, turn.news.options);
    turn.brief.metrics.replaceChildren(
      chip(`기사 ${metrics.articles}건`), chip(`언론사 ${metrics.providers}곳`), chip(`분야 ${metrics.categories}개`),
      chip(`가장 최신 ${newsAge(metrics.newestMinutes)}`),
      ...(metrics.within != null ? [chip(`기간 이내 ${Math.round(metrics.within * 100)}%`)] : []),
      chip(`답변 음성 ${metrics.answerSeconds != null ? `${Math.round(metrics.answerSeconds)}초` : "없음"}`),
      chip(`응답 시작 ${newsSeconds(metrics.firstAudioMs)}`), chip(`검색 ${newsSeconds(metrics.searchMs)}`));
    turn.brief.checkList.replaceChildren(...checks.map((check) => {
      const item = textNode("li", "", "check");
      item.dataset.state = check.state;
      const icon = textNode("span", { ok: "✓", warn: "!", bad: "✕", info: "i" }[check.state], "ic");
      icon.setAttribute("aria-hidden", "true");
      item.append(icon, textNode("span", check.text), textNode("em", check.value));
      return item;
    }));
    const record = {
      id: turn.news.id, scenario: turn.news.scenario, q: turn.news.q, seed: Boolean(turn.news.seed),
      question: turn.question || cell.input.text || "", at: new Date().toISOString(),
      status: cell.status === "done" ? "done" : cell.status, options: turn.news.options, metrics,
      checks: checks.map(({ state, text, value }) => ({ state, text, value })),
      answer: shortText(info.answer || "", 600), rating: { ...turn.news.rating },
    };
    records = [...records.filter((item) => item.id !== record.id), record];
    saveNewsRecords(records);
    refresh();
    onRecords?.();
  }
  function renderArticles(turn, cell) {
    const articles = newsArticles(cell);
    const now = Date.now();
    turn.brief.articlesCount.textContent = turn.news.outputs ? `${articles.length}건 받음` : "검색 대기";
    turn.brief.articleList.replaceChildren(...articles.slice(0, 10).map((article, index) => {
      const item = textNode("li", "", "art");
      const minutes = article.published ? Math.max(0, (now - article.published.getTime()) / 60000) : null;
      const limit = NEWS_WINDOW_MINUTES[turn.news.options.freshness];
      const age = textNode("span", newsAge(minutes), "age");
      if (minutes != null && limit && minutes > limit) age.dataset.old = "true";
      const meta = textNode("span", "", "art-m");
      if (article.category) meta.append(textNode("span", article.category, "cat"));
      meta.append([article.provider, article.published ? clock.format(article.published) : ""].filter(Boolean).join(" · "));
      const title = article.url ? sourceLink(article.url, shortText(article.title, 120)) : textNode("span", shortText(article.title, 120));
      title.className = "art-t";
      item.append(textNode("span", String(index + 1), "art-n"), title, age, meta);
      return item;
    }));
    turn.brief.articleList.hidden = !articles.length;
  }
  function rate(turn, key, value) {
    turn.news.rating[key] = turn.news.rating[key] === value ? null : value;
    syncRating(turn);
    const record = records.find((item) => item.id === turn.news.id);
    if (record) {
      record.rating = { ...turn.news.rating };
      saveNewsRecords(records);
      onRecords?.();
    }
  }
  function syncRating(turn) {
    for (const [key, buttons] of turn.brief.rateButtons) {
      for (const { button, value } of buttons) button.setAttribute("aria-checked", String(turn.news.rating[key] === value));
    }
  }

  function renderRail() {
    const latest = latestNewsRecords(records);
    const done = latest.size;
    get("news-progress-text").textContent = `${done} / ${NEWS_QUESTION_TOTAL}`;
    const bar = get("news-progress-bar");
    if (bar.style) bar.style.width = `${Math.round((done / NEWS_QUESTION_TOTAL) * 100)}%`;
    get("nav-news-count").textContent = done ? `${done}/${NEWS_QUESTION_TOTAL}` : "";
    get("news-scenarios").replaceChildren(...NEWS_SCENARIOS.map((scenario, index) => {
      const count = scenario.questions.filter((_, q) => latest.has(`${index}:${q}`)).length;
      const item = textNode("div", "", "scenario-item");
      item.setAttribute("role", "listitem");
      const button = textNode("button", "", "scenario");
      button.type = "button";
      button.id = `news-scenario-${index}`;
      button.setAttribute("aria-current", String(index === selected));
      button.dataset.state = count === scenario.questions.length ? "done" : count ? "partial" : "todo";
      button.append(textNode("span", newsScenarioNumber(index), "sc-n"), textNode("span", scenario.title, "sc-t"),
        textNode("small", `${count}/${scenario.questions.length}`, "sc-p"));
      button.addEventListener("click", () => select(index));
      item.append(button);
      return item;
    }));
  }
  function renderStage() {
    const scenario = NEWS_SCENARIOS[selected];
    const latest = latestNewsRecords(records);
    get("news-title").textContent = `${newsScenarioNumber(selected)} ${scenario.title}`;
    get("news-desc").textContent = scenario.desc;
    get("news-crit").replaceChildren(...scenario.crit.map((text) => chip(text)));
    get("news-examples").replaceChildren(...scenario.questions.map((question, q) => {
      const button = textNode("button", "", "ex");
      button.type = "button";
      button.id = `news-example-${q}`;
      button.dataset.prompt = question;
      button.dataset.done = String(latest.has(`${selected}:${q}`));
      button.append(textNode("span", `Q${q + 1}`, "ex-n"), question);
      button.addEventListener("click", () => onPick(question));
      return button;
    }));
  }
  function refresh() {
    renderRail();
    renderStage();
  }
  function select(index) {
    if (!Number.isInteger(index) || !NEWS_SCENARIOS[index]) return;
    selected = index;
    refresh();
  }

  get("news-run").addEventListener("click", () => onRun(selected));
  get("news-run-all").addEventListener("click", () => onRunAll());
  refresh();

  return {
    ...inner,
    question(text, meta = null) {
      pendingMeta = meta || matchQuestion(text, selected) || { scenario: selected, q: null };
      try { return inner.question(text); } finally { pendingMeta = null; }
    },
    reset() {
      inner.reset();
      get("news-empty").hidden = false;
    },
    selected: () => selected,
    select,
    refresh,
    reload() {
      records = loadNewsRecords();
      refresh();
    },
    running(active) {
      get("news-run").disabled = active;
      get("news-run-all").disabled = active;
      get("news-run-label").textContent = active ? "실행 중…" : "이 시나리오 실행";
    },
  };
}
