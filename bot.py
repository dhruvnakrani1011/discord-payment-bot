import os
import re
import io
import asyncio
import discord
import requests
import pytesseract

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


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
    "you sent",
    "sent",
    "successfully paid",
    "payment successful",
    "payment successful!",
    "paid successfully",
    "transfer amount",
    "transaction amount",
    "debited",
    "credited",
    "money sent",
    "money transferred",
    "payment done",
    "transfer successful",
    "successfully sent"

]


MEDIUM_KEYWORDS = [

    "upi",
    "transfer",
    "success",
    "successful",
    "completed",
    "transaction",
    "expense",
    "paid to",
    "sent to"

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
    "upi reference",
    "account number",
    "account no",
    "mobile",
    "phone",
    "contact",
    "ifsc",
    "rrn",
    "balance",
    "available balance",
    "kotak txn id",
    "transaction number"

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
    value = value.replace("inr", "")

    value = value.replace(",", "")
    value = value.replace(" ", "")

    value = value.replace("-", "")
    value = value.replace("–", "")
    value = value.replace("—", "")

    value = re.sub(r"[^\d.]", "", value)

    if value.count(".") > 1:

        parts = value.split(".")

        value = parts[0] + "." + parts[1]

    return value


# =========================================================
# VALID AMOUNT CHECK
# =========================================================

def is_valid_amount(value):

    try:

        number = float(value)

        if number < 1:
            return False

        if number > 10000000:
            return False

        return True

    except:

        return False


# =========================================================
# SUSPICIOUS NUMBER CHECK
# =========================================================

def is_suspicious_number(number):

    digits = re.sub(r"\D", "", str(number))

    if not digits:
        return True


    # Mobile number
    if len(digits) == 10:

        return True


    # Long transaction / reference numbers
    if len(digits) >= 11:

        return True


    # Years
    if digits in [

        "2023",
        "2024",
        "2025",
        "2026",
        "2027",
        "2028",
        "2029",
        "2030"

    ]:

        return True


    # Very common time values
    if len(digits) == 4:

        try:

            num = int(digits)

            # HHMM possible time
            hour = num // 100
            minute = num % 100

            if hour <= 23 and minute <= 59:

                return True

        except:

            pass


    return False


# =========================================================
# DATE CHECK
# =========================================================

def is_date_line(line):

    patterns = [

        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',

        r'\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)',

        r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b'

    ]


    for pattern in patterns:

        if re.search(pattern, line.lower()):

            return True


    return False


# =========================================================
# EXTRACT NUMBER CANDIDATES
# =========================================================

def find_numbers_in_line(line):

    results = []


    # Currency amount patterns
    currency_patterns = [

        r'[-–—]?\s*₹\s*[\d,]+(?:\.\d{1,2})?',

        r'[-–—]?\s*(?:rs\.?|inr)\s*[\d,]+(?:\.\d{1,2})?',

        r'₹\s*[\d,]+(?:\.\d{1,2})?',

        r'(?:rs\.?|inr)\s*[\d,]+(?:\.\d{1,2})?'

    ]


    for pattern in currency_patterns:

        matches = re.findall(

            pattern,

            line,

            re.IGNORECASE

        )


        for match in matches:

            results.append({

                "raw": match,

                "currency": True

            })


    # Normal numbers
    normal_pattern = r'(?<![\d/])\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?(?![\d/])'

    matches = re.findall(normal_pattern, line)


    for match in matches:

        results.append({

            "raw": match,

            "currency": False

        })


    # Plain number only if short enough
    plain_pattern = r'(?<![\d/])\d+(?:\.\d{1,2})?(?![\d/])'

    matches = re.findall(plain_pattern, line)


    for match in matches:

        # Avoid duplicates
        already = False

        for item in results:

            if clean_amount(item["raw"]) == clean_amount(match):

                already = True

                break


        if not already:

            results.append({

                "raw": match,

                "currency": False

            })


    return results


# =========================================================
# SCORE CANDIDATE
# =========================================================

def calculate_score(

    raw_number,
    line,
    previous_line,
    next_line,
    line_index,
    is_top_area

):

    score = 0

    line_lower = line.lower()

    previous_lower = previous_line.lower()

    next_lower = next_line.lower()


    # =====================================================
    # CURRENCY BONUS
    # =====================================================

    if "₹" in raw_number:

        score += 500


    if "rs" in raw_number.lower():

        score += 400


    if "inr" in raw_number.lower():

        score += 400


    # =====================================================
    # STRONG KEYWORD SAME LINE
    # =====================================================

    for keyword in STRONG_KEYWORDS:

        if keyword in line_lower:

            score += 200


    # =====================================================
    # MEDIUM KEYWORD SAME LINE
    # =====================================================

    for keyword in MEDIUM_KEYWORDS:

        if keyword in line_lower:

            score += 50


    # =====================================================
    # PREVIOUS LINE
    # =====================================================

    for keyword in STRONG_KEYWORDS:

        if keyword in previous_lower:

            score += 100


    for keyword in MEDIUM_KEYWORDS:

        if keyword in previous_lower:

            score += 25


    # =====================================================
    # NEXT LINE
    # =====================================================

    for keyword in STRONG_KEYWORDS:

        if keyword in next_lower:

            score += 100


    for keyword in MEDIUM_KEYWORDS:

        if keyword in next_lower:

            score += 25


    # =====================================================
    # BAD KEYWORDS
    # =====================================================

    for keyword in BAD_KEYWORDS:

        if keyword in line_lower:

            score -= 500


    for keyword in BAD_KEYWORDS:

        if keyword in previous_lower:

            score -= 200


    # =====================================================
    # DATE PENALTY
    # =====================================================

    if is_date_line(line):

        score -= 300


    # =====================================================
    # TOP AREA BONUS
    # =====================================================

    if is_top_area:

        score += 100


    # First few OCR lines generally payment summary
    if line_index <= 6:

        score += 30


    return score


# =========================================================
# EXTRACT CANDIDATES
# =========================================================

def extract_candidates(text, is_top_area=False):

    candidates = []

    lines = text.splitlines()


    for index, line in enumerate(lines):

        line = line.strip()


        if not line:

            continue


        previous_line = ""

        next_line = ""


        if index > 0:

            previous_line = lines[index - 1]


        if index < len(lines) - 1:

            next_line = lines[index + 1]


        numbers = find_numbers_in_line(line)


        for item in numbers:


            raw_number = item["raw"]


            amount = clean_amount(raw_number)


            if not amount:

                continue


            if not is_valid_amount(amount):

                continue


            if is_suspicious_number(amount):

                continue


            # If line looks like date and no currency symbol,
            # reject it completely

            if is_date_line(line) and not item["currency"]:

                continue


            score = calculate_score(

                raw_number=raw_number,

                line=line,

                previous_line=previous_line,

                next_line=next_line,

                line_index=index,

                is_top_area=is_top_area

            )


            # Currency explicitly found
            if item["currency"]:

                score += 300


            candidate = {

                "amount": amount,

                "score": score,

                "line": line,

                "raw": raw_number,

                "currency": item["currency"]

            }


            candidates.append(candidate)


    return candidates


# =========================================================
# REMOVE DUPLICATE CANDIDATES
# =========================================================

def remove_duplicate_candidates(candidates):

    best_candidates = {}


    for candidate in candidates:


        amount = candidate["amount"]


        if amount not in best_candidates:

            best_candidates[amount] = candidate


        else:


            if candidate["score"] > best_candidates[amount]["score"]:

                best_candidates[amount] = candidate


    return list(best_candidates.values())


# =========================================================
# SELECT BEST AMOUNT
# =========================================================

def select_best_amount(candidates):

    if not candidates:

        return "", 0


    candidates = remove_duplicate_candidates(candidates)


    candidates = sorted(

        candidates,

        key=lambda x: x["score"],

        reverse=True

    )


    print("\n========== ALL AMOUNT CANDIDATES ==========")


    for candidate in candidates:

        print(

            f"Amount: {candidate['amount']} | "

            f"Score: {candidate['score']} | "

            f"Currency: {candidate['currency']} | "

            f"Line: {candidate['line']}"

        )


    print("============================================\n")


    best = candidates[0]


    # Very low confidence reject

    if best["score"] < 50:

        return "NOT FOUND", 0


    return best["amount"], best["score"]


# =========================================================
# PREPROCESS IMAGE
# =========================================================

def preprocess_image(image):


    image = image.convert("RGB")


    width, height = image.size


    # Resize small screenshots

    if width < 1800:


        scale = 2


        image = image.resize(

            (

                width * scale,

                height * scale

            )

        )


    image = ImageOps.grayscale(image)


    image = ImageEnhance.Contrast(image).enhance(2.5)


    image = ImageEnhance.Sharpness(image).enhance(2)


    image = image.filter(

        ImageFilter.SHARPEN

    )


    return image


# =========================================================
# OCR FUNCTION
# =========================================================

def perform_ocr(image, mode):

    try:


        text = pytesseract.image_to_string(

            image,

            config=f"--oem 3 --psm {mode}"

        )


        return text


    except Exception as e:


        print(

            f"OCR Error Mode {mode}: {e}"

        )


        return ""


# =========================================================
# OCR IMAGE WITH MULTIPLE METHODS
# =========================================================

def extract_amount_from_image(image):


    processed = preprocess_image(image)


    all_candidates = []


    # =====================================================
    # FULL IMAGE OCR MODE 6
    # =====================================================

    print("\nRunning OCR Mode 6...")


    text_6 = perform_ocr(

        processed,

        6

    )


    print("\n========== OCR MODE 6 ==========")

    print(text_6)

    print("================================")


    all_candidates.extend(

        extract_candidates(

            text_6,

            False

        )

    )


    # =====================================================
    # FULL IMAGE OCR MODE 11
    # =====================================================

    print("\nRunning OCR Mode 11...")


    text_11 = perform_ocr(

        processed,

        11

    )


    print("\n========== OCR MODE 11 ==========")

    print(text_11)

    print("=================================")


    all_candidates.extend(

        extract_candidates(

            text_11,

            False

        )

    )


    width, height = processed.size


    # =====================================================
    # TOP 50% OCR
    # =====================================================

    top_image = processed.crop(

        (

            0,

            0,

            width,

            int(height * 0.50)

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


    all_candidates.extend(

        extract_candidates(

            top_text,

            True

        )

    )


    # =====================================================
    # TOP 35% OCR MODE 11
    # =====================================================

    top_small = processed.crop(

        (

            0,

            0,

            width,

            int(height * 0.35)

        )

    )


    print("\nRunning TOP SMALL OCR...")


    top_small_text = perform_ocr(

        top_small,

        11

    )


    all_candidates.extend(

        extract_candidates(

            top_small_text,

            True

        )

    )


    return select_best_amount(

        all_candidates

    )


# =========================================================
# UNIVERSAL AMOUNT EXTRACTOR
# =========================================================

def extract_amount(image_url):

    try:


        print("\n")

        print("========================================")

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


        print(

            f"Image Size: {image.size}"

        )


        amount, score = extract_amount_from_image(

            image

        )


        if not amount:

            print("FINAL RESULT: NOT FOUND")

            return "NOT FOUND", 0


        print("\n")

        print("========================================")

        print(f"FINAL AMOUNT: {amount}")

        print(f"CONFIDENCE SCORE: {score}")

        print("========================================")


        return amount, score


    except Exception as e:


        print("\n")

        print("========================================")

        print("UNIVERSAL OCR ERROR")

        print(str(e))

        print("========================================")


        return "NOT FOUND", 0


# =========================================================
# CONFIDENCE STATUS
# =========================================================

def get_status(score):


    if score >= 700:

        return "VERIFIED"


    elif score >= 400:

        return "LIKELY"


    elif score >= 100:

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


    # Ignore message without attachment

    if not message.attachments:

        return


    # Party name

    party_name = message.content.strip()


    if not party_name:


        print("❌ PARTY NAME MISSING")


        return


    print("\n\n")

    print("========================================")

    print("📩 NEW PAYMENT MESSAGE DETECTED")

    print("========================================")

    print(f"Party Name: {party_name}")

    print(f"Discord User: {message.author}")

    print(f"Message ID: {message.id}")

    print(f"Attachments: {len(message.attachments)}")

    print("========================================")


    # Process attachments

    for attachment in message.attachments:


        print("\n")

        print(

            f"Processing: {attachment.filename}"

        )


        is_image = False


        # Discord content type check

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


        screenshot_url = attachment.url


        print(

            f"Screenshot URL: {screenshot_url}"

        )


        # =================================================
        # OCR PROCESS
        # =================================================

        print(

            "Starting OCR..."

        )


        # Run blocking OCR separately

        amount, confidence = await asyncio.to_thread(

            extract_amount,

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

        await asyncio.to_thread(

            send_to_google_sheet,

            party_name,

            amount,

            confidence,

            screenshot_url,

            str(message.author),

            str(message.id)

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
