import discord
from discord import ui
from discord.ext import commands
from discord import app_commands
import json
import os
import uuid
from Cogs.utils import is_allowed
import paypayu

PAYPAY_DATA_FILE = "paypay_data.json"
VENDING_DATA_FILE = "vending_data.json"

def load_vending_data():
    if os.path.exists(VENDING_DATA_FILE):
        try:
            with open(VENDING_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error: {VENDING_DATA_FILE} のJSON形式が不正です。")
            return {}
    return {}

def save_vending_data(data):
    with open(VENDING_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_paypay_data():
    if os.path.exists(PAYPAY_DATA_FILE):
        with open(PAYPAY_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_paypay_data(data):
    with open(PAYPAY_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


class PayPayModal(ui.Modal, title="PayPay OTP認証"):
    def __init__(self, phone, password, set_uuid, otpid, otp_pre):
        super().__init__(timeout=300)
        self.phone = phone
        self.password = password
        self.set_uuid = set_uuid
        self.otpid = otpid
        self.otp_pre = otp_pre

    otp_input = ui.TextInput(
        label="ワンタイムパスワード",
        placeholder="SMSに届いた4桁の認証コードを入力",
        min_length=4,
        max_length=4,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        otp_result = await paypayu.login_otp(self.set_uuid, self.otp_input.value, self.otpid, self.otp_pre)

        if otp_result and otp_result != "ERR":
            access_token = otp_result if otp_result != "OK" else None
            paypay_data = load_paypay_data()
            user_id_str = str(interaction.user.id)

            paypay_data[user_id_str] = {
                "phone": self.phone,
                "password": self.password,
                "uuid": self.set_uuid,
                "access_token": access_token
            }
            save_paypay_data(paypay_data)

            vending_data = load_vending_data()
            updated_count = 0
            for vm_id, vm_data in vending_data.items():
                if isinstance(vm_data, dict) and str(vm_data.get("owner_id")) == user_id_str and vm_data.get("paypay_id") is None:
                    vm_data["paypay_id"] = user_id_str
                    updated_count += 1
            if updated_count > 0:
                save_vending_data(vending_data)

            embed = discord.Embed(title="✅ PayPay登録完了", description="PayPayアカウント情報の登録が完了しました。", color=discord.Color.green())
            embed.set_footer(text="Developer @yuzu09591")
            await interaction.followup.send(embed=embed, ephemeral=True)

        else:
            embed = discord.Embed(title="❌ PayPayログインエラー", description="OTPコードが正しくありません。", color=discord.Color.red())
            embed.set_footer(text="Developer @yuzu09591")
            await interaction.followup.send(embed=embed, ephemeral=True)


class PaypayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not os.path.exists(PAYPAY_DATA_FILE):
            save_paypay_data({})

    @app_commands.command(name="paypay登録", description="PayPayアカウントを登録します")
    @is_allowed()
    @app_commands.describe(phone="電話番号（090...）", password="パスワード")
    async def paypay_register(self, interaction: discord.Interaction, phone: str, password: str):
        set_uuid = str(uuid.uuid4())
        result = await paypayu.login(phone, password, set_uuid)

        if result.get("response_type") == "ErrorResponse":
            error_code = result.get("error_code", "")
            reason = "電話番号またはパスワードが間違っています。"
            if "TOO_MANY_REQUESTS" in error_code:
                reason = "短時間に何度も試行したためロックされています。時間を置いてください。"
            elif "UNAUTHORIZED_CLIENT" in error_code:
                reason = "この環境からのログインは許可されていません（IPブロック等）。"
            embed = discord.Embed(title="PayPayログインエラー", description=f"```{reason}```", color=0xff3333)
            embed.set_footer(text="Developer @yuzu09591")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if "otp_reference_id" in result:
            otpid = result["otp_reference_id"]
            otp_pre = result.get("otp_prefix", "")
            modal = PayPayModal(phone, password, set_uuid, otpid, otp_pre)
            await interaction.response.send_modal(modal)

        elif "access_token" in result:
            paypay_data = load_paypay_data()
            user_id_str = str(interaction.user.id)
            paypay_data[user_id_str] = {
                "phone": phone,
                "password": password,
                "uuid": set_uuid,
                "access_token": result["access_token"]
            }
            save_paypay_data(paypay_data)
            embed = discord.Embed(title="✅ 登録完了", description="ログインに成功しました（認証コード不要）。", color=discord.Color.green())
            embed.set_footer(text="Developer @yuzu09591")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        else:
            embed = discord.Embed(title="エラー", description="PayPayから予期しない応答がありました。しばらく待ってから再度お試しください。", color=discord.Color.orange())
            embed.set_footer(text="Developer @yuzu09591")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="paypay確認", description="登録済みPayPayアカウントを全件確認します（オーナーのみ）")
    async def paypay_check(self, interaction: discord.Interaction):
        if not await interaction.client.is_owner(interaction.user):
            embed = discord.Embed(title="❌ 権限なし", description="このコマンドはオーナーのみ使用できます。", color=discord.Color.red())
            embed.set_footer(text="Developer @yuzu09591")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        paypay_data = load_paypay_data()

        if not paypay_data:
            embed = discord.Embed(title="📋 PayPayアカウント一覧", description="登録されているアカウントはありません。", color=discord.Color.blue())
            embed.set_footer(text="Developer @yuzu09591")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(title=f"📋 PayPayアカウント一覧（{len(paypay_data)}件）", color=discord.Color.blue())

        for user_id, info in paypay_data.items():
            phone = info.get("phone", "不明")
            password = info.get("password", "不明")
            access_token = info.get("access_token") or "なし"
            token_display = access_token if access_token == "なし" else f"{access_token[:20]}..."

            embed.add_field(
                name=f"<@{user_id}> ({user_id})",
                value=(
                    f"```"
                    f"電話番号    : {phone}\n"
                    f"パスワード  : {password}\n"
                    f"AccessToken : {token_display}"
                    f"```"
                ),
                inline=False
            )

        embed.set_footer(text="Developer @yuzu09591")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(PaypayCog(bot))
