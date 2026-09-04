import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Discord token
TOKEN = os.getenv("DISCORD_TOKEN")

# Check token before starting
if not TOKEN:
    raise ValueError("DISCORD_TOKEN is missing! Please add it in Railway Variables.")

# Remove accidental spaces
TOKEN = TOKEN.strip()

# Discord Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Create Bot
bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==============================
# BOT READY
# ==============================

@bot.event
async def on_ready():

    print("=================================")
    print(f"Bot Logged In Successfully!")
    print(f"Bot Name: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("=================================")

    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="Payment Verification Bot")
        )
    except Exception as e:
        print(f"Presence Error: {e}")


# ==============================
# ERROR HANDLER
# ==============================

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.CommandNotFound):
        return

    print(f"Command Error: {error}")

    try:
        await ctx.send(f"❌ Error: {error}")
    except:
        pass


# ==============================
# TEST COMMAND
# ==============================

@bot.command()
async def ping(ctx):

    await ctx.send("🏓 Pong! Bot is working properly.")


# ==============================
# BOT STATUS COMMAND
# ==============================

@bot.command()
async def status(ctx):

    embed = discord.Embed(
        title="🤖 Bot Status",
        description="Bot is currently online and working!",
    )

    embed.add_field(
        name="Bot Name",
        value=str(bot.user),
        inline=False
    )

    embed.add_field(
        name="Latency",
        value=f"{round(bot.latency * 1000)} ms",
        inline=False
    )

    await ctx.send(embed=embed)


# ==============================
# START BOT
# ==============================

async def main():

    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except discord.LoginFailure:
        print("ERROR: Invalid Discord Token!")
        print("Please check DISCORD_TOKEN in Railway Variables.")

    except Exception as e:
        print(f"Fatal Error: {e}")
        response = requests.get(image_url, timeout=30)

        image = Image.open(io.BytesIO(response.content))

        text = pytesseract.image_to_string(image)

        print("OCR TEXT:", text)

        patterns = [

            r'₹\s?([\d,]+(?:\.\d{1,2})?)',

            r'INR\s?([\d,]+(?:\.\d{1,2})?)',

            r'Amount[:\s]*₹?\s?([\d,]+(?:\.\d{1,2})?)',

            r'Paid[:\s]*₹?\s?([\d,]+(?:\.\d{1,2})?)'

        ]

        for pattern in patterns:

            match = re.search(pattern, text, re.IGNORECASE)

            if match:

                amount = match.group(1).replace(",", "")

                return amount

        return ""

    except Exception as e:

        print("OCR ERROR:", e)

        return ""


# ==============================
# DISCORD MESSAGE
# ==============================

@client.event
async def on_ready():

    print(f"Bot Logged In: {client.user}")


@client.event
async def on_message(message):

    # Bot ના પોતાના messages ignore
    if message.author.bot:
        return


    # Screenshot ન હોય તો ignore
    if not message.attachments:
        return


    # Party Name
    party_name = message.content.strip()


    # Party name ખાલી હોય તો ignore
    if not party_name:
        return


    for attachment in message.attachments:

        # માત્ર image files
        if attachment.content_type and attachment.content_type.startswith("image"):

            screenshot_url = attachment.url

            # Amount OCR
            amount = extract_amount(screenshot_url)


            data = {

                "secret": SECRET_KEY,

                "partyName": party_name,

                "amount": amount,

                "screenshot": screenshot_url,

                "discordUser": str(message.author),

                "messageId": str(message.id)

            }


            try:

                response = requests.post(
                    GOOGLE_SCRIPT_URL,
                    json=data,
                    timeout=30
                )

                print(response.text)


            except Exception as e:

                print("GOOGLE SHEET ERROR:", e)


client.run(DISCORD_TOKEN)
