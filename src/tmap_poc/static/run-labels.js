export const providerNames = { webiq: "WebIQ", bing: "Grounding with Bing" };
export const comparedProviders = ["webiq", "bing"];

export const modeNames = {
  agent: "Agent 연결 (기본)", realtime_agent_tool: "End-to-end (Realtime)",
};

// How each engine is reached for the chosen voice pipeline; the actual route is reported by the server.
export function routeSummary(mode) {
  if (mode === "realtime_agent_tool") {
    return "Realtime 모델이 음성을 직접 듣고 말합니다. Agent 없이 모델이 두 검색을 바로 부릅니다: "
      + "WebIQ는 MCP로 WebIQ 검색, Bing은 앱 서버가 Foundry Toolbox의 Bing 기반 Web Search(MCP)를 불러 결과를 전달합니다. "
      + "엔진마다 모델이 따로 들어서 같은 말도 다르게 알아들을 수 있습니다.";
  }
  return "두 엔진 모두 Agent에 연결합니다. 같은 모델·같은 지시의 Agent가 각자의 검색 도구로 찾아 답합니다.";
}
