import datetime as dt
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("futuresnow", ROOT / "futuresnow.py")
assert SPEC and SPEC.loader
futuresnow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(futuresnow)


class FuturesNowTests(unittest.TestCase):
    def test_parse_posts(self):
        initial_data = {
            "contents": {
                "backstagePostRenderer": {
                    "postId": "Ugkx-test",
                    "contentText": {
                        "runs": [
                            {
                                "text": (
                                    "2026년 7월 22일 미국 증시 요약\n"
                                    "나스닥은 금리 하락으로 상승"
                                )
                            }
                        ]
                    },
                    "publishedTimeText": {"simpleText": "2시간 전"},
                }
            }
        }
        page = "var ytInitialData = " + json.dumps(initial_data) + ";"
        rows = futuresnow.parse_posts(
            page,
            collected_at=dt.datetime(2026, 7, 23, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["report_date"], "2026-07-22")
        self.assertEqual(rows[0]["label"], "오선")
        self.assertIn("나스닥", rows[0]["text"])


if __name__ == "__main__":
    unittest.main()
