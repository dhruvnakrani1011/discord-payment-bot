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
# LOG FUNCTION
# ============================================================

def log(message):

    now = datetime.now(IST).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    print(
        f"[{now}] {message}",
        flush=True
    )


# ============================================================
# CLEAN PARTY NAME
# PARTY NAME = DISCORD MESSAGE TEXT
# ============================================================

def clean_party_name(value):

    try:

        if not value:
            return ""

        value = str(value).strip()

        # Multiple spaces / lines clean
        value = " ".join(value.split())

        return value

    except Exception:

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

        log(
            f"Download Status: {response.status_code}"
        )

        if response.status_code != 200:

            return None

        log(
            f"Image Size: {len(response.content)} bytes"
        )

        return response.content

    except Exception as e:

        log(
            f"DOWNLOAD ERROR: {str(e)}"
        )

        return None


# ============================================================
# GEMINI IMAGE ANALYSIS
# ONLY AMOUNT + DATE + TIME
# ============================================================

def analyze_image(image_bytes, mime_type):

    try:

        log("Starting Gemini AI analysis...")

        image_base64 = base64.b64encode(
            image_bytes
        ).decode("utf-8")


        prompt = """
Analyze this Indian payment screenshot carefully.

Extract ONLY the following:

1. Actual successful payment amount
2. Payment date
3. Payment time

DO NOT extract party name.

IMPORTANT AMOUNT RULES:

- Extract ONLY the actual successful payment amount.
- Ignore account balance.
- Ignore available balance.
- Ignore wallet balance.
- Ignore cashback.
- Ignore offers.
- Ignore transaction ID.
- Ignore reference numbers.
- Ignore phone numbers.
- Ignore UPI IDs.
- Ignore random numbers.
- Ignore failed transaction amounts.
- If multiple amounts exist, select the amount that was actually paid successfully.

DATE RULES:

- Extract the actual payment transaction date.
- Ignore screenshot date if unrelated.

TIME RULES:

- Extract the actual payment transaction time.
- Ignore mobile status bar time if possible.

Return ONLY valid JSON.

Format exactly:

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
"""


        # GEMINI MODEL

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


        if response.status_code != 200:

            log("========== GEMINI ERROR ==========")

            log(response.text)

            log("==================================")

            return None


        result = response.json()


        try:

            text = (
                result["candidates"][0]
                ["content"]
                ["parts"][0]
                ["text"]
            )

        except Exception:

            log(
                "Could not read Gemini response"
            )

            log(
                json.dumps(
                    result,
                    indent=2
                )
            )

            return None


        log(
            f"Gemini Raw Response: {text}"
        )


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

        log(
            f"GEMINI ERROR: {str(e)}"
        )

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

    except Exception:

        return ""


# ============================================================
# SEND TO GOOGLE SHEET
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
            f"Google Script Status: {response.status_code}"
        )

        log(
            f"Google Script Response: {response.text}"
        )


        return response.status_code == 200


    except Exception as e:

        log(
            f"GOOGLE SHEET ERROR: {str(e)}"
        )

        return False


# ============================================================
# PROCESS PAYMENT MESSAGE
# CREATE OR UPDATE
# ============================================================

