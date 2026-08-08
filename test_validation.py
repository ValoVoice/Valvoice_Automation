import json
import os
import shutil
import unittest
from scripts.validate_content import _deterministic_validation, _semantic_validation, validate_bgm
from scripts.select_assets import select_bgm

class TestValVoiceValidation(unittest.TestCase):
    def test_good_content_pass(self):
        txt = "ValVoice routes AI TTS to your Valorant team."
        res = _semantic_validation(txt)
        self.assertEqual(res, "PASS")

    def test_riot_approved_fail(self):
        txt = "ValVoice is fully Riot approved and completely safe."
        res = _semantic_validation(txt)
        self.assertIn(res, ["FAIL", "HUMAN_REVIEW_REQUIRED"])

    def test_free_forever_fail(self):
        txt = "It's free forever!"
        self.assertFalse(_deterministic_validation(txt))

    def test_voices_29(self):
        txt = "ValVoice supports exactly 29 voices."
        self.assertTrue(_deterministic_validation(txt))
        
    def test_voices_50_fail(self):
        txt = "ValVoice supports 50 voices."
        self.assertFalse(_deterministic_validation(txt))
        
    def test_all_valorant_agents_fail(self):
        txt = "We support all Valorant agents in the game!"
        res = _semantic_validation(txt)
        self.assertIn(res, ["FAIL", "HUMAN_REVIEW_REQUIRED"])
        
    def test_approved_bgm(self):
        os.makedirs("assets/bgm/approved", exist_ok=True)
        with open("assets/bgm/approved/dummy.mp3", "w") as f:
            f.write("a")
        bgm = select_bgm()
        self.assertTrue(validate_bgm(bgm))

    def test_unapproved_bgm(self):
        self.assertFalse(validate_bgm(os.path.abspath("assets/bgm/unapproved_dummy.mp3")))

    def test_valid_metadata(self):
        meta = {"youtube": {"title": "ValVoice feature breakdown", "description": "Routing AI TTS to your team."}}
        self.assertEqual(validate_metadata(json.dumps(meta)), "PASS")
        
    def test_problematic_metadata(self):
        meta = {"youtube": {"title": "Get ValVoice FREE FOREVER — Riot-approved AI!"}}
        res = validate_metadata(json.dumps(meta))
        self.assertIn(res, ["FAIL", "HUMAN_REVIEW_REQUIRED"])

if __name__ == '__main__':
    unittest.main()
