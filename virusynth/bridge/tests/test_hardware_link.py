"""Tests de bridge/hardware_link.py: fallback automático al performer
sintético cuando no hay hardware físico, y vuelta atrás al reconectar
(CLAUDE.md §7 -- "el show sigue")."""
from __future__ import annotations

import asyncio
import unittest

from bridge.hardware_link import HardwareLink


class TestHardwareLinkAutoFallback(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_starts_mock_task(self):
        queue: asyncio.Queue = asyncio.Queue()
        link = HardwareLink(queue)
        self.assertIsNone(link._mock_task)
        link._on_status_change(False)
        await asyncio.sleep(0)
        self.assertIsNotNone(link._mock_task)
        self.assertFalse(link._mock_task.done())
        link.stop()

    async def test_reconnect_stops_mock_task(self):
        queue: asyncio.Queue = asyncio.Queue()
        link = HardwareLink(queue)
        link._on_status_change(False)
        await asyncio.sleep(0)
        mock_task = link._mock_task
        self.assertIsNotNone(mock_task)
        link._on_status_change(True)
        self.assertIsNone(link._mock_task)
        await asyncio.sleep(0)
        self.assertTrue(mock_task.cancelled() or mock_task.cancelling() > 0)

    async def test_repeated_disconnect_does_not_duplicate_task(self):
        queue: asyncio.Queue = asyncio.Queue()
        link = HardwareLink(queue)
        link._on_status_change(False)
        await asyncio.sleep(0)
        first = link._mock_task
        link._on_status_change(False)
        await asyncio.sleep(0)
        self.assertIs(link._mock_task, first)
        link.stop()

    async def test_force_mock_starts_synthetic_performer_without_serial(self):
        queue: asyncio.Queue = asyncio.Queue()
        link = HardwareLink(queue)
        link.start(asyncio.get_running_loop(), port="COM_NOPE", baud=115200,
                  force_mock=True, disable=False)
        await asyncio.sleep(0)
        self.assertIsNotNone(link._mock_task)
        link.stop()

    async def test_disable_starts_nothing(self):
        queue: asyncio.Queue = asyncio.Queue()
        link = HardwareLink(queue)
        link.start(asyncio.get_running_loop(), port="COM_NOPE", baud=115200,
                  force_mock=False, disable=True)
        await asyncio.sleep(0)
        self.assertIsNone(link._mock_task)
        self.assertIsNone(link._serial_thread)


if __name__ == "__main__":
    unittest.main()
