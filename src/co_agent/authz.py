from __future__ import annotations

from dataclasses import dataclass

import discord


@dataclass(frozen=True)
class AccessController:
    allowed_guild_ids: set[int]
    allowed_role_ids: set[int]
    allowed_user_ids: set[int]

    def is_allowed(self, interaction: discord.Interaction) -> bool:
        guild_id = interaction.guild_id
        if self.allowed_guild_ids and guild_id not in self.allowed_guild_ids:
            return False
        user = interaction.user
        if user.id in self.allowed_user_ids:
            return True
        if not self.allowed_role_ids:
            return user.id in self.allowed_user_ids
        if isinstance(user, discord.Member):
            role_ids = {role.id for role in user.roles}
            return bool(role_ids & self.allowed_role_ids)
        return False

    async def assert_allowed(self, interaction: discord.Interaction) -> bool:
        if self.is_allowed(interaction):
            return True
        await interaction.response.send_message(
            "You are not allowed to use this command.",
            ephemeral=True,
        )
        return False
