import os
import re
import io
import asyncio
import discord
import requests
import pytesseract

from PIL import Image, ImageEnhance, ImageFilter


# =========================================================
# ENVIRONMENT VARIABLES
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
# PAYMENT KEYWORDS
# =========================================================

STRONG_KEYWORDS = [

    "amount",
    "paid",
    "payment",
    "you paid",
    "successfully paid",
    "sent",
    "transfer amount",
    "debited",
    "credited",
    "total amount",
    "transaction amount",
    "paid successfully",
    "payment successful",
    "money sent"

]


MEDIUM_KEYWORDS = [

    "upi",
    "transfer",
    "success",
    "completed",
    "successful",
    "transaction"

]


# =========================================================
# BAD KEYWORDS
# =========================================================

BAD_KEYWORDS = [

    "transaction id",
    "txn id",
    "utr",
    "reference",
    "upi ref",
    "account number",
    "account no",
    "mobile",
    "phone",
    "contact",
    "date",
    "time",
    "ifsc",
    "rrn"

]


# =========================================================
# CLEAN AMOUNT
# =========================================================

def clean_amount(value):

    if not value:
        return ""

    value = str(value)

    value = value.replace("₹", "")
    value = value.replace("Rs.", "")
    value = value.replace("Rs", "")
    value = value.replace("INR", "")

    value = value.replace(",", "")
    value = value.replace(" ", "")

    value = value.replace("-", "")
    value = value.replace("–", "")
    value = value.replace("—", "")

    value = re.sub(
        r"[^\d.]",
        "",
        value
    )

    # Multiple decimal avoid
    if value.count(".") > 1:

        parts = value.split(".")

        value = parts[0] + "." + parts[1]

    return value


# =========================================================
# VALIDATE POSSIBLE AMOUNT
# =========================================================

def is_valid_amount(value):

    try:

        value = float(value)

        # Payment amount limits
        if value < 1:
            return False

        if value > 100000000:
            return False

        return True

    except:

        return False


# =========================================================
# IGNORE INVALID NUMBERS
# =========================================================

def is_suspicious_number(number):

    digits = re.sub(
        r"\D",
        "",
        number
    )

    # Mobile number
    if len(digits) == 10:

        return True

    # Transaction IDs / Account numbers
    if len(digits) >= 11:

        return True

    # Year
    if digits in [

        "2023",
        "2024",
        "2025",
        "2026",
        "2027",
        "2028"

    ]:

        return True

    return False


# =========================================================
# EXTRACT CANDIDATE AMOUNTS
# =========================================================

def extract_candidates(text):

    candidates = []

    lines = text.splitlines()


    for index, line in enumerate(lines):

        original_line = line

        line_lower = line.lower()


        # Find numbers with comma
        numbers = re.findall(

            r'(?<!\d)(?:₹|rs\.?|inr)?\s*[-–—]?\s*\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?',

            original_line,

            re.IGNORECASE

        )


        # Find normal numbers
        numbers += re.findall(

            r'(?<![\d/])(?:₹|rs\.?|inr)?\s*[-–—]?\s*\d+(?:\.\d{1,2})?(?![\d/])',

            original_line,

            re.IGNORECASE

        )


        for raw_number in numbers:


            # Remove duplicates / empty
            if not raw_number.strip():

                continue


            amount = clean_amount(raw_number)


            if not amount:

                continue


            if not is_valid_amount(amount):

                continue


            if is_suspicious_number(amount):

                continue


            score = 0


            # =============================================
            # CURRENCY SYMBOL BONUS
            # =============================================

            if "₹" in raw_number:

                score += 80


            if "rs" in raw_number.lower():

                score += 60


            if "inr" in raw_number.lower():

                score += 60


            # =============================================
            # STRONG KEYWORDS
            # =============================================

            for keyword in STRONG_KEYWORDS:

                if keyword in line_lower:

                    score += 100


            # =============================================
            # MEDIUM KEYWORDS
            # =============================================

            for keyword in MEDIUM_KEYWORDS:

                if keyword in line_lower:

                    score += 25


            # =============================================
            # BAD KEYWORDS
            # =============================================

            for keyword in BAD_KEYWORDS:

                if keyword in line_lower:

                    score -= 150


            # =============================================
            # CHECK PREVIOUS LINE
            # =============================================

            if index > 0:

                previous = lines[index - 1].lower()


                for keyword in STRONG_KEYWORDS:

                    if keyword in previous:

                        score += 50


                for keyword in BAD_KEYWORDS:

                    if keyword in previous:

                        score -= 100


            # =============================================
            # CHECK NEXT LINE
            # =============================================

            if index < len(lines) - 1:

                next_line = lines[index + 1].lower()


                for keyword in STRONG_KEYWORDS:

                    if keyword in next_line:

                        score += 50


            # =============================================
            # PAYMENT SCREENSHOT TOP AREA BONUS
            # =============================================

            if index <= 5:

                score += 20


            candidate = {

                "amount": amount,

                "score": score,

                "line": original_line.strip(),

                "raw": raw_number.strip()

            }


            candidates.append(candidate)


    return candidates


