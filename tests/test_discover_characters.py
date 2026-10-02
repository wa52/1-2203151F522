import json
import tempfile
import unittest
from pathlib import Path

from tools.discover_characters import discover


class DiscoverCharactersTests(unittest.TestCase):
    def test_discovers_cross_chapter_action_subject_and_avoids_common_words(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "chunks.jsonl"
            rows = []
            for index in range(1, 7):
                rows.append(
                    {
                        "chapter_id": f"ch-{index:04d}",
                        "chapter_title": f"第{index}章",
                        "chunk_id": f"ch-{index:04d}-ck-001",
                        "text": (
                            "陆辛说道。陆辛抬头看向窗外。"
                            "陈菁点头，陈菁问道。"
                            "这个事情就是这样，这个事情没有问题。"
                        ) * 4,
                    }
                )
            with path.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")

            result = discover(path, min_mentions=5, min_chapters=5, limit=20)
            names = [item["name"] for item in result["candidates"]]
            self.assertIn("陆辛", names)
            self.assertIn("陈菁", names)
            self.assertNotIn("事情", names)
            self.assertTrue(all(item["review_required"] for item in result["candidates"]))


if __name__ == "__main__":
    unittest.main()
