from __future__ import annotations

import unittest

from tetherly.discord_bot import (
    _DISPATCH_BUTTONS,
    _DISCORD_KEY_ALIASES,
    components_for_intent,
    components_for_status,
    components_for_tail,
)
from tetherly.telegram_bot import MessageIntent


def _all_custom_ids(rows) -> list[str]:
    return [
        button["custom_id"]
        for row in rows
        for button in row.get("components", [])
    ]


class ComponentsForIntentTest(unittest.TestCase):
    def test_plain_intent_has_no_components(self) -> None:
        self.assertIsNone(components_for_intent(MessageIntent.PLAIN))

    def test_stop_intent_offers_enter_tail_ctrlc(self) -> None:
        rows = components_for_intent(MessageIntent.STOP)
        self.assertIsNotNone(rows)
        ids = _all_custom_ids(rows)
        self.assertIn("tetherly:key:enter", ids)
        self.assertIn("tetherly:tail", ids)
        self.assertIn("tetherly:key:ctrl-c", ids)

    def test_permission_intent_offers_yes_no_tail(self) -> None:
        rows = components_for_intent(MessageIntent.PERMISSION)
        self.assertIsNotNone(rows)
        ids = _all_custom_ids(rows)
        self.assertIn("tetherly:key:enter", ids)  # Yes
        self.assertIn("tetherly:key:ctrl-c", ids)  # No
        self.assertIn("tetherly:tail", ids)


class StatusTailComponentsTest(unittest.TestCase):
    def test_status_components_have_refresh_and_keys(self) -> None:
        ids = _all_custom_ids(components_for_status())
        self.assertIn("tetherly:status", ids)
        self.assertIn("tetherly:tail", ids)
        self.assertIn("tetherly:key:enter", ids)
        self.assertIn("tetherly:key:ctrl-c", ids)

    def test_tail_components_have_refresh_and_keys(self) -> None:
        ids = _all_custom_ids(components_for_tail())
        self.assertIn("tetherly:tail", ids)
        self.assertIn("tetherly:key:enter", ids)
        self.assertIn("tetherly:key:ctrl-c", ids)


class CustomIdLengthTest(unittest.TestCase):
    """Discord caps custom_id at 100 bytes — make sure all our values fit."""

    def test_all_custom_ids_under_100_bytes(self) -> None:
        bundles = [
            components_for_intent(MessageIntent.STOP),
            components_for_intent(MessageIntent.PERMISSION),
            components_for_status(),
            components_for_tail(),
        ]
        for rows in bundles:
            if rows is None:
                continue
            for cid in _all_custom_ids(rows):
                self.assertLessEqual(len(cid.encode("utf-8")), 100, cid)


class ActionRowSizeTest(unittest.TestCase):
    """Each ActionRow can hold at most 5 buttons."""

    def test_action_rows_within_button_cap(self) -> None:
        bundles = [
            components_for_intent(MessageIntent.STOP),
            components_for_intent(MessageIntent.PERMISSION),
            components_for_status(),
            components_for_tail(),
        ]
        for rows in bundles:
            if rows is None:
                continue
            for row in rows:
                self.assertEqual(row["type"], 1)
                self.assertLessEqual(len(row.get("components", [])), 5)


class DispatchTableTest(unittest.TestCase):
    """Every custom_id we emit must be in the persistent dispatcher's button table."""

    def test_dispatch_covers_all_emitted_custom_ids(self) -> None:
        emitted: set[str] = set()
        for rows in (
            components_for_intent(MessageIntent.STOP),
            components_for_intent(MessageIntent.PERMISSION),
            components_for_status(),
            components_for_tail(),
        ):
            if rows is None:
                continue
            for cid in _all_custom_ids(rows):
                emitted.add(cid)
        for cid in emitted:
            self.assertIn(cid, _DISPATCH_BUTTONS, cid)


class KeyAliasTest(unittest.TestCase):
    def test_aliases_match_telegram(self) -> None:
        self.assertEqual(_DISCORD_KEY_ALIASES["enter"], "enter")
        self.assertEqual(_DISCORD_KEY_ALIASES["esc"], "esc")
        self.assertEqual(_DISCORD_KEY_ALIASES["ctrlc"], "ctrl-c")
        self.assertEqual(_DISCORD_KEY_ALIASES["ctrld"], "ctrl-d")
        self.assertEqual(_DISCORD_KEY_ALIASES["tab"], "tab")


if __name__ == "__main__":
    unittest.main()
