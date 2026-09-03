"""Prompts, verbatim from the planning document.

These are fixed variables in the experiment. The system prompt is identical on
every path; the synthesis prompt is identical on every passage-returning path.
Changing either invalidates cross-path comparison, so edits must be deliberate
and recorded in the run metadata.
"""

from __future__ import annotations

# Planning document, section 2. Applied identically to all paths.
SYSTEM_PROMPT = """당신은 차량 내 음성 어시스턴트입니다. 운전 중 사용자가 음성으로 질문하며,
답변은 TTS로 읽힙니다.

[답변 규칙]
- 2~3문장, 40단어 이내. 운전 중 청취 가능한 길이로.
- 숫자·시간·가격은 구체적으로. 모호한 표현("최근", "곧") 금지.
- 정보의 기준 시점을 반드시 포함 (예: "9월 2일 기준").
- 근거가 불충분하면 추측하지 말고 "확인되지 않습니다"라고 답할 것.
- 목록이 필요하면 최대 3개까지만.

[출력 형식 — JSON만 반환]
{
  "answer": "음성으로 읽힐 답변 문장",
  "as_of": "정보 기준 시점 (YYYY-MM-DD 또는 YYYY-MM-DD HH:mm)",
  "confidence": "high | medium | low",
  "citations": [
    {"title": "출처 제목", "url": "출처 URL", "published": "발행일 또는 null"}
  ],
  "insufficient_evidence": true | false
}"""

# Planning document, section 2, synthesis prompt. Used by every path that
# returns passages. The no-search path drops the <search_results> block only.
SYNTHESIS_TEMPLATE = """아래는 웹 검색 결과입니다. 이 근거만 사용해 위 규칙대로 답하세요.
검색 결과에 없는 내용은 절대 생성하지 마세요.

<search_results>
{passages}
</search_results>

질문: {query}
현재 시각: {now_kst}"""

NULL_TEMPLATE = """질문: {query}
현재 시각: {now_kst}"""

#: Shown when retrieval succeeded but returned nothing. Stating the miss
#: explicitly is more honest than sending an empty block, which the model
#: could read as a formatting glitch rather than an absence of evidence.
NO_RESULTS_MARKER = "(검색 결과 없음)"


def format_passages(passages) -> str:
    """Render passages for the prompt.

    The index, title and URL are all shown so the model can cite precisely,
    which is what makes it possible to check afterwards whether a citation
    actually came from the passage set.
    """
    if not passages:
        return NO_RESULTS_MARKER
    blocks = []
    for passage in passages:
        published = passage.published_at or "발행일 미상"
        blocks.append(
            f"[{passage.rank}] {passage.title}\n"
            f"URL: {passage.url}\n"
            f"날짜: {published}\n"
            f"{passage.text}"
        )
    return "\n\n".join(blocks)


def build_messages(query: str, now_kst: str, passages, grounded: bool) -> list[dict]:
    if grounded:
        user = SYNTHESIS_TEMPLATE.format(
            passages=format_passages(passages), query=query, now_kst=now_kst
        )
    else:
        user = NULL_TEMPLATE.format(query=query, now_kst=now_kst)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
