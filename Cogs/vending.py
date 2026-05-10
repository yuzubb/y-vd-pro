import discord
from discord import app_commands, ui
from discord.ext import commands
import time
import uuid
from Cogs.utils import load_items, is_allowed
from Cogs.nyanko_editor import CloudEditor
import Cogs.db as db # db.pyを読み込む
import paypayu

class PayPayModal(ui.Modal, title="支払い・引継ぎコード入力"):
    paypay_link = ui.TextInput(label="PayPayリンク *", placeholder="https://pay.paypay.ne.jp/...", required=True)
    transfer_code = ui.TextInput(label="引継ぎコード *", placeholder="引継ぎコード", required=True)
    pin = ui.TextInput(label="PIN *", placeholder="PIN", required=True)

    def __init__(self, selected_items, total_price, user, guild, bot, vending_id):
        super().__init__()
        self.selected_items = selected_items
        self.total_price = total_price
        self.user = user # 購入ユーザー
        self.guild = guild
        self.bot = bot
        self.vending_id = vending_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            payment_info = await paypayu.check_link(self.paypay_link.value)
            amount = payment_info.get("payload", {}).get("message", {}).get("data", {}).get("amount")
            if amount is None or amount < self.total_price:
                return await interaction.followup.send("金額が不足しています", ephemeral=True)

            # --- 設置者（オーナー）のPayPayで受け取り ---
            vm_data = db.get_vending_machine(self.vending_id)
            owner_id = int(vm_data['owner_id'])
            owner_account = db.get_paypay_account(owner_id) # 設置者のアカウントを取得
            
            if not owner_account:
                return await interaction.followup.send("設置者のPayPayアカウントが見つかりません", ephemeral=True)

            result = await paypayu.link_rev(
                self.paypay_link.value,
                owner_account["phone"],
                owner_account["password"],
                owner_account["uuid"]
            )

            if result != True:
                return await interaction.followup.send("受け取りに失敗しました", ephemeral=True)

            # --- 処理実行 ---
            editor = CloudEditor(self.transfer_code.value, self.pin.value, self.user, self.guild.id, modifications=self.selected_items)
            if not editor.download_save():
                return await interaction.followup.send("引継ぎコードが正しくありません", ephemeral=True)
            
            editor.apply_modifications()
            new_code, new_pin = editor.upload_save()

            if new_code and new_pin:
                db.record_sale(self.vending_id, self.user.id, str(self.user.name), self.selected_items, self.total_price)
                
                # --- 購入者本人にDM送信 ---
                dm_embed = discord.Embed(title="✅ 代行完了", color=0x2ecc71)
                dm_embed.add_field(name="新しいコード", value=f"`{new_code}`", inline=False)
                dm_embed.add_field(name="PIN", value=f"`{new_pin}`", inline=False)
                
                try:
                    await self.user.send(embed=dm_embed) # 購入者本人(self.user)に送る
                except discord.Forbidden:
                    pass # DM拒否の場合は無視

                await interaction.followup.send("完了しました。DMをご確認ください。", ephemeral=True)
                
                # ロール付与などの事後処理... (省略)
        except Exception as e:
            await interaction.followup.send(f"エラー: {e}", ephemeral=True)

# ※ VendingCog内の vending_machine コマンドの型エラー箇所も db.py の修正により解消されます。
