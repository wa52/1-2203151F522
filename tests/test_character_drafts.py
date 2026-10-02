import unittest

from tools.build_character_drafts import build_drafts


class CharacterDraftTests(unittest.TestCase):
    def test_only_recommended_candidates_become_drafts(self):
        result = build_drafts(
            {
                "schema_version": "character-discovery/2",
                "candidates": [
                    {
                        "name": "陆辛",
                        "candidate_kind": "personal_name",
                        "score": 100,
                        "mention_count": 100,
                        "chapter_count": 20,
                        "subject_action_hits": 30,
                        "self_intro_hits": 1,
                        "first_seen": {"chapter_id": "ch-1"},
                        "recommended_for_canon_review": True
                    },
                    {
                        "name": "直接",
                        "candidate_kind": "alias_or_codename",
                        "score": 50,
                        "recommended_for_canon_review": False
                    }
                ]
            }
        )
        self.assertEqual(result["draft_count"], 1)
        draft = result["drafts"][0]
        self.assertEqual(draft["name"], "陆辛")
        self.assertFalse(draft["registry_ready"])
        self.assertIsNone(draft["canon_contract"])


if __name__ == "__main__":
    unittest.main()
