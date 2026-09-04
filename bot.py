import os
import discord
from discord.ext import commands

# =========================================================
# DISCORD BOT SETUP
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError(
        "DISCORD_TOKEN Railway Variables ma add karyo nathi!"
    )

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    print("=" * 50)
    print(f"Bot Active: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"Servers: {len(bot.guilds)}")
    print("=" * 50)

    try:
        synced = await bot.tree.sync()
        print(f"Slash commands synced: {len(synced)}")

    except Exception as e:
        print(f"Command sync error: {e}")


# =========================================================
# BOT JOIN SERVER
# =========================================================

@bot.event
async def on_guild_join(guild):

    print(f"Joined server: {guild.name}")


# =========================================================
# MESSAGE DETECTION
# =========================================================

@bot.event
async def on_message(message):

    # Bot potana messages ignore kare
    if message.author.bot:
        return

    # Normal commands process
    await bot.process_commands(message)


# =========================================================
# SLASH COMMAND - STATUS
# =========================================================

@bot.tree.command(
    name="status",
    description="Check bot status"
)
async def status(interaction: discord.Interaction):

    await interaction.response.send_message(
        "🟢 Payment Bot is Active!",
        ephemeral=True
    )


# =========================================================
# SLASH COMMAND - PING
# =========================================================

@bot.tree.command(
    name="ping",
    description="Check bot connection"
)
async def ping(interaction: discord.Interaction):

    latency = round(bot.latency * 1000)

    await interaction.response.send_message(
        f"🏓 Pong! Latency: {latency}ms"
    )


# =========================================================
# SLASH COMMAND - HELP
# =========================================================

@bot.tree.command(
    name="help",
    description="Show bot commands"
)
async def help_command(interaction: discord.Interaction):

    message = """
🤖 **Payment Bot Commands**

/status - Bot active che ke nahi check karo

/ping - Bot connection check karo

Aagal payment screenshot checking system pan add karishu.
"""

    await interaction.response.send_message(message)


# =========================================================
# ERROR HANDLER
# =========================================================

@bot.event
async def on_command_error(ctx, error):

    print(f"Command Error: {error}")


# =========================================================
# START BOT
# =========================================================

if __name__ == "__main__":

    print("Starting Discord Payment Bot...")

    bot.run(TOKEN)
