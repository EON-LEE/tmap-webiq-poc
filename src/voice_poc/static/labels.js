export const providerNames = { webiq: "WebIQ", bing: "Grounding with Bing" };
export const comparedProviders = ["webiq", "bing"];

export const modeNames = {
  agent: "Agent 연결 (기본)", end_to_end: "End-to-end (Realtime)", gpt_live: "GPT-Live",
};
export const shortModeNames = { agent: "Agent 연결", end_to_end: "End-to-end", gpt_live: "GPT-Live" };
export const modeDescriptions = {
  agent: "음성 인식 → 기존 Foundry Agent → 음성 합성",
  end_to_end: "Realtime 모델이 직접 듣고 말하며 검색 도구를 부릅니다 · 별도 비용",
  gpt_live: "말하는 중에도 듣고 반응합니다 · 검색은 WebIQ/Bing Agent에 위임 · 음성 전용",
};

// How each engine is reached for the chosen voice pipeline; the actual route is reported by the server.
export function routeSummary(mode) {
  if (mode === "gpt_live") {
    return "GPT-Live가 음성을 직접 듣고 말합니다. 검색이 필요하면 엔진마다 Agent 연결과 같은 WebIQ Agent와 Bing Agent에 위임하고, "
      + "받은 답을 이어서 말합니다. 텍스트 질문은 받지 않습니다.";
  }
  if (mode === "end_to_end") {
    return "Realtime 모델이 음성을 직접 듣고 말합니다. Agent 없이 모델이 두 검색을 바로 부릅니다: "
      + "WebIQ는 MCP로 WebIQ 검색, Bing은 앱 서버가 Foundry Toolbox의 Bing 기반 Web Search(MCP)를 불러 결과를 전달합니다"
      + "(Toolbox가 없는 환경에서는 Bing Agent). "
      + "엔진마다 모델이 따로 들어서 같은 말도 다르게 알아들을 수 있습니다.";
  }
  return "두 엔진 모두 Agent에 연결합니다. 같은 모델·같은 지시의 Agent가 각자의 검색 도구로 찾아 답합니다.";
}
