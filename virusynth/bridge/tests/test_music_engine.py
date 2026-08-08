"""Tests del motor musical (Fase 3). Ejecutar desde virusynth/:
    python -m unittest discover -s bridge/tests -t .
"""
from __future__ import annotations

import unittest

from bridge import music_engine as me


class TestParseScale(unittest.TestCase):
    def test_minor_pentatonic(self):
        self.assertEqual(me.parse_scale("Am_pentatonic"), (9, "minor_pentatonic"))

    def test_major(self):
        self.assertEqual(me.parse_scale("C_major"), (0, "major"))

    def test_dorian(self):
        self.assertEqual(me.parse_scale("D_dorian"), (2, "dorian"))

    def test_minor(self):
        self.assertEqual(me.parse_scale("E_minor"), (4, "minor"))

    def test_flat_root(self):
        self.assertEqual(me.parse_scale("Bb_major"), (10, "major"))

    def test_blues_with_m(self):
        self.assertEqual(me.parse_scale("Am_blues"), (9, "blues"))

    def test_invalid_raises(self):
        for bad in ("H_major", "A_klingon", "Am_major", "", "A#m_pentatonic_x"):
            with self.assertRaises(me.ScaleError, msg=bad):
                me.parse_scale(bad)

    def test_roundtrip(self):
        for name in ("Am_pentatonic", "C_pentatonic", "F#_dorian", "G_mixolydian"):
            pc, mode = me.parse_scale(name)
            self.assertEqual(me.scale_name(pc, mode), name)


class TestScaleNotes(unittest.TestCase):
    def test_am_pentatonic_pcs(self):
        # A C D E G
        self.assertEqual(me.pitch_classes("Am_pentatonic"), {9, 0, 2, 4, 7})

    def test_notes_within_range(self):
        notes = me.scale_notes("C_major", 60, 72)
        self.assertEqual(notes, [60, 62, 64, 65, 67, 69, 71, 72])

    def test_quantize_in_scale_is_identity(self):
        self.assertEqual(me.quantize(69, "Am_pentatonic"), 69)

    def test_quantize_nearest(self):
        # A#(70) en Am pentatónica: A(69) a 1 y C(72) a 2 -> 69
        self.assertEqual(me.quantize(70, "Am_pentatonic"), 69)

    def test_quantize_tie_prefers_lower(self):
        # B(71) en Am pentatónica: A(69) y C(72)... distancias 2 y 1 -> 72
        self.assertEqual(me.quantize(71, "Am_pentatonic"), 72)
        # F#(66) en C mayor: F(65) y G(67) a 1 -> empate hacia abajo: 65
        self.assertEqual(me.quantize(66, "C_major"), 65)


class TestClashes(unittest.TestCase):
    def test_out_of_scale_detected(self):
        clashes = me.find_clashes([61], "C_major")  # C#
        self.assertTrue(any(c["type"] == "out_of_scale" for c in clashes))

    def test_tritone_pair_detected(self):
        clashes = me.find_clashes([60, 66], "C_major")  # C y F#
        self.assertTrue(any(c["type"] == "interval" and c["interval"] == 6
                            for c in clashes))

    def test_clean_pattern_no_clashes(self):
        self.assertEqual(me.find_clashes([60, 64, 67], "C_major"), [])

    def test_resolve_pattern(self):
        resolved, changes = me.resolve_pattern([60, 61, 67], "C_major")
        self.assertEqual(resolved, [60, 60, 67])
        self.assertEqual(changes, [{"from": 61, "to": 60}])
        self.assertTrue(all(me.is_in_scale(n, "C_major") for n in resolved))


class TestNeighborsAndModulation(unittest.TestCase):
    def test_relative_major_is_top_neighbor(self):
        # C mayor comparte las 7 notas con A menor: máxima afinidad
        neighbors = me.scale_neighbors("A_minor")
        self.assertEqual(me.shared_pcs("A_minor", neighbors[0]),
                         len(me.pitch_classes("A_minor")))
        self.assertIn("C_major", neighbors[:3])

    def test_modulation_direct_when_close(self):
        # Am pentatónica ⊂ C mayor: paso directo
        self.assertEqual(me.modulation_step("Am_pentatonic", "C_major"), "C_major")

    def test_modulation_gradual_when_far(self):
        step = me.modulation_step("C_major", "F#_major")
        self.assertNotEqual(step, "F#_major")   # nunca saltar directo a la antípoda
        self.assertNotEqual(step, "C_major")

    def test_same_scale_noop(self):
        self.assertEqual(me.modulation_step("C_major", "C_major"), "C_major")


