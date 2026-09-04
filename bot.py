import discord
import requests
import re
import io
from PIL import Image
import pytesseract

# ==============================
# SETTINGS
# ==============================

DISCORD_TOKEN = "YOUR_DISCORD_BOT_TOKEN"

GOOGLE_SCRIPT_URL = "YOUR_GOOGLE_APPS_SCRIPT_WEB_APP_URL"

SECRET_KEY = "CHANGE_THIS_TO_YOUR_SECRET_KEY"


# ==============================
# DISCORD SETTINGS
# ==============================

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


# ==============================
# AMOUNT DETECTION
# ==============================

def extract_amount(image_url):

    try:

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
