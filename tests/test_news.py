import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from voice_poc.agents import AgentReference
from voice_poc.news import NEWS_DEFAULTS, NewsOptionsError, news_rules, validate_news
from voice_poc.settings import AppSettings
from voice_poc.voice import MAX_TEXT, VoiceProtocolError, VoiceSession, context_message, parse_control


def settings():
    return AppSettings(
        project_endpoint="https://agent.example.invalid/api/projects/voice-poc",
        voice_endpoint="https://voice.example.invalid",
        model="test-model", subscription="explicit-test-subscription",
        agents={
            "bing": AgentReference("test-bing", "1"),
            "webiq": AgentReference("test-webiq", "2"),
        },
    )


class NewsOptionsTests(unittest.TestCase):
    def test_none_is_off_and_missing_keys_use_defaults(self):
        self.assertIsNone(validate_news(None))
        self.assertEqual(validate_news({}), NEWS_DEFAULTS)
        self.assertEqual(validate_news({"count": 10}), {**NEWS_DEFAULTS, "count": 10})
        original = {"freshness": "week"}
        result = validate_news(original)
        result["count"] = 3
        self.assertEqual(original, {"freshness": "week"})
        self.assertEqual(NEWS_DEFAULTS["count"], 5)

    def test_every_allowed_value_is_accepted(self):
        for key, values in (
            ("freshness", ("day", "week", "any")), ("count", (3, 5, 10)),
            ("length", ("30s", "60s", "free")), ("cite", (True, False)), ("group_events", (True, False)),
        ):
            for value in values:
                with self.subTest(key=key, value=value):
                    self.assertEqual(validate_news({key: value})[key], value)

    def test_strict_types_and_unknown_keys_are_rejected(self):
        for value in (
            [], "day", 1, True, {"unknown": 1}, {1: "day"},
            {"freshness": "month"}, {"freshness": None}, {"count": 4}, {"count": "5"}, {"count": 5.0},
            {"count": True}, {"length": 60}, {"length": "90s"}, {"cite": 1}, {"cite": "true"},
            {"group_events": None},
        ):
            with self.subTest(value=value), self.assertRaises(NewsOptionsError) as caught:
                validate_news(value)
            self.assertIsInstance(caught.exception, ValueError)
            self.assertRegex(str(caught.exception), "[가-힣]")

    def test_rules_follow_each_option(self):
        default = news_rules(NEWS_DEFAULTS)
        lines = default.splitlines()
        self.assertEqual(lines[0], "[뉴스 브리핑 규칙]")
        self.assertIn("최근 24시간", default)
        self.assertIn("freshness를 Day", default)
        self.assertIn("서로 다른 기사 5건 안팎", default)
        self.assertIn("약 1분(한국어 약 300자)", default)
        self.assertIn("언론사 이름과 게시 시각", default)
        self.assertIn("하나로 묶어", default)
        self.assertEqual(lines[-1], "- 검색 결과에 없는 내용은 추측하지 말고, 기사가 부족하면 부족하다고 말하세요.")

        custom = news_rules({
            "freshness": "week", "count": 3, "length": "30s", "cite": False, "group_events": False,
        })
        self.assertIn("최근 7일", custom)
        self.assertIn("freshness를 Week", custom)
        self.assertIn("3건 안팎", custom)
        self.assertIn("약 30초(한국어 약 150자)", custom)
        self.assertNotIn("언론사", custom)
        self.assertNotIn("묶어", custom)
        self.assertIn("추측하지 말고", custom)

        free = news_rules({"freshness": "any", "count": 10, "length": "free"})
        self.assertIn("기간 제한 없이", free)
        self.assertNotIn("freshness를", free)
        self.assertIn("10건", free)
        self.assertIn("길이 제한 없이", free)
        self.assertEqual(news_rules(None), "")


