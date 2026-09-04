import os
import re
import io
import asyncio

import discord
import requests
import pytesseract

from PIL import Image, ImageEnhance, ImageFilter


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
# IMAGE OCR
# =========================================================

def download_image(image_url):

    response = requests.get(
        image_url,
        timeout=30
    )

    response.raise_for_status()

    image = Image.open(
        io.BytesIO(response.content)
    )

    return image


# =========================================================
# CLEAN AMOUNT
# =========================================================

def clean_amount(amount):

    if not amount:
        return ""

    amount = str(amount)

    amount = amount.replace(",", "")
    amount = amount.replace("₹", "")
    amount = amount.replace("INR", "")
    amount = amount.replace(" ", "")

    try:

        value = float(amount)

        if value.is_integer():
            return str(int(value))

        return str(value)

    except:

        return ""


# =========================================================
# VALID AMOUNT CHECK
# =========================================================

def is_valid_amount(amount):

    try:

        value = float(
            str(amount).replace(",", "")
        )

        if value <= 0:
            return False

        # Payment screenshot mate reasonable limit
        if value > 100000000:
            return False

        return True

    except:

        return False


# =========================================================
# FIND AMOUNT FROM TEXT
# =========================================================

def find_amount_from_text(text):

    if not text:
        return ""


    text = text.replace("\n", " ")


    patterns = [

        # ₹15,000
        r'₹\s*([\d,]+(?:\.\d{1,2})?)',

        # Rs. 15000
        r'Rs\.?\s*([\d,]+(?:\.\d{1,2})?)',

        # INR 15000
        r'INR\s*([\d,]+(?:\.\d{1,2})?)',

        # Amount ₹15000
        r'Amount\s*[:\-]?\s*₹?\s*([\d,]+(?:\.\d{1,2})?)',

        # Paid ₹15000
        r'Paid\s*[:\-]?\s*₹?\s*([\d,]+(?:\.\d{1,2})?)',

        # Payment ₹15000
        r'Payment\s*[:\-]?\s*₹?\s*([\d,]+(?:\.\d{1,2})?)',

        # Total ₹15000
        r'Total\s*[:\-]?\s*₹?\s*([\d,]+(?:\.\d{1,2})?)',

        # Transaction amount
        r'Transaction\s*Amount\s*[:\-]?\s*₹?\s*([\d,]+(?:\.\d{1,2})?)'

    ]


    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            re.IGNORECASE
        )

        for match in matches:

            amount = clean_amount(match)

            if is_valid_amount(amount):

                print(
                    f"AMOUNT FOUND BY PATTERN: {amount}"
                )

                return amount


    return ""


# =========================================================
# OCR PREPROCESS
# =========================================================

def preprocess_image(image):

    image = image.convert("RGB")

    # Resize
    width, height = image.size

    new_width = width * 2
    new_height = height * 2

    image = image.resize(
        (new_width, new_height)
    )


    # Enhance contrast
    enhancer = ImageEnhance.Contrast(image)

    image = enhancer.enhance(2)


    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(image)

    image = enhancer.enhance(2)


    return image


# =========================================================
# EXTRACT AMOUNT
# =========================================================

def extract_amount(image_url):

    try:

        print("")
        print("========================================")
        print("STARTING PAYMENT OCR")
        print("========================================")


        image = download_image(image_url)


        image = preprocess_image(image)


        # Different OCR modes
        psm_modes = [

            6,
            11,
            12

        ]


        all_text = ""


        for mode in psm_modes:

            try:

                print(
                    f"Running OCR Mode {mode}..."
                )


                text = pytesseract.image_to_string(

                    image,

                    config=f'--psm {mode}'

                )


                print("")
                print(
                    f"========== OCR MODE {mode} =========="
                )

                print(text)

                print(
                    "======================================"
                )


                all_text += "\n" + text


                amount = find_amount_from_text(text)


                if amount:

                    print(
                        f"FINAL AMOUNT FOUND: {amount}"
                    )

                    return amount


            except Exception as e:

                print(
                    f"OCR Error Mode {mode}: {e}"
                )


        # Final search in combined text

        amount = find_amount_from_text(
            all_text
        )


        if amount:

            return amount


        # =================================================
        # FALLBACK:
        # Find large numbers from OCR
        # =================================================

        numbers = re.findall(

            r'(?<![A-Za-z0-9])(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d{3,9}(?:\.\d{1,2})?)(?![A-Za-z0-9])',

            all_text

        )


        valid_numbers = []


        for number in numbers:

            amount = clean_amount(number)


            if is_valid_amount(amount):

                value = float(amount)

                # Ignore probable years
                if 2000 <= value <= 2100:

                    continue


                valid_numbers.append(value)


        if valid_numbers:

            # Screenshot ma usually largest payment amount hoy
            best_amount = max(valid_numbers)


            if best_amount.is_integer():

                best_amount = str(
                    int(best_amount)
                )

            else:

                best_amount = str(best_amount)


            print(
                f"FALLBACK AMOUNT FOUND: {best_amount}"
            )


            return best_amount


        print("FINAL RESULT: NOT FOUND")


        return "NOT FOUND"


    except Exception as e:

        print(
            f"FINAL OCR ERROR: {e}"
        )

        return "NOT FOUND"


