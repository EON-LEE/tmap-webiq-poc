import { textNode } from "./search-results.js";
import { NEWS_SCENARIOS, NEWS_QUESTION_TOTAL, NEWS_RATINGS, loadNewsRecords, saveNewsRecords, latestNewsRecords, newsAge, newsSeconds, newsScenarioNumber } from "./news-view.js";

const SUMMARY_BASELINE_KEY = "voice-poc.news-baseline.v1";
const SUMMARY_BASELINE_FIELDS = [
  ["refresh", "헤드라인 갱신 주기", "예: 30분"],
  ["categories", "제공 분야 수", "예: 8개"],
  ["delay", "게시 → 제공 지연", "예: 10분"],
  ["providers", "제공 언론사 수", "예: 12곳"],
];
const SUMMARY_VERDICTS = { ok: "기준 충족", warn: "보완 필요", rate: "평가 필요", wait: "진행 중" };

const summaryNumbers = (values) => values.filter((value) => typeof value === "number" && Number.isFinite(value));
function summaryMedian(values) {
  const sorted = summaryNumbers(values).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}
function summaryMean(values) {
  const numbers = summaryNumbers(values);
  return numbers.length ? numbers.reduce((total, value) => total + value, 0) / numbers.length : null;
}
const summaryPercent = (value) => value == null ? "—" : `${Math.round(value * 100)}%`;
const summaryCited = (record) => record.metrics?.mentioned > 0 && record.metrics?.timeMentioned;
const summaryRatingLabel = (key, value) => NEWS_RATINGS[key].options.find(([option]) => option === value)?.[1] || "";

