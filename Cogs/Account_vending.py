import discord
from discord.ext import commands

from Cogs.db import (
    save_paypay_account,
    get_paypay_account
)


class AccountVending(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