# =========================================================
# GOOGLE SHEET - NEW ENTRY
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

            "action": "new",

            "secret": SECRET_KEY,

            "partyName": party_name,

            "amount": amount,

            "screenshot": screenshot_url,

            "discordUser": discord_user,

            "messageId": message_id

        }


        print("")
        print("Sending NEW entry to Google Sheet...")


        response = requests.post(

            GOOGLE_SCRIPT_URL,

            json=data,

            timeout=30

        )


        print(
            "Google Sheet Response:"
        )

        print(
            response.text
        )


        return True


    except Exception as e:

        print(
            f"Google Sheet Error: {e}"
        )

        return False


# =========================================================
# GOOGLE SHEET - UPDATE PARTY NAME
# =========================================================

def update_party_in_google_sheet(

    party_name,
    message_id,
    discord_user

):

    try:

        data = {

            "action": "update_party",

            "secret": SECRET_KEY,

            "partyName": party_name,

            "discordUser": discord_user,

            "messageId": message_id

        }


        print("")
        print("Updating Party Name in Google Sheet...")

        print(
            f"New Party Name: {party_name}"
        )

        print(
            f"Message ID: {message_id}"
        )


        response = requests.post(

            GOOGLE_SCRIPT_URL,

            json=data,

            timeout=30

        )


        print(
            "Google Sheet Update Response:"
        )

        print(
            response.text
        )


        return True


    except Exception as e:

        print(
            f"Google Sheet Update Error: {e}"
        )

        return False


# =========================================================
# BOT READY
# =========================================================

@client.event
async def on_ready():

    print("")
    print("======================================")
    print("🤖 DISCORD PAYMENT BOT ACTIVE")
    print("======================================")

    print(
        f"Bot Name: {client.user}"
    )

    print(
        f"Bot ID: {client.user.id}"
    )

    print(
        f"Servers: {len(client.guilds)}"
    )

    print("======================================")


# =========================================================
# NEW DISCORD MESSAGE
# =========================================================

@client.event
async def on_message(message):


    # Bot messages ignore

    if message.author.bot:

        return


    # Screenshot nathi

    if not message.attachments:

        return


    # Party Name

    party_name = message.content.strip()


    if not party_name:

        print("Party Name Missing")

        return


    print("")
    print("======================================")
    print("NEW PAYMENT MESSAGE DETECTED")
    print("======================================")

    print(
        f"Party Name: {party_name}"
    )

    print(
        f"User: {message.author}"
    )

    print(
        f"Message ID: {message.id}"
    )

    print(
        f"Attachments: {len(message.attachments)}"
    )

    print("======================================")


    # All attachments

    for attachment in message.attachments:


        # Image check

        is_image = False


        if attachment.content_type:

            if attachment.content_type.startswith(
                "image"
            ):

                is_image = True


        # File extension fallback

        filename = attachment.filename.lower()


        image_extensions = (

            ".jpg",
            ".jpeg",
            ".png",
            ".webp"

        )


        if filename.endswith(image_extensions):

            is_image = True


        if not is_image:

            continue


        screenshot_url = attachment.url


        print(
            f"Processing: {filename}"
        )


        # OCR BLOCKING HOY ETLE THREAD MA RUN KARO

        amount = await asyncio.to_thread(

            extract_amount,

            screenshot_url

        )


        print(
            f"FINAL PAYMENT AMOUNT: {amount}"
        )


        # Google Sheet entry

        await asyncio.to_thread(

            send_to_google_sheet,

            party_name,

            amount,

            screenshot_url,

            str(message.author),

            str(message.id)

        )


        # Only first screenshot process

        break


# =========================================================
# MESSAGE EDIT DETECTION
# =========================================================

@client.event
async def on_message_edit(before, after):


    # Bot messages ignore

    if after.author.bot:

        return


    # Party name change check

    old_party_name = before.content.strip()

    new_party_name = after.content.strip()


    # Same text hoy to kai karvanu nahi

    if old_party_name == new_party_name:

        return


    # New name blank hoy to ignore

    if not new_party_name:

        print(
            "Edited Party Name is blank"
        )

        return


    print("")
    print("======================================")
    print("MESSAGE EDIT DETECTED")
    print("======================================")

    print(
        f"OLD PARTY: {old_party_name}"
    )

    print(
        f"NEW PARTY: {new_party_name}"
    )

    print(
        f"MESSAGE ID: {after.id}"
    )

    print(
        f"USER: {after.author}"
    )

    print("======================================")


    # Google Sheet update

    result = await asyncio.to_thread(

        update_party_in_google_sheet,

        new_party_name,

        str(after.id),

        str(after.author)

    )


    if result:

        print(
            "PARTY NAME UPDATED SUCCESSFULLY"
        )

    else:

        print(
            "PARTY NAME UPDATE FAILED"
        )


# =========================================================
# MESSAGE DELETE LOG
# =========================================================

@client.event
async def on_message_delete(message):


    if message.author.bot:

        return


    if not message.attachments:

        return


    print("")
    print("======================================")
    print("PAYMENT MESSAGE DELETED")
    print("======================================")

    print(
        f"Party: {message.content}"
    )

    print(
        f"Message ID: {message.id}"
    )

    print(
        f"Deleted By/Author: {message.author}"
    )

    print("======================================")


# =========================================================
# START BOT
# =========================================================

if __name__ == "__main__":

    print("")
    print("======================================")
    print("Starting Discord Payment Bot...")
    print("======================================")

    client.run(DISCORD_TOKEN)
