import discord
from discord.ext import commands
from discord import app_commands
import os
import traceback
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('TOKEN')
owner_id = int(os.getenv('OWNER_ID', 0))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='$', intents=intents, help_command=None, owner_id=owner_id)

EXCLUDED_COGS = {"__init__.py", "db.py", "utils.py", "nyanko_editor.py"}

async def load_cogs():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cogs_dir = os.path.join(base_dir, "Cogs")

    if not os.path.exists(cogs_dir):
        print("[ERROR] Cogsフォルダが存在しません")
        return

    for filename in os.listdir(cogs_dir):
        if filename.endswith(".py") and filename not in EXCLUDED_COGS:
            ext = f"Cogs.{filename[:-3]}"
            try:
                await bot.load_extension(ext)
                print(f"✅ Loaded {filename}")
            except Exception as e:
                print(f"❌ Failed to load {filename}: {e}")
                traceback.print_exc()

    await bot.tree.sync()
    print("✅ Commands synced")

bot.setup_hook = load_cogs

STATUS = "にゃんこ大戦争自動代行"

@bot.event
async def on_ready():
    print(f"🤖 Bot Is Ready: {bot.user}")
    await bot.change_presence(activity=discord.Game(name=STATUS), status=discord.Status.idle)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        print(f"❌ {interaction.user}によるコマンド({interaction.command.name})の実行がブロックされました。")
        return
    print(f"❌ Error: {error}")
    traceback.print_exc()

if __name__ == "__main__":
    bot.run(token)
