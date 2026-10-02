import { isRecord, safeSourceUrl } from "./search-results.js";

function observedFields(value, keys) {
  if (!isRecord(value)) return {};
  return Object.fromEntries(keys.filter((key) => Object.hasOwn(value, key)
    && (value[key] === null || typeof value[key] === "boolean"
      || typeof value[key] === "string" && value[key].length <= 4000
      || typeof value[key] === "number" && Number.isFinite(value[key])))
    .map((key) => [key, value[key]]));
}

export function projectFlowEvent(event) {
  const envelope = observedFields(event, ["stage", "status", "observation", "operation", "source_event",
    "item_id", "response_id", "tool_id"]);
  event = { ...envelope, data: event.data };
  const original = isRecord(event.data) ? event.data : {};
  const sessionFields = ["service_model", "model_scope", "service_session_id", "expires_at",
    "input_audio_sampling_rate", "input_audio_format", "output_audio_format"];
  const sessionUpdate = event.stage === "request" && event.operation === "session.update";
  const stages = {
    connection: ["api_version", "connection_mode", "target_scope", "endpoint_host", "project_name",
      "foundry_resource_override", "requested_model", "search_attachment"],
    session: sessionFields,
    request: event.operation === "session.update" ? sessionFields
      : event.operation === "input_audio_buffer.append" ? ["input_mode", "first_frame_bytes"]
        : ["purpose", "role", "content_omitted", ...(original.purpose === "user_input" ? ["input_mode", "text"] : [])],
    input: ["input_mode", "text", "role", "format", "sample_rate", "first_frame_bytes", "previous_item_id"],
    speech: ["audio_start_ms", "audio_end_ms"],
    response: ["status", "purpose"],
    tool: ["status", "kind", "name", "server_label", "call_id", "agent_response_id",
      "arguments_observed", "arguments_parseable", "arguments_filtered"],
    tool_discovery: ["server_label", "tools_truncated"],
    audio: ["scope"],
    service: ["code", "param"],
  };
  const data = observedFields(original, Object.hasOwn(stages, event.stage) ? stages[event.stage] : []);
  const session = event.stage === "session" || sessionUpdate;
  for (const [key, fields] of Object.entries({
    agent: ["name", "version"],
    agent_tool: ["agent_name", "agent_version", "project_name", "foundry_resource_override", "return_agent_response_directly"],
    search_tool: ["type", "server_label", "server_host"],
    voice: ["type", "name", "rate"],
    input_audio_transcription: ["model", "language"],
    turn_detection: ["type", "create_response", "interrupt_response", "silence_duration_ms"],
    arguments: ["query", "q", "search_query", "url", "language", "region", "vertical", "maxResults", "contentFormat",
      "maxLength", "location", "safeSearch", "count", "market", "set_lang", "freshness", "app", "destination_id",
      "place_id", "input"],
  })) {
    const permitted = key === "arguments" ? event.stage === "tool"
      : key === "agent" ? event.stage === "connection"
        : key === "agent_tool" || key === "search_tool" ? sessionUpdate : session;
    if (permitted && isRecord(original[key])) data[key] = observedFields(original[key], fields);
  }
  if (data.search_tool && Array.isArray(original.search_tool.allowed_tools)) {
    data.search_tool.allowed_tools = original.search_tool.allowed_tools.slice(0, 32)
      .filter((name) => typeof name === "string" && name.length <= 128);
  }
  if (data.arguments) {
    if (Object.keys(data.arguments).length !== Object.keys(original.arguments).length) data.arguments_filtered = true;
    if (data.arguments.url != null) {
      const url = safeSourceUrl(data.arguments.url);
      const privateKeys = new Set(["key", "apikey", "token", "accesstoken", "authtoken", "authorization",
        "clientsecret", "password", "credential", "sig", "signature", "traceaccess", "traceaccesstoken", "xtraceaccess"]);
      const keys = url ? [...url.searchParams.keys(), ...new URL(`https://localhost/?${url.hash.slice(1)}`).searchParams.keys()] : [];
      if (!url || keys.some((key) => privateKeys.has(key.toLowerCase().replace(/[_-]/g, "")))) {
        delete data.arguments.url;
        data.arguments_filtered = true;
      }
    }
  }
  if (event.stage === "tool_discovery" && Array.isArray(original.tools)) {
    data.tools = original.tools.slice(0, 64).filter((name) => typeof name === "string" && name.length <= 256);
  }
  return {
    ...envelope,
    data,
  };
}