async def process_payment(
    message,
    action="create"
):


    log("")

    log(
        "========================================"
    )

    log(
        f"PROCESSING PAYMENT - {action.upper()}"
    )

    log(
        "========================================"
    )


    log(
        f"Message ID: {message.id}"
    )

    log(
        f"User: {message.author}"
    )

    log(
        f"Content: {message.content}"
    )

    log(
        f"Attachments: {len(message.attachments)}"
    )


    # Ignore bot messages

    if message.author.bot:

        log(
            "Ignored: Bot message"
        )

        return


    # ========================================================
    # PARTY NAME FROM DISCORD TEXT
    # ========================================================

    party_name = clean_party_name(
        message.content
    )


    if not party_name:

        log(
            "Party Name missing in Discord message"
        )

        # Update/create with blank name not allowed
        return


    log(
        f"PARTY NAME: {party_name}"
    )


    # ========================================================
    # CHECK ATTACHMENT
    # ========================================================

    if len(message.attachments) == 0:

        log(
            "No screenshot attached"
        )

        # If edit only name and screenshot unchanged,
        # we need to send update.
        if action == "update":

            success = send_to_sheet(

                action="update",

                party_name=party_name,

                amount="",

                screenshot_url="",

                discord_user=str(message.author),

                message_id=message.id,

                payment_date="",

                payment_time=""

            )

            if success:

                log(
                    "NAME UPDATE SENT SUCCESSFULLY"
                )

        return


    # ========================================================
    # PROCESS FIRST IMAGE
    # ========================================================

    attachment = message.attachments[0]


    filename = attachment.filename.lower()


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
            "Attachment is not image"
        )

        return


    log(
        f"Processing image: {attachment.filename}"
    )


    # ========================================================
    # MIME TYPE
    # ========================================================

    if filename.endswith(".png"):

        mime_type = "image/png"

    elif filename.endswith(".webp"):

        mime_type = "image/webp"

    else:

        mime_type = "image/jpeg"


    # ========================================================
    # DOWNLOAD IMAGE
    # ========================================================

    image_bytes = download_image(
        attachment.url
    )


    if not image_bytes:

        log(
            "Image download failed"
        )

        return


    # ========================================================
    # GEMINI ANALYSIS
    # ========================================================

    result = analyze_image(

        image_bytes,

        mime_type

    )


    if not result:

        log(
            "Gemini did not return result"
        )

        return


    log("")

    log(
        "========== AI RESULT =========="
    )

    log(
        json.dumps(
            result,
            indent=2
        )
    )

    log(
        "==============================="
    )


    # ========================================================
    # AMOUNT
    # ========================================================

    amount = clean_amount(

        result.get(
            "amount",
            ""
        )

    )


    # ========================================================
    # DATE
    # ========================================================

    payment_date = result.get(

        "payment_date",

        ""

    )


    # ========================================================
    # TIME
    # ========================================================

    payment_time = result.get(

        "payment_time",

        ""

    )


    # ========================================================
    # VALIDATE AMOUNT
    # ========================================================

    if amount == "":

        log(
            "Amount not found - Entry not saved"
        )

        return


    # ========================================================
    # FINAL DATA
    # ========================================================

    log("")

    log(
        "========== FINAL DATA =========="
    )

    log(
        f"Action: {action}"
    )

    log(
        f"Party Name: {party_name}"
    )

    log(
        f"Amount: {amount}"
    )

    log(
        f"Payment Date: {payment_date}"
    )

    log(
        f"Payment Time: {payment_time}"
    )

    log(
        "================================"
    )


    # ========================================================
    # SEND TO GOOGLE SHEET
    # ========================================================

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


# ============================================================
# BOT READY
# ============================================================

@client.event
async def on_ready():

    log("")

    log(
        "========================================"
    )

    log(
        "DISCORD PAYMENT BOT ACTIVE"
    )

    log(
        "========================================"
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
        "========================================"
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
            f"NEW MESSAGE ERROR: {str(e)}"
        )


# ============================================================
# MESSAGE EDIT
# ============================================================

@client.event
async def on_message_edit(before, after):

    try:

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
            f"Old Name/Text: {before.content}"
        )

        log(
            f"New Name/Text: {after.content}"
        )


        await process_payment(

            after,

            action="update"

        )


    except Exception as e:

        log(
            f"MESSAGE EDIT ERROR: {str(e)}"
        )


# ============================================================
# MESSAGE DELETE
# ============================================================

@client.event
async def on_message_delete(message):

    try:

        # Ignore bot messages

        if message.author.bot:

            return


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
            f"Message ID: {message.id}"
        )


        success = send_to_sheet(

            action="delete",

            message_id=message.id

        )


        if success:

            log(
                "SHEET ROW DELETE REQUEST SUCCESSFUL"
            )

        else:

            log(
                "SHEET ROW DELETE FAILED"
            )


    except Exception as e:

        log(
            f"MESSAGE DELETE ERROR: {str(e)}"
        )


# ============================================================
# ERROR HANDLER
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

    log(
        "Starting Payment Bot..."
    )


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


    client.run(
        DISCORD_TOKEN
    )
