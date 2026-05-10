"""
権限管理 Cog
- 管理者が手動で権限を付与・剥奪
- ユーザーがPayPayで権限を購入
- Supabaseに保存するため再起動後も永続
"""
import discord
from discord import app_commands, ui
from discord.ext import commands
from Cogs.db import (
    is_admin, add_admin, remove_admin,
    grant_permission, revoke_permission, list_allowed_users,
    get_paypay_account, get_permission_price, set_permission_price
)
import paypayu


# ────────────── 権限購入モーダル ──────────────

class PermissionBuyModal(ui.Modal, title="権限購入 - PayPay支払い"):
    paypay_link = ui.TextInput(
        label="PayPayリンク",
        placeholder="https://pay.paypay.ne.jp/...",
        required=True
    )

    def __init__(self, price: int, owner_id: int, bot):
        super().__init__()
        self.price = price
        self.owner_id = owner_id
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not self.paypay_link.value.startswith("https://pay.paypay.ne.jp/"):
            return await interaction.followup.send(
                embed=discord.Embed(title="❌ エラー", description="有効なPayPayリンクを入力してください", color=0xff0000),
                ephemeral=True
            )

        await interaction.followup.send(
            embed=discord.Embed(title="🔄 処理中", description="PayPayリンクを確認中...", color=0xFFB700),
            ephemeral=True
        )

        # リンク確認
        payment_info = await paypayu.check_link(self.paypay_link.value)
        if not payment_info:
            return await interaction.followup.send(
                embed=discord.Embed(title="❌ エラー", description="有効なPayPayリンクではありません", color=0xff0000),
                ephemeral=True
            )

        amount = payment_info.get("payload", {}).get("message", {}).get("data", {}).get("amount")
        if amount is None or amount < self.price:
            return await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ 金額不足",
                    description=f"必要金額: ¥{self.price}\n送信金額: ¥{amount or 0}",
                    color=0xff0000
                ),
                ephemeral=True
            )

        # オーナーのPayPayアカウントで受け取り
        owner_account = get_paypay_account(self.owner_id)
        if not owner_account:
            return await interaction.followup.send(
                embed=discord.Embed(title="❌ エラー", description="オーナーのPayPayアカウントが登録されていません", color=0xff0000),
                ephemeral=True
            )

        result = await paypayu.link_rev(
            self.paypay_link.value,
            owner_account["phone"],
            owner_account["password"],
            owner_account["uuid"]
        )

        if result != True:
            return await interaction.followup.send(
                embed=discord.Embed(title="❌ 受け取り失敗", description="PayPayリンクが無効か期限切れです", color=0xff0000),
                ephemeral=True
            )

        # 権限付与
        grant_permission(interaction.user.id, granted_by=self.owner_id, memo=f"PayPay購入 ¥{self.price}")

        embed = discord.Embed(
            title="✅ 権限購入完了",
            description=f"¥{self.price} の支払いが確認されました。\nBotの使用権限が付与されました！",
            color=0x2ecc71
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

        # オーナーに通知
        try:
            owner = await self.bot.fetch_user(self.owner_id)
            notify = discord.Embed(
                title="💰 権限購入通知",
                description=f"{interaction.user.mention} (`{interaction.user.id}`) が権限を購入しました\n金額: ¥{self.price}",
                color=0x2ecc71
            )
            await owner.send(embed=notify)
        except:
            pass


# ────────────── Cog ──────────────

class PermissionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── 権限付与（オーナー・管理者用）──

    @app_commands.command(name="権限付与", description="ユーザーにBot使用権限を付与します（管理者のみ）")
    @app_commands.describe(user="権限を付与するユーザー", memo="メモ（任意）")
    async def grant_perm(self, interaction: discord.Interaction, user: discord.User, memo: str = None):
        if not await interaction.client.is_owner(interaction.user) and not is_admin(interaction.user.id):
            return await interaction.response.send_message(
                embed=discord.Embed(title="❌ 権限なし", description="このコマンドは管理者のみ使用できます", color=0xff0000),
                ephemeral=True
            )

        grant_permission(user.id, granted_by=interaction.user.id, memo=memo)

        embed = discord.Embed(
            title="✅ 権限付与",
            description=f"{user.mention} にBot使用権限を付与しました",
            color=0x2ecc71
        )
        if memo:
            embed.add_field(name="メモ", value=memo, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="権限剥奪", description="ユーザーのBot使用権限を剥奪します（管理者のみ）")
    @app_commands.describe(user="権限を剥奪するユーザー")
    async def revoke_perm(self, interaction: discord.Interaction, user: discord.User):
        if not await interaction.client.is_owner(interaction.user) and not is_admin(interaction.user.id):
            return await interaction.response.send_message(
                embed=discord.Embed(title="❌ 権限なし", description="このコマンドは管理者のみ使用できます", color=0xff0000),
                ephemeral=True
            )

        revoke_permission(user.id)

        embed = discord.Embed(
            title="✅ 権限剥奪",
            description=f"{user.mention} の使用権限を剥奪しました",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="権限一覧", description="使用権限を持つユーザーの一覧を表示（管理者のみ）")
    async def list_perms(self, interaction: discord.Interaction):
        if not await interaction.client.is_owner(interaction.user) and not is_admin(interaction.user.id):
            return await interaction.response.send_message(
                embed=discord.Embed(title="❌ 権限なし", description="このコマンドは管理者のみ使用できます", color=0xff0000),
                ephemeral=True
            )

        users = list_allowed_users()
        if not users:
            embed = discord.Embed(title="権限一覧", description="権限を持つユーザーはいません", color=0x3498db)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        lines = []
        for u in users:
            memo = f" ({u['memo']})" if u.get("memo") else ""
            lines.append(f"<@{u['discord_id']}>{memo}")

        embed = discord.Embed(
            title=f"権限一覧（{len(users)}人）",
            description="\n".join(lines),
            color=0x3498db
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── 管理者管理（オーナーのみ）──

    @app_commands.command(name="管理者追加", description="管理者を追加します（オーナーのみ）")
    @app_commands.describe(user="管理者にするユーザー")
    async def add_admin_cmd(self, interaction: discord.Interaction, user: discord.User):
        if not await interaction.client.is_owner(interaction.user):
            return await interaction.response.send_message("このコマンドはオーナーのみ使用できます", ephemeral=True)

        add_admin(user.id)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ 管理者追加", description=f"{user.mention} を管理者に追加しました", color=0x2ecc71),
            ephemeral=True
        )

    @app_commands.command(name="管理者削除", description="管理者を削除します（オーナーのみ）")
    @app_commands.describe(user="削除するユーザー")
    async def remove_admin_cmd(self, interaction: discord.Interaction, user: discord.User):
        if not await interaction.client.is_owner(interaction.user):
            return await interaction.response.send_message("このコマンドはオーナーのみ使用できます", ephemeral=True)

        remove_admin(user.id)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ 管理者削除", description=f"{user.mention} を管理者から削除しました", color=0x2ecc71),
            ephemeral=True
        )

    # ── 権限購入（一般ユーザー）──

    @app_commands.command(name="権限購入", description="PayPayでBot使用権限を購入します")
    async def buy_permission(self, interaction: discord.Interaction):
        price = get_permission_price()
        owner_id = self.bot.owner_id

        embed = discord.Embed(
            title="🛒 Bot使用権限の購入",
            description=(
                f"このBotを利用するには使用権限の購入が必要です。\n\n"
                f"**価格: ¥{price}**\n\n"
                f"PayPayで上記金額を送金し、リンクを入力してください。\n"
                f"確認後、即時に権限が付与されます。"
            ),
            color=0xFFB700
        )

        view = ui.View()

        async def buy_cb(it):
            await it.response.send_modal(PermissionBuyModal(price, owner_id, self.bot))

        btn = ui.Button(label=f"¥{price} で購入する", style=discord.ButtonStyle.success, emoji="💳")
        btn.callback = buy_cb
        view.add_item(btn)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ── 権限価格設定（オーナーのみ）──

    @app_commands.command(name="権限価格設定", description="権限購入価格を設定します（オーナーのみ）")
    @app_commands.describe(price="新しい価格（円）")
    async def set_price(self, interaction: discord.Interaction, price: int):
        if not await interaction.client.is_owner(interaction.user):
            return await interaction.response.send_message("このコマンドはオーナーのみ使用できます", ephemeral=True)

        if price < 1:
            return await interaction.response.send_message("1円以上の価格を設定してください", ephemeral=True)

        set_permission_price(price)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="✅ 価格更新",
                description=f"権限購入価格を **¥{price}** に設定しました",
                color=0x2ecc71
            ),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(PermissionCog(bot))
