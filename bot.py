import os
import re
import io
import asyncio
from collections import Counter

import discord
import requests
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import easyocr


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
# EASY OCR INITIALIZATION
# =========================================================

print("Loading OCR Engine...")

reader = easyocr.Reader(
    ['en'],
    gpu=False
)

print("OCR Engine Ready")


# =========================================================
# NUMBER CLEAN FUNCTION
# =========================================================

def clean_amount(value):

    if not value:
        return None

    value = str(value)

    # Remove spaces
    value = value.strip()

    # OCR common mistakes
    value = value.replace("O", "0")
    value = value.replace("o", "0")

    # Remove currency
    value = value.replace("₹", "")
    value = value.replace("INR", "")
    value = value.replace("Rs.", "")
    value = value.replace("Rs", "")

    value = value.strip()

    # Remove unwanted characters
    value = re.sub(
        r"[^0-9.,]",
        "",
        value
    )

    if not value:
        return None


    # Indian comma format
    # Example: 1,921.00

    try:

        # If decimal present
        if "." in value:

            parts = value.split(".")

            integer_part = parts[0].replace(",", "")
            decimal_part = parts[-1]

            if len(decimal_part) > 2:
                decimal_part = decimal_part[:2]

            number = float(
                integer_part + "." + decimal_part
            )

        else:

            number = float(
                value.replace(",", "")
            )


        # Invalid small/huge numbers reject

        if number <= 0:
            return None

        if number > 100000000:
            return None


        return round(number, 2)


    except:

        return None


# =========================================================
# FORMAT AMOUNT
# =========================================================

def format_amount(amount):

    if amount is None:
        return None

    try:

        return "{:,.2f}".format(
            float(amount)
        )

    except:

        return None


# =========================================================
# PREPROCESS IMAGE
# =========================================================

def preprocess_image(image):

    # Convert RGB

    if image.mode != "RGB":

        image = image.convert("RGB")


    # Enhance contrast

    enhancer = ImageEnhance.Contrast(image)

    image = enhancer.enhance(1.8)


    # Enhance sharpness

    enhancer = ImageEnhance.Sharpness(image)

    image = enhancer.enhance(2)


    return image


# =========================================================
# OCR IMAGE
# =========================================================

def run_ocr(image):

    try:

        image_np = np.array(image)


        results = reader.readtext(
            image_np,
            detail=1,
            paragraph=False
        )


        texts = []


        for result in results:

            bbox = result[0]

            text = result[1]

            confidence = result[2]


            texts.append({

                "text": text,

                "confidence": confidence,

                "bbox": bbox

            })


        return texts


    except Exception as e:

        print("OCR ERROR:", e)

        return []


# =========================================================
# EXTRACT AMOUNT FROM TEXT
# =========================================================

def find_amount_candidates(ocr_results):

    candidates = []


    for item in ocr_results:

        text = item["text"]

        confidence = item["confidence"]


        print(
            f"OCR: {text} | Confidence: {confidence:.2f}"
        )


        # -----------------------------------------
        # Pattern 1
        # ₹1,921.00
        # ₹ 15,000
        # -----------------------------------------

        patterns = [

            r'₹\s*([0-9OolI,]+(?:\.[0-9]{1,2})?)',

            # Rs 1500

            r'Rs\.?\s*([0-9OolI,]+(?:\.[0-9]{1,2})?)',

            # INR 1500

            r'INR\s*([0-9OolI,]+(?:\.[0-9]{1,2})?)',

            # Amount 1500

            r'(?:Amount|Paid|Payment|Total|Debited|Credited)'
            r'[:\s]*₹?\s*'
            r'([0-9OolI,]+(?:\.[0-9]{1,2})?)'
        ]


        for pattern in patterns:

            matches = re.findall(
                pattern,
                text,
                re.IGNORECASE
            )


            for match in matches:

                amount = clean_amount(match)


                if amount:

                    candidates.append({

                        "amount": amount,

                        "confidence": confidence,

                        "source": text,

                        "priority": "currency"
                    })


        # -----------------------------------------
        # Plain amount detection
        # Example:
        # 1,921.00
        # 15,000
        # -----------------------------------------

        plain_matches = re.findall(

            r'\b\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?\b',

            text

        )


        for match in plain_matches:

            amount = clean_amount(match)


            if amount:

                candidates.append({

                    "amount": amount,

                    "confidence": confidence * 0.8,

                    "source": text,

                    "priority": "plain"
                })


    return candidates


