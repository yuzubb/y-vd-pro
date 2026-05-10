import discord
from discord.ext import commands

from Cogs.db import (
    add_allowed_user,
    get_allowed_users,
    is_allowed_user,
    save_paypay_account,
    get_paypay_account
)


class AccountVending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # 権限付与
    # =====================================================

    @commands.hybrid_command(name="権限付与")
    async def grant_permission(self, ctx, user: discord.User):
        try:
            ok = add_allowed_user(
                discord_id=user.id,
                granted_by=ctx.author.id,
                memo="discord command"
            )

            if ok:
                embed = discord.Embed(
                    title="✅ 権限付与",
                    description=f"{user.mention} にBot使用権限を付与しました",
                    color=0x00ff88
                )
            else:
                embed = discord.Embed(
                    title="❌ エラー",
                    description="Supabase保存に失敗しました",
                    color=0xff0000
                )

            await ctx.reply(embed=embed)

        except Exception as e:
            await ctx.reply(f"エラー: {e}")

    # =====================================================
    # 権限一覧
    # =====================================================

    @commands.hybrid_command(name="権限一覧")
    async def permission_list(self, ctx):
        try:
            users = get_allowed_users()

            if len(users) == 0:
                embed = discord.Embed(
                    title="権限一覧",
                    description="権限を持つユーザーはいません",
                    color=0x3498db
                )

                return await ctx.reply(embed=embed)

            text = ""

            for u in users:
                text += f"<@{u['discord_id']}>\n"

            embed = discord.Embed(
                title="権限一覧",
                description=text,
                color=0x3498db
            )

            await ctx.reply(embed=embed)

        except Exception as e:
            await ctx.reply(f"エラー: {e}")

    # =====================================================
    # Token Login
    # =====================================================

    @commands.hybrid_command(name="tokenlogin")
    async def token_login(self, ctx, access_token: str):
        try:
            uuid = f"token_{ctx.author.id}"

            ok = save_paypay_account(
                discord_user_id=ctx.author.id,
                phone="TOKEN_LOGIN",
                password="TOKEN_LOGIN",
                uuid=uuid,
                access_token=access_token
            )

            if ok:
                embed = discord.Embed(
                    title="✅ Token Login",
                    description="AccessTokenを保存しました",
                    color=0x00ff88
                )
            else:
                embed = discord.Embed(
                    title="❌ エラー",
                    description="AccessToken保存失敗",
                    color=0xff0000
                )

            await ctx.reply(embed=embed)

        except Exception as e:
            await ctx.reply(f"エラー: {e}")

    # =====================================================
    # ログイン確認
    # =====================================================

    @commands.hybrid_command(name="logincheck")
    async def login_check(self, ctx):
        try:
            account = get_paypay_account(ctx.author.id)

            if not account:
                return await ctx.reply("PayPayアカウント未登録")

            text = f"""
Discord ID: {account['discord_id']}
UUID: {account['uuid']}
AccessToken: {'あり' if account.get('access_token') else 'なし'}
"""

            embed = discord.Embed(
                title="PayPay Login Info",
                description=text,
                color=0x3498db
            )

            await ctx.reply(embed=embed)

        except Exception as e:
            await ctx.reply(f"エラー: {e}")


async def setup(bot):
    await bot.add_cog(AccountVending(bot))
