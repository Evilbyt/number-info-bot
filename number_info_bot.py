#!/usr/bin/env python3
"""
number_info_bot.py
A Telegram bot that parses phone numbers and returns info using the `phonenumbers` library.
Requires:
  pip install python-telegram-bot phonenumbers python-dotenv
"""

import os
import logging
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import phonenumbers
from phonenumbers import geocoder, carrier, timezone, PhoneNumberFormat
from phonenumbers.phonenumberutil import NumberParseException

# ---- Config ----
load_dotenv()  # loads .env if present
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEFAULT_REGION = os.getenv("DEFAULT_REGION", "US")  # fallback region when user omits +countrycode, e.g. "US" or "IN"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required. Create a .env with BOT_TOKEN=your_token")

# ---- Logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- Helpers ----
PHONE_TYPE_MAP = {
    phonenumbers.PhoneNumberType.FIXED_LINE: "Fixed line",
    phonenumbers.PhoneNumberType.MOBILE: "Mobile",
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed or Mobile",
    phonenumbers.PhoneNumberType.TOLL_FREE: "Toll free",
    phonenumbers.PhoneNumberType.PREMIUM_RATE: "Premium rate",
    phonenumbers.PhoneNumberType.SHARED_COST: "Shared cost",
    phonenumbers.PhoneNumberType.VOIP: "VoIP",
    phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Personal number",
    phonenumbers.PhoneNumberType.PAGER: "Pager",
    phonenumbers.PhoneNumberType.UAN: "UAN",
    phonenumbers.PhoneNumberType.VOICEMAIL: "Voicemail",
    phonenumbers.PhoneNumberType.UNKNOWN: "Unknown",
}

def format_number_info(num):
    """Return a multi-line string with info about a parsed phonenumbers.PhoneNumber object."""
    intl = phonenumbers.format_number(num, PhoneNumberFormat.INTERNATIONAL)
    e164 = phonenumbers.format_number(num, PhoneNumberFormat.E164)
    nat = phonenumbers.format_number(num, PhoneNumberFormat.NATIONAL)
    region = phonenumbers.region_code_for_number(num) or "Unknown"
    valid = phonenumbers.is_valid_number(num)
    possible = phonenumbers.is_possible_number(num)
    ptype = phonenumbers.number_type(num)
    ptype_str = PHONE_TYPE_MAP.get(ptype, str(ptype))
    carrier_name = carrier.name_for_number(num, "en") or "Unknown"
    location = geocoder.description_for_number(num, "en") or "Unknown"
    tzs = timezone.time_zones_for_number(num) or []
    tzs_str = ", ".join(tzs) if tzs else "Unknown"

    parts = [
        f"*International:* `{intl}`",
        f"*E.164:* `{e164}`",
        f"*National:* `{nat}`",
        f"*Country / Region code:* `{region}`",
        f"*Valid number:* `{valid}`",
        f"*Possible number:* `{possible}`",
        f"*Number type:* `{ptype_str}`",
        f"*Carrier (best-effort):* `{carrier_name}`",
        f"*Geographic hint:* `{location}`",
        f"*Timezones (possible):* `{tzs_str}`",
        "",
        "_Note: this provides formatting/location hints and carrier data when available. It does not provide owner names or any private registration data._"
    ]
    return "\n".join(parts)

def extract_first_number_from_text(text, default_region):
    """Try to find the first phone number in text. Returns a phonenumbers.PhoneNumber or None."""
    matcher = phonenumbers.PhoneNumberMatcher(text, default_region)
    for match in matcher:
        return match.number
    return None

# ---- Telegram handlers ----
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Send me a phone number (or use /info <number>) and I'll return details: country, formats, type, carrier hint, etc.\n\n"
        "Examples:\n• `/info +14155552671`\n• send `+44 20 7946 0958` as a message"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_cmd(update, context)

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Accept /info <number> or reply to a message
    text = " ".join(context.args).strip()
    if not text and update.message.reply_to_message and update.message.reply_to_message.text:
        text = update.message.reply_to_message.text.strip()

    if not text:
        await update.message.reply_text("Usage: /info <phone-number>\nE.g. `/info +91 98765 43210`", parse_mode="Markdown")
        return

    # Try direct parse first (if user passed a single number). Otherwise use matcher
    num_obj = None
    try:
        # Try parsing as a full number (prefer '+' included)
        num_obj = phonenumbers.parse(text, None)  # if text has + it will parse
    except NumberParseException:
        # fallback: try using default region parse
        try:
            num_obj = phonenumbers.parse(text, DEFAULT_REGION)
        except NumberParseException:
            num_obj = None

    # If still none, try to extract from the whole string
    if num_obj is None:
        num_obj = extract_first_number_from_text(text, DEFAULT_REGION)

    if num_obj is None:
        await update.message.reply_text(
            "I couldn't find a phone number in that text. Make sure you include a country code (e.g. +1, +44) or send a clear phone number."
        )
        return

    reply = format_number_info(num_obj)
    await update.message.reply_text(reply, parse_mode="Markdown")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    num_obj = extract_first_number_from_text(text, DEFAULT_REGION)
    if num_obj:
        reply = format_number_info(num_obj)
        await update.message.reply_text(reply, parse_mode="Markdown")
    else:
        # Ignore or give a small hint
        await update.message.reply_text("Send a phone number or use /info <number> to get details.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Error while handling an update: %s", context.error)

# ---- Main ----
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)

    logger.info("Bot started. Running polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
