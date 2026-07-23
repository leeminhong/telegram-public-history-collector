import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "render_results", ROOT / "render_results.py"
)
assert SPEC and SPEC.loader
render_results = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_results)


PAYLOAD = {
    "window_kst": {
        "start": "2026-07-22T20:10:00+09:00",
        "end": "2026-07-23T08:10:00+09:00",
    },
    "telegram_count": 1,
    "futuresnow_count": 0,
    "items": [
        {
            "source": "nhfutures",
            "label": "NH",
            "published_at_kst": "2026-07-23T07:00:00+09:00",
            "report_date": None,
            "published_text": None,
            "title": "환율 브리핑",
            "text": "원달러 상승",
            "url": "https://t.me/s/nhfutures/123",
        }
    ],
}


class RenderResultsTests(unittest.TestCase):
    def test_copy_package_contains_prompt_and_json(self):
        value = render_results.render_copy_package(
            PAYLOAD, "PROMPT BODY", "MORNING_0810"
        )
        self.assertIn("REPORT_TYPE: MORNING_0810", value)
        self.assertIn("REPORT_AT_KST: 2026-07-23T08:10:00+09:00", value)
        self.assertIn("PROMPT BODY", value)
        self.assertIn('"nhfutures"', value)
        self.assertTrue(value.startswith("# Gemini 복사"))

    def test_sources_contains_visible_link_and_text(self):
        value = render_results.render_sources(PAYLOAD)
        self.assertIn("[원문](https://t.me/s/nhfutures/123)", value)
        self.assertIn("원달러 상승", value)
        self.assertIn("Telegram: **1건**", value)

    def test_close_report_uses_1630_cutoff(self):
        value = render_results.render_copy_package(
            PAYLOAD, "PROMPT BODY", "CLOSE_1630"
        )
        self.assertIn("REPORT_AT_KST: 2026-07-23T16:30:00+09:00", value)


if __name__ == "__main__":
    unittest.main()