# =========================================================
# FILTER BAD NUMBERS
# =========================================================

def is_valid_payment_amount(amount):

    if amount is None:
        return False


    # Very small random OCR values ignore

    if amount < 1:
        return False


    # Unrealistically huge

    if amount > 10000000:
        return False


    return True


# =========================================================
# IMAGE CROP OCR
# =========================================================

def create_crops(image):

    width, height = image.size


    crops = []


    # Full Image

    crops.append(
        ("FULL", image)
    )


    # Top 50%

    crops.append(

        (
            "TOP_HALF",

            image.crop(
                (
                    0,
                    0,
                    width,
                    int(height * 0.50)
                )
            )
        )
    )


    # Top 65%

    crops.append(

        (
            "TOP_65",

            image.crop(
                (
                    0,
                    0,
                    width,
                    int(height * 0.65)
                )
            )
        )
    )


    # Top center

    crops.append(

        (
            "TOP_CENTER",

            image.crop(
                (
                    int(width * 0.10),
                    int(height * 0.05),
                    int(width * 0.90),
                    int(height * 0.55)
                )
            )
        )
    )


    # Center Area

    crops.append(

        (
            "CENTER",

            image.crop(
                (
                    int(width * 0.05),
                    int(height * 0.15),
                    int(width * 0.95),
                    int(height * 0.70)
                )
            )
        )
    )


    return crops


# =========================================================
# SMART AMOUNT SELECTOR
# =========================================================

def choose_best_amount(all_candidates):

    if not all_candidates:

        return None, 0


    valid_candidates = []


    for item in all_candidates:

        amount = item["amount"]


        if is_valid_payment_amount(amount):

            valid_candidates.append(item)


    if not valid_candidates:

        return None, 0


    # Group same amounts

    amount_scores = {}


    for item in valid_candidates:

        amount = item["amount"]

        score = item["confidence"]


        # Currency amount gets priority

        if item["priority"] == "currency":

            score += 0.5


        if amount not in amount_scores:

            amount_scores[amount] = 0


        amount_scores[amount] += score


    # Sort

    sorted_amounts = sorted(

        amount_scores.items(),

        key=lambda x: x[1],

        reverse=True

    )


    best_amount = sorted_amounts[0][0]

    best_score = sorted_amounts[0][1]


    return best_amount, best_score


# =========================================================
# MAIN OCR FUNCTION
# =========================================================

def extract_amount(image_url):

    try:

        print("")
        print("========================================")
        print("DOWNLOADING SCREENSHOT")
        print("========================================")


        response = requests.get(

            image_url,

            timeout=30

        )


        response.raise_for_status()


        image = Image.open(

            io.BytesIO(response.content)

        )


        print(
            f"Image Size: {image.size}"
        )


        # Preprocess

        image = preprocess_image(image)


        # Create image crops

        crops = create_crops(image)


        all_candidates = []


        # ----------------------------------------
        # OCR EVERY CROP
        # ----------------------------------------

        for crop_name, crop_image in crops:


            print("")
            print("========================================")

            print(
                f"RUNNING OCR: {crop_name}"
            )

            print("========================================")


            results = run_ocr(
                crop_image
            )


            candidates = find_amount_candidates(
                results
            )


            for candidate in candidates:

                candidate["crop"] = crop_name

                all_candidates.append(
                    candidate
                )


        # ----------------------------------------
        # PRINT ALL FOUND AMOUNTS
        # ----------------------------------------

        print("")
        print("========================================")

        print("ALL AMOUNT CANDIDATES")

        print("========================================")


        for item in all_candidates:

            print(

                f"Amount: {item['amount']} | "
                f"Confidence: {item['confidence']:.2f} | "
                f"Crop: {item['crop']} | "
                f"Text: {item['source']}"

            )


        # ----------------------------------------
        # SELECT BEST AMOUNT
        # ----------------------------------------

        amount, score = choose_best_amount(

            all_candidates

        )


        if amount:


            final_amount = format_amount(
                amount
            )


            print("")
            print("========================================")

            print(
                f"FINAL AMOUNT: {final_amount}"
            )

            print(
                f"FINAL SCORE: {score}"
            )

            print("========================================")


            return final_amount


        print("")
        print("========================================")

        print("FINAL RESULT: NOT FOUND")

        print("========================================")


        return "NOT FOUND"


    except Exception as e:


        print("")
        print("========================================")

        print("OCR FATAL ERROR")

        print(e)

        print("========================================")


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


        print("")
        print("========================================")

        print("SENDING TO GOOGLE SHEET")

        print(data)

        print("========================================")


        response = requests.post(

            GOOGLE_SCRIPT_URL,

            json=data,

            timeout=30

        )


        print("GOOGLE SHEET RESPONSE:")

        print(response.status_code)

        print(response.text)


    except Exception as e:


        print("GOOGLE SHEET ERROR:")

        print(e)


