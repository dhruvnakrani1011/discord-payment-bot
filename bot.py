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
        ).convert("RGB")


        # Image size print
        print(f"Image Size: {image.size}")


        # =================================================
        # OCR - DIFFERENT SETTINGS TRY KARO
        # =================================================

        text1 = pytesseract.image_to_string(
            image,
            config="--psm 6"
        )


        text2 = pytesseract.image_to_string(
            image,
            config="--psm 11"
        )


        text = text1 + "\n" + text2


        print("\n========== OCR TEXT ==========")

        print(text)

        print("==============================\n")


        # =================================================
        # CLEAN TEXT
        # =================================================

        text = text.replace(",", "")

        text = text.replace("₹", "₹ ")


        # =================================================
        # AMOUNT PATTERNS
        # =================================================

        patterns = [

            # ₹ 5000
            r'₹\s*([\d]+(?:\.\d{1,2})?)',

            # Rs 5000
            r'Rs\.?\s*([\d]+(?:\.\d{1,2})?)',

            # INR 5000
            r'INR\.?\s*([\d]+(?:\.\d{1,2})?)',

            # ₹5,000.00 type
            r'₹\s*([\d]+\.\d{2})',

            # Paid ₹5000
            r'Paid.*?₹?\s*([\d]+(?:\.\d{1,2})?)',

            # Amount Paid 5000
            r'Amount\s*Paid.*?₹?\s*([\d]+(?:\.\d{1,2})?)',

            # Payment of 5000
            r'Payment.*?₹?\s*([\d]+(?:\.\d{1,2})?)',

            # Total Amount 5000
            r'Total\s*Amount.*?₹?\s*([\d]+(?:\.\d{1,2})?)',

            # Transaction Amount 5000
            r'Transaction.*?₹?\s*([\d]+(?:\.\d{1,2})?)',

            # Amount: 5000
            r'Amount\s*[:\-]?\s*₹?\s*([\d]+(?:\.\d{1,2})?)',

            # Total: 5000
            r'Total\s*[:\-]?\s*₹?\s*([\d]+(?:\.\d{1,2})?)',

            # Debited 5000
            r'Debited.*?₹?\s*([\d]+(?:\.\d{1,2})?)',

            # Sent 5000
            r'Sent.*?₹?\s*([\d]+(?:\.\d{1,2})?)',

            # Received 5000
            r'Received.*?₹?\s*([\d]+(?:\.\d{1,2})?)'

        ]


        # =================================================
        # FIND AMOUNT
        # =================================================

        for pattern in patterns:

            matches = re.findall(
                pattern,
                text,
                re.IGNORECASE | re.DOTALL
            )


            if matches:

                for amount in matches:

                    amount = str(amount)

                    amount = amount.replace(",", "")

                    try:

                        number = float(amount)


                        # Minimum payment amount
                        if number >= 1:

                            print(
                                f"Amount Found: {amount}"
                            )

                            return amount


                    except:

                        continue


        print("❌ Amount not found")

        return "NOT FOUND"


    except Exception as e:

        print(f"OCR ERROR: {e}")

        return "NOT FOUND"


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
