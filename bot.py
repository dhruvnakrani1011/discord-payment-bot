import discord
import requests
import os
import json
import re
from datetime import datetime, timezone, timedelta

# ============================================================
# CONFIGURATION
# ============================================================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SCRIPT_URL = os.getenv("GOOGLE_SCRIPT_URL")

IST = timezone(timedelta(hours=5, minutes=30))

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


# ============================================================
# HELPER - LOG
# ============================================================

def log(text):
    print(f"[{datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')}] {text}")


# ============================================================
# DOWNLOAD IMAGE
# ============================================================

def download_image(url):

    try:

        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            return response.content

        log(f"Image download failed: {response.status_code}")
        return None

    except Exception as e:

        log(f"Image download error: {e}")
        return None


# ============================================================
# GEMINI AI OCR
# ============================================================

def read_payment_screenshot(image_bytes):

    try:

        import base64

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        prompt = """
You are a payment screenshot data extraction system.

Analyze the payment screenshot carefully.

Extract ONLY these details:

1. Amount paid
2. Recipient / Party Name
3. Payment Date if visible
4. Payment Time if visible

IMPORTANT RULES:

- The amount must be the actual successful payment amount.
- Ignore advertisements.
- Ignore cashback.
- Ignore account balance.
- Ignore transaction IDs.
- Ignore unrelated numbers.
- Party name should be the person or business who received the payment.
- If name is long, extract the complete visible recipient name.
- Do not invent information.
- If information is not visible return empty string.

Return ONLY valid JSON.

Format:

{
  "amount": "",
  "party_name": "",
  "payment_date": "",
  "payment_time": "",
  "confidence": ""
}
"""

        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            "models/gemini-2.5-flash:generateContent"
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
                                "mime_type": "image/jpeg",
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

        response = requests.post(
            url,
            json=payload,
            timeout=60
        )

        log(f"Gemini Status: {response.status_code}")

        if response.status_code != 200:

            log(f"Gemini Error: {response.text}")
            return None

        result = response.json()

        text = result["candidates"][0]["content"]["parts"][0]["text"]

        log(f"Gemini Raw Result: {text}")

        # Remove markdown if Gemini sends it
        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

        data = json.loads(text)

        return data

    except Exception as e:

        log(f"Gemini Processing Error: {e}")
        return None


# ============================================================
# CLEAN AMOUNT
# ============================================================

def clean_amount(amount):

    if not amount:
        return ""

    amount = str(amount)

    amount = amount.replace("₹", "")
    amount = amount.replace(",", "")
    amount = amount.replace("Rs.", "")
    amount = amount.replace("INR", "")
    amount = amount.strip()

    try:

        value = float(amount)

        return round(value, 2)

    except:

        return amount


# ============================================================
# SEND DATA TO GOOGLE SHEETS
# ============================================================

def send_to_google_sheet(
    party_name,
    amount,
    screenshot_url,
    discord_user,
    message_id,
    payment_date="",
    payment_time=""
):

    try:

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

        log("Sending data to Google Sheet...")

        response = requests.post(

            GOOGLE_SCRIPT_URL,

            json=payload,

            timeout=30

        )

        log(f"Google Script Response: {response.text}")

        return True

    except Exception as e:

        log(f"Google Sheet Error: {e}")

        return False


# ============================================================
# PROCESS MESSAGE
# ============================================================

async def process_payment_message(message):

    if message.author.bot:
        return

    if not message.attachments:
        return

    log("=" * 60)
    log("NEW PAYMENT MESSAGE RECEIVED")
    log(f"Message ID: {message.id}")
    log(f"Discord User: {message.author}")
    log(f"Attachments: {len(message.attachments)}")

    attachment = message.attachments[0]

    # Check image
    if not attachment.content_type:

        filename = attachment.filename.lower()

        if not filename.endswith(
            (".jpg", ".jpeg", ".png", ".webp")
        ):
            log("Not an image")
            return

    log(f"Processing image: {attachment.filename}")

    image_bytes = download_image(attachment.url)

    if not image_bytes:

        log("Image could not be downloaded")

        return

    # ========================================================
    # AI OCR
    # ========================================================

    result = read_payment_screenshot(image_bytes)

    if not result:

        log("FINAL RESULT: NOT FOUND")

        return

    party_name = result.get("party_name", "")
    amount = clean_amount(result.get("amount", ""))

    payment_date = result.get("payment_date", "")
    payment_time = result.get("payment_time", "")

    confidence = result.get("confidence", "")

    log("=" * 60)
    log("AI RESULT")
    log(f"Party Name: {party_name}")
    log(f"Amount: {amount}")
    log(f"Payment Date: {payment_date}")
    log(f"Payment Time: {payment_time}")
    log(f"Confidence: {confidence}")
    log("=" * 60)

    # ========================================================
    # VALIDATION
    # ========================================================

    if not amount:

        log("Amount not found")

        return

    if not party_name:

        party_name = "UNKNOWN"

    # ========================================================
    # SEND TO GOOGLE SHEET
    # ========================================================

    success = send_to_google_sheet(

        party_name=party_name,

        amount=amount,

        screenshot_url=attachment.url,

        discord_user=str(message.author),

        message_id=message.id,

        payment_date=payment_date,

        payment_time=payment_time

    )

    if success:

        log("FINAL RESULT: SAVED SUCCESSFULLY")

    else:

        log("FINAL RESULT: GOOGLE SHEET ERROR")


# ============================================================
# BOT READY
# ============================================================

@client.event
async def on_ready():

    log("=" * 60)
    log("🤖 DISCORD PAYMENT BOT ACTIVE")
    log("=" * 60)

    log(f"Bot Name: {client.user}")
    log(f"Bot ID: {client.user.id}")
    log(f"Servers: {len(client.guilds)}")

    log("=" * 60)


# ============================================================
# NEW MESSAGE
# ============================================================

@client.event
async def on_message(message):

    try:

        await process_payment_message(message)

    except Exception as e:

        log(f"Message Processing Error: {e}")


# ============================================================
# START BOT
# ============================================================

if __name__ == "__main__":

    if not DISCORD_TOKEN:

        raise ValueError("DISCORD_TOKEN not found")

    if not GEMINI_API_KEY:

        raise ValueError("GEMINI_API_KEY not found")

    if not GOOGLE_SCRIPT_URL:

        raise ValueError("GOOGLE_SCRIPT_URL not found")

    client.run(DISCORD_TOKEN)
