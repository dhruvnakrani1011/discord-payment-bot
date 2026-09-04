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


# ============================================================
# DISCORD INTENTS
# ============================================================

intents = discord.Intents.default()

intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)


# ============================================================
# LOG
# ============================================================

def log(message):

    now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

    print(
        f"[{now}] {message}",
        flush=True
    )


# ============================================================
# CLEAN PARTY NAME
# DISCORD MESSAGE TEXT = PARTY NAME
# ============================================================

def clean_party_name(value):

    try:

        if not value:
            return ""

        value = str(value).strip()

        # Remove extra spaces and line breaks
        value = " ".join(value.split())

        return value

    except Exception as e:

        log(f"PARTY NAME ERROR: {e}")

        return ""


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

            log("Image download failed")

            return None

        log(
            f"Image Size: {len(response.content)} bytes"
        )

        return response.content

    except Exception as e:

        log(f"DOWNLOAD ERROR: {e}")

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


        # ====================================================
        # GEMINI PROMPT
        # ====================================================

        prompt = """
You are analyzing a payment screenshot.

Extract ONLY these three things:

1. Actual successful payment amount
2. Actual payment date
3. Actual payment time

IMPORTANT:

DO NOT extract party name.

DO NOT extract:
- Account balance
- Available balance
- Wallet balance
- Cashback
- Offers
- Phone numbers
- UPI IDs
- Transaction IDs
- Reference numbers
- Random numbers
- Failed transaction amounts

AMOUNT RULE:

Find the amount that was actually PAID successfully.

If multiple amounts are visible, select only the successful transaction amount.

DATE RULE:

Find the transaction/payment date.

TIME RULE:

Find the transaction/payment time.

Return ONLY valid JSON.

Use exactly this format:

{
  "amount": "",
  "payment_date": "",
  "payment_time": ""
}

Example:

{
  "amount": "1921.00",
  "payment_date": "01/09/2026",
  "payment_time": "04:15 PM"
}

Do not include markdown.
Do not include explanation.
Only JSON.
"""


        # ====================================================
        # GEMINI API
        # ====================================================

        url = (
            "https://generativelanguage.googleapis.com/"
            "v1beta/models/gemini-3.6-flash:generateContent"
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


        log(
            f"Gemini Status Code: {response.status_code}"
        )


        # ====================================================
        # GEMINI ERROR
        # ====================================================

        if response.status_code != 200:

            log("========== GEMINI ERROR ==========")

            log(response.text)

            log("==================================")

            return None


        result = response.json()


        # ====================================================
        # READ GEMINI RESPONSE
        # ====================================================

        try:

            text = (
                result["candidates"][0]
                ["content"]
                ["parts"][0]
                ["text"]
            )

        except Exception:

            log("Could not read Gemini response")

            log(
                json.dumps(
                    result,
                    indent=2
                )
            )

            return None


        log(f"Gemini Raw Response: {text}")


        # Remove markdown if Gemini sends it

        text = text.replace(
            "```json",
            ""
        )

        text = text.replace(
            "```",
            ""
        )

        text = text.strip()


        data = json.loads(text)


        return data


    except Exception as e:

        log(f"GEMINI ERROR: {e}")

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


        amount = float(value)


        return amount


    except Exception:

        return ""


# ============================================================
# SEND DATA TO GOOGLE SHEET
# ============================================================

def send_to_sheet(

    action,

    party_name="",

    amount="",

    screenshot_url="",

    discord_user="",

    message_id="",

    payment_date="",

    payment_time=""

):

    try:

        now = datetime.now(IST)


        payload = {

            "action": action,

            "date_time": now.strftime(
                "%d/%m/%Y %H:%M:%S"
            ),

            "party_name": party_name,

            "amount": amount,

            "screenshot_url": screenshot_url,

            "discord_user": discord_user,

            "message_id": str(message_id),

            "payment_date": payment_date,

            "payment_time": payment_time

        }


        log(
            f"Sending {action.upper()} request to Google Sheet..."
        )


        response = requests.post(

            GOOGLE_SCRIPT_URL,

            json=payload,

            timeout=60,

            headers={

                "Content-Type": "application/json"

            }

        )


        log(
            f"Google Sheet Status: {response.status_code}"
        )

        log(
            f"Google Sheet Response: {response.text}"
        )


        if response.status_code == 200:

            return True

        return False


    except Exception as e:

        log(
            f"GOOGLE SHEET ERROR: {e}"
        )

        return False


# ============================================================
# PROCESS PAYMENT
# ============================================================

async def process_payment(
    message,
    action="create"
):

    try:

        log("")

        log(
            "=========================================="
        )

        log(
            f"PROCESS PAYMENT: {action.upper()}"
        )

        log(
            "=========================================="
        )


        # Ignore bot messages

        if message.author.bot:

            log("Ignored bot message")

            return


        # ====================================================
        # MESSAGE INFORMATION
        # ====================================================

        log(f"Message ID: {message.id}")

        log(f"User: {message.author}")

        log(f"Message Text: {message.content}")

        log(
            f"Attachments: {len(message.attachments)}"
        )


        # ====================================================
        # PARTY NAME
        # ====================================================

        party_name = clean_party_name(
            message.content
        )


        if not party_name:

            log(
                "Party name is empty"
            )

            return


        log(
            f"Party Name: {party_name}"
        )


        # ====================================================
        # NO SCREENSHOT
        # ====================================================

        if len(message.attachments) == 0:

            log("No screenshot attached")


            # If message is edited and only party name changed,
            # update only party name in Google Sheet

            if action == "update":

                send_to_sheet(

                    action="update",

                    party_name=party_name,

                    amount="",

                    screenshot_url="",

                    discord_user=str(message.author),

                    message_id=message.id,

                    payment_date="",

                    payment_time=""

                )


            return


        # ====================================================
        # GET FIRST ATTACHMENT
        # ====================================================

        attachment = message.attachments[0]

        filename = attachment.filename.lower()


        # ====================================================
        # CHECK IMAGE FORMAT
        # ====================================================

        allowed_extensions = (

            ".jpg",

            ".jpeg",

            ".png",

            ".webp"

        )


        if not filename.endswith(
            allowed_extensions
        ):

            log(
                "Attachment is not a supported image"
            )

            return


        log(
            f"Processing image: {attachment.filename}"
        )


        # ====================================================
        # MIME TYPE
        # ====================================================

        if filename.endswith(".png"):

            mime_type = "image/png"


        elif filename.endswith(".webp"):

            mime_type = "image/webp"


        else:

            mime_type = "image/jpeg"


        # ====================================================
        # DOWNLOAD IMAGE
        # ====================================================

        image_bytes = download_image(
            attachment.url
        )


        if not image_bytes:

            log(
                "Screenshot download failed"
            )

            return


        # ====================================================
        # GEMINI ANALYSIS
        # ====================================================

        result = analyze_image(

            image_bytes,

            mime_type

        )


        if not result:

            log(
                "STOPPED: Gemini did not return result"
            )

            return


        # ====================================================
        # READ RESULT
        # ====================================================

        amount = clean_amount(

            result.get(
                "amount",
                ""
            )

        )


        payment_date = str(

            result.get(
                "payment_date",
                ""
            )

        ).strip()


        payment_time = str(

            result.get(
                "payment_time",
                ""
            )

        ).strip()


        # ====================================================
        # CHECK AMOUNT
        # ====================================================

        if amount == "":

            log(
                "STOPPED: Amount not found"
            )

            return


        # ====================================================
        # FINAL RESULT
        # ====================================================

        log("")

        log(
            "========== FINAL DATA =========="
        )

        log(f"Action: {action}")

        log(f"Party Name: {party_name}")

        log(f"Amount: {amount}")

        log(f"Payment Date: {payment_date}")

        log(f"Payment Time: {payment_time}")

        log(
            "================================"
        )


        # ====================================================
        # SEND TO GOOGLE SHEET
        # ====================================================

        success = send_to_sheet(

            action=action,

            party_name=party_name,

            amount=amount,

            screenshot_url=attachment.url,

            discord_user=str(message.author),

            message_id=message.id,

            payment_date=payment_date,

            payment_time=payment_time

        )


        if success:

            log(
                f"{action.upper()} SUCCESSFUL"
            )

        else:

            log(
                f"{action.upper()} FAILED"
            )


    except Exception as e:

        log(
            f"PROCESS PAYMENT ERROR: {e}"
        )


# ============================================================
# BOT READY
# ============================================================

@client.event
async def on_ready():

    log("")

    log(
        "=========================================="
    )

    log(
        "DISCORD PAYMENT BOT ACTIVE"
    )

    log(
        "=========================================="
    )

    log(
        f"Bot Name: {client.user}"
    )

    log(
        f"Bot ID: {client.user.id}"
    )

    log(
        f"Servers: {len(client.guilds)}"
    )

    log(
        "=========================================="
    )


# ============================================================
# NEW MESSAGE
# ============================================================

@client.event
async def on_message(message):

    try:

        await process_payment(

            message,

            action="create"

        )

    except Exception as e:

        log(
            f"NEW MESSAGE ERROR: {e}"
        )


# ============================================================
# MESSAGE EDIT
# ============================================================

@client.event
async def on_message_edit(before, after):

    try:

        # Ignore if nothing actually changed

        if (
            before.content == after.content
            and
            len(before.attachments)
            == len(after.attachments)
        ):

            return


        log("")

        log(
            "########################################"
        )

        log(
            "DISCORD MESSAGE EDIT DETECTED"
        )

        log(
            "########################################"
        )

        log(
            f"Message ID: {after.id}"
        )

        log(
            f"Old Text: {before.content}"
        )

        log(
            f"New Text: {after.content}"
        )


        await process_payment(

            after,

            action="update"

        )


    except Exception as e:

        log(
            f"MESSAGE EDIT ERROR: {e}"
        )


# ============================================================
# MESSAGE DELETE
# ============================================================

@client.event
async def on_raw_message_delete(payload):

    try:

        log("")

        log(
            "########################################"
        )

        log(
            "DISCORD MESSAGE DELETE DETECTED"
        )

        log(
            "########################################"
        )

        log(
            f"Message ID: {payload.message_id}"
        )


        success = send_to_sheet(

            action="delete",

            message_id=payload.message_id

        )


        if success:

            log(
                "SHEET ROW DELETED"
            )

        else:

            log(
                "SHEET DELETE FAILED"
            )


    except Exception as e:

        log(
            f"MESSAGE DELETE ERROR: {e}"
        )


# ============================================================
# DISCORD ERROR
# ============================================================

@client.event
async def on_error(event, *args, **kwargs):

    log(
        f"DISCORD ERROR EVENT: {event}"
    )


# ============================================================
# START BOT
# ============================================================

if __name__ == "__main__":

    log("Starting Payment Bot...")


    # ========================================================
    # CHECK ENVIRONMENT VARIABLES
    # ========================================================

    if not DISCORD_TOKEN:

        raise Exception(
            "DISCORD_TOKEN is missing"
        )


    if not GEMINI_API_KEY:

        raise Exception(
            "GEMINI_API_KEY is missing"
        )


    if not GOOGLE_SCRIPT_URL:

        raise Exception(
            "GOOGLE_SCRIPT_URL is missing"
        )


    # ========================================================
    # START
    # ========================================================

    try:

        client.run(

            DISCORD_TOKEN,

            reconnect=True

        )


    except discord.HTTPException as e:

        log(
            f"DISCORD HTTP ERROR: {e}"
        )

        raise


    except Exception as e:

        log(
            f"BOT START ERROR: {e}"
        )

        raise