function summaryStorage() {
  try { return window.localStorage || null; } catch { return null; }
}
function loadBaseline() {
  try {
    const parsed = JSON.parse(summaryStorage()?.getItem(SUMMARY_BASELINE_KEY) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch { return {}; }
}
function saveBaseline(values) {
  try { summaryStorage()?.setItem(SUMMARY_BASELINE_KEY, JSON.stringify(values)); } catch { /* Storage is optional. */ }
}

// Aggregates the latest result of every scenario question.
export function summarizeNews(records) {
  const latest = latestNewsRecords(records);
  const all = [...latest.values()];
  const citable = all.filter((record) => record.options?.cite !== false);
  const rated = all.filter((record) => record.rating?.accuracy);
  const scenarios = NEWS_SCENARIOS.map((scenario, index) => {
    const rows = scenario.questions.map((_, q) => latest.get(`${index}:${q}`)).filter(Boolean);
    const scored = rows.filter((record) => record.rating?.accuracy);
    const within = summaryMean(rows.map((record) => record.metrics?.within));
    const cited = rows.filter((record) => record.options?.cite !== false);
    const verdict = rows.length < scenario.questions.length ? "wait"
      : scored.some((record) => record.rating.accuracy !== "match") || (within != null && within < 0.8) ? "warn"
        : scored.length < rows.length ? "rate" : "ok";
    return {
      index, title: scenario.title, done: rows.length, total: scenario.questions.length,
      firstAudio: summaryMedian(rows.map((record) => record.metrics?.firstAudioMs)),
      newest: rows.length ? summaryNumbers(rows.map((record) => record.metrics?.newestMinutes)).sort((a, b) => a - b)[0] ?? null : null,
      within, providers: summaryMean(rows.map((record) => record.metrics?.providers)),
      cited: cited.length ? cited.filter(summaryCited).length / cited.length : null,
      passed: scored.filter((record) => record.rating.accuracy === "match").length, rated: scored.length, verdict,
    };
  });
  const notes = [];
  for (const record of all) {
    const scenario = NEWS_SCENARIOS[record.scenario];
    const label = `${newsScenarioNumber(record.scenario)} “${record.question || scenario?.questions[record.q] || ""}”`;
    if (record.rating?.accuracy && record.rating.accuracy !== "match") {
      notes.push({ state: "bad", text: `${label} · 사람 평가 ${summaryRatingLabel("accuracy", record.rating.accuracy)}` });
    }
    for (const check of record.checks || []) {
      if (check.state === "bad" || check.state === "warn") notes.push({ state: check.state, text: `${label} · ${check.text} ${check.value}` });
    }
  }
  return {
    done: latest.size, total: NEWS_QUESTION_TOTAL, free: records.filter((record) => record.q == null).length,
    firstAudio: summaryMedian(all.map((record) => record.metrics?.firstAudioMs)),
    within: summaryMean(all.map((record) => record.metrics?.within)),
    cited: citable.length ? citable.filter(summaryCited).length / citable.length : null,
    passed: rated.filter((record) => record.rating.accuracy === "match").length, rated: rated.length,
    providers: summaryMean(all.map((record) => record.metrics?.providers)),
    scenarios, notes: notes.sort((a, b) => (a.state === "bad" ? 0 : 1) - (b.state === "bad" ? 0 : 1)),
  };
}

const summaryCsvCell = (value) => {
  const text = value == null ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};
export function newsCsv(records) {
  const head = ["시나리오", "문항", "질문", "실행 시각", "상태", "기사 수", "언론사 수", "분야 수", "가장 최신(분 전)", "기간 이내 비율",
    "답변 음성(초)", "응답 시작(초)", "검색(초)", "언급한 언론사 수", "게시 시각 언급", "기사 내용 평가", "듣기 길이 평가"];
  const rows = records.map((record) => {
    const metrics = record.metrics || {};
    const round = (value, digits = 1) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "";
    return [
      NEWS_SCENARIOS[record.scenario]?.title || "", record.q != null ? `Q${record.q + 1}` : record.seed ? "앞선 브리핑" : "자유 질문",
      record.question, record.at, record.status, metrics.articles, metrics.providers, metrics.categories, round(metrics.newestMinutes, 0),
      round(metrics.within, 2), round(metrics.answerSeconds), round(metrics.firstAudioMs != null ? metrics.firstAudioMs / 1000 : null),
      round(metrics.searchMs != null ? metrics.searchMs / 1000 : null), metrics.mentioned, metrics.timeMentioned ? "예" : "아니요",
      summaryRatingLabel("accuracy", record.rating?.accuracy), summaryRatingLabel("length", record.rating?.length),
    ].map(summaryCsvCell).join(",");
  });
  return `\uFEFF${[head.join(","), ...rows].join("\n")}\n`;
}
export function newsReport(records, baseline) {
  const summary = summarizeNews(records);
  const lines = [
    "# WebIQ 뉴스 브리핑 평가 요약", "",
    `- 작성 시각: ${new Date().toLocaleString("ko-KR")}`,
    `- 진행: ${summary.done} / ${summary.total} 문항 (자유 질문 ${summary.free}건 별도)`,
    `- 응답 시작 중앙값: ${newsSeconds(summary.firstAudio)}`,
    `- 기간 이내 기사 비율: ${summaryPercent(summary.within)}`,
    `- 언론사·게시 시각 언급: ${summaryPercent(summary.cited)}`,
    `- 사람 평가 일치: ${summary.passed} / ${summary.rated}`,
    `- 문항당 언론사 수 평균: ${summary.providers == null ? "—" : `${summary.providers.toFixed(1)}곳`}`, "",
    "## 시나리오별 결과", "",
    "| 시나리오 | 문항 | 응답 시작 | 가장 최신 기사 | 기간 이내 | 언론사 | 출처·시각 언급 | 사람 평가 | 판정 |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ...summary.scenarios.map((row) => `| ${newsScenarioNumber(row.index)} ${row.title} | ${row.done}/${row.total} | ${newsSeconds(row.firstAudio)} | ${newsAge(row.newest)} | ${summaryPercent(row.within)} | ${row.providers == null ? "—" : `${row.providers.toFixed(1)}곳`} | ${summaryPercent(row.cited)} | ${row.passed}/${row.rated} | ${SUMMARY_VERDICTS[row.verdict]} |`),
    "", "## 기존 뉴스 공급사 기준값", "",
    ...SUMMARY_BASELINE_FIELDS.map(([key, label]) => `- ${label}: ${baseline[key] || "미입력"}`),
    "", "## 보완이 필요한 문항", "",
    ...(summary.notes.length ? summary.notes.map((note) => `- ${note.text}`) : ["- 없음"]),
    "", "> 자동 점검은 검색 결과와 답변 텍스트로 계산한 참고값입니다. 기사 내용 일치는 사람 평가로 판단합니다.", "",
  ];
  return lines.join("\n");
}

function summaryDownload(name, text, type) {
  if (typeof Blob !== "function" || typeof URL?.createObjectURL !== "function") return false;
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove?.();
  setTimeout(() => URL.revokeObjectURL?.(url), 1000);
  return true;
}

export function createNewsSummary({ onCleared }) {
  const get = (id) => document.getElementById(id);
  const root = get("summary-root");
  const baseline = loadBaseline();
  let message = "";

  function button(id, text, className = "btn") {
    const node = textNode("button", text, className);
    node.type = "button";
    node.id = id;
    return node;
  }
  function kpi(label, value, note) {
    const card = textNode("div", "", "card kpi");
    card.append(textNode("span", label), textNode("b", value), textNode("small", note));
    return card;
  }
  function stamp() {
    const now = new Date();
    const pad = (value) => String(value).padStart(2, "0");
    return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`;
  }
  function exported(ok) {
    message = ok ? "" : "이 브라우저에서는 파일을 내려받을 수 없습니다.";
    render();
  }

  function render() {
    const records = loadNewsRecords();
    const summary = summarizeNews(records);
    const actions = textNode("div", "", "summary-actions");
    const csv = button("summary-export-csv", "CSV 내려받기");
    const report = button("summary-export-report", "보고서 내려받기", "btn primary");
    const clear = button("summary-clear", "기록 지우기", "btn danger");
    csv.disabled = report.disabled = clear.disabled = !records.length;
    csv.addEventListener("click", () => exported(summaryDownload(`news-briefing-${stamp()}.csv`, newsCsv(records), "text/csv;charset=utf-8")));
    report.addEventListener("click", () => exported(summaryDownload(`news-briefing-${stamp()}.md`, newsReport(records, baseline), "text/markdown;charset=utf-8")));
    clear.addEventListener("click", () => {
      const confirmed = typeof window.confirm === "function" ? window.confirm("이 브라우저에 저장한 뉴스 평가 기록을 모두 지울까요?") : true;
      if (!confirmed) return;
      saveNewsRecords([]);
      onCleared?.();
      render();
    });
    const note = textNode("p", records.length
      ? `기록 ${records.length}건 · 문항별 최신 결과로 집계합니다. 자유 질문 ${summary.free}건은 CSV에만 포함됩니다.`
      : "아직 기록이 없습니다. 뉴스 브리핑 화면에서 시나리오를 실행하세요.", "summary-note");
    const notice = textNode("p", message, "error");
    notice.setAttribute("role", "alert");
    notice.hidden = !message;
    actions.append(note, csv, report, clear);

    const kpis = textNode("div", "", "kpis");
    kpis.append(
      kpi("진행", `${summary.done} / ${summary.total}`, "문항 완료"),
      kpi("응답 시작 (중앙값)", newsSeconds(summary.firstAudio), "질문 끝 → 답변 시작"),
      kpi("기간 이내 기사", summaryPercent(summary.within), "검색 결과 기준"),
      kpi("언론사·시각 언급", summaryPercent(summary.cited), "답변에서 둘 다 말함"),
      kpi("사람 평가 일치", `${summary.passed} / ${summary.rated}`, "기사 내용과 일치"),
      kpi("언론사 수 (평균)", summary.providers == null ? "—" : `${summary.providers.toFixed(1)}곳`, "문항당"),
    );

    const tableCard = textNode("section", "", "card table-card");
    const tableTitle = textNode("h3", "시나리오별 결과", "section-title");
    tableTitle.append(textNode("small", "판정: 세 문항 모두 실행 · 사람 평가 모두 일치 · 기간 이내 80% 이상"));
    const table = textNode("table", "", "score");
    const head = textNode("thead", "");
    const headRow = textNode("tr", "");
    for (const label of ["시나리오", "문항", "응답 시작", "가장 최신 기사", "기간 이내", "언론사", "출처·시각 언급", "사람 평가", "판정"]) {
      const cell = textNode("th", label);
      cell.scope = "col";
      headRow.append(cell);
    }
    head.append(headRow);
    const body = textNode("tbody", "");
    for (const row of summary.scenarios) {
      const tr = textNode("tr", "");
      const within = textNode("td", "");
      if (row.within != null) {
        const bar = textNode("span", "", "mini");
        const fill = textNode("span", "");
        if (fill.style) fill.style.width = `${Math.round(row.within * 100)}%`;
        bar.append(fill);
        within.append(bar);
      }
      within.append(summaryPercent(row.within));
      const verdict = textNode("td", "");
      verdict.append(textNode("span", SUMMARY_VERDICTS[row.verdict], `verdict ${row.verdict}`));
      tr.append(textNode("td", `${newsScenarioNumber(row.index)} ${row.title}`), textNode("td", `${row.done}/${row.total}`),
        textNode("td", newsSeconds(row.firstAudio)), textNode("td", newsAge(row.newest)), within,
        textNode("td", row.providers == null ? "—" : `${row.providers.toFixed(1)}곳`), textNode("td", summaryPercent(row.cited)),
        textNode("td", `${row.passed}/${row.rated}`), verdict);
      body.append(tr);
    }
    table.append(head, body);
    const wrap = textNode("div", "", "table-wrap");
    wrap.append(table);
    tableCard.append(tableTitle, wrap);

    const split = textNode("div", "", "split");
    const base = textNode("section", "", "card baseline");
    const baseTitle = textNode("h3", "기존 뉴스 공급사 기준값", "section-title");
    baseTitle.append(textNode("small", "입력하면 보고서에 함께 적습니다 · 이 브라우저에만 저장"));
    const grid = textNode("div", "", "bl-grid");
    for (const [key, label, placeholder] of SUMMARY_BASELINE_FIELDS) {
      const field = textNode("label", "", "bl-field");
      const input = document.createElement("input");
      input.id = `baseline-${key}`;
      input.placeholder = placeholder;
      input.autocomplete = "off";
      input.value = typeof baseline[key] === "string" ? baseline[key] : "";
      input.addEventListener("input", () => {
        baseline[key] = input.value.slice(0, 80);
        saveBaseline(baseline);
      });
      field.append(textNode("span", label), input);
      grid.append(field);
    }
    base.append(baseTitle, grid);
    const notes = textNode("section", "", "card notes");
    notes.append(textNode("h3", "보완이 필요한 문항", "section-title"));
    const list = textNode("ul", "");
    for (const item of summary.notes.slice(0, 10)) {
      const row = textNode("li", "");
      row.dataset.state = item.state;
      const icon = textNode("span", item.state === "bad" ? "✕" : "!", "ic");
      icon.setAttribute("aria-hidden", "true");
      row.append(icon, item.text);
      list.append(row);
    }
    if (!summary.notes.length) list.append(textNode("li", summary.done ? "자동 점검과 사람 평가에서 걸린 문항이 없습니다." : "실행한 문항이 없습니다.", "muted"));
    notes.append(list);
    split.append(base, notes);
    const footnote = textNode("p", "자동 점검은 검색 결과와 답변 텍스트로 계산한 참고값입니다. 기사 내용 일치는 사람 평가로 판단합니다.", "summary-note");

    root.replaceChildren(actions, notice, kpis, tableCard, split, footnote);
  }

  render();
  return { render };
}
