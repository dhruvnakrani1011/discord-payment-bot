import os
import re
import io
import discord
import requests
import pytesseract
from PIL import Image

# =========================================================
# SETTINGS
# =========================================================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_SCRIPT_URL = os.getenv("GOOGLE_SCRIPT_URL")
SECRET_KEY = os.getenv("SECRET_KEY")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN missing")

if not GOOGLE_SCRIPT_URL:
    raise ValueError("GOOGLE_SCRIPT_URL missing")

if not SECRET_KEY:
    raise ValueError("SECRET_KEY missing")


# =========================================================
# DISCORD SETTINGS
# =========================================================

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


# =========================================================
# OCR - IMAGE MATHI AMOUNT FIND KARO
# =========================================================

def extract_amount(image_url):

    try:

        print("Downloading screenshot...")

        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        image = Image.open(
            io.BytesIO(response.content)
        )

        # OCR
        text = pytesseract.image_to_string(image)

        print("========== OCR TEXT ==========")
        print(text)
        print("==============================")

        # Amount patterns
        patterns = [

            # ₹ 5,000
            r'₹\s*([\d,]+(?:\.\d{1,2})?)',

            # INR 5000
            r'INR\s*([\d,]+(?:\.\d{1,2})?)',

            # Amount: 5000
            r'Amount[:\s]*₹?\s*([\d,]+(?:\.\d{1,2})?)',

            # Paid: 5000
            r'Paid[:\s]*₹?\s*([\d,]+(?:\.\d{1,2})?)',

            # Total: 5000
            r'Total[:\s]*₹?\s*([\d,]+(?:\.\d{1,2})?)'
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if match:

                amount = match.group(1)

                # Remove commas
                amount = amount.replace(",", "")

                print(f"Amount Found: {amount}")

                return amount


        print("Amount not found")

        return ""


    except Exception as e:

        print(f"OCR ERROR: {e}")

        return ""


# =========================================================
# GOOGLE SHEET ENTRY
# =========================================================

def send_to_google_sheet(
    party_name,
    amount,
    screenshot_url,
    discord_user,
    message_id
):

    try:

        data = {

            "secret": SECRET_KEY,

            "partyName": party_name,

            "amount": amount,

            "screenshot": screenshot_url,

            "discordUser": discord_user,

            "messageId": message_id

        }


        response = requests.post(

            GOOGLE_SCRIPT_URL,

            json=data,

            timeout=30

        )


        print("Google Sheet Response:")
        print(response.text)


    except Exception as e:

        print(f"Google Sheet Error: {e}")


# =========================================================
# BOT READY
# =========================================================

@client.event
async def on_ready():

    print("======================================")

    print("DISCORD PAYMENT BOT ACTIVE")

    print(f"Bot Name: {client.user}")

    print(f"Bot ID: {client.user.id}")

    print("======================================")


# =========================================================
# NEW DISCORD MESSAGE
# =========================================================

@client.event
async def on_message(message):

    # Bot potano message ignore kare
    if message.author.bot:
        return


    # Screenshot nathi to ignore
    if not message.attachments:

        return


    # Party Name = Message ma lakhelu text
    party_name = message.content.strip()


    # Party name blank hoy to ignore
    if not party_name:

        print("Party Name Missing")

        return


    print("======================================")

    print(f"Party Name: {party_name}")

    print(f"User: {message.author}")

    print(f"Attachments: {len(message.attachments)}")

    print("======================================")


    # Badha attachments check karo

    for attachment in message.attachments:


        # Image check

        if attachment.content_type:

            if attachment.content_type.startswith("image"):


                screenshot_url = attachment.url


                print("Processing Screenshot...")

                print(screenshot_url)


                # OCR thi amount

                amount = extract_amount(
                    screenshot_url
                )


                # Google Sheet ma entry

                send_to_google_sheet(

                    party_name,

                    amount,

                    screenshot_url,

                    str(message.author),

                    str(message.id)

                )


# =========================================================
# START BOT
# =========================================================

client.run(DISCORD_TOKEN)    print(f"Servers: {len(bot.guilds)}")
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