# =========================================================
# SELECT BEST AMOUNT
# =========================================================

def select_best_amount(candidates):

    if not candidates:

        return "", 0


    # Sort highest score first

    candidates = sorted(

        candidates,

        key=lambda x: x["score"],

        reverse=True

    )


    print("\n========== AMOUNT CANDIDATES ==========")

    for candidate in candidates:

        print(

            f"Amount: {candidate['amount']} | "

            f"Score: {candidate['score']} | "

            f"Line: {candidate['line']}"

        )


    print("========================================\n")


    best = candidates[0]


    return best["amount"], best["score"]


# =========================================================
# OCR ONE IMAGE
# =========================================================

def perform_ocr(image, mode):

    try:

        text = pytesseract.image_to_string(

            image,

            config=f"--psm {mode}"

        )

        return text

    except Exception as e:

        print(f"OCR Error Mode {mode}: {e}")

        return ""


# =========================================================
# IMAGE PREPROCESSING
# =========================================================

def preprocess_image(image):


    # Convert RGB
    image = image.convert("RGB")


    # Resize for better OCR
    width, height = image.size


    if width < 2000:

        image = image.resize(

            (

                width * 2,

                height * 2

            )

        )


    # Convert grayscale

    image = image.convert("L")


    # Contrast

    image = ImageEnhance.Contrast(

        image

    ).enhance(2)


    # Sharpness

    image = ImageEnhance.Sharpness(

        image

    ).enhance(2)


    return image


# =========================================================
# UNIVERSAL AMOUNT EXTRACTOR
# =========================================================

def extract_amount(image_url):

    try:


        print("\n========================================")

        print("DOWNLOADING PAYMENT SCREENSHOT")

        print("========================================")


        response = requests.get(

            image_url,

            timeout=30

        )


        response.raise_for_status()


        image = Image.open(

            io.BytesIO(response.content)

        )


        print(f"Image Size: {image.size}")


        processed_image = preprocess_image(image)


        all_candidates = []


        # =================================================
        # OCR MODE 6
        # =================================================

        print("\nRunning OCR Mode 6...")


        text_6 = perform_ocr(

            processed_image,

            6

        )


        print("\n========== OCR MODE 6 ==========")

        print(text_6)

        print("================================")


        candidates = extract_candidates(text_6)

        all_candidates.extend(candidates)


        # =================================================
        # OCR MODE 11
        # =================================================

        print("\nRunning OCR Mode 11...")


        text_11 = perform_ocr(

            processed_image,

            11

        )


        print("\n========== OCR MODE 11 ==========")

        print(text_11)

        print("=================================")


        candidates = extract_candidates(text_11)

        all_candidates.extend(candidates)


        # =================================================
        # OCR TOP SECTION
        # =================================================

        width, height = processed_image.size


        # Top 40% generally payment amount hoy

        top_image = processed_image.crop(

            (

                0,

                0,

                width,

                int(height * 0.40)

            )

        )


        print("\nRunning TOP AREA OCR...")


        top_text = perform_ocr(

            top_image,

            6

        )


        print("\n========== TOP OCR ==========")

        print(top_text)

        print("=============================")


        candidates = extract_candidates(top_text)


        # Top area candidates extra priority

        for candidate in candidates:

            candidate["score"] += 40


        all_candidates.extend(candidates)


        # =================================================
        # SELECT BEST RESULT
        # =================================================

        amount, score = select_best_amount(

            all_candidates

        )


        if not amount:

            print("FINAL RESULT: NOT FOUND")

            return "NOT FOUND", 0


        print("\n========================================")

        print(f"FINAL AMOUNT: {amount}")

        print(f"CONFIDENCE SCORE: {score}")

        print("========================================")


        return amount, score


    except Exception as e:


        print("\n========================================")

        print("UNIVERSAL OCR ERROR")

        print(str(e))

        print("========================================")


        return "NOT FOUND", 0


