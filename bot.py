import discord
import requests
import os
import json
import base64
from datetime import datetime, timezone, timedelta

# ============================================================
# CONFIG
# ============================================================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SCRIPT_URL = os.getenv("GOOGLE_SCRIPT_URL")

IST = timezone(timedelta(hours=5, minutes=30))

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)


# ============================================================
# LOG
# ============================================================

def log(message):
    now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}", flush=True)


# ============================================================
# DOWNLOAD IMAGE
# ============================================================

def download_image(url):

    try:

        log("Downloading screenshot...")

        response = requests.get(
            url,
            timeout=30
        )

        log(f"Download Status: {response.status_code}")

        if response.status_code != 200:
            return None

        log(f"Image Size: {len(response.content)} bytes")

        return response.content

    except Exception as e:

        log(f"DOWNLOAD ERROR: {str(e)}")

        return None


# ============================================================
# GEMINI IMAGE ANALYSIS
# ============================================================

def analyze_image(image_bytes, mime_type):

    try:

        log("Starting Gemini AI analysis...")

        image_base64 = base64.b64encode(
            image_bytes
        ).decode("utf-8")


        prompt = """
Analyze this payment screenshot carefully.

Extract the following information:

1. Actual successful payment amount
2. Name of the person or business who received payment
3. Payment date visible in screenshot
4. Payment time visible in screenshot

IMPORTANT:

- Extract ONLY the actual payment amount.
- Ignore advertisements.
- Ignore offers.
- Ignore cashback.
- Ignore account balance.
- Ignore transaction ID.
- Ignore phone numbers.
- Ignore random numbers.
- The party name must be the recipient name after words like:
  "Paid to"
  "To"
  "Payment to"
  "Sent to"
- Do not use the sender name.
- Do not invent data.

Return ONLY JSON.

Example:

{
  "amount": "1921.00",
  "party_name": "Dhadhodra Arvindbhai Boghabhai",
  "payment_date": "01/09/2026",
  "payment_time": "04:15 PM"
}
"""


        url = (
            "https://generativelanguage.googleapis.com/"
            "v1beta/models/gemini-2.5-flash:generateContent"
            f"?key={GEMINI_API_KEY}"
        )


        payload = {

            "contents": [

                {

                    "parts": [

                        {

                            "text": prompt

                        },

                        {

                            "inline_data": {

                                "mime_type": mime_type,

                                "data": image_base64

                            }

                        }

                    ]

                }

            ],

            "generationConfig": {

                "temperature": 0,

                "responseMimeType": "application/json"

            }

        }


        log("Sending request to Gemini...")

        response = requests.post(

            url,

            json=payload,

            timeout=90

        )


        log(f"Gemini Status Code: {response.status_code}")


        if response.status_code != 200:

            log("========== GEMINI ERROR ==========")

            log(response.text)

            log("==================================")

            return None


        result = response.json()


        log("Gemini response received")


        try:

            text = result["candidates"][0]["content"]["parts"][0]["text"]

        except Exception:

            log("Could not read Gemini response")

            log(json.dumps(result, indent=2))

            return None


        log(f"Gemini Raw Response: {text}")


        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()


        data = json.loads(text)


        return data


    except Exception as e:

        log(f"GEMINI ERROR: {str(e)}")

        return None


# ============================================================
# CLEAN AMOUNT
# ============================================================

def clean_amount(value):

    try:

        if value is None:
            return ""

        value = str(value)

        value = value.replace("₹", "")
        value = value.replace(",", "")
        value = value.replace("INR", "")
        value = value.replace("Rs.", "")
        value = value.replace("Rs", "")
        value = value.strip()

        return float(value)

    except:

        return ""


# ============================================================
# SEND TO GOOGLE SHEET
# ============================================================