class NewsProtocolTests(unittest.TestCase):
    def start(self, **fields):
        return json.dumps({"type": "start", "provider": "webiq", **fields})

    def test_start_accepts_optional_news_and_normalizes_it(self):
        self.assertNotIn("news", parse_control(self.start()))
        self.assertIsNone(parse_control(self.start(news=None))["news"])
        self.assertEqual(parse_control(self.start(news={"count": 3}))["news"], {**NEWS_DEFAULTS, "count": 3})
        message = parse_control(self.start(news={}, context="destination example"))
        self.assertEqual(message["news"], NEWS_DEFAULTS)
        self.assertEqual(message["context"], "destination example")

    def test_invalid_news_has_a_stable_code(self):
        for news in ([], "day", {"count": 7}, {"extra": True}):
            with self.subTest(news=news), self.assertRaises(VoiceProtocolError) as caught:
                parse_control(self.start(news=news))
            self.assertEqual(caught.exception.code, "invalid_news_options")

    def test_news_is_webiq_only(self):
        with self.assertRaises(VoiceProtocolError) as caught:
            parse_control(json.dumps({"type": "start", "provider": "bing", "news": {}}))
        self.assertEqual(caught.exception.code, "news_requires_webiq")
        self.assertEqual(str(caught.exception), "뉴스 브리핑은 WebIQ로만 실행합니다.")
        self.assertIsNone(parse_control(json.dumps({"type": "start", "provider": "bing", "news": None}))["news"])

    def test_existing_limits_still_apply(self):
        with self.assertRaises(VoiceProtocolError):
            parse_control(self.start(news={}, context="x" * (MAX_TEXT + 1)))
        with self.assertRaises(VoiceProtocolError):
            parse_control(self.start(news={}, endpoint="override"))
        self.assertIsNone(VoiceProtocolError("x").code)


class NewsContextTests(unittest.IsolatedAsyncioTestCase):
    def test_context_message_appends_rules_and_keeps_empty_context_working(self):
        plain = context_message("", at="2026-10-01T09:00:00+09:00")
        self.assertNotIn("[뉴스 브리핑 규칙]", plain)
        self.assertIn("별도 앱 맥락 없음", plain)
        news = context_message("", at="2026-10-01T09:00:00+09:00", news={"count": 3})
        self.assertIn("별도 앱 맥락 없음", news)
        self.assertIn(news_rules({"count": 3}), news)
        self.assertTrue(news.endswith("이 메시지 자체에는 답하지 말고 다음 사용자 질문을 해석할 때 참고하세요."))
        self.assertTrue(news.startswith("대화 기준시각: 2026-10-01T09:00:00+09:00\n"))

    async def test_voice_session_sends_rules_with_its_context(self):
        connection = SimpleNamespace(conversation=SimpleNamespace(item=SimpleNamespace(create=AsyncMock())))
        socket = SimpleNamespace(send_json=AsyncMock())
        session = VoiceSession(settings(), "webiq", "arrival 20:10", news={"length": "30s"})
        self.assertEqual(session.news, {**NEWS_DEFAULTS, "length": "30s"})
        await session.handle_event({"type": "session.updated"}, connection, socket)
        text = connection.conversation.item.create.call_args.kwargs["item"].as_dict()["content"][0]["text"]
        self.assertIn("arrival 20:10", text)
        self.assertIn("[뉴스 브리핑 규칙]", text)
        self.assertIn("약 30초", text)

        plain = VoiceSession(settings(), "webiq", "")
        await plain.handle_event({"type": "session.updated"}, connection, socket)
        text = connection.conversation.item.create.call_args.kwargs["item"].as_dict()["content"][0]["text"]
        self.assertNotIn("[뉴스 브리핑 규칙]", text)

    def test_voice_session_rejects_news_for_bing(self):
        with self.assertRaises(VoiceProtocolError) as caught:
            VoiceSession(settings(), "bing", news={})
        self.assertEqual(caught.exception.code, "news_requires_webiq")
        self.assertIsNone(VoiceSession(settings(), "bing", news=None).news)


if __name__ == "__main__":
    unittest.main()
