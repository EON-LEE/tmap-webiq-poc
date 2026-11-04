import { textNode } from "./search-results.js";
import { modeNames, modeDescriptions } from "./labels.js";

const LIVE_VOICE_NOTES = { noeul: "한국어 음성 · 권장", marin: "서비스 기본 음성" };
const MISMATCH_NOTE = "‘Marin + 지시 없음’은 한국어 음성이 나오지 않는 상황을 재현하는 비교용 조합입니다.";

export function createSettingsView() {
  const get = (id) => document.getElementById(id);
  const groups = new Map();
  const fields = new Map();
  let mismatch = null;
  const fieldGroups = {
    connection_mode: "pipeline", realtime_model: "pipeline", return_agent_response_directly: "pipeline",
    voice_name: "tts", speech_rate: "tts",
    live_voice: "live", live_language: "live", live_backchannel: "live",
  };
  const labels = {
    connection_mode: "음성 처리 방식", realtime_model: "Realtime 모델",
    return_agent_response_directly: "Bing Agent 답변 전달",
    live_voice: "음성", live_language: "대화 언어 지시", live_backchannel: "맞장구 (“네”, “음”)",
  };
  // Choices that read better as cards or segments than as a drop-down. The select stays the source of truth.
  const styles = { connection_mode: "cards", live_voice: "voices", live_language: "seg", live_backchannel: "seg" };

  function radio(className, label) {
    const button = textNode("button", "", className);
    button.type = "button";
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", "false");
    if (label) button.setAttribute("aria-label", label);
    return button;
  }
  function choice(style, key, option, label) {
    if (style === "cards") {
      const button = radio("opt");
      const note = textNode("em", "서버에 배포 설정이 없어 고를 수 없습니다.", "opt-note");
      note.hidden = true;
      button.append(textNode("span", "", "radio"), textNode("b", label),
        textNode("small", Object.hasOwn(modeDescriptions, option.value) ? modeDescriptions[option.value] : ""), note);
      return { button, note };
    }
    if (style === "voices") {
      const button = radio("voice");
      const name = typeof option.value === "string" ? option.value.charAt(0).toUpperCase() + option.value.slice(1) : label;
      button.append(textNode("b", name),
        textNode("small", Object.hasOwn(LIVE_VOICE_NOTES, option.value) ? LIVE_VOICE_NOTES[option.value] : label));
      button.setAttribute("aria-label", label);
      return { button, note: null };
    }
    const button = radio("");
    button.textContent = label;
    return { button, note: null };
  }

  return {
    fieldLabel: (key, fallback) => Object.hasOwn(labels, key) ? labels[key] : fallback,
    // End-to-end models hear the audio themselves and reach both searches over MCP, so these choices do not apply.
    hidden: (key, mode) => mode === "end_to_end" && ["transcription_model", "return_agent_response_directly"].includes(key),
    optionLabel: (key, option) => key === "connection_mode" && Object.hasOwn(modeNames, option.value)
      ? modeNames[option.value] : option.label,
    reset() {
      get("voice-options-fields").replaceChildren();
      groups.clear();
      fields.clear();
      mismatch = null;
      for (const [key, title] of Object.entries({
        pipeline: "음성 처리 방식", live: "GPT-Live", stt: "음성 입력", tts: "TTS · 음성 출력",
      })) {
        const group = textNode("fieldset", "", "settings-group");
        group.id = `voice-group-${key}`;
        group.hidden = true;
        group.append(textNode("legend", title));
        if (key === "live") {
          group.append(textNode("p", "검색은 엔진마다 Agent 연결과 같은 WebIQ Agent와 Bing Agent에 위임합니다.", "info-row"));
          mismatch = textNode("p", MISMATCH_NOTE, "warn-note");
          mismatch.id = "live-mismatch-note";
          mismatch.setAttribute("role", "note");
          mismatch.hidden = true;
        }
        groups.set(key, group);
        get("voice-options-fields").append(group);
      }
    },
    // control: { definition, input, label, onPick } from the app; the select keeps the value either way.
    // Returns the card or segment list to place after the hidden select, or null for a plain control.
    addField(key, wrapper, control = null) {
      const name = Object.hasOwn(fieldGroups, key) ? fieldGroups[key] : "stt";
      const entry = { wrapper, input: control?.input || null, choices: [] };
      fields.set(key, entry);
      wrapper.dataset.settingsGroup = name;
      groups.get(name).append(wrapper);
      if (key === "live_language" && mismatch) groups.get(name).append(mismatch);
      const style = Object.hasOwn(styles, key) ? styles[key] : null;
      if (!style || control?.definition?.type !== "select") return null;
      wrapper.className = `${wrapper.className} enhanced`.trim();
      const list = textNode("div", "", style === "cards" ? "opts" : style === "voices" ? "voices" : "seg");
      list.setAttribute("role", "radiogroup");
      if (control.label) {
        control.label.id = `${control.input.id}-label`;
        list.setAttribute("aria-labelledby", control.label.id);
        // The group legend already reads "음성 처리 방식"; keep the label for screen readers only.
        if (key === "connection_mode") control.label.className = `${control.label.className} visually-hidden`.trim();
      }
      control.definition.options.forEach((option, index) => {
        const made = choice(style, key, option, this.optionLabel(key, option));
        made.button.id = `${control.input.id}-choice-${index}`;
        made.button.dataset.value = String(option.value);
        made.button.addEventListener("click", () => {
          if (made.button.disabled) return;
          control.onPick(index);
        });
        entry.choices.push({ ...made, index });
        list.append(made.button);
      });
      return list;
    },
    // Keeps the cards in step with the selects after every change.
    layout(values = {}) {
      for (const entry of fields.values()) {
        if (!entry.input) continue;
        for (const { button, note, index } of entry.choices) {
          const option = entry.input.children[index];
          button.hidden = Boolean(option?.hidden);
          button.disabled = Boolean(option?.disabled) || Boolean(entry.input.disabled);
          button.setAttribute("aria-checked", String(entry.input.value === String(index)));
          if (note) note.hidden = !option?.disabled || Boolean(option?.hidden);
        }
      }
      if (mismatch) {
        mismatch.hidden = !(values.connection_mode === "gpt_live" && values.live_voice === "marin" && values.live_language === "none");
      }
      for (const [key, group] of groups) {
        group.hidden = ![...fields.values()].some((entry) => entry.wrapper.dataset.settingsGroup === key && !entry.wrapper.hidden);
      }
    },
    // News briefing rules are plain values the app keeps; each row is a segmented choice.
    newsOptions(definitions, onPick) {
      const rows = definitions.map((definition) => {
        const row = textNode("div", "", "field");
        const label = textNode("span", definition.label, "field-label");
        label.id = `news-option-${definition.key}-label`;
        const seg = textNode("div", "", "seg");
        seg.setAttribute("role", "radiogroup");
        seg.setAttribute("aria-labelledby", label.id);
        const buttons = definition.options.map(([value, text]) => {
          const button = radio("");
          button.textContent = text;
          button.id = `news-option-${definition.key}-${String(value)}`;
          button.addEventListener("click", () => onPick(definition.key, value));
          seg.append(button);
          return { button, value };
        });
        row.append(label, seg);
        return { key: definition.key, row, buttons };
      });
      get("news-options-fields").replaceChildren(...rows.map((item) => item.row));
      return (values) => {
        for (const { key, buttons } of rows) {
          for (const { button, value } of buttons) button.setAttribute("aria-checked", String(values[key] === value));
        }
      };
    },
  };
}
