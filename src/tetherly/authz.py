from __future__ import annotations

from dataclasses import dataclass

import discord


@dataclass(frozen=True)
class AccessController:
    allowed_guild_ids: set[int]
    allowed_role_ids: set[int]
    allowed_user_ids: set[int]

    def is_allowed_user(
        self,
        guild_id: int | None,
        user: object,
        *,
        chat_trusted: bool = False,
    ) -> bool:
        if self.allowed_guild_ids and guild_id not in self.allowed_guild_ids:
            return False
        if chat_trusted:
            return True
        user_id = getattr(user, "id", None)
        if user_id in self.allowed_user_ids:
            return True
        if not self.allowed_role_ids:
            return user_id in self.allowed_user_ids
        if isinstance(user, discord.Member):
            role_ids = {role.id for role in user.roles}
            return bool(role_ids & self.allowed_role_ids)
        return False

    def is_allowed(
        self,
        interaction: discord.Interaction,
        *,
        chat_trusted: bool = False,
    ) -> bool:
        return self.is_allowed_user(
            interaction.guild_id, interaction.user, chat_trusted=chat_trusted
        )

    def is_privileged(self, user_id: int | None) -> bool:
        """True only for users on the env-level user allowlist.

        Used to gate commands that grant access to others (e.g. flipping
        trust_chat on). chat-membership trust must NOT bootstrap itself.
        """
        return user_id is not None and user_id in self.allowed_user_ids

    async def assert_allowed(
        self,
        interaction: discord.Interaction,
        *,
        chat_trusted: bool = False,
    ) -> bool:
        if self.is_allowed(interaction, chat_trusted=chat_trusted):
            return True
        await interaction.response.send_message(
            "You are not allowed to use this command.",
            ephemeral=True,
        )
        return False
