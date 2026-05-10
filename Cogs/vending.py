import discord
from discord import app_commands, ui
from discord.ext import commands
import time
import uuid
from Cogs.utils import load_items, is_allowed
from Cogs.nyanko_editor import CloudEditor
from Cogs.db import (
    get_paypay_account, record_sale, get_sales,
    get_vending_machines, get_vending_machine,
    create_vending_machine, update_vending_machine,
    get_log_channels, set_log_channel
)
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
            discord.SelectOption(
                label=f"{item['name']} (¥{item['price']})",
                value=str(offset + i),
                description=f"価格: ¥{item['price']}"
            )
            for i, item in enumerate(items)
        ]

        super().__init__(
            placeholder=f"購入したいアイテムを選択してください{label_suffix}",
            min_values=1,
            max_values=min(25, len(items)),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_items = []
        for idx in self.values:
            local_idx = int(idx) - self.offset
            item = self.items[local_idx]
            selected_items.append({
                'name': item['name'],
                'price': item['price'],
                'quantity': 1,
                'subtotal': item['price']
            })

        total_price = sum(item['subtotal'] for item in selected_items)

        embed = discord.Embed(title="注文確認", color=0x2ecc71)
        embed.add_field(
            name="選択アイテム",
            value="\n".join([f"{item['name']} × {item['quantity']}個" for item in selected_items]),
            inline=False
        )
        embed.add_field(name="合計金額", value=f"¥{total_price}", inline=False)

        view = ui.View()

        async def buy_cb(it):
            await it.response.send_modal(
                PayPayModal(selected_items, total_price, self.user, self.guild, self.bot, self.vending_id)
            )

        btn = ui.Button(label="購入する", style=discord.ButtonStyle.success)
        btn.callback = buy_cb
        view.add_item(btn)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class PayPayModal(ui.Modal, title="支払い・引継ぎコード入力"):
    paypay_link = ui.TextInput(
        label="PayPayリンク *",
        placeholder="https://pay.paypay.ne.jp/...",
        required=True
    )
    transfer_code = ui.TextInput(
        label="引継ぎコード *",
        placeholder="引継ぎコード",
        required=True
    )
    pin = ui.TextInput(
        label="PIN *",
        placeholder="PIN",
        required=True
    )

    def __init__(self, selected_items, total_price, user, guild, bot, vending_id):
        super().__init__()
        self.selected_items = selected_items
        self.total_price = total_price
        self.user = user
        self.guild = guild
        self.bot = bot
        self.vending_id = vending_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            if not self.paypay_link.value.startswith("https://pay.paypay.ne.jp/"):
                return await interaction.followup.send(
                    embed=discord.Embed(title="❌ エラー", description="有効なPayPayリンクを入力してください", color=0xff0000),
                    ephemeral=True
                )

            await interaction.followup.send(
                embed=discord.Embed(title="🔄 処理中", description="PayPayリンクを確認中...", color=0xFFB700),
                ephemeral=True
            )

            payment_info = await paypayu.check_link(self.paypay_link.value)
            if not payment_info:
                return await interaction.followup.send(
                    embed=discord.Embed(title="❌ エラー", description="有効なPayPayリンクではありません", color=0xff0000),
                    ephemeral=True
                )

            amount = payment_info.get("payload", {}).get("message", {}).get("data", {}).get("amount")
            if amount is None or amount < self.total_price:
                return await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ 金額不足",
                        description=f"必要な金額: ¥{self.total_price}\n送信された金額: ¥{amount or 0}",
                        color=0xff0000
                    ),
                    ephemeral=True
                )

            # 自販機設置者のPayPayアカウントで受け取り（Supabaseから取得）
            vm = get_vending_machine(self.vending_id)
            if not vm:
                return await interaction.followup.send(
                    embed=discord.Embed(title="❌ エラー", description="自販機が見つかりません", color=0xff0000),
                    ephemeral=True
                )
            vm_owner_id = int(vm["owner_id"])
            owner_account = get_paypay_account(vm_owner_id)
            if not owner_account:
                return await interaction.followup.send(
                    embed=discord.Embed(title="❌ エラー", description="自販機設置者のPayPayアカウントが登録されていません", color=0xff0000),
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

            await interaction.followup.send(
                embed=discord.Embed(title="🔄 代行中", description="セーブファイルを改造中...", color=0xFFB700),
                ephemeral=True
            )

            editor = CloudEditor(
                self.transfer_code.value,
                self.pin.value,
                self.user,
                self.guild.id,
                modifications=self.selected_items
            )

            if not editor.download_save():
                return await interaction.followup.send(
                    embed=discord.Embed(title="❌ エラー", description="引継ぎコードまたはPINが正しくありません", color=0xff0000),
                    ephemeral=True
                )

            if not editor.apply_modifications():
                return await interaction.followup.send(
                    embed=discord.Embed(title="❌ エラー", description=editor.last_error, color=0xff0000),
                    ephemeral=True
                )

            new_code, new_pin = editor.upload_save()

            if new_code and new_pin:
                # Supabaseに販売記録
                record_sale(self.vending_id, self.user.id, str(self.user.name), self.selected_items, self.total_price)

                dm_embed = discord.Embed(title="✅ 代行完了", color=0x2ecc71)
                items_text = "\n".join([f"{item['name']} × {item['quantity']}個" for item in self.selected_items])
                dm_embed.add_field(name="購入商品", value=items_text, inline=False)
                dm_embed.add_field(name="合計金額", value=f"¥{self.total_price}", inline=False)
                dm_embed.add_field(name="新しい引継ぎコード", value=f"`{new_code}`", inline=False)
                dm_embed.add_field(name="PIN", value=f"`{new_pin}`", inline=False)
                dm_embed.set_footer(text="必ず保存してください")

                try:
                    await self.user.send(embed=dm_embed)
                except:
                    pass

                await interaction.followup.send(
                    embed=discord.Embed(
                        title="✅ 代行完了",
                        description="PayPayを自動受け取りしました\n新しい引継ぎコードをDMで送信しました",
                        color=0x2ecc71
                    ),
                    ephemeral=True
                )

                # ロール付与
                if vm and vm.get("role_id"):
                    role = self.guild.get_role(int(vm["role_id"]))
                    if role and role not in self.user.roles:
                        try:
                            await self.user.add_roles(role)
                        except:
                            pass

                # ログ
                log_channels = get_log_channels(self.guild.id)
                items_text = "\n".join([f"{item['name']} × {item['quantity']}個" for item in self.selected_items])

                if log_channels.get("public"):
                    ch = self.bot.get_channel(log_channels["public"])
                    if ch:
                        log_embed = discord.Embed(title="✅ 代行完了", color=0x2ecc71)
                        log_embed.set_author(name=self.user.name, icon_url=self.user.display_avatar.url)
                        log_embed.add_field(name="ユーザー", value=self.user.mention, inline=False)
                        log_embed.add_field(name="商品", value=items_text, inline=False)
                        log_embed.add_field(name="合計金額", value=f"¥{self.total_price}", inline=False)
                        log_embed.add_field(name="日時", value=f"<t:{int(time.time())}:F>", inline=False)
                        await ch.send(embed=log_embed)

                if log_channels.get("private"):
                    ch = self.bot.get_channel(log_channels["private"])
                    if ch:
                        log_embed = discord.Embed(title="✅ 代行完了（詳細）", color=0x3498db)
                        log_embed.set_author(name=self.user.name, icon_url=self.user.display_avatar.url)
                        log_embed.add_field(name="ユーザー", value=self.user.mention, inline=False)
                        log_embed.add_field(name="商品", value=items_text, inline=False)
                        log_embed.add_field(name="合計金額", value=f"¥{self.total_price}", inline=False)
                        log_embed.add_field(name="新コード", value=f"`{new_code}`", inline=False)
                        log_embed.add_field(name="日時", value=f"<t:{int(time.time())}:F>", inline=False)
                        await ch.send(embed=log_embed)
            else:
                await interaction.followup.send(
                    embed=discord.Embed(title="❌ エラー", description=f"アップロード失敗: {editor.last_error}", color=0xff0000),
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                embed=discord.Embed(title="❌ エラー", description=f"```{str(e)}```", color=0xff0000),
                ephemeral=True
            )


class VendingView(ui.View):
    def __init__(self, all_items, vending_id, user, guild, bot):
        super().__init__()
        mid = len(all_items) // 2
        self.add_item(ProductSelectDropdown(all_items[:mid], vending_id, user, guild, bot, offset=0, label_suffix="（前半）"))
        self.add_item(ProductSelectDropdown(all_items[mid:], vending_id, user, guild, bot, offset=mid, label_suffix="（後半）"))


async def vending_machine_autocomplete(interaction: discord.Interaction, current: str):
    machines = get_vending_machines(owner_id=interaction.user.id)
    return [
        app_commands.Choice(name=vm.get("name", "名称未設定"), value=vm["id"])
        for vm in machines
        if current.lower() in vm.get("name", "").lower()
    ][:25]


class VendingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="自販機作成", description="自販機を作成します")
    @is_allowed()
    @app_commands.describe(name="自販機の名前")
    async def create_vending(self, interaction: discord.Interaction, name: str):
        vm_id = str(uuid.uuid4())
        create_vending_machine(vm_id, name, interaction.user.id)

        embed = discord.Embed(
            title="✅ 自販機作成",
            description=f"自販機「{name}」を作成しました\n**ID:** `{vm_id}`",
            color=0x2ecc71
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="自販機商品追加", description="自販機に商品を追加します")
    @is_allowed()
    @app_commands.autocomplete(vending_id=vending_machine_autocomplete)
    @app_commands.describe(vending_id="自販機", name="商品名", price="価格（円）")
    async def add_item(self, interaction: discord.Interaction, vending_id: str, name: str, price: int):
        vm = get_vending_machine(vending_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません", ephemeral=True)

        items = vm.get("custom_items", [])
        items.append({"name": name, "price": price})
        update_vending_machine(vending_id, custom_items=items)

        await interaction.response.send_message(
            embed=discord.Embed(title="✅ 商品追加", description=f"商品「{name}」(¥{price})を追加しました", color=0x2ecc71),
            ephemeral=True
        )

    @app_commands.command(name="自販機", description="自動販売機を起動します")
    @is_allowed()
    @app_commands.autocomplete(vending_id=vending_machine_autocomplete)
    @app_commands.describe(vending_id="起動する自販機")
    async def vending_machine(self, interaction: discord.Interaction, vending_id: str):
        vm = get_vending_machine(vending_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません", ephemeral=True)

        items = load_items()
        if vm.get("custom_items"):
            items['menu1'].extend(vm["custom_items"])

        all_items = items['menu1'] + items['menu2']

        embed = discord.Embed(
            title=vm['name'],
            description="購入したいアイテムを以下から選択してください。",
            color=0x2b2d31
        )

        menu1_lines = "\n".join([f"**{item['name']}**\n{item['price']}円" for item in items['menu1']])
        menu2_lines = "\n".join([f"**{item['name']}**\n{item['price']}円" for item in items['menu2']])
        if menu1_lines:
            embed.add_field(name="メニュー1", value=menu1_lines, inline=False)
        if menu2_lines:
            embed.add_field(name="メニュー2", value=menu2_lines, inline=False)

        view = VendingView(all_items, vending_id, interaction.user, interaction.guild, self.bot)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="販売履歴", description="自販機の販売履歴と利益を表示します")
    @is_allowed()
    @app_commands.autocomplete(vending_id=vending_machine_autocomplete)
    @app_commands.describe(vending_id="確認する自販機")
    async def show_sales(self, interaction: discord.Interaction, vending_id: str):
        vm = get_vending_machine(vending_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません", ephemeral=True)

        sales = get_sales(vending_id)
        if not sales:
            return await interaction.response.send_message(
                embed=discord.Embed(title=f"📊 {vm['name']} - 販売履歴", description="まだ販売実績がありません", color=0x3498db),
                ephemeral=True
            )

        total_revenue = sum(s['total_price'] for s in sales)
        total_sales = len(sales)

        item_stats = {}
        for sale in sales:
            for item in sale['items']:
                n = item['name']
                if n not in item_stats:
                    item_stats[n] = {'quantity': 0, 'revenue': 0}
                item_stats[n]['quantity'] += item['quantity']
                item_stats[n]['revenue'] += item['subtotal']

        embed = discord.Embed(title=f"📊 {vm['name']} - 販売利益", color=0x3498db)
        embed.add_field(name="総売上", value=f"¥{total_revenue}", inline=True)
        embed.add_field(name="販売件数", value=f"{total_sales}件", inline=True)
        embed.add_field(name="平均単価", value=f"¥{int(total_revenue / total_sales)}", inline=True)
        embed.add_field(
            name="商品別売上",
            value="```\n" + "\n".join([
                f"{name}: ¥{stats['revenue']}（{stats['quantity']}個）"
                for name, stats in sorted(item_stats.items(), key=lambda x: x[1]['revenue'], reverse=True)
            ]) + "```",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ロール設定", description="購入時に付与するロールを設定します")
    @is_allowed()
    @app_commands.autocomplete(vending_id=vending_machine_autocomplete)
    @app_commands.describe(vending_id="設定する自販機", role="付与するロール")
    async def set_vending_role(self, interaction: discord.Interaction, vending_id: str, role: discord.Role):
        vm = get_vending_machine(vending_id)
        if not vm or vm.get("owner_id") != str(interaction.user.id):
            return await interaction.response.send_message("指定された自販機が見つかりません", ephemeral=True)

        update_vending_machine(vending_id, role_id=str(role.id))
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ ロール設定", description=f"購入時に {role.mention} を付与します", color=0x2ecc71),
            ephemeral=True
        )

    @app_commands.command(name="公開ログ設定", description="公開ログチャンネルを設定します")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="ログを送信するチャンネル")
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        set_log_channel(interaction.guild.id, "public", channel.id)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ 公開ログ設定", description=f"{channel.mention} に設定しました", color=0x2ecc71),
            ephemeral=True
        )

    @app_commands.command(name="非公開ログ設定", description="非公開ログチャンネルを設定します")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="ログを送信するチャンネル")
    async def set_private_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        set_log_channel(interaction.guild.id, "private", channel.id)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ 非公開ログ設定", description=f"{channel.mention} に設定しました", color=0x2ecc71),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(VendingCog(bot))
