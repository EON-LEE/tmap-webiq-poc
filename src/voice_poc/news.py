"""News briefing options: a WebIQ-only scenario for replacing a news provider."""

from collections.abc import Mapping

NEWS_DEFAULTS = {"freshness": "day", "count": 5, "length": "60s", "cite": True, "group_events": True}
_CHOICES = {"freshness": ("day", "week", "any"), "count": (3, 5, 10), "length": ("30s", "60s", "free")}
_FRESHNESS = {
    "day": "최근 24시간 안에 게시된 기사를 찾으세요 (도구가 지원하면 freshness를 Day로 지정).",
    "week": "최근 7일 안에 게시된 기사를 찾으세요 (도구가 지원하면 freshness를 Week로 지정).",
    "any": "기간 제한 없이 게시된 기사를 찾으세요.",
}
_LENGTH = {
    "30s": "약 30초(한국어 약 150자) 분량으로 말하세요.",
    "60s": "약 1분(한국어 약 300자) 분량으로 말하세요.",
    "free": "길이 제한 없이 필요한 만큼 말하세요.",
}


class NewsOptionsError(ValueError):
    """News briefing options are invalid."""


def validate_news(value):
    """Validate without coercion; return a fresh complete dict, or None when news mode is off."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise NewsOptionsError("뉴스 옵션은 JSON 객체여야 합니다.")
    if any(not isinstance(key, str) for key in value) or set(value) - set(NEWS_DEFAULTS):
        raise NewsOptionsError("지원하지 않는 뉴스 옵션 키가 있습니다.")
    result = {**NEWS_DEFAULTS, **value}
    for key, allowed in _CHOICES.items():
        item = result[key]
        if type(item) is not type(allowed[0]) or item not in allowed:
            raise NewsOptionsError(f"뉴스 옵션 {key}는 {', '.join(map(str, allowed))} 중 하나여야 합니다.")
    for key in ("cite", "group_events"):
        if type(result[key]) is not bool:
            raise NewsOptionsError(f"뉴스 옵션 {key}는 true 또는 false여야 합니다.")
    return result


def news_rules(news):
    news = validate_news(news)
    if news is None:
        return ""
    lines = [
        "[뉴스 브리핑 규칙]",
        "- 뉴스 검색 도구로 " + _FRESHNESS[news["freshness"]],
        f"- 서로 다른 기사 {news['count']}건 안팎을 골라 브리핑하세요.",
        "- 답변 분량: " + _LENGTH[news["length"]],
    ]
    if news["cite"]:
        lines.append("- 각 기사마다 언론사 이름과 게시 시각(예: 2시간 전)을 함께 말하세요.")
    if news["group_events"]:
        lines.append("- 같은 사건을 다룬 여러 기사는 하나로 묶어 말하세요.")
    lines.append("- 검색 결과에 없는 내용은 추측하지 말고, 기사가 부족하면 부족하다고 말하세요.")
    return "\n".join(lines)