def send_to_sheet(
    party_name,
    amount,
    screenshot_url,
    discord_user,
    message_id,
    payment_date,
    payment_time
):

    try:

        log("Preparing Google Sheet data...")


        now = datetime.now(IST)


        payload = {

            "date_time": now.strftime("%d/%m/%Y %H:%M:%S"),

            "party_name": party_name,

            "amount": amount,

            "screenshot_url": screenshot_url,

            "discord_user": discord_user,

            "message_id": str(message_id),

            "payment_date": payment_date,

            "payment_time": payment_time

        }


        log("Sending data to Google Apps Script...")


        response = requests.post(

            GOOGLE_SCRIPT_URL,

            json=payload,

            timeout=60,

            headers={

                "Content-Type": "application/json"

            }

        )


        log(f"Google Script Status: {response.status_code}")

        log(f"Google Script Response: {response.text}")


        if response.status_code == 200:

            return True

        return False


    except Exception as e:

        log(f"GOOGLE SHEET ERROR: {str(e)}")

        return False


# ============================================================
# PROCESS PAYMENT
# ============================================================

async def process_payment(message):

    log("")
    log("========================================")
    log("NEW DISCORD MESSAGE RECEIVED")
    log("========================================")

    log(f"Message ID: {message.id}")

    log(f"User: {message.author}")

    log(f"Content: {message.content}")

    log(f"Attachments: {len(message.attachments)}")


    if message.author.bot:

        log("Ignored: Message is from bot")

        return


    if len(message.attachments) == 0:

        log("Ignored: No attachment")

        return


    attachment = message.attachments[0]


    log(f"Filename: {attachment.filename}")

    log(f"Content Type: {attachment.content_type}")

    log(f"URL: {attachment.url}")


    filename = attachment.filename.lower()


    allowed = (

        ".jpg",
        ".jpeg",
        ".png",
        ".webp"

    )


    if not filename.endswith(allowed):

        log("Ignored: Attachment is not image")

        return


    # MIME TYPE

    if filename.endswith(".png"):

        mime_type = "image/png"

    elif filename.endswith(".webp"):

        mime_type = "image/webp"

    else:

        mime_type = "image/jpeg"


    # DOWNLOAD

    image_bytes = download_image(
        attachment.url
    )


    if not image_bytes:

        log("STOPPED: Image download failed")

        return


    # GEMINI

    result = analyze_image(

        image_bytes,

        mime_type

    )


    if not result:

        log("STOPPED: Gemini did not return result")

        return


    log("")
    log("========== AI RESULT ==========")

    log(json.dumps(result, indent=2))

    log("===============================")


    party_name = result.get(

        "party_name",

        ""

    )


    amount = clean_amount(

        result.get(

            "amount",

            ""

        )

    )


    payment_date = result.get(

        "payment_date",

        ""

    )


    payment_time = result.get(

        "payment_time",

        ""

    )


    if not amount:

        log("STOPPED: Amount not found")

        return


    if not party_name:

        party_name = "UNKNOWN"


    # GOOGLE SHEET

    success = send_to_sheet(

        party_name,

        amount,

        attachment.url,

        str(message.author),

        message.id,

        payment_date,

        payment_time

    )


    if success:

        log("")

        log("################################")

        log("FINAL RESULT: PAYMENT SAVED")

        log("################################")


    else:

        log("")

        log("################################")

        log("FINAL RESULT: SHEET SAVE FAILED")

        log("################################")


# ============================================================
# BOT READY
# ============================================================

@client.event
async def on_ready():

    log("")

    log("========================================")

    log("🤖 DISCORD PAYMENT BOT ACTIVE")

    log("========================================")

    log(f"Bot Name: {client.user}")

    log(f"Bot ID: {client.user.id}")

    log(f"Servers: {len(client.guilds)}")

    log("========================================")


# ============================================================
# MESSAGE EVENT
# ============================================================

@client.event
async def on_message(message):

    try:

        await process_payment(message)

    except Exception as e:

        log(f"UNEXPECTED ERROR: {str(e)}")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    log("Starting bot...")


    if not DISCORD_TOKEN:

        raise Exception("DISCORD_TOKEN is missing")


    if not GEMINI_API_KEY:

        raise Exception("GEMINI_API_KEY is missing")


    if not GOOGLE_SCRIPT_URL:

        raise Exception("GOOGLE_SCRIPT_URL is missing")


    client.run(DISCORD_TOKEN)
