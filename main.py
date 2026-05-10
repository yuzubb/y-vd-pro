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

async def load_cogs():
    # 読み込みから除外するファイル
    exclude_files = ("__init__.py", "nyanko_editor.py", "db.py")
    
    for filename in os.listdir("./Cogs"):
        if filename.endswith(".py") and filename not in exclude_files:
            try:
                await bot.load_extension(f"Cogs.{filename[:-3]}")
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
