import discord
from discord import app_commands, ui
from discord.ext import commands
import time
import uuid
from Cogs.utils import load_items, is_allowed
from Cogs.nyanko_editor import CloudEditor
import Cogs.db as db
import paypayu

class ProductSelectDropdown(ui.Select):
    def __init__(self, items, vending_id, user, guild, bot, offset=0, label_suffix=""):
        self.items = items
        self.vending_id = vending_id
        self.user = user
        self.guild = guild
        self.bot = bot
        self.offset = offset
        options = [
            discord.SelectOption(label=f"{i['name']} (¥{i['price']})", value=str(offset + idx))
            for idx, i in enumerate(items)
        ]
        super().__init__(placeholder=f"アイテムを選択{label_suffix}", min_values=1, max_values=min(25, len(items)), options=options)

    async def callback(self, interaction: discord.Interaction):
        selected = [self.items[int(i) - self.offset] for i in self.values]
        total = sum(i['price'] for i in selected)
        items_data = [{'name': i['name'], 'price': i['price'], 'quantity': 1, 'subtotal': i['price']} for i in selected]
        
        embed = discord.Embed(title="注文確認", color=0x2ecc71)
        embed.add_field(name="合計金額", value=f"¥{total}", inline=False)
        
        view = ui.View()
        async def buy_cb(it):
            await it.response.send_modal(PayPayModal(items_data, total, self.user, self.guild, self.bot, self.vending_id))
        
        btn = ui.Button(label="購入する", style=discord.ButtonStyle.success)
        btn.callback = buy_cb
        view.add_item(btn)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class PayPayModal(ui.Modal, title="支払い・引継ぎコード入力"):
    paypay_link = ui.TextInput(label="PayPayリンク", placeholder="https://pay.paypay.ne.jp/...", required=True)
    transfer_code = ui.TextInput(label="引継ぎコード", required=True)
    pin = ui.TextInput(label="PIN", required=True)

    def __init__(self, selected_items, total_price, user, guild, bot, vending_id):
        super().__init__()
        self.items = selected_items
        self.total = total_price
        self.user = user # 購入者
        self.guild = guild
        self.bot = bot
        self.vending_id = vending_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            p_info = await paypayu.check_link(self.paypay_link.value)
            amount = p_info.get("payload", {}).get("message", {}).get("data", {}).get("amount")
            if amount is None or amount < self.total:
                return await interaction.followup.send("金額が不足しています", ephemeral=True)

            # ✅ 設置者のPayPayアカウントを取得
            vm = db.get_vending_machine(self.vending_id)
            owner_acc = db.get_paypay_account(int(vm['owner_id']))
            if not owner_acc:
                return await interaction.followup.send("設置者のPayPayが登録されていません", ephemeral=True)

            # ✅ 設置者のアカウントで受け取り
            result = await paypayu.link_rev(self.paypay_link.value, owner_acc["phone"], owner_acc["password"], owner_acc["uuid"])
            if result != True:
                return await interaction.followup.send("受け取りに失敗しました", ephemeral=True)

            # 代行処理
            editor = CloudEditor(self.transfer_code.value, self.pin.value, self.user, self.guild.id, modifications=self.items)
            if not editor.download_save():
                return await interaction.followup.send("引継ぎコードが違います", ephemeral=True)
            
            editor.apply_modifications()
            new_code, new_pin = editor.upload_save()

            if new_code:
                db.record_sale(self.vending_id, self.user.id, self.user.name, self.items, self.total)
                
                # ✅ 購入者(self.user)だけにDM
                dm = discord.Embed(title="✅ 代行完了", color=0x2ecc71)
                dm.add_field(name="新コード", value=f"`{new_code}`")
                dm.add_field(name="PIN", value=f"`{new_pin}`")
                try:
                    await self.user.send(embed=dm)
                except:
                    pass
                await interaction.followup.send("完了。DMを確認してください", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"エラー: {e}", ephemeral=True)

class VendingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="自販機", description="自販機を起動")
    async def vending_machine(self, interaction: discord.Interaction, vending_id: str):
        vm = db.get_vending_machine(vending_id)
        if not vm: return await interaction.response.send_message("自販機不明", ephemeral=True)
        
        items = load_items()
        all_items = items['menu1'] + items['menu2'] + vm.get('custom_items', [])
        
        view = ui.View()
        mid = len(all_items) // 2
        view.add_item(ProductSelectDropdown(all_items[:mid], vending_id, interaction.user, interaction.guild, self.bot, 0, "(1)"))
        if all_items[mid:]:
            view.add_item(ProductSelectDropdown(all_items[mid:], vending_id, interaction.user, interaction.guild, self.bot, mid, "(2)"))
        
        await interaction.response.send_message(embed=discord.Embed(title=vm['name']), view=view)

async def setup(bot):
    await bot.add_cog(VendingCog(bot))
