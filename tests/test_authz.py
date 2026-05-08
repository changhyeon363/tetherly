from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from tetherly.authz import AccessController


class AccessControllerTest(unittest.TestCase):
    def test_rejects_user_from_unlisted_guild(self) -> None:
        controller = AccessController(
            allowed_guild_ids={100},
            allowed_role_ids=set(),
            allowed_user_ids={200},
        )
        interaction = SimpleNamespace(
            guild_id=999,
            user=SimpleNamespace(id=200),
        )

        self.assertFalse(controller.is_allowed(interaction))

    def test_allows_listed_user_in_listed_guild(self) -> None:
        controller = AccessController(
            allowed_guild_ids={100},
            allowed_role_ids=set(),
            allowed_user_ids={200},
        )
        interaction = SimpleNamespace(
            guild_id=100,
            user=SimpleNamespace(id=200),
        )

        self.assertTrue(controller.is_allowed(interaction))

    def test_allows_matching_role_in_listed_guild(self) -> None:
        controller = AccessController(
            allowed_guild_ids={100},
            allowed_role_ids={300},
            allowed_user_ids=set(),
        )
        class FakeMember:
            def __init__(self) -> None:
                self.id = 200
                self.roles = [SimpleNamespace(id=300)]

        interaction = SimpleNamespace(guild_id=100, user=FakeMember())

        with mock.patch("tetherly.authz.discord.Member", FakeMember):
            self.assertTrue(controller.is_allowed(interaction))

    def test_is_allowed_user_supports_message_author(self) -> None:
        controller = AccessController(
            allowed_guild_ids={100},
            allowed_role_ids=set(),
            allowed_user_ids={200},
        )

        self.assertTrue(controller.is_allowed_user(100, SimpleNamespace(id=200)))

    def test_chat_trusted_admits_unlisted_user(self) -> None:
        controller = AccessController(
            allowed_guild_ids={100},
            allowed_role_ids=set(),
            allowed_user_ids={200},
        )
        interaction = SimpleNamespace(guild_id=100, user=SimpleNamespace(id=999))
        self.assertFalse(controller.is_allowed(interaction))
        self.assertTrue(controller.is_allowed(interaction, chat_trusted=True))

    def test_chat_trusted_still_blocked_by_guild_allowlist(self) -> None:
        controller = AccessController(
            allowed_guild_ids={100},
            allowed_role_ids=set(),
            allowed_user_ids={200},
        )
        interaction = SimpleNamespace(guild_id=999, user=SimpleNamespace(id=999))
        self.assertFalse(controller.is_allowed(interaction, chat_trusted=True))

    def test_is_privileged_excludes_role_only_users(self) -> None:
        controller = AccessController(
            allowed_guild_ids={100},
            allowed_role_ids={300},
            allowed_user_ids={200},
        )
        self.assertTrue(controller.is_privileged(200))
        self.assertFalse(controller.is_privileged(999))
        self.assertFalse(controller.is_privileged(None))


if __name__ == "__main__":
    unittest.main()
