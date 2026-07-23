import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("collector", ROOT / "collector.py")
assert SPEC and SPEC.loader
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


SAMPLE_HTML = """
<html><body>
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="sample_channel/42">
    <a class="tgme_widget_message_owner_name">작성자 &amp; 팀</a>
    <div class="tgme_widget_message_text js-message_text" dir="auto">
      환율 <b>상승</b><br>두 번째 줄\u200b
    </div>
    <span class="tgme_widget_message_views">1.2K</span>
    <time datetime="2026-07-23T00:01:02+00:00"></time>
  </div>
</div>
<div class="tgme_widget_message_wrap">
  <div class="tgme_widget_message" data-post="sample_channel/43">
    <a class="tgme_widget_message_photo_wrap"></a>
    <time datetime="2026-07-23T01:02:03+00:00"></time>
  </div>
</div>
</body></html>
"""


class CollectorTests(unittest.TestCase):
    def test_parse_page(self):
        rows = collector.parse_page(SAMPLE_HTML, "sample_channel", "샘플")
        self.assertEqual([row["post_id"] for row in rows], [42, 43])
        self.assertEqual(rows[0]["text"], "환율 상승\n두 번째 줄")
        self.assertEqual(rows[0]["author"], "작성자 & 팀")
        self.assertEqual(rows[0]["published_at"], "2026-07-23T00:01:02Z")
        self.assertTrue(rows[1]["has_media"])
        self.assertEqual(rows[1]["text"], "")

    def test_load_channels_accepts_urls_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "channels.json"
            config.write_text(
                json.dumps([{"id": "nhfutures", "label": "NH"}]),
                encoding="utf-8",
            )
            rows = collector.load_channels(
                config, "https://t.me/s/nhfutures, @nhfutures"
            )
        self.assertEqual(rows, [{"id": "nhfutures", "label": "NH"}])


if __name__ == "__main__":
    unittest.main()