class TestValidateDecision(unittest.TestCase):
    def test_valid_change_scale(self):
        d = me.validate_decision({"action": "change_scale", "value": "E_minor",
                                 "reasoning": "ok"})
        self.assertEqual(d["value"], "E_minor")

    def test_invalid_scale_rejected(self):
        self.assertIsNone(me.validate_decision(
            {"action": "change_scale", "value": "X_nope", "reasoning": ""}))

    def test_bpm_clamped(self):
        d = me.validate_decision({"action": "set_bpm", "value": 999,
                                 "reasoning": ""})
        self.assertEqual(d["value"], 180)

    def test_fx_clamped_and_filtered(self):
        d = me.validate_decision({"action": "set_fx",
                                  "value": {"reverb": 3.0, "hack": 1},
                                  "reasoning": ""})
        self.assertEqual(d["value"], {"reverb": 1.0})

    def test_unknown_action_rejected(self):
        self.assertIsNone(me.validate_decision(
            {"action": "drop_the_bass", "value": 1, "reasoning": ""}))


class TestRuleBasedSuggestion(unittest.TestCase):
    def _snapshot(self, **overrides):
        snap = {"scale": "Am_pentatonic", "bpm": 112,
                "fx": {"reverb": 0.35, "delay": 0.25, "distortion": 0.05},
                "amplitude": 0.4, "current_notes": [69, 72],
                "votes": {"scale_votes": {}, "bpm_avg": None, "fx_avg": {},
                          "voters": 0},
                "pending_suggestion": None,
                "last_scale_change_age_s": 999.0, "recent_actions": []}
        snap.update(overrides)
        return snap

    def test_priority_1_harmonic_resolution(self):
        snap = self._snapshot(
            pending_suggestion={"artist_id": "a1", "notes": [61, 66]},
            votes={"scale_votes": {"C_major": 5}, "bpm_avg": 160, "fx_avg": {},
                   "voters": 5})
        d = me.rule_based_suggestion(snap)
        self.assertEqual(d["action"], "harmonic_resolution")
        self.assertTrue(d["harmonic_resolution"]["resolved_notes"])
        self.assertEqual(d["source"], "reglas_locales")

    def test_priority_2_scale_votes(self):
        snap = self._snapshot(votes={"scale_votes": {"C_major": 3},
                                     "bpm_avg": None, "fx_avg": {}, "voters": 3})
        d = me.rule_based_suggestion(snap)
        self.assertEqual(d["action"], "change_scale")
        self.assertEqual(d["value"], "C_major")   # relativa: paso directo

    def test_scale_votes_respect_cooldown(self):
        snap = self._snapshot(votes={"scale_votes": {"C_major": 3},
                                     "bpm_avg": None, "fx_avg": {}, "voters": 3},
                              last_scale_change_age_s=5.0)
        d = me.rule_based_suggestion(snap)
        self.assertNotEqual(d["action"], "change_scale")

    def test_priority_3_bpm(self):
        snap = self._snapshot(votes={"scale_votes": {}, "bpm_avg": 140,
                                     "fx_avg": {}, "voters": 4})
        d = me.rule_based_suggestion(snap)
        self.assertEqual(d["action"], "set_bpm")
        self.assertEqual(d["value"], 122)   # paso máximo de 10

    def test_priority_4_fx(self):
        snap = self._snapshot(votes={"scale_votes": {}, "bpm_avg": None,
                                     "fx_avg": {"reverb": 0.9}, "voters": 2})
        d = me.rule_based_suggestion(snap)
        self.assertEqual(d["action"], "set_fx")
        self.assertAlmostEqual(d["value"]["reverb"], 0.55, places=2)

    def test_default_no_change(self):
        d = me.rule_based_suggestion(self._snapshot())
        self.assertEqual(d["action"], "no_change")
        self.assertTrue(d["reasoning"])


if __name__ == "__main__":
    unittest.main()
