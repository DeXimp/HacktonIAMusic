"""Tests de bridge/ai_director.py: el fallback a reglas locales debe ser
100% confiable sin importar por qué falla Claude — sin API key, timeout,
error de red/auth/créditos, o decisión inválida (CLAUDE.md §7)."""
from __future__ import annotations

import unittest

from bridge import config
from bridge.ai_director import AIDirector


async def _noop_apply(decision):
    pass


class TestAIDirectorFallback(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._old_key = config.ANTHROPIC_API_KEY
        config.ANTHROPIC_API_KEY = ""   # por defecto: sin key en estos tests

    def tearDown(self):
        config.ANTHROPIC_API_KEY = self._old_key

    async def test_no_api_key_never_touches_network(self):
        director = AIDirector(object(), _noop_apply)
        self.assertIsNone(director._client)
        snapshot = {"scale": "Am_pentatonic", "bpm": 112,
                   "fx": {"reverb": 0.35, "delay": 0.25, "distortion": 0.05},
                   "amplitude": 0.4, "current_notes": [69],
                   "votes": {"scale_votes": {}, "bpm_avg": None, "fx_avg": {}, "voters": 0},
                   "pending_suggestion": None, "last_scale_change_age_s": 999.0,
                   "recent_actions": []}
        decision = await director.decide(snapshot)
        self.assertEqual(decision["source"], "reglas_locales")

    async def test_timeout_falls_back(self):
        director = AIDirector(object(), _noop_apply)
        director._client = object()   # sentinel truthy: fuerza la rama "con cliente"

        async def _hangs(snapshot):
            import asyncio
            await asyncio.sleep(10)

        director._ask_claude = _hangs
        old_timeout = config.AI_TIMEOUT_S
        config.AI_TIMEOUT_S = 0.05
        try:
            decision = await director.decide({"scale": "Am_pentatonic", "bpm": 112,
                                              "votes": {}, "fx": {}})
        finally:
            config.AI_TIMEOUT_S = old_timeout
        self.assertEqual(decision["source"], "reglas_locales")

    async def test_network_or_credit_error_falls_back(self):
        director = AIDirector(object(), _noop_apply)
        director._client = object()

        async def _boom(snapshot):
            raise RuntimeError("simulated: insufficient credits / auth failure")

        director._ask_claude = _boom
        decision = await director.decide({"scale": "Am_pentatonic", "bpm": 112,
                                          "votes": {}, "fx": {}})
        self.assertEqual(decision["source"], "reglas_locales")

    async def test_credit_or_auth_status_code_logs_specifically(self):
        director = AIDirector(object(), _noop_apply)
        director._client = object()

        class _FakeAPIError(Exception):
            def __init__(self, status_code):
                super().__init__("fake api error")
                self.status_code = status_code

        async def _forbidden(snapshot):
            raise _FakeAPIError(403)

        director._ask_claude = _forbidden
        decision = await director.decide({"scale": "Am_pentatonic", "bpm": 112,
                                          "votes": {}, "fx": {}})
        self.assertEqual(decision["source"], "reglas_locales")

    async def test_invalid_decision_falls_back(self):
        director = AIDirector(object(), _noop_apply)
        director._client = object()

        async def _invalid(snapshot):
            return {"action": "not_a_real_action", "reasoning": "??"}

        director._ask_claude = _invalid
        decision = await director.decide({"scale": "Am_pentatonic", "bpm": 112,
                                          "votes": {}, "fx": {}})
        self.assertEqual(decision["source"], "reglas_locales")

    async def test_valid_decision_uses_claude_source(self):
        director = AIDirector(object(), _noop_apply)
        director._client = object()

        async def _ok(snapshot):
            return {"action": "no_change", "reasoning": "todo bien"}

        director._ask_claude = _ok
        decision = await director.decide({"scale": "Am_pentatonic", "bpm": 112,
                                          "votes": {}, "fx": {}})
        self.assertEqual(decision["source"], "claude")


if __name__ == "__main__":
    unittest.main()
