from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from co_agent.authz import AccessController


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

        with mock.patch("co_agent.authz.discord.Member", FakeMember):
            self.assertTrue(controller.is_allowed(interaction))

    def test_is_allowed_user_supports_message_author(self) -> None:
        controller = AccessController(
            allowed_guild_ids={100},
            allowed_role_ids=set(),
            allowed_user_ids={200},
        )

        self.assertTrue(controller.is_allowed_user(100, SimpleNamespace(id=200)))


if __name__ == "__main__":
    unittest.main()
