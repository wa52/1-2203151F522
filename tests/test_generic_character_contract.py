import json
import unittest

from tools.export_generic_character_contract import build_contract, validate


class GenericContractTests(unittest.TestCase):
    def test_lexical_profile_never_creates_hard_visual_lock(self):
        profile = {
            "schema_version": "generic-character-profile/1",
            "character_id": "CHAR-X",
            "name": "角色X",
            "review_categories": {
                "role_context": {
                    "recurring_terms": [
                        {"term": "工作", "anchor_count": 5},
                        {"term": "组长", "anchor_count": 3},
                    ],
                    "evidence": [
                        {
                            "chapter_id": "ch-1",
                            "chapter_title": "第一章",
                            "chunk_id": "ch-1-ck-1",
                            "line_start": 1,
                            "line_end": 10,
                        }
                    ],
                }
            },
            "visual_policy": {"not_yet_locked": ["age", "face_shape", "hairstyle"]},
            "forbidden_inferences": ["不要脑补外貌"],
        }
        contract = build_contract(profile, "canon/x.profile.json")
        validate(contract)
        self.assertEqual(contract["locked_facts"], [])
        self.assertIn("face_shape", contract["unresolved_visual_features"])
        self.assertEqual(contract["soft_constraints"][0]["evidence_semantics"], "lexical-context-only")


if __name__ == "__main__":
    unittest.main()
