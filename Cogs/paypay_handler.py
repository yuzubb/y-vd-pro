import discord
from discord import ui
from discord.ext import commands
from discord import app_commands
import uuid
from Cogs.db import get_paypay_account, save_paypay_account
from Cogs.utils import is_allowed
import paypayu


class PayPayOTPModal(ui.Modal, title="PayPay OTP認証"):
    otp_input = ui.TextInput(
        label="ワンタイムパスワード",
        placeholder="SMSに届いた4桁の認証コードを入力",
        min_length=4,
        max_length=4,
        required=True
    )

    def __init__(self, phone, password, set_uuid, otpid, otp_pre):
        super().__init__(timeout=300)
        self.phone = phone
        self.password = password
        self.set_uuid = set_uuid
        self.otpid = otpid
        self.otp_pre = otp_pre

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        otp_result = await paypayu.login_otp(
            self.set_uuid, self.otp_input.value, self.otpid, self.otp_pre
        )

        # otp_resultがaccess_token文字列の場合もOKとみなす
        if otp_result and otp_result != "ERR":
            access_token = otp_result if otp_result != "OK" else None
            save_paypay_account(interaction.user.id, self.phone, self.password, self.set_uuid, access_token=access_token)

            embed = discord.Embed(
                title="✅ 登録完了",
                description="PayPayアカウントを登録しました。\nサーバー再起動後も引き続き利用できます。",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="❌ 認証エラー",
                description="認証コードが正しくないか、期限切れです。",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


class PaypayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="paypay登録", description="PayPayアカウントを登録します（再起動後も維持）")
    @is_allowed()
    @app_commands.describe(phone="電話番号（090...）", password="パスワード")
    async def paypay_register(self, interaction: discord.Interaction, phone: str, password: str):
        set_uuid = str(uuid.uuid4())

        result = await paypayu.login(phone, password, set_uuid)

        print(f"--- PayPay Login Response ---")
        print(result)
        print(f"-----------------------------")

        if result.get("response_type") == "ErrorResponse":
            error_code = result.get("error_code", "")
            reason = "電話番号またはパスワードが間違っています。"

            if "TOO_MANY_REQUESTS" in error_code:
                reason = "短時間に何度も試行したためロックされています。時間を置いてください。"
            elif "UNAUTHORIZED_CLIENT" in error_code:
                reason = "この環境からのログインは許可されていません（IPブロック等）。"

            embed = discord.Embed(title="PayPayログインエラー", description=reason, color=0xff3333)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if "otp_reference_id" in result:
            otpid = result["otp_reference_id"]
            otp_pre = result.get("otp_prefix", "")
            modal = PayPayOTPModal(phone, password, set_uuid, otpid, otp_pre)
            await interaction.response.send_modal(modal)

        elif "access_token" in result:
            save_paypay_account(interaction.user.id, phone, password, set_uuid, access_token=result["access_token"])
            embed = discord.Embed(
                title="✅ 登録完了",
                description="ログインに成功しました（認証コード不要）。\nサーバー再起動後も引き続き利用できます。",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        else:
            embed = discord.Embed(
                title="エラー",
                description="PayPayから予期しない応答がありました。しばらく待ってから再度お試しください。",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="paypay確認", description="登録済みPayPayアカウントを確認します")
    @is_allowed()
    async def paypay_check(self, interaction: discord.Interaction):
        account = get_paypay_account(interaction.user.id)
        if account:
            embed = discord.Embed(
                title="✅ PayPay登録済み",
                description=f"電話番号: `{account['phone'][:4]}****{account['phone'][-4:]}`\nSupabaseに保存済みのため、再起動後も有効です。",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ 未登録",
                description="/paypay登録 コマンドで登録してください。",
                color=discord.Color.red()
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(PaypayCog(bot))
