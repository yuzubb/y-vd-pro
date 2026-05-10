import discord
from discord.ext import commands
from discord import app_commands, ui
import json
import uuid
import io
import random
from Cogs.utils import is_allowed
from Cogs import db
import paypayu


# ────────────── オートコンプリート ──────────────

async def vending_machine_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    vending_data = db.get_all_vending_machines()
    user_id_str = str(interaction.user.id)

    return [
        app_commands.Choice(name=vm_data.get("name", "名称未設定"), value=vm_id)
        for vm_id, vm_data in vending_data.items()
        if vm_data.get("owner_id") == user_id_str
        and current.lower() in vm_data.get("name", "").lower()
    ]


async def coupon_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    coupon_data = db.get_coupons_by_owner(interaction.user.id)
    vending_data = db.get_all_vending_machines()

    choices = []
    for coupon_code, coupon_info in coupon_data.items():
        if current.lower() in coupon_code.lower():
            discount = coupon_info.get("discount", 0)
            vm_id = coupon_info.get("vending_machine_id", "")
            vm_name = vending_data.get(vm_id, {}).get("name", "不明") if vm_id else "不明"
            choices.append(app_commands.Choice(
                name=f"{coupon_code} (-{discount}円) [{vm_name}]",
                value=coupon_code
            ))
    return choices[:25]


async def role_assignment_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    vending_data = db.get_all_vending_machines()
    choices = []
    for vm_id, vm_data in vending_data.items():
        if vm_data.get("owner_id") == str(interaction.user.id):
            vm_name = vm_data.get("name", "不明な自販機")
            if current.lower() in vm_name.lower():
                choices.append(app_commands.Choice(name=vm_name, value=vm_id))
    return choices[:25]


async def handle_error(interaction: discord.Interaction, error: Exception, ephemeral: bool = True):
    try:
        embed = discord.Embed(
            title="エラーが発生しました",
            description=f"```{str(error)}```",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="Developer @yuzu09591")
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
    except:
        print(f"Error sending error message: {error}")


async def check_stock(interaction: discord.Interaction, products: list):
    embed = discord.Embed(
        title="在庫・販売数情報",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text="Developer @yuzu09591")

    if not products:
        embed.description = "この自販機には商品が登録されていません。"
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    for product in products:
        product_name = product.get("name", "不明")
        sales_count = product.get("sales_count", 0)

        if product.get("infinite_stock"):
            embed.add_field(
                name=product_name,
                value=f"```在庫数: ∞個\n販売数: {sales_count}個```",
                inline=False
            )
        else:
            product_id = product.get("product_id")
            stock_count = db.count_stock(product_id) if product_id else 0
            embed.add_field(
                name=product_name,
                value=f"```在庫数: {stock_count}個\n販売数: {sales_count}個```",
                inline=False
            )

    await interaction.followup.send(embed=embed, ephemeral=True)


class VendingMachineCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Cogロード時に永続化Viewを復元"""
        vending_data = db.get_all_vending_machines()

        for vm_id in vending_data.keys():
            view = VendingMachineCog.VendingMachineView(vm_id, self.bot)
            self.bot.add_view(view)

        all_products = []
        for vm_data in vending_data.values():
            all_products.extend(vm_data.get("products", []))

        if all_products:
            self.bot.add_view(VendingMachineCog.ProductSelectViewForStock(all_products))
            self.bot.add_view(VendingMachineCog.WithdrawStockView(all_products, 1))
            self.bot.add_view(VendingMachineCog.ContentView(all_products))

    # ────────────── コマンド ──────────────

    @app_commands.command(name="自販機作成", description="自販機を作成します")
    @is_allowed()
    @app_commands.describe(name="自販機の名前")
    async def vm_create(self, interaction: discord.Interaction, name: str):
        user_id = str(interaction.user.id)
        new_vm_id = str(uuid.uuid4())
        paypay = db.get_paypay_account(interaction.user.id)
        paypay_id = user_id if paypay else None

        db.create_vending_machine(new_vm_id, name, interaction.user.id, paypay_id)

        if paypay_id:
            await interaction.response.send_message(
                f"自販機「{name}」を作成しました。\n**自販機ID:** `{new_vm_id}`", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"自販機「{name}」を作成しました。\n**自販機ID:** `{new_vm_id}`\nPayPayアカウントが未登録です。`/paypay登録` を実行してください。", ephemeral=True)

    @app_commands.command(name="公開ログ設定", description="公開販売ログを送信するチャンネルを設定します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    @app_commands.describe(vending_machine_id="自販機", channel="ログを送信するチャンネル")
    async def vm_set_log(self, interaction: discord.Interaction, vending_machine_id: str, channel: discord.TextChannel):
        vm = db.get_vending_machine(vending_machine_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません。", ephemeral=True)
        db.update_vending_machine(vending_machine_id, log_channel_id=str(channel.id))
        await interaction.response.send_message(f"自販機「{vm['name']}」のログチャンネルを {channel.mention} に設定しました。", ephemeral=True)

    @app_commands.command(name="非公開ログ設定", description="非公開販売ログを送信するチャンネルを設定します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    @app_commands.describe(vending_machine_id="自販機", channel="ログを送信するチャンネル")
    async def vm_set_private_log(self, interaction: discord.Interaction, vending_machine_id: str, channel: discord.TextChannel):
        vm = db.get_vending_machine(vending_machine_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません。", ephemeral=True)
        db.update_vending_machine(vending_machine_id, private_log_channel_id=str(channel.id))
        await interaction.response.send_message(f"自販機「{vm['name']}」の非公開ログチャンネルを {channel.mention} に設定しました。", ephemeral=True)

    @app_commands.command(name="商品追加", description="指定した自販機に新しい商品を追加します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    @app_commands.describe(vending_machine_id="商品を登録する自販機", name="商品名", description="商品説明（任意）", price="価格", emoji="商品絵文字")
    async def vm_add_product(self, interaction: discord.Interaction, vending_machine_id: str, name: str, price: int, description: str = None, emoji: str = None):
        vm = db.get_vending_machine(vending_machine_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません。", ephemeral=True)

        product_id = str(uuid.uuid4())
        new_product = {
            "product_id": product_id,
            "name": name,
            "description": description or "",
            "price": price,
            "emoji": emoji,
            "infinite_stock": False,
            "infinite_content": None,
            "sales_count": 0
        }
        products = vm.get("products", [])
        products.append(new_product)
        db.update_vending_machine(vending_machine_id, products=products)
        await interaction.response.send_message(f"自販機「{vm['name']}」に商品「{name}」を追加しました。", ephemeral=True)

    @app_commands.command(name="在庫追加", description="商品の在庫を追加します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    @app_commands.describe(vending_machine_id="自販機", stock_type="在庫タイプ", stock_file="在庫ファイル(txtのみ)")
    @app_commands.choices(stock_type=[
        app_commands.Choice(name="有限", value="finite"),
        app_commands.Choice(name="無限", value="infinite")
    ])
    async def vm_add_stock(self, interaction: discord.Interaction, vending_machine_id: str, stock_type: str, stock_file: discord.Attachment = None):
        if stock_file and not stock_file.filename.endswith(".txt"):
            return await interaction.response.send_message("ファイル形式は.txtのみ対応しています。", ephemeral=True)

        vm = db.get_vending_machine(vending_machine_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません。", ephemeral=True)

        products = vm.get("products")
        if not products:
            return await interaction.response.send_message("在庫を追加できる商品がありません。", ephemeral=True)

        view = VendingMachineCog.ProductSelectViewForStock(products, stock_file, stock_type)
        await interaction.response.send_message("在庫追加を行う商品を選択してください:", view=view, ephemeral=True)

    @app_commands.command(name="自販機設置", description="自販機パネルを設置します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    @app_commands.describe(vending_machine_id="設置する自販機", panel_title="パネルのタイトル", panel_description="パネルの説明文", panel_image="パネルの画像")
    async def vm_setup(self, interaction: discord.Interaction, vending_machine_id: str, panel_title: str = None, panel_description: str = None, panel_image: discord.Attachment = None):
        vm = db.get_vending_machine(vending_machine_id)
        if not vm:
            return await interaction.response.send_message("指定された自販機が見つかりません。", ephemeral=True)

        is_custom = any([panel_title, panel_description, panel_image])
        if is_custom:
            title = panel_title or "自販機"
            description = panel_description or "購入したい商品を下のメニューから選択してください。"
            embed = discord.Embed(title=title, description=description, color=discord.Color.green())
            if panel_image:
                embed.set_image(url=panel_image.url)
        else:
            embed = discord.Embed(title="自販機", description="購入したい商品を下のメニューから選択してください。", color=discord.Color.green())

        embed.set_footer(text="Developer @yuzu09591")
        products = vm.get("products", [])
        if products:
            for p in products:
                price_text = f"```価格: {p.get('price', '未設定')}円```"
                product_description = p.get('description', '').strip()
                value = f"{product_description}{price_text}" if product_description else price_text
                embed.add_field(name=p['name'], value=value, inline=False)
        else:
            if not is_custom:
                embed.description = "```現在、販売中の商品はありません。```"

        view = VendingMachineCog.VendingMachineView(vending_machine_id, self.bot)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="在庫引出", description="商品の在庫を引き出します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    @app_commands.describe(vending_machine_id="自販機", quantity="数量")
    async def vm_withdraw_stock(self, interaction: discord.Interaction, vending_machine_id: str, quantity: int):
        if quantity <= 0:
            return await interaction.response.send_message("引出数量は1以上で指定してください。", ephemeral=True)
        vm = db.get_vending_machine(vending_machine_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません。", ephemeral=True)
        products = vm.get("products")
        if not products:
            return await interaction.response.send_message("引出できる商品がありません。", ephemeral=True)
        view = VendingMachineCog.WithdrawStockView(products, quantity)
        await interaction.response.send_message("在庫引出を行う商品を選択してください:", view=view, ephemeral=True)

    @app_commands.command(name="在庫内容確認", description="商品の在庫内容を確認します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    @app_commands.describe(vending_machine_id="自販機")
    async def vm_check_stock_content(self, interaction: discord.Interaction, vending_machine_id: str):
        vm = db.get_vending_machine(vending_machine_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません。", ephemeral=True)
        products = vm.get("products")
        if not products:
            return await interaction.response.send_message("内容を確認できる商品がありません。", ephemeral=True)
        view = VendingMachineCog.ContentView(products)
        await interaction.response.send_message("在庫内容確認を行う商品を選択してください:", view=view, ephemeral=True)

    @app_commands.command(name="商品削除", description="自販機から商品を完全に削除します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    @app_commands.describe(vending_machine_id="自販機")
    async def vm_delete_product(self, interaction: discord.Interaction, vending_machine_id: str):
        vm = db.get_vending_machine(vending_machine_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません。", ephemeral=True)
        products = vm.get("products")
        if not products:
            return await interaction.response.send_message("削除できる商品がありません。", ephemeral=True)
        view = ui.View(timeout=None)
        view.add_item(VendingMachineCog.ProductSelectForDelete(products))
        await interaction.response.send_message("削除する商品を選択してください:", view=view, ephemeral=True)

    @app_commands.command(name="商品情報変更", description="商品の各情報を変更します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    @app_commands.describe(vending_machine_id="自販機")
    async def vm_edit_product(self, interaction: discord.Interaction, vending_machine_id: str):
        vm = db.get_vending_machine(vending_machine_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません。", ephemeral=True)
        products = vm.get("products")
        if not products:
            return await interaction.response.send_message("情報を変更できる商品がありません。", ephemeral=True)
        view = VendingMachineCog.EditProductView(products, vending_machine_id)
        await interaction.response.send_message("情報を変更する商品を選択してください:", view=view, ephemeral=True)

    @app_commands.command(name="自販機削除", description="自販機を完全に削除します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    @app_commands.describe(vending_machine_id="削除する自販機")
    async def vm_delete(self, interaction: discord.Interaction, vending_machine_id: str):
        try:
            vm = db.get_vending_machine(vending_machine_id)
            if not vm or vm.get("owner_id") != str(interaction.user.id):
                return await interaction.response.send_message("指定された自販機が見つかりません。", ephemeral=True)
            vm_name = vm.get("name", "名称不明")
            view = VendingMachineCog.VendingMachineDeleteConfirmView(vending_machine_id, vm_name)
            embed = discord.Embed(
                title="自販機削除確認",
                description=f"本当に自販機「{vm_name}」を削除しますか？\n\n**この操作は取り消せません。**\n**すべての商品と在庫データも削除されます。**",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="Developer @yuzu09591")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await handle_error(interaction, e)

    @app_commands.command(name="自販機パネル更新", description="自販機パネルを更新します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    @app_commands.describe(vending_machine_id="更新する自販機", message_link="更新するメッセージのリンク",
                           panel_title="パネルのタイトル", panel_description="パネルの説明文", panel_image="パネルの画像")
    async def vm_update(self, interaction: discord.Interaction, vending_machine_id: str, message_link: str,
                        panel_title: str = None, panel_description: str = None, panel_image: discord.Attachment = None):
        await interaction.response.defer(ephemeral=True)
        try:
            vm = db.get_vending_machine(vending_machine_id)
            if not vm or vm.get("owner_id") != str(interaction.user.id):
                return await interaction.followup.send(embed=discord.Embed(title="ERROR", description="指定された自販機が見つかりません。", color=discord.Color.red()), ephemeral=True)

            try:
                link_parts = message_link.replace("https://discord.com/channels/", "").replace("https://discordapp.com/channels/", "")
                guild_id, channel_id, message_id = link_parts.split("/")
                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    return await interaction.followup.send(embed=discord.Embed(title="ERROR", description="指定されたチャンネルが見つかりません。", color=discord.Color.red()), ephemeral=True)
                message = await channel.fetch_message(int(message_id))
                if message.author.id != self.bot.user.id:
                    return await interaction.followup.send(embed=discord.Embed(title="ERROR", description="指定されたメッセージはBOTが送信したものではありません。", color=discord.Color.red()), ephemeral=True)
            except (ValueError, IndexError):
                return await interaction.followup.send(embed=discord.Embed(title="ERROR", description="メッセージリンクの形式が正しくありません。", color=discord.Color.red()), ephemeral=True)

            is_custom = any([panel_title, panel_description, panel_image])
            if is_custom:
                embed = discord.Embed(title=panel_title or "自販機", description=panel_description or "購入したい商品を下のメニューから選択してください。", color=discord.Color.green())
                if panel_image:
                    embed.set_image(url=panel_image.url)
            else:
                embed = discord.Embed(title="自販機", description="購入したい商品を下のメニューから選択してください。", color=discord.Color.green())
            embed.set_footer(text="Developer @yuzu09591")

            for p in vm.get("products", []):
                price_text = f"```価格: {p.get('price', '未設定')}円```"
                product_description = p.get('description', '').strip()
                value = f"{product_description}{price_text}" if product_description else price_text
                embed.add_field(name=p['name'], value=value, inline=False)

            view = VendingMachineCog.VendingMachineView(vending_machine_id, self.bot)
            await message.edit(embed=embed, view=view)
            await interaction.followup.send(embed=discord.Embed(title="更新完了", description=f"自販機「{vm['name']}」のパネルを更新しました。", color=discord.Color.green()), ephemeral=True)
        except Exception as e:
            await handle_error(interaction, e)

    # ────────────── View / Modal ──────────────

    class VendingMachineDeleteConfirmView(ui.View):
        def __init__(self, vending_machine_id: str, vm_name: str):
            super().__init__(timeout=300)
            self.vending_machine_id = vending_machine_id
            self.vm_name = vm_name

        @ui.button(label="削除する", style=discord.ButtonStyle.danger)
        async def confirm_delete(self, interaction, button):
            await interaction.response.defer(ephemeral=True)
            try:
                vm = db.get_vending_machine(self.vending_machine_id)
                if not vm or vm.get("owner_id") != str(interaction.user.id):
                    return await interaction.followup.send("指定された自販機が見つかりません。", ephemeral=True)

                # 在庫アイテムを削除
                for product in vm.get("products", []):
                    try:
                        db.delete_product_stock(product["product_id"])
                    except:
                        pass

                db.delete_vending_machine(self.vending_machine_id)

                embed = discord.Embed(title="削除完了", description=f"自販機「{self.vm_name}」を削除しました。", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                embed.set_footer(text="Developer @yuzu09591")
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                await handle_error(interaction, e)

        @ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
        async def cancel_delete(self, interaction, button):
            embed = discord.Embed(title="キャンセル", description="自販機削除をキャンセルしました。", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
            embed.set_footer(text="Developer @yuzu09591")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    class CouponModal(ui.Modal, title="購入情報入力"):
        def __init__(self, vending_machine_id: str, product: dict, bot: commands.Bot):
            super().__init__()
            self.vending_machine_id = vending_machine_id
            self.product = product
            self.bot = bot
            self.quantity_input = ui.TextInput(label="購入数", placeholder="1", default="1", required=True, max_length=5)
            self.add_item(self.quantity_input)
            self.coupon_input = ui.TextInput(label="クーポンコード", placeholder="あればクーポンコードを入力", required=False, max_length=50)
            self.add_item(self.coupon_input)

        async def on_submit(self, interaction):
            try:
                if self.product.get('infinite_stock'):
                    quantity = 1
                else:
                    quantity = int(self.quantity_input.value)
                    if quantity <= 0:
                        return await interaction.response.send_message("購入数は1以上で入力してください。", ephemeral=True)
            except ValueError:
                return await interaction.response.send_message("購入数には整数を入力してください。", ephemeral=True)

            coupon_code = self.coupon_input.value.strip() if self.coupon_input.value else None
            discount = 0
            if coupon_code:
                coupon_info = db.get_coupon(coupon_code)
                if coupon_info:
                    if coupon_info.get("vending_machine_id") == self.vending_machine_id:
                        discount = coupon_info.get("discount", 0)
                    else:
                        return await interaction.response.send_message("このクーポンコードはこの自販機では使用できません。", ephemeral=True)
                else:
                    return await interaction.response.send_message("無効なクーポンコードです。", ephemeral=True)

            product_price = self.product.get('price', 0)
            final_price = max(0, product_price * quantity - discount * quantity)

            embed = discord.Embed(title="購入確認", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
            embed.add_field(name="商品名", value=f"```{self.product['name']}```", inline=False)
            embed.add_field(name="個数", value=f"```{'1' if self.product.get('infinite_stock') else quantity}個```", inline=False)
            if discount > 0:
                embed.add_field(name="金額", value=f"```{product_price}円 × {quantity}個 - {discount}円 × {quantity}個 = {final_price}円```", inline=False)
            else:
                embed.add_field(name="金額", value=f"```{final_price}円```", inline=False)
            embed.set_footer(text="Developer @yuzu09591")

            view = VendingMachineCog.PurchaseConfirmView(self.vending_machine_id, self.product, quantity, final_price, self.bot)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    class PurchaseConfirmView(ui.View):
        def __init__(self, vending_machine_id: str, product: dict, quantity: int, final_price: int, bot: commands.Bot):
            super().__init__(timeout=300)
            self.vending_machine_id = vending_machine_id
            self.product = product
            self.quantity = quantity
            self.final_price = final_price
            self.bot = bot

        @ui.button(label="購入確定", style=discord.ButtonStyle.green)
        async def confirm_purchase(self, interaction, button):
            if self.final_price == 0:
                await self.process_purchase(interaction, None)
            else:
                modal = VendingMachineCog.PayPayModal(self.vending_machine_id, self.product, self.quantity, self.final_price, self.bot)
                await interaction.response.send_modal(modal)

        async def process_purchase(self, interaction, pay_link):
            await interaction.response.defer(ephemeral=True)
            try:
                vm = db.get_vending_machine(self.vending_machine_id)
                if not vm:
                    return await interaction.followup.send(embed=discord.Embed(title="エラー", description="この自販機は削除されているか、データが不正です。", color=discord.Color.red()), ephemeral=True)

                if self.final_price > 0:
                    payment_info = await paypayu.check_link(pay_link)
                    if not payment_info:
                        return await interaction.followup.send("有効なPayPayリンクを入力してください。", ephemeral=True)
                    total_payment_amount = payment_info.get("payload", {}).get("message", {}).get("data", {}).get("amount")
                    if total_payment_amount < self.final_price:
                        return await interaction.followup.send(f"金額が不足しています。\n必要な金額: {self.final_price}円\nあなたの支払額: {total_payment_amount}円", ephemeral=True)

                    paypay_id = vm.get("paypay_id", "")
                    owner_account = db.get_paypay_account(int(paypay_id)) if paypay_id else None
                    if not owner_account:
                        return await interaction.followup.send("販売者のPayPayアカウントが設定されていません。\n販売者にお問い合わせください。", ephemeral=True)

                    result = await paypayu.link_rev(pay_link, owner_account["phone"], owner_account["password"], owner_account["uuid"])
                    if result == False:
                        try:
                            login_result = await paypayu.login(owner_account["phone"], owner_account["password"], owner_account["uuid"])
                            if login_result:
                                result = await paypayu.link_rev(pay_link, owner_account["phone"], owner_account["password"], owner_account["uuid"])
                        except Exception as e:
                            print(f"自動再ログインエラー: {e}")
                    if result != True:
                        return await interaction.followup.send("PayPay決済の処理に失敗しました。リンクが正しいか確認してください。", ephemeral=True)

                if self.product.get("infinite_stock"):
                    purchased_content_text = self.product.get('infinite_content', '')
                    purchased_content = f"```\n{purchased_content_text}\n```"
                else:
                    product_id = self.product.get("product_id")
                    items = db.pop_stock_items(product_id, self.quantity)
                    if len(items) < self.quantity:
                        return await interaction.followup.send(f"在庫が不足しています。\n必要数: {self.quantity}個\n現在の在庫: {len(items)}個", ephemeral=True)
                    purchased_content_text = "\n".join(items)
                    purchased_content = f"```\n{purchased_content_text}\n```"

                price_display = "0円" if self.final_price == 0 else f"{self.final_price}円"
                embed = discord.Embed(
                    title="購入完了",
                    description=f"**商品:** `{self.product['name']}`\n**数量:** `{self.quantity}`個\n**合計金額:** `{price_display}`",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="購入した商品", value=purchased_content, inline=False)
                embed.set_footer(text="Developer @yuzu09591")
                await interaction.followup.send(embed=embed, ephemeral=True)

                # sales_count更新
                vm2 = db.get_vending_machine(self.vending_machine_id)
                if vm2:
                    products = vm2.get("products", [])
                    for p in products:
                        if p.get("product_id") == self.product.get("product_id"):
                            p["sales_count"] = p.get("sales_count", 0) + self.quantity
                            break
                    db.update_vending_machine(self.vending_machine_id, products=products)

                # ロール付与
                try:
                    role_info = db.get_role_assignment(self.vending_machine_id)
                    if role_info and int(role_info.get("guild_id", 0)) == interaction.guild.id:
                        role = interaction.guild.get_role(int(role_info.get("role_id")))
                        if role and role not in interaction.user.roles:
                            await interaction.user.add_roles(role)
                except:
                    pass

                # DM送信
                try:
                    import datetime, pytz
                    jst = pytz.timezone('Asia/Tokyo')
                    formatted_time = datetime.datetime.now(jst).strftime("%Y/%m/%d %H:%M:%S(JST)")
                    dm_embed = discord.Embed(title="購入が完了しました", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                    dm_embed.add_field(name="購入日", value=f"```{formatted_time}```", inline=True)
                    dm_embed.add_field(name="購入サーバー", value=f"```{interaction.guild.name}({interaction.guild.id})```", inline=True)
                    dm_embed.add_field(name="商品名", value=f"```{self.product['name']}```", inline=True)
                    dm_embed.add_field(name="購入数", value=f"```{self.quantity}個```", inline=True)
                    dm_embed.add_field(name="支払金額", value=f"```{price_display}```", inline=True)
                    dm_embed.set_footer(text="Developer @yuzu09591")
                    await interaction.user.send(purchased_content_text, embed=dm_embed)
                except:
                    pass

                # 公開ログ
                if vm.get("log_channel_id"):
                    try:
                        log_channel = self.bot.get_channel(int(vm["log_channel_id"]))
                        if log_channel:
                            colors = [discord.Color.red(), discord.Color.blue(), discord.Color.green(), discord.Color.yellow(), discord.Color.purple()]
                            log_embed = discord.Embed(color=random.choice(colors))
                            log_embed.add_field(name="商品名", value=f"```{self.product['name']}```", inline=True)
                            log_embed.add_field(name="購入数", value=f"```{self.quantity}個```", inline=True)
                            log_embed.add_field(name="購入サーバー", value=f"```{interaction.guild.name}```", inline=True)
                            log_embed.add_field(name="購入者", value=f"{interaction.user.mention}({interaction.user.id})", inline=True)
                            log_embed.set_footer(text="Developer @yuzu09591")
                            await log_channel.send(embed=log_embed)
                    except:
                        pass

                # 非公開ログ
                if vm.get("private_log_channel_id"):
                    try:
                        private_log_channel = self.bot.get_channel(int(vm["private_log_channel_id"]))
                        if private_log_channel:
                            private_log_embed = discord.Embed(color=discord.Color.orange())
                            private_log_embed.add_field(name="商品名", value=f"```{self.product['name']}```", inline=True)
                            private_log_embed.add_field(name="購入数", value=f"```{self.quantity}個```", inline=True)
                            private_log_embed.add_field(name="購入サーバー", value=f"```{interaction.guild.name}```", inline=True)
                            private_log_embed.add_field(name="購入者", value=f"{interaction.user.mention}")
                            private_log_embed.add_field(name="支払金額", value=f"```{price_display}```", inline=True)
                            private_log_embed.add_field(name="自販機", value=f"```{vm['name']}```", inline=True)
                            private_log_embed.set_footer(text="Developer @yuzu09591")
                            discord_file = discord.File(io.BytesIO(purchased_content_text.encode('utf-8')), filename=f"purchase_{interaction.user.id}_{int(discord.utils.utcnow().timestamp())}.txt")
                            await private_log_channel.send(embed=private_log_embed, file=discord_file)
                    except:
                        pass
            except Exception as e:
                await handle_error(interaction, e)

    class PayPayModal(ui.Modal, title="PayPay決済"):
        def __init__(self, vending_machine_id, product, quantity, final_price, bot):
            super().__init__()
            self.vending_machine_id = vending_machine_id
            self.product = product
            self.quantity = quantity
            self.final_price = final_price
            self.bot = bot
            self.paypay_input = ui.TextInput(label="PayPayリンク", placeholder="https://pay.paypay.ne.jp/...", required=True)
            self.add_item(self.paypay_input)

        async def on_submit(self, interaction):
            confirm_view = VendingMachineCog.PurchaseConfirmView(self.vending_machine_id, self.product, self.quantity, self.final_price, self.bot)
            await confirm_view.process_purchase(interaction, self.paypay_input.value)

    class ProductSelect(ui.Select):
        def __init__(self, vending_machine_id: str, bot: commands.Bot):
            self.vending_machine_id = vending_machine_id
            self.bot = bot

            vm = db.get_vending_machine(vending_machine_id) or {}
            products = vm.get("products", [])

            options = []
            for product in products:
                product_id = product.get("product_id")
                sales_count = product.get("sales_count", 0)
                if product.get("infinite_stock"):
                    description = f"価格: {product['price']}円│在庫数: ∞個│販売数: {sales_count}個"
                else:
                    stock_count = db.count_stock(product_id) if product_id else 0
                    description = f"価格: {product['price']}円│在庫数: {stock_count}個│販売数: {sales_count}個"
                options.append(discord.SelectOption(
                    label=product['name'],
                    value=product["product_id"],
                    description=description,
                    emoji=product.get("emoji")
                ))

            if not options:
                options.append(discord.SelectOption(label="商品なし", value="none", description="現在販売中の商品はありません"))

            super().__init__(placeholder="商品を選択する", options=options, custom_id=f"product_select_{vending_machine_id}")

        async def callback(self, interaction):
            if self.values[0] == "none":
                return await interaction.response.send_message("現在販売中の商品はありません。", ephemeral=True)
            try:
                vm = db.get_vending_machine(self.vending_machine_id)
                if not vm:
                    return await interaction.response.send_message(embed=discord.Embed(title="エラー", description="この自販機は削除されているか、存在しません。", color=discord.Color.red()), ephemeral=True)

                products = vm.get("products", [])
                product = next((p for p in products if p["product_id"] == self.values[0]), None)
                if not product:
                    return await interaction.response.send_message("商品が見つかりません。", ephemeral=True)

                if not product.get("infinite_stock"):
                    stock_count = db.count_stock(product.get("product_id"))
                    if stock_count == 0:
                        embed = discord.Embed(title="在庫不足", description=f"現在 {product['name']}の在庫が不足しています。", color=discord.Color.orange())
                        embed.set_footer(text="Developer @yuzu09591")
                        return await interaction.response.send_message(embed=embed, ephemeral=True)

                modal = VendingMachineCog.CouponModal(self.vending_machine_id, product, self.bot)
                await interaction.response.send_modal(modal)
            except Exception as e:
                await handle_error(interaction, e)

    class PurchaseButton(ui.Button):
        def __init__(self, vending_machine_id: str, bot: commands.Bot):
            super().__init__(label="購入する", style=discord.ButtonStyle.green, emoji="🛒", custom_id=f"purchase_{vending_machine_id}")
            self.vending_machine_id = vending_machine_id
            self.bot = bot

        async def callback(self, interaction):
            try:
                embed = discord.Embed(title="購入する商品を選択してください。", color=discord.Color.green())
                view = VendingMachineCog.ProductSelectView(self.vending_machine_id, self.bot)
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            except Exception as e:
                await handle_error(interaction, e)

    class ProductSelectView(ui.View):
        def __init__(self, vending_machine_id, bot):
            super().__init__(timeout=None)
            self.add_item(VendingMachineCog.ProductSelect(vending_machine_id, bot))

    class StockCheckButton(ui.Button):
        def __init__(self, vending_machine_id: str):
            super().__init__(label="在庫・販売数確認", style=discord.ButtonStyle.primary, emoji="📦", custom_id=f"check_stock_{vending_machine_id}")
            self.vending_machine_id = vending_machine_id

        async def callback(self, interaction):
            try:
                vm = db.get_vending_machine(self.vending_machine_id)
                if not vm:
                    return await interaction.response.send_message(embed=discord.Embed(title="エラー", description="この自販機は削除されているか、存在しません。", color=discord.Color.red()), ephemeral=True)
                await interaction.response.defer(ephemeral=True)
                await check_stock(interaction, vm.get("products", []))
            except Exception as e:
                await handle_error(interaction, e)

    class VendingMachineView(ui.View):
        def __init__(self, vending_machine_id, bot):
            super().__init__(timeout=None)
            self.add_item(VendingMachineCog.PurchaseButton(vending_machine_id, bot))
            self.add_item(VendingMachineCog.StockCheckButton(vending_machine_id))

    class ProductSelectViewForStock(ui.View):
        def __init__(self, products, attachment=None, stock_type="finite"):
            super().__init__(timeout=None)
            self.add_item(VendingMachineCog.ProductSelectForStock(products, attachment, stock_type))

    class ProductSelectForStock(ui.Select):
        def __init__(self, products, attachment=None, stock_type="finite"):
            self.products = products
            self.attachment = attachment
            self.stock_type = stock_type
            options = [discord.SelectOption(label=p["name"], value=p["product_id"]) for p in products]
            super().__init__(placeholder="在庫を追加する商品を選択...", options=options, custom_id="stock_add_select")

        async def callback(self, interaction):
            try:
                product = next((p for p in self.products if p["product_id"] == self.values[0]), None)
                if not product:
                    return await interaction.response.send_message("商品が見つかりません。", ephemeral=True)

                if self.stock_type == "infinite":
                    if self.attachment:
                        await interaction.response.defer(ephemeral=True)
                        new_stock_content = await self.attachment.read()
                        infinite_content = new_stock_content.decode('utf-8').strip()
                        await self._set_infinite(interaction, product, infinite_content)
                    else:
                        modal = VendingMachineCog.InfiniteStockModal(product)
                        await interaction.response.send_modal(modal)
                else:
                    if self.attachment:
                        await interaction.response.defer(ephemeral=True)
                        new_stock_content = await self.attachment.read()
                        lines = [l for l in new_stock_content.decode('utf-8').splitlines() if l.strip()]
                        db.add_stock_lines(product["product_id"], lines)
                        await interaction.followup.send(f"商品「{product['name']}」に`{len(lines)}`個の在庫を追加しました。", ephemeral=True)
                        await self._send_stock_notification(interaction, product, len(lines))
                    else:
                        modal = VendingMachineCog.StockAddModal(product)
                        await interaction.response.send_modal(modal)
            except Exception as e:
                await handle_error(interaction, e)

        async def _set_infinite(self, interaction, product, infinite_content):
            vending_data = db.get_all_vending_machines()
            for vm_id, vm_data in vending_data.items():
                products = vm_data.get("products", [])
                for i, p in enumerate(products):
                    if p["product_id"] == product["product_id"]:
                        products[i]["infinite_stock"] = True
                        products[i]["infinite_content"] = infinite_content
                        db.update_vending_machine(vm_id, products=products)
                        break
            await interaction.followup.send(f"商品「{product['name']}」を無限在庫に設定しました。", ephemeral=True)

        async def _send_stock_notification(self, interaction, product, added_count):
            try:
                vending_data = db.get_all_vending_machines()
                vending_machine_id = None
                for vm_id, vm_data in vending_data.items():
                    for p in vm_data.get("products", []):
                        if p["product_id"] == product["product_id"]:
                            vending_machine_id = vm_id
                            break
                    if vending_machine_id:
                        break
                if not vending_machine_id:
                    return
                notification_info = db.get_stock_notification(vending_machine_id)
                if notification_info and int(notification_info.get("guild_id", 0)) == interaction.guild.id:
                    channel = interaction.guild.get_channel(int(notification_info.get("channel_id")))
                    role = interaction.guild.get_role(int(notification_info.get("role_id")))
                    if channel and role:
                        embed = discord.Embed(title="在庫追加通知", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                        embed.add_field(name="追加商品", value=f"```{product['name']}```", inline=True)
                        embed.add_field(name="追加数", value=f"```{added_count}個```", inline=True)
                        embed.set_footer(text="Developer @yuzu09591")
                        await channel.send(f"{role.mention}", embed=embed)
            except Exception as e:
                print(f"在庫追加通知送信エラー: {e}")

    class StockAddModal(ui.Modal, title="在庫追加"):
        def __init__(self, product: dict):
            super().__init__(timeout=None)
            self.product = product

        stock_input = ui.TextInput(label="在庫内容", style=discord.TextStyle.long, placeholder="追加する在庫を1行ずつ入力してください", required=True)

        async def on_submit(self, interaction):
            await interaction.response.defer(ephemeral=True)
            try:
                lines = [l for l in self.stock_input.value.splitlines() if l.strip()]
                db.add_stock_lines(self.product["product_id"], lines)
                await interaction.followup.send(f"商品「{self.product['name']}」に`{len(lines)}`個の在庫を追加しました。", ephemeral=True)
                await self._send_stock_notification(interaction, self.product, len(lines))
            except Exception as e:
                await handle_error(interaction, e)

        async def _send_stock_notification(self, interaction, product, added_count):
            try:
                vending_data = db.get_all_vending_machines()
                vending_machine_id = None
                for vm_id, vm_data in vending_data.items():
                    for p in vm_data.get("products", []):
                        if p["product_id"] == product["product_id"]:
                            vending_machine_id = vm_id
                            break
                    if vending_machine_id:
                        break
                if not vending_machine_id:
                    return
                notification_info = db.get_stock_notification(vending_machine_id)
                if notification_info and int(notification_info.get("guild_id", 0)) == interaction.guild.id:
                    channel = interaction.guild.get_channel(int(notification_info.get("channel_id")))
                    role = interaction.guild.get_role(int(notification_info.get("role_id")))
                    if channel and role:
                        embed = discord.Embed(title="在庫追加通知", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                        embed.add_field(name="追加商品", value=f"```{product['name']}```", inline=True)
                        embed.add_field(name="追加数", value=f"```{added_count}個```", inline=True)
                        embed.set_footer(text="Developer @yuzu09591")
                        await channel.send(f"{role.mention}", embed=embed)
            except Exception as e:
                print(f"在庫追加通知送信エラー: {e}")

    class InfiniteStockModal(ui.Modal, title="無限在庫設定"):
        def __init__(self, product: dict):
            super().__init__(timeout=None)
            self.product = product

        stock_input = ui.TextInput(label="無限在庫内容", style=discord.TextStyle.long, placeholder="購入時に送信される内容を入力してください", required=True)

        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            try:
                infinite_content = self.stock_input.value.strip()
                vending_data = db.get_all_vending_machines()
                for vm_id, vm_data in vending_data.items():
                    products = vm_data.get("products", [])
                    for i, p in enumerate(products):
                        if p["product_id"] == self.product["product_id"]:
                            products[i]["infinite_stock"] = True
                            products[i]["infinite_content"] = infinite_content
                            db.update_vending_machine(vm_id, products=products)
                            break
                await interaction.followup.send(f"商品「{self.product['name']}」を無限在庫に設定しました。", ephemeral=True)
            except Exception as e:
                await handle_error(interaction, e)

    class WithdrawStockView(ui.View):
        def __init__(self, products, quantity):
            super().__init__(timeout=None)
            self.add_item(VendingMachineCog.ProductSelectForWithdraw(products, quantity))

    class ProductSelectForWithdraw(ui.Select):
        def __init__(self, products, quantity):
            self.products = products
            self.quantity = quantity
            options = [discord.SelectOption(label=p["name"], value=p["product_id"]) for p in products]
            super().__init__(placeholder="在庫を引き出す商品を選択...", options=options, custom_id="withdraw_select")

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            try:
                product = next((p for p in self.products if p["product_id"] == self.values[0]), None)
                if not product:
                    return await interaction.followup.send("商品が見つかりません。", ephemeral=True)

                if product.get("infinite_stock"):
                    # 無限在庫解除
                    vending_data = db.get_all_vending_machines()
                    withdrawn_content = ""
                    for vm_id, vm_data in vending_data.items():
                        products = vm_data.get("products", [])
                        for i, p in enumerate(products):
                            if p["product_id"] == product["product_id"]:
                                withdrawn_content = p.get('infinite_content', '')
                                products[i]["infinite_stock"] = False
                                products[i]["infinite_content"] = None
                                db.update_vending_machine(vm_id, products=products)
                                break
                    embed = discord.Embed(title="無限在庫解除完了", description=f"**商品:** `{product['name']}`\n**解除された無限在庫内容:**", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                    embed.add_field(name="引き出した無限在庫", value=f"`{withdrawn_content}\n`", inline=False)
                    embed.set_footer(text="Developer @yuzu09591")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    product_id = product.get("product_id")
                    stock_count = db.count_stock(product_id)
                    if stock_count < self.quantity:
                        return await interaction.followup.send(f"在庫が不足しています。\n引出希望数: {self.quantity}個\n現在の在庫: {stock_count}個", ephemeral=True)

                    items = db.pop_stock_items(product_id, self.quantity)
                    withdrawn_content = "\n".join(items)
                    embed = discord.Embed(title="在庫引出完了", description=f"**商品:** `{product['name']}`\n**引出数量:** `{self.quantity}`個", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                    embed.add_field(name="引き出した在庫", value=f"`{withdrawn_content}\n`", inline=False)
                    embed.set_footer(text="Developer @yuzu09591")
                    await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                await handle_error(interaction, e)

    class ContentView(ui.View):
        def __init__(self, products):
            super().__init__(timeout=None)
            self.add_item(VendingMachineCog.ProductSelectForContent(products))

    class ProductSelectForContent(ui.Select):
        def __init__(self, products):
            self.products = products
            options = [discord.SelectOption(label=p["name"], value=p["product_id"]) for p in products]
            super().__init__(placeholder="在庫内容を確認する商品を選択...", options=options, custom_id="content_select")

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            try:
                product = next((p for p in self.products if p["product_id"] == self.values[0]), None)
                if not product:
                    return await interaction.followup.send("商品が見つかりません。", ephemeral=True)

                if product.get("infinite_stock"):
                    infinite_content = product.get("infinite_content", "")
                    embed = discord.Embed(title="在庫内容", description=f"**商品:** `{product['name']}`\n**在庫数:** `∞`個", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                    embed.add_field(name="無限在庫内容", value=f"`{infinite_content}\n`", inline=False)
                    embed.set_footer(text="Developer @yuzu09591")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    product_id = product.get("product_id")
                    lines = db.list_stock_contents(product_id)
                    if not lines:
                        embed = discord.Embed(title="在庫内容", description=f"**商品:** `{product['name']}`\n**在庫数:** `0`個", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                        embed.add_field(name="在庫内容", value="```\n在庫がありません\n```", inline=False)
                    else:
                        content = "\n".join(lines)
                        embed = discord.Embed(title="在庫内容", description=f"**商品:** `{product['name']}`\n**在庫数:** `{len(lines)}`個", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
                        embed.add_field(name="在庫内容", value=f"`{content}`\n", inline=False)
                    embed.set_footer(text="Developer @yuzu09591")
                    await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                await handle_error(interaction, e)

    class ProductSelectForDelete(ui.Select):
        def __init__(self, products):
            self.products = products
            options = [discord.SelectOption(label=p["name"], value=p["product_id"]) for p in products]
            super().__init__(placeholder="削除する商品を選択...", options=options, custom_id="delete_select")

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            try:
                product = next((p for p in self.products if p["product_id"] == self.values[0]), None)
                if not product:
                    return await interaction.followup.send("商品が見つかりません。", ephemeral=True)
                view = VendingMachineCog.DeleteConfirmView(product)
                embed = discord.Embed(title="商品削除確認", description=f"本当に商品「{product['name']}」を削除しますか？\n\n**この操作は取り消せません。**", color=discord.Color.red())
                embed.set_footer(text="Developer @yuzu09591")
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            except Exception as e:
                await handle_error(interaction, e)

    class ProductDeleteView(ui.View):
        def __init__(self, products, vending_machine_id):
            super().__init__(timeout=None)
            self.vending_machine_id = vending_machine_id
            self.add_item(VendingMachineCog.ProductSelectForDelete(products))

    class DeleteConfirmView(ui.View):
        def __init__(self, product):
            super().__init__(timeout=None)
            self.product = product

        @ui.button(label="削除する", style=discord.ButtonStyle.danger)
        async def confirm_delete(self, interaction: discord.Interaction, button: ui.Button):
            await interaction.response.defer(ephemeral=True)
            try:
                # 在庫を削除
                try:
                    db.delete_product_stock(self.product["product_id"])
                except:
                    pass

                # 商品リストから除外
                vending_data = db.get_all_vending_machines()
                for vm_id, vm_data in vending_data.items():
                    products = vm_data.get("products", [])
                    new_products = [p for p in products if p["product_id"] != self.product["product_id"]]
                    if len(new_products) != len(products):
                        db.update_vending_machine(vm_id, products=new_products)
                        break

                embed = discord.Embed(title="削除完了", description=f"商品「{self.product['name']}」を削除しました。", color=discord.Color.green())
                embed.set_footer(text="Developer @yuzu09591")
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                await handle_error(interaction, e)

        @ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
        async def cancel_delete(self, interaction: discord.Interaction, button: ui.Button):
            embed = discord.Embed(title="キャンセル", description="商品削除をキャンセルしました。", color=discord.Color.blue())
            embed.set_footer(text="Developer @yuzu09591")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    class EditProductView(ui.View):
        def __init__(self, products, vending_machine_id):
            super().__init__(timeout=None)
            self.vending_machine_id = vending_machine_id
            self.add_item(VendingMachineCog.ProductSelectForEdit(products, vending_machine_id))

    class ProductSelectForEdit(ui.Select):
        def __init__(self, products, vending_machine_id):
            self.products = products
            self.vending_machine_id = vending_machine_id
            options = [discord.SelectOption(label=p["name"], value=p["product_id"]) for p in products]
            super().__init__(placeholder="編集する商品を選択...", options=options, custom_id="edit_select")

        async def callback(self, interaction: discord.Interaction):
            try:
                product = next((p for p in self.products if p["product_id"] == self.values[0]), None)
                if not product:
                    return await interaction.response.send_message("商品が見つかりません。", ephemeral=True)
                modal = VendingMachineCog.EditProductModal(product, self.vending_machine_id)
                await interaction.response.send_modal(modal)
            except Exception as e:
                await handle_error(interaction, e)

    class EditProductModal(ui.Modal, title="商品情報編集"):
        name_input = ui.TextInput(label="商品名", placeholder="新しい商品名を入力...", required=False, max_length=100)
        description_input = ui.TextInput(label="商品説明", style=discord.TextStyle.long, placeholder="新しい商品説明を入力...", required=False, max_length=1000)
        price_input = ui.TextInput(label="価格", placeholder="新しい価格を入力...", required=False, max_length=10)
        emoji_input = ui.TextInput(label="絵文字", placeholder="新しい絵文字を入力...", required=False, max_length=50)

        def __init__(self, product, vending_machine_id):
            super().__init__(timeout=None)
            self.product = product
            self.vending_machine_id = vending_machine_id
            self.name_input.default = product.get("name", "")
            self.description_input.default = product.get("description", "")
            self.price_input.default = str(product.get("price", 0))
            self.emoji_input.default = product.get("emoji", "")

        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            try:
                vm = db.get_vending_machine(self.vending_machine_id)
                if not vm:
                    return await interaction.followup.send("自販機が見つかりません。", ephemeral=True)

                products = vm.get("products", [])
                updated_fields = []
                for p in products:
                    if p["product_id"] == self.product["product_id"]:
                        if self.name_input.value.strip():
                            p["name"] = self.name_input.value.strip()
                            updated_fields.append("商品名")
                        if self.description_input.value is not None:
                            p["description"] = self.description_input.value.strip()
                            updated_fields.append("商品説明")
                        if self.price_input.value.strip():
                            try:
                                new_price = int(self.price_input.value.strip())
                                if new_price >= 0:
                                    p["price"] = new_price
                                    updated_fields.append("価格")
                                else:
                                    return await interaction.followup.send("価格は0以上で入力してください。", ephemeral=True)
                            except ValueError:
                                return await interaction.followup.send("価格には整数を入力してください。", ephemeral=True)
                        if self.emoji_input.value.strip():
                            p["emoji"] = self.emoji_input.value.strip()
                            updated_fields.append("絵文字")
                        break

                if updated_fields:
                    db.update_vending_machine(self.vending_machine_id, products=products)
                    embed = discord.Embed(title="商品情報更新完了", description=f"商品「{self.product['name']}」を更新しました:\n• " + "\n• ".join(updated_fields), color=discord.Color.green())
                    embed.set_footer(text="Developer @yuzu09591")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send("更新する項目が入力されていません。", ephemeral=True)
            except Exception as e:
                await handle_error(interaction, e)

    @app_commands.command(name="在庫追加通知設定", description="在庫追加時の通知設定を行います")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    @app_commands.describe(vending_machine_id="通知設定する自販機", channel="通知を送信するチャンネル", role="メンションするロール")
    async def stock_notification_setup(self, interaction: discord.Interaction, vending_machine_id: str, channel: discord.TextChannel, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        try:
            vm = db.get_vending_machine(vending_machine_id)
            if not vm or vm.get("owner_id") != str(interaction.user.id):
                return await interaction.followup.send("指定された自販機が見つかりません。", ephemeral=True)
            db.set_stock_notification(vending_machine_id, channel.id, role.id, interaction.guild.id)
            embed = discord.Embed(title="在庫追加通知設定", description=f"自販機「{vm['name']}」の在庫追加通知を設定しました。", color=discord.Color.green())
            embed.add_field(name="通知チャンネル", value=channel.mention, inline=True)
            embed.add_field(name="メンションロール", value=role.mention, inline=True)
            embed.set_footer(text="Developer @yuzu09591")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await handle_error(interaction, e)

    @app_commands.command(name="在庫追加設定解除", description="在庫追加通知設定を解除します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    async def stock_notification_remove(self, interaction: discord.Interaction, vending_machine_id: str):
        await interaction.response.defer(ephemeral=True)
        try:
            vm = db.get_vending_machine(vending_machine_id)
            if not vm or vm.get("owner_id") != str(interaction.user.id):
                return await interaction.followup.send("指定された自販機が見つかりません。", ephemeral=True)
            existing = db.get_stock_notification(vending_machine_id)
            if existing:
                db.delete_stock_notification(vending_machine_id)
                await interaction.followup.send(f"自販機「{vm['name']}」の在庫追加通知設定を解除しました。", ephemeral=True)
            else:
                await interaction.followup.send("通知設定が見つかりません。", ephemeral=True)
        except Exception as e:
            await handle_error(interaction, e)

    @app_commands.command(name="自販機クーポン作成", description="指定した自販機用のクーポンコードを作成します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    async def vm_create_coupon(self, interaction: discord.Interaction, vending_machine_id: str, coupon_code: str, discount: int):
        try:
            if discount <= 0:
                return await interaction.response.send_message("割引金額は1円以上で指定してください。", ephemeral=True)
            vm = db.get_vending_machine(vending_machine_id)
            if not vm or vm.get("owner_id") != str(interaction.user.id):
                return await interaction.response.send_message("指定された自販機が見つかりません。", ephemeral=True)
            if db.get_coupon(coupon_code):
                return await interaction.response.send_message("そのコードは既に存在します。", ephemeral=True)
            db.create_coupon(coupon_code, discount, interaction.user.id, vending_machine_id)
            await interaction.response.send_message(f"クーポン「{coupon_code}」を作成しました。", ephemeral=True)
        except Exception as e:
            await handle_error(interaction, e)

    @app_commands.command(name="クーポン削除", description="作成したクーポンを削除します")
    @is_allowed()
    @app_commands.autocomplete(coupon_code=coupon_autocomplete)
    async def vm_delete_coupon(self, interaction: discord.Interaction, coupon_code: str):
        try:
            coupon_info = db.get_coupon(coupon_code)
            if not coupon_info:
                return await interaction.response.send_message("クーポンが見つかりません。", ephemeral=True)
            if coupon_info.get("owner_id") != str(interaction.user.id):
                return await interaction.response.send_message("他人のクーポンを削除することはできません。", ephemeral=True)
            db.delete_coupon(coupon_code)
            await interaction.response.send_message(f"クーポン「{coupon_code}」を削除しました。", ephemeral=True)
        except Exception as e:
            await handle_error(interaction, e)

    @app_commands.command(name="自販機クーポン一覧", description="作成したクーポン一覧を表示します")
    @is_allowed()
    async def vm_list_coupons(self, interaction: discord.Interaction):
        try:
            coupon_data = db.get_coupons_by_owner(interaction.user.id)
            vending_data = db.get_all_vending_machines()
            if not coupon_data:
                return await interaction.response.send_message("クーポンがありません。", ephemeral=True)
            embed = discord.Embed(title="クーポン一覧", color=discord.Color.blue())
            for code, info in coupon_data.items():
                vm_name = vending_data.get(info.get("vending_machine_id"), {}).get("name", "不明")
                embed.add_field(name=f"コード: {code}", value=f"割引: {info['discount']}円\n自販機: {vm_name}", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await handle_error(interaction, e)

    @app_commands.command(name="自販機ロール設定", description="購入時に付与するロールを設定します")
    @is_allowed()
    @app_commands.autocomplete(vending_machine_id=vending_machine_autocomplete)
    async def vm_set_role(self, interaction: discord.Interaction, vending_machine_id: str, role: discord.Role):
        try:
            vm = db.get_vending_machine(vending_machine_id)
            if not vm or vm.get("owner_id") != str(interaction.user.id):
                return await interaction.response.send_message("自販機が見つかりません。", ephemeral=True)
            db.set_role_assignment(vending_machine_id, role.id, interaction.guild.id)
            await interaction.response.send_message(f"ロール {role.mention} を設定しました。", ephemeral=True)
        except Exception as e:
            await handle_error(interaction, e)


async def setup(bot):
    await bot.add_cog(VendingMachineCog(bot))
