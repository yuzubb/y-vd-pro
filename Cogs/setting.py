import discord
from discord.ext import commands
from discord import app_commands

from Cogs import db
from Cogs.utils import is_allowed


class SettingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="許可ユーザー追加", description="管理コマンドを使えるユーザーを追加します")
    @app_commands.describe(user="追加するユーザー")
    @is_allowed()
    async def add_allowed_user(self, interaction: discord.Interaction, user: discord.User):
        if db.is_user_allowed(user.id):
            await interaction.response.send_message(f"🚫 {user.mention} は既に許可ユーザーリストに含まれています。", ephemeral=True)
        else:
            db.grant_permission(user.id, granted_by=interaction.user.id)
            await interaction.response.send_message(f"✅ {user.mention} を許可ユーザーリストに追加しました。", ephemeral=True)

    @app_commands.command(name="許可ユーザー削除", description="許可ユーザーリストからユーザーを削除します")
    @app_commands.describe(user="削除するユーザー")
    @is_allowed()
    async def remove_allowed_user(self, interaction: discord.Interaction, user: discord.User):
        if db.is_user_allowed(user.id):
            db.revoke_permission(user.id)
            await interaction.response.send_message(f"✅ {user.mention} を許可ユーザーリストから削除しました。", ephemeral=True)
        else:
            await interaction.response.send_message(f"🚫 {user.mention} は許可ユーザーリストに含まれていません。", ephemeral=True)


async def setup(bot):
    await bot.add_cog(SettingCog(bot))
