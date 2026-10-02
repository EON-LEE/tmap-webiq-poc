export function textNode(tag, text, className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

export function safeSourceUrl(value) {
  if (typeof value !== "string" || !/^https?:\/\//i.test(value.trim())) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && url.hostname && !url.username && !url.password ? url : null;
  } catch { return null; }
}

export function sourceLink(url, title) {
  const link = textNode("a", title);
  link.href = url.href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

export const isRecord = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
export const shortText = (value, limit = 280) => {
  const text = (value !== null && typeof value === "object" ? readableValue(value) : String(value)).replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
};

export function readableValue(value, depth = 0) {
  if (value === null) return "없음";
  if (typeof value !== "object") return shortText(value);
  if (depth >= 3) return "상세 값은 원본 이벤트 참조";
  const values = Array.isArray(value) ? value.map((item) => readableValue(item, depth + 1))
    : Object.entries(value).map(([key, item]) => `${key}: ${readableValue(item, depth + 1)}`);
  return shortText(values.join(" · "));
}

export function field(list, label, value) {
  if (value === undefined || value === null || value === "") return;
  list.append(textNode("dt", label), textNode("dd", shortText(value, 600)));
}

function outputObjects(value) {
  if (isRecord(value)) return [value];
  if (typeof value !== "string") return null;
  try {
    const parsed = JSON.parse(value);
    return isRecord(parsed) ? [parsed] : null;
  } catch { /* MCP output can contain consecutive JSON objects. */ }
  const objects = [];
  let start = -1, depth = 0, quoted = false, escaped = false;
  for (let i = 0; i < value.length; i++) {
    const char = value[i];
    if (start === -1) {
      if (/\s/.test(char)) continue;
      if (char !== "{") return null;
      start = i;
      depth = 1;
    } else if (quoted) {
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === '"') quoted = false;
    } else if (char === '"') quoted = true;
    else if (char === "{") depth++;
    else if (char === "}" && --depth === 0) {
      try { objects.push(JSON.parse(value.slice(start, i + 1))); } catch { return null; }
      start = -1;
    }
  }
  return start === -1 && objects.length ? objects : null;
}

export function resultKey(value) {
  if (Array.isArray(value)) return `[${value.map(resultKey).join(",")}]`;
  if (isRecord(value)) return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${resultKey(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}

export function toolOutput(value) {
  const objects = outputObjects(value);
  const results = [], traceIds = new Set(), seen = new Set();
  let unreadable = !objects;
  function visit(object, depth = 0) {
    if (depth > 8) { unreadable = true; return false; }
    if (typeof object.traceId === "string" && object.traceId.trim()) traceIds.add(object.traceId);
    let recognized = false;
    for (const [key, items] of Object.entries(object)) {
      if (!/results$/i.test(key)) continue;
      if (!Array.isArray(items)) { unreadable = true; continue; }
      recognized = true;
      for (const item of items) {
        // Distinct observations at the same URL are not duplicate search results.
        const identity = `${key}:${resultKey(item)}`;
        if (!seen.has(identity)) { seen.add(identity); results.push({ kind: key, item }); }
      }
    }
    for (const key of ["structuredResponse", "structuredContent"]) {
      if (!Object.hasOwn(object, key)) continue;
      const wrapped = outputObjects(object[key]);
      if (!wrapped) unreadable = true;
      else for (const nested of wrapped) {
        const found = visit(nested, depth + 1);
        if (!found) unreadable = true;
        recognized = found || recognized;
      }
    }
    return recognized;
  }
  for (const object of objects || []) if (!visit(object)) unreadable = true;
  return { results, traceIds, unreadable };
}

export function resultSummary({ item }) {
  if (!isRecord(item)) return null;
  const data = isRecord(item.data) ? item.data : {};
  const instrument = isRecord(data.instrument) ? data.instrument : {};
  const firstText = (...values) => values.find((value) => typeof value === "string" && value.trim());
  const url = safeSourceUrl(item.url);
  const title = firstText(instrument.displayName, item.title, item.name, data.name, url?.hostname);
  const excerpt = firstText(item.snippet, item.excerpt, item.description, data.description, data.address, item.content);
  const facts = [];
  if (instrument.price != null) {
    facts.push(`${instrument.price}${instrument.currency ? ` ${instrument.currency}` : ""}`);
  }
  if (instrument.lastTradedAt) facts.push(String(instrument.lastTradedAt));
  if (!title && !excerpt && !facts.length) return null;
  return {
    title: title || "검색 결과", url, excerpt: excerpt || facts.join(" · "),
    symbol: instrument.symbol ? String(instrument.symbol) : "",
  };
}