# =========================================================
# CONFIDENCE STATUS
# =========================================================

def get_status(score):


    if score >= 150:

        return "VERIFIED"


    elif score >= 80:

        return "LIKELY"


    elif score > 0:

        return "CHECK"


    return "NOT FOUND"


# =========================================================
# GOOGLE SHEET ENTRY
# =========================================================

def send_to_google_sheet(

    party_name,

    amount,

    confidence,

    screenshot_url,

    discord_user,

    message_id

):


    try:


        status = get_status(confidence)


        data = {

            "secret": SECRET_KEY,

            "partyName": party_name,

            "amount": amount,

            "confidence": confidence,

            "status": status,

            "screenshot": screenshot_url,

            "discordUser": discord_user,

            "messageId": message_id

        }


        print("\n========== SENDING DATA ==========")

        print(data)

        print("==================================\n")


        response = requests.post(

            GOOGLE_SCRIPT_URL,

            json=data,

            timeout=30

        )


        print("\n========== GOOGLE SHEET RESPONSE ==========")

        print(f"Status Code: {response.status_code}")

        print(response.text)

        print("============================================\n")


    except Exception as e:


        print(

            f"Google Sheet Error: {e}"

        )


# =========================================================
# BOT READY
# =========================================================

@client.event
async def on_ready():


    print("\n")

    print("========================================")

    print("🤖 DISCORD PAYMENT BOT ACTIVE")

    print("========================================")

    print(f"Bot Name: {client.user}")

    print(f"Bot ID: {client.user.id}")

    print(f"Servers: {len(client.guilds)}")

    print("========================================")

    print("\n")


# =========================================================
# BOT JOIN SERVER
# =========================================================

@client.event
async def on_guild_join(guild):


    print(

        f"Joined Server: {guild.name}"

    )


# =========================================================
# NEW DISCORD MESSAGE
# =========================================================

@client.event
async def on_message(message):


    # Ignore bot messages

    if message.author.bot:

        return


    # Screenshot check

    if not message.attachments:

        return


    # Party name

    party_name = message.content.strip()


    if not party_name:


        print(

            "❌ PARTY NAME MISSING"

        )


        return


    print("\n\n")

    print("========================================")

    print("📩 NEW PAYMENT MESSAGE DETECTED")

    print("========================================")

    print(f"Party Name: {party_name}")

    print(f"Discord User: {message.author}")

    print(f"Message ID: {message.id}")

    print(

        f"Attachments: {len(message.attachments)}"

    )

    print("========================================")


    # Process every attachment

    for attachment in message.attachments:


        print("\n")

        print(

            f"Processing: {attachment.filename}"

        )


        # =================================================
        # IMAGE CHECK
        # =================================================

        is_image = False


        if attachment.content_type:


            if attachment.content_type.startswith("image"):

                is_image = True


        # Backup extension check

        filename = attachment.filename.lower()


        if filename.endswith(

            (

                ".jpg",

                ".jpeg",

                ".png",

                ".webp"

            )

        ):


            is_image = True


        if not is_image:


            print(

                "Skipping non-image file"

            )


            continue


        # =================================================
        # SCREENSHOT URL
        # =================================================

        screenshot_url = attachment.url


        print(

            f"Screenshot URL: {screenshot_url}"

        )


        # =================================================
        # OCR PROCESS
        # =================================================

        amount, confidence = extract_amount(

            screenshot_url

        )


        status = get_status(confidence)


        print("\n")

        print("========================================")

        print("FINAL PAYMENT RESULT")

        print("========================================")

        print(f"Party: {party_name}")

        print(f"Amount: {amount}")

        print(f"Confidence: {confidence}")

        print(f"Status: {status}")

        print("========================================")

        print("\n")


        # =================================================
        # SEND TO GOOGLE SHEET
        # =================================================

        send_to_google_sheet(

            party_name=party_name,

            amount=amount,

            confidence=confidence,

            screenshot_url=screenshot_url,

            discord_user=str(message.author),

            message_id=str(message.id)

        )


# =========================================================
# START BOT
# =========================================================

if __name__ == "__main__":


    print("\n")

    print("========================================")

    print("STARTING UNIVERSAL PAYMENT BOT")

    print("========================================")

    print("\n")


    client.run(DISCORD_TOKEN)