# =========================================================
# BOT READY
# =========================================================

@client.event
async def on_ready():


    print("")

    print("========================================")

    print("🤖 DISCORD PAYMENT BOT ACTIVE")

    print("========================================")

    print(
        f"Bot Name: {client.user}"
    )

    print(
        f"Bot ID: {client.user.id}"
    )

    print(
        f"Servers: {len(client.guilds)}"
    )

    print("========================================")

    print("")


# =========================================================
# BOT JOIN SERVER
# =========================================================

@client.event
async def on_guild_join(guild):


    print("")

    print(
        f"Joined Server: {guild.name}"
    )


# =========================================================
# NEW DISCORD MESSAGE
# =========================================================

@client.event
async def on_message(message):


    # -----------------------------------------
    # Ignore Bot Messages
    # -----------------------------------------

    if message.author.bot:

        return


    # -----------------------------------------
    # No attachment
    # -----------------------------------------

    if not message.attachments:

        return


    # -----------------------------------------
    # Party Name
    # -----------------------------------------

    party_name = message.content.strip()


    if not party_name:


        print("")

        print("========================================")

        print("PARTY NAME MISSING")

        print(
            f"Message ID: {message.id}"
        )

        print("========================================")


        return


    # -----------------------------------------
    # Message Info
    # -----------------------------------------

    print("")

    print("========================================")

    print("NEW PAYMENT MESSAGE")

    print("========================================")

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

    print("========================================")


    # -----------------------------------------
    # PROCESS ALL ATTACHMENTS
    # -----------------------------------------

    for attachment in message.attachments:


        # Check image


        is_image = False


        if attachment.content_type:


            if attachment.content_type.startswith("image"):

                is_image = True


        # If Discord content type missing


        if not is_image:


            filename = attachment.filename.lower()


            if filename.endswith(

                (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".webp"
                )

            ):

                is_image = True


        if not is_image:

            print(

                f"Skipping non-image: "
                f"{attachment.filename}"

            )

            continue


        # -------------------------------------
        # PROCESS IMAGE
        # -------------------------------------

        screenshot_url = attachment.url


        print("")

        print("========================================")

        print(
            f"PROCESSING IMAGE: {attachment.filename}"
        )

        print(
            f"Screenshot URL: {screenshot_url}"
        )

        print("========================================")


        # OCR in separate thread
        # Bot freeze na thay


        amount = await asyncio.to_thread(

            extract_amount,

            screenshot_url

        )


        # -------------------------------------
        # SEND TO GOOGLE SHEET
        # -------------------------------------

        await asyncio.to_thread(

            send_to_google_sheet,

            party_name,

            amount,

            screenshot_url,

            str(message.author),

            str(message.id)

        )


        print("")

        print("========================================")

        print("PAYMENT PROCESS COMPLETED")

        print(
            f"Party: {party_name}"
        )

        print(
            f"Amount: {amount}"
        )

        print(
            f"Message ID: {message.id}"
        )

        print("========================================")


# =========================================================
# START BOT
# =========================================================

if __name__ == "__main__":


    print("")

    print("========================================")

    print("STARTING DISCORD PAYMENT BOT")

    print("========================================")

    client.run(DISCORD_TOKEN)
