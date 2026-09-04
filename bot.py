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
intents.guilds = True

client = discord.Client(intents=intents)


# =========================================================
# OCR - IMAGE MATHI AMOUNT FIND KARO
# =========================================================

def extract_amount(image_url):

    try:

        print("\nDownloading screenshot...")

        response = requests.get(
            image_url,
            timeout=30
        )

        response.raise_for_status()


        image = Image.open(
            io.BytesIO(response.content)
        )


        # OCR
        text = pytesseract.image_to_string(image)


        print("\n========== OCR TEXT ==========")
        print(text)
        print("==============================\n")


        # Amount patterns
        patterns = [

            # ₹ 5,000
            r'₹\s*([\d,]+(?:\.\d{1,2})?)',

            # Rs 5000
            r'Rs\.?\s*([\d,]+(?:\.\d{1,2})?)',

            # INR 5000
            r'INR\s*([\d,]+(?:\.\d{1,2})?)',

            # Amount: 5000
            r'Amount[:\s]*₹?\s*([\d,]+(?:\.\d{1,2})?)',

            # Paid: 5000
            r'Paid[:\s]*₹?\s*([\d,]+(?:\.\d{1,2})?)',

            # Total: 5000
            r'Total[:\s]*₹?\s*([\d,]+(?:\.\d{1,2})?)',

            # Payment: 5000
            r'Payment[:\s]*₹?\s*([\d,]+(?:\.\d{1,2})?)'

        ]


        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )


            if match:

                amount = match.group(1)

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


        print("\nSending data to Google Sheet...")

        response = requests.post(

            GOOGLE_SCRIPT_URL,

            json=data,

            timeout=30

        )


        print("Google Sheet Status Code:")

        print(response.status_code)


        print("Google Sheet Response:")

        print(response.text)


        return True


    except Exception as e:

        print(f"Google Sheet Error: {e}")

        return False


# =========================================================
# BOT READY
# =========================================================

@client.event
async def on_ready():

    print("\n======================================")

    print("DISCORD PAYMENT BOT ACTIVE")

    print(f"Bot Name: {client.user}")

    print(f"Bot ID: {client.user.id}")

    print(f"Servers: {len(client.guilds)}")

    print("======================================\n")


# =========================================================
# BOT JOIN SERVER
# =========================================================

@client.event
async def on_guild_join(guild):

    print("======================================")

    print(f"Joined Server: {guild.name}")

    print(f"Server ID: {guild.id}")

    print("======================================")


# =========================================================
# NEW DISCORD MESSAGE
# =========================================================

@client.event
async def on_message(message):


    # Bot potana message ignore kare

    if message.author.bot:

        return


    # Screenshot nathi to ignore

    if not message.attachments:

        return


    # Party Name = Message ma lakhelu text

    party_name = message.content.strip()


    # Party name blank hoy

    if not party_name:

        print("\nParty Name Missing")

        print("Message ID:", message.id)

        return


    print("\n======================================")

    print("NEW PAYMENT MESSAGE DETECTED")

    print(f"Party Name: {party_name}")

    print(f"User: {message.author}")

    print(f"User ID: {message.author.id}")

    print(f"Attachments: {len(message.attachments)}")

    print(f"Message ID: {message.id}")

    print("======================================\n")


    # Badha attachments check karo

    for attachment in message.attachments:


        # Image type check

        is_image = False


        if attachment.content_type:

            if attachment.content_type.startswith("image"):

                is_image = True


        # Content type na hoy to filename thi check

        if attachment.filename.lower().endswith(

            (
                ".png",
                ".jpg",
                ".jpeg",
                ".webp"
            )

        ):

            is_image = True


        # Image nathi to skip

        if not is_image:

            print(

                f"Skipping non-image file: {attachment.filename}"

            )

            continue


        screenshot_url = attachment.url


        print("\nProcessing Screenshot...")

        print(f"File: {attachment.filename}")

        print(f"URL: {screenshot_url}")


        # OCR thi amount find karo

        amount = extract_amount(

            screenshot_url

        )


        # Amount na male to pan entry moklo

        if not amount:

            amount = "NOT FOUND"


        # Google Sheet ma entry

        success = send_to_google_sheet(

            party_name=party_name,

            amount=amount,

            screenshot_url=screenshot_url,

            discord_user=str(message.author),

            message_id=str(message.id)

        )


        # Console status

        if success:

            print("\n✓ Successfully sent to Google Sheet\n")

        else:

            print("\n✗ Failed to send to Google Sheet\n")


# =========================================================
# START BOT
# =========================================================

if __name__ == "__main__":

    print("\n======================================")

    print("Starting Discord Payment Bot...")

    print("======================================\n")


    client.run(DISCORD_TOKEN)
