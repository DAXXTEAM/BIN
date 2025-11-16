from pyrogram import Client, filters
from pyrogram.enums import ParseMode
import asyncio
import re
import random
import os
import time
import requests
from datetime import datetime

API_ID = 24509589
API_HASH = "717cf21d94c4934bcbe1eaa1ad86ae75"
BOT_TOKEN = "8529807653:AAGa3fUu5hvV4y16g_wtAuuXgnG-kGnuKms"
app = Client("Flah", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

CARD_GEN_LIMIT = 50000000
CVV_REPLACE_LIMIT = 5000000
TXT_FILE_SIZE_LIMIT = 50 * 1024 * 1024  # 50 MB

BIN_PATTERN = re.compile(r"\b(\d{6})\d*\b")
card_pattern = re.compile(
    r"(?<!\d)(\d{13,16})(?!\d).*?[|/:\s]+(\d{1,2})[|/:\s]+(\d{2,4})(?:[|/:\s]+(\d{3,4}))?",
    re.DOTALL
)

def luhn_check(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10 == 0

def country_code_to_emoji(code):
    if not code:
        return ""
    code = str(code).upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return chr(0x1F1E6 + ord(code[0]) - ord("A")) + chr(0x1F1E6 + ord(code[1]) - ord("A"))

def fetch_bin_info(bin_number):
    try:
        raw = requests.get(
            f"https://bins.antipublic.cc/bins/{str(bin_number)[:6]}",
            timeout=10
        ).json()
    except:
        return {"result": False}
    if "bin" not in raw:
        return {"result": False}
    currency = (raw.get("country_currencies") or ["Unknown"])[0]
    flag = raw.get("country_flag", "")
    data = {
        "brand": raw.get("brand", "Unknown"),
        "type": raw.get("type", "Unknown"),
        "level": raw.get("level", "Unknown"),
        "bank": {"name": raw.get("bank", "Unknown")},
        "country": {
            "name": raw.get("country_name", "Unknown"),
            "emoji": flag,
            "currency": currency
        }
    }
    return {"result": True, "data": data}

async def get_bin_info(bin_number):
    bin_data = fetch_bin_info(bin_number)
    if not bin_data or not bin_data.get("result"):
        return "Unknown", "Unknown", "Unknown", "Unknown", "Unknown", ""
    data = bin_data.get("data", {})
    bank = data.get("bank", {})
    country = data.get("country", {})
    brand = data.get("brand", "Unknown")
    card_type = data.get("type", "Unknown")
    level = data.get("level", "Unknown")
    bank_name = bank.get("name", "Unknown")
    country_name = country.get("name", "Unknown")
    flag = country.get("emoji", "")
    return brand, card_type, level, bank_name, country_name, flag

def format_bin_info(bin_data, bin_number):
    if not bin_data.get("result"):
        return "❌ Invalid BIN or not found"
    d = bin_data["data"]
    b = d["bank"]
    c = d["country"]
    return f"""
💳 **BIN Information**
┌ **BIN**: `{bin_number}`
├ **Brand**: {d['brand']}
├ **Type**: {d['type']}
├ **Level**: {d['level']}
├ **Bank**: {b['name']}
├ **Country**: {c['name']} {c['emoji']}
└ **Currency**: {c['currency']}
"""

@app.on_message(filters.command(["bin"], ["/", "."]))
async def bin_command(client, message):
    processing_msg = await message.reply_text("🔍 **Processing BINs...**")
    bin_input = ""
    if len(message.command) > 1:
        bin_input = " ".join(message.command[1:])
    elif message.reply_to_message and (message.reply_to_message.text or "").strip():
        bin_input = message.reply_to_message.text.strip()
    if not bin_input:
        await processing_msg.edit_text("❌ Please provide BINs or reply to a message containing BINs")
        return
    found_bins = BIN_PATTERN.findall(bin_input)
    if not found_bins:
        await processing_msg.edit_text("❌ No valid 6-digit BINs found")
        return
    unique_bins = list(dict.fromkeys(found_bins))[:10]
    results = []
    for bin_num in unique_bins:
        bin_data = fetch_bin_info(bin_num)
        result_text = format_bin_info(bin_data, bin_num)
        results.append(result_text.strip())
        await asyncio.sleep(0.1)
    result_text = f"🔍 **Found {len(results)} BINs:**\n\n" + "\n\n".join(results)
    await processing_msg.edit_text(result_text)

def complete_luhn(base):
    for d in "0123456789":
        candidate = base + d
        if luhn_check(candidate):
            return candidate
    return None

def get_card_length(brand):
    brand = (brand or "").upper()
    if brand in {"AMEX", "AMERICAN EXPRESS"}:
        return 15
    if brand == "DINERS CLUB":
        return 14
    return 16

async def generate_cards(cc_bin, amount, mes="x", ano="x", cvv="x"):
    output = []
    seen = set()
    bin_part = re.sub(r"\D", "", cc_bin.replace("x", "0"))[:6].ljust(6, "0")
    brand, *_ = await get_bin_info(bin_part)
    card_length = get_card_length(brand)
    cvv_length = 4 if card_length == 15 else 3
    attempts = 0
    while len(output) < amount and attempts < amount * 30:
        attempts += 1
        base = "".join(random.choice("0123456789") if c.lower() == "x" else c for c in cc_bin)
        base = base[: card_length - 1]
        if len(base) < card_length - 1:
            base += "".join(random.choices("0123456789", k=card_length - 1 - len(base)))
        card_number = complete_luhn(base)
        if not card_number or card_number in seen:
            continue
        seen.add(card_number)
        if mes.lower() == "x":
            month = random.randint(1, 12)
        else:
            try:
                m = int(mes)
                month = m if 1 <= m <= 12 else random.randint(1, 12)
            except:
                month = random.randint(1, 12)
        mes_str = str(month).zfill(2)
        if ano.lower() == "x":
            year = random.randint(datetime.now().year, 2030)
        else:
            try:
                y = int(ano)
                if y < 100:
                    y += 2000
                year = y if datetime.now().year <= y <= 2030 else datetime.now().year
            except:
                year = datetime.now().year
        ano_str = str(year)[2:]
        if cvv.lower() == "x":
            cvv_str = "".join(random.choices("0123456789", k=cvv_length))
        else:
            cvv_str = cvv
        output.append(f"{card_number}|{mes_str}|{ano_str}|{cvv_str}")
    return output

def parse_input(text):
    text = (
        text.replace("`", "")
        .replace("\n", "|")
        .replace("/", "|")
        .replace("random", "x")
        .replace("rnd", "x")
    )
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None, "x", "x", "x", 10
    args = parts[1].strip()
    if " " in args:
        block, amt = args.rsplit(" ", 1)
    else:
        block, amt = args, "10"
    tokens = [p.strip() for p in re.sub(r"[|/ ]+", "|", block).split("|") if p.strip()]
    bin_ = tokens[0] if tokens else None
    mon = tokens[1] if len(tokens) > 1 else "x"
    year = tokens[2] if len(tokens) > 2 else "x"
    cvv = tokens[3] if len(tokens) > 3 else "x"
    amount = int(amt) if amt.isdigit() and 1 <= int(amt) <= CARD_GEN_LIMIT else 10
    return bin_, mon, year, cvv, amount

@app.on_message(filters.command(["gen"], [".", "!", "/"]))
async def generate_card(client, message):
    try:
        status = await message.reply("**Generating cards, please wait...**")
        start_time = time.time()
        bin_, mon, year, cvv, amount = parse_input(message.text or "")
        if not bin_ or len(re.sub(r"[xX]", "", bin_)) < 6:
            await status.edit("❌ **Please provide at least a 6-digit BIN.**")
            return
        bin_numeric = re.sub(r"\D", "", bin_.replace("x", "0"))[:6].ljust(6, "0")
        brand, card_type, level, bank, country, flag = await get_bin_info(bin_numeric)
        cards = await generate_cards(bin_, amount, mes=mon, ano=year, cvv=cvv)
        elapsed = time.time() - start_time
        user_obj = message.from_user
        profile_link = (
            f"https://t.me/{user_obj.username}"
            if user_obj.username
            else f"tg://user?id={user_obj.id}"
        )
        fullname = f"{user_obj.first_name}{(' ' + user_obj.last_name) if user_obj.last_name else ''}"
        await status.delete()
        if amount > 10:
            file_name = "cards.txt"
            with open(file_name, "w") as f:
                f.write("\n".join(cards))
            caption = (
                f"**BIN** ⇾ `{bin_numeric}`\n"
                f"**Amount** ⇾ `{amount}`\n"
                f"**Info** ⇾ `{brand}` - `{card_type}` - `{level}`\n"
                f"**Issuer** ⇾ `{bank}`\n"
                f"**Country** ⇾ `{country}` {flag}\n"
                f"**Time Taken** ⇾ {elapsed:.2f}s\n"
                f"**Requested By**: [{fullname}]({profile_link})"
            )
            await client.send_document(
                message.chat.id,
                file_name,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=message.id,
            )
            os.remove(file_name)
        else:
            card_lines = "\n".join(f"`{c}`" for c in cards)
            text = (
                f"**BIN** ⇾ `{bin_numeric}`\n"
                f"**Amount** ⇾ `{amount}`\n\n"
                f"{card_lines}\n\n"
                f"**Info** ⇾ `{brand}` - `{card_type}` - `{level}`\n"
                f"**Issuer** ⇾ `{bank}`\n"
                f"**Country** ⇾ `{country}` {flag}\n"
                f"**Time Taken** ⇾ {elapsed:.2f}s\n"
                f"**Requested By**: [{fullname}]({profile_link})"
            )
            await message.reply(
                text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
    except Exception as e:
        error_msg = await message.reply(f"❌ Error: `{e}`")
        await asyncio.sleep(5)
        await error_msg.delete()


@app.on_message(filters.command(["mgen"], [".", "!", "/"]))
async def mass_generate_cards(client, message):
    try:
        if not message.reply_to_message:
            await message.reply("❌ **Please reply to a message or text file containing BINs**")
            return
        
        reply_msg = message.reply_to_message
        bin_text = ""
        
        if reply_msg.document and reply_msg.document.mime_type == 'text/plain':
            if reply_msg.document.file_size > TXT_FILE_SIZE_LIMIT:
                await message.reply(f"❌ File size too large. Maximum allowed: {TXT_FILE_SIZE_LIMIT // (1024*1024)}MB")
                return
            
            file_path = await reply_msg.download()
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                bin_text = f.read()
            os.remove(file_path)
        
        elif reply_msg.text:
            bin_text = reply_msg.text
        else:
            await message.reply("❌ **Please reply to a text message or text file containing BINs**")
            return
        
        if len(message.command) < 2:
            await message.reply("❌ **Please specify the amount, e.g., `/mgen 500`**")
            return
        
        try:
            total_amount = int(message.command[1])
            if total_amount < 1 or total_amount > CARD_GEN_LIMIT:
                await message.reply(f"❌ **Amount must be between 1 and {CARD_GEN_LIMIT}**")
                return
        except ValueError:
            await message.reply("❌ **Invalid amount. Please provide a valid number**")
            return
        
        extracted_bins = extract_bins_from_text(bin_text)
        
        if not extracted_bins:
            await message.reply("❌ **No valid BINs found in the replied message/file**")
            return
        
        unique_bins = list(dict.fromkeys(extracted_bins))[:50]
        
        status_msg = await message.reply(f"🔍 **Found {len(unique_bins)} unique BINs. Generating {total_amount} cards...**")
        start_time = time.time()
        
        cards_per_bin = max(1, total_amount // len(unique_bins))
        remaining_cards = total_amount % len(unique_bins)
        
        all_cards = []
        bin_info_map = {}
        
        for i, bin_num in enumerate(unique_bins):
            current_amount = cards_per_bin
            if i < remaining_cards:
                current_amount += 1
            
            if current_amount <= 0:
                continue
            
            bin_numeric = re.sub(r"\D", "", bin_num.replace("x", "0"))[:6].ljust(6, "0")
            if bin_numeric not in bin_info_map:
                brand, card_type, level, bank, country, flag = await get_bin_info(bin_numeric)
                bin_info_map[bin_numeric] = {
                    'brand': brand,
                    'type': card_type,
                    'level': level,
                    'bank': bank,
                    'country': country,
                    'flag': flag,
                    'count': 0
                }
            
            bin_cards = await generate_cards(bin_num, current_amount)
            all_cards.extend(bin_cards)
            bin_info_map[bin_numeric]['count'] += len(bin_cards)
            
            await asyncio.sleep(0.1)
        
        random.shuffle(all_cards)
        
        all_cards = all_cards[:total_amount]
        
        elapsed = time.time() - start_time
        
        user_obj = message.from_user
        profile_link = (
            f"https://t.me/{user_obj.username}"
            if user_obj.username
            else f"tg://user?id={user_obj.id}"
        )
        fullname = f"{user_obj.first_name}{(' ' + user_obj.last_name) if user_obj.last_name else ''}"
        
        await status_msg.delete()
        
        if total_amount > 10:
            file_name = "mass_generated_cards.txt"
            with open(file_name, "w", encoding='utf-8') as f:
                f.write("\n".join(all_cards))
            
            bin_summary = "\n".join([
                f"• `{bin_num}`: {info['count']} cards ({info['brand']} - {info['bank']})"
                for bin_num, info in bin_info_map.items()
            ])
            
            caption = (
                f"🎴 **Mass Generation Complete!**\n"
                f"📊 **Total Cards**: `{len(all_cards)}`\n"
                f"🔢 **BINs Used**: `{len(unique_bins)}`\n"
                f"⏱️ **Time Taken**: `{elapsed:.2f}s`\n\n"
                f"📋 **BIN Summary**:\n{bin_summary}\n\n"
                f"👤 **Requested By**: [{fullname}]({profile_link})"
            )
            
            await client.send_document(
                message.chat.id,
                file_name,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_to_message_id=message.id,
            )
            os.remove(file_name)
            
        else:
            card_lines = "\n".join(f"`{c}`" for c in all_cards)
            bin_summary = " | ".join([
                f"`{bin_num}`"
                for bin_num in unique_bins[:5]
            ])
            if len(unique_bins) > 5:
                bin_summary += f" ... and {len(unique_bins) - 5} more"
            
            text = (
                f"🎴 **Mass Generation Complete!**\n"
                f"📊 **Total Cards**: `{len(all_cards)}`\n"
                f"🔢 **BINs Used**: `{len(unique_bins)}`\n\n"
                f"{card_lines}\n\n"
                f"🔍 **BINs**: {bin_summary}\n"
                f"⏱️ **Time Taken**: `{elapsed:.2f}s`\n"
                f"👤 **Requested By**: [{fullname}]({profile_link})"
            )
            
            await message.reply(
                text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            
    except Exception as e:
        error_msg = await message.reply(f"❌ Error in mass generation: `{e}`")
        await asyncio.sleep(5)
        await error_msg.delete()


def extract_bins_from_text(text):
    bins = set()
    
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        cleaned_line = re.sub(r'[^\dx|]', '', line)
        
        card_match = re.search(r'(\d{6,})', cleaned_line)
        if card_match:
            bin_candidate = card_match.group(1)[:6]
            if len(bin_candidate) == 6 and bin_candidate.isdigit():
                bins.add(bin_candidate)
                continue
        
        bin_pattern_match = re.search(r'(\d{1,6}[x\d]*)', cleaned_line)
        if bin_pattern_match:
            bin_candidate = bin_pattern_match.group(1)
            if len(bin_candidate) >= 6:
                if len(bin_candidate) < 6:
                    bin_candidate = bin_candidate.ljust(6, 'x')
                bins.add(bin_candidate)
                continue
        
        plain_bin_match = re.search(r'\b(\d{6})\b', line)
        if plain_bin_match:
            bins.add(plain_bin_match.group(1))
    
    return list(bins)


def extract_multiple_cards(text, limit=CVV_REPLACE_LIMIT):
    matches = card_pattern.findall(text)
    valid_cards = []
    for match in matches:
        cc, mm, yy, cvv = match
        if cc and mm and yy and cvv and 3 <= len(cvv) <= 4:
            valid_cards.append(f"{cc}|{mm}|{yy}|{cvv}")
        if len(valid_cards) >= limit:
            break
    return valid_cards

@app.on_message(filters.command("cvv"))
async def cvv_command(client, message):
    if len(message.command) < 2:
        await message.reply("❌ Please provide the new CVV, e.g., /cvv 000")
        return
    new_cvv = message.command[1]
    if not re.match(r'^\d{3,4}$', new_cvv):
        await message.reply("❌ Invalid CVV. Must be 3 or 4 digits.")
        return
    is_file = False
    text = ""
    if message.reply_to_message:
        reply = message.reply_to_message
        if reply.document and reply.document.mime_type == 'text/plain' and reply.document.file_size <= TXT_FILE_SIZE_LIMIT:
            is_file = True
            file_name = await reply.download()
            with open(file_name, 'r', encoding='utf-8') as f:
                text = f.read()
            os.remove(file_name)
        elif reply.text:
            text = reply.text
    if not text:
        await message.reply("❌ No text or file to extract cards from.")
        return
    cards = extract_multiple_cards(text)
    if not cards:
        await message.reply("❌ No valid cards found.")
        return
    updated_cards = []
    for card in cards:
        parts = card.rsplit('|', 1)
        if len(parts) == 2:
            updated = parts[0] + '|' + new_cvv
            updated_cards.append(updated)
    if not updated_cards:
        await message.reply("❌ No cards to update.")
        return
    header = f"✅ CVV Replacement Complete! 🎉\n🔑 New CVV: {new_cvv}\n"
    footer = "\n🔄 All cards updated with new CVV ✨"
    if is_file:
        new_file_name = "updated_cards.txt"
        with open(new_file_name, 'w', encoding='utf-8') as f:
            f.write('\n'.join(updated_cards) + '\n')
        caption = header + footer
        await client.send_document(
            message.chat.id,
            new_file_name,
            caption=caption,
            reply_to_message_id=message.id
        )
        os.remove(new_file_name)
    else:
        card_list = '\n'.join(updated_cards)
        reply_text = header + card_list + footer
        await message.reply(reply_text)

@app.on_message(filters.command(["start", "help"], ["/"]))
async def start_command(client, message):
    start_text = """
🤖 **BIN Checker & Generator Bot**
**BIN Commands:**
- `/bin 123456` - Check single BIN
- `.bin 123456` - Check single BIN
- Reply to message with `/bin` or `.bin` - Extract BINs from replied text

**Generator Commands:**
- `/gen 123456` - Generate 10 cards
- `/gen 123456|x|x|x 20` - Generate 20 cards with random details
- `/gen 123456|12|2025|123 5` - Generate 5 cards with specific details

**Mass Generator Command:**
- `/mgen 500` - Reply to message/file with BINs to generate 500 cards distributed among all BINs

**CVV Command:**
- `/cvv 000` - Replace CVV in replied message or file
    """
    await message.reply_text(start_text)

print("Bot Started!")

app.run()
