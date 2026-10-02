import { textNode } from "./search-results.js";
import { modeNames } from "./run-labels.js";

export function createSettingsView() {
  const get = (id) => document.getElementById(id);
  const groups = new Map();
  const fields = new Map();
  const fieldGroups = {
    connection_mode: "pipeline", llm_model: "pipeline", realtime_model: "pipeline", return_agent_response_directly: "pipeline",
    voice_name: "tts", speech_rate: "tts",
  };
  const labels = {
    connection_mode: "음성 처리 방식", llm_model: "텍스트 모델", realtime_model: "Realtime 모델",
    return_agent_response_directly: "Bing Agent 답변 전달",
  };
  return {
    fieldLabel: (key, fallback) => Object.hasOwn(labels, key) ? labels[key] : fallback,
    // End-to-end models hear the audio themselves and reach both searches over MCP, so these choices do not apply.
    hidden: (key, mode) => mode === "realtime_agent_tool" && ["transcription_model", "return_agent_response_directly"].includes(key),
    optionLabel: (key, option) => key === "connection_mode" && Object.hasOwn(modeNames, option.value)
      ? modeNames[option.value] : option.label,
    // STT → LLM → TTS and the app-control navigation scenario are not part of the search comparison.
    excluded: (key, option) => key === "connection_mode" && ["model_search", "model_tools"].includes(option.value),
    reset() {
      get("voice-options-fields").replaceChildren();
      groups.clear();
      fields.clear();
      for (const [key, title] of Object.entries({
        pipeline: "음성 처리 방식", stt: "음성 입력", tts: "TTS · 음성 출력",
      })) {
        const group = textNode("fieldset", "", "settings-group");
        group.id = `voice-group-${key}`;
        group.hidden = true;
        group.append(textNode("legend", title));
        groups.set(key, group);
        get("voice-options-fields").append(group);
      }
    },
    addField(key, wrapper) {
      const name = Object.hasOwn(fieldGroups, key) ? fieldGroups[key] : "stt";
      fields.set(key, wrapper);
      wrapper.dataset.settingsGroup = name;
      groups.get(name).append(wrapper);
    },
    layout() {
      for (const [key, group] of groups) {
        group.hidden = ![...fields.values()].some((wrapper) => wrapper.dataset.settingsGroup === key && !wrapper.hidden);
      }
    },
  };
}
