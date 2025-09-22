#!/usr/bin/env python3
"""
advanced_number_info_bot.py
An advanced Telegram bot that parses phone numbers and returns comprehensive info.
Includes name/username lookup capabilities and enhanced details.
"""

import os
import logging
import re
from dotenv import load_dotenv
from typing import Dict, List, Optional, Tuple

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import phonenumbers
from phonenumbers import geocoder, carrier, timezone, PhoneNumberFormat
from phonenumbers.phonenumberutil import NumberParseException

# ---- Config ----
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEFAULT_REGION = os.getenv("DEFAULT_REGION", "US")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required.")

# ---- Enhanced Logging ----
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---- Enhanced Data Structures ----
PHONE_TYPE_MAP = {
    phonenumbers.PhoneNumberType.FIXED_LINE: "📞 Fixed line",
    phonenumbers.PhoneNumberType.MOBILE: "📱 Mobile",
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "📞📱 Fixed or Mobile",
    phonenumbers.PhoneNumberType.TOLL_FREE: "🆓 Toll free",
    phonenumbers.PhoneNumberType.PREMIUM_RATE: "💎 Premium rate",
    phonenumbers.PhoneNumberType.SHARED_COST: "💰 Shared cost",
    phonenumbers.PhoneNumberType.VOIP: "🌐 VoIP",
    phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "👤 Personal number",
    phonenumbers.PhoneNumberType.PAGER: "📟 Pager",
    phonenumbers.PhoneNumberType.UAN: "🏢 UAN (Universal Access Number)",
    phonenumbers.PhoneNumberType.VOICEMAIL: "💬 Voicemail",
    phonenumbers.PhoneNumberType.UNKNOWN: "❓ Unknown",
}

CARRIER_EMOJIS = {
    'verizon': '🔴', 'att': '🔵', 't-mobile': '🟡', 'sprint': '🟠',
    'vodafone': '🔴', 'orange': '🟠', 'telefonica': '🔵', 'deutsche telekom': '🟡',
    'china mobile': '🇨🇳', 'airtel': '🟡', 'jio': '🟣', 'vodacom': '🔴'
}

# Mock database for name/username lookup (in real implementation, use proper APIs)
MOCK_NAME_DATABASE = {
    "+14155552671": {"name": "John Smith", "username": "johnsmith", "carrier": "Verizon Wireless"},
    "+442079460958": {"name": "Sarah Johnson", "username": "sarahj", "carrier": "BT Group"},
    "+4915735987612": {"name": "Hans Müller", "username": "hansm", "carrier": "Deutsche Telekom"},
    "+919876543210": {"name": "Priya Sharma", "username": "priyas", "carrier": "Airtel"},
}

# ---- Enhanced Helper Functions ----
def get_carrier_emoji(carrier_name: str) -> str:
    """Get appropriate emoji for carrier."""
    carrier_lower = carrier_name.lower()
    for key, emoji in CARRIER_EMOJIS.items():
        if key in carrier_lower:
            return emoji
    return "📡"

def lookup_name_info(phone_number: str) -> Dict:
    """Lookup name and username information (mock implementation)."""
    # In real implementation, integrate with services like Truecaller, Whitepages, etc.
    return MOCK_NAME_DATABASE.get(phone_number, {})

def get_number_risk_assessment(num_obj) -> str:
    """Assess potential risk level of the number."""
    if not phonenumbers.is_valid_number(num_obj):
        return "⚠️ High Risk (Invalid Number)"
    
    number_type = phonenumbers.number_type(num_obj)
    risky_types = [
        phonenumbers.PhoneNumberType.PREMIUM_RATE,
        phonenumbers.PhoneNumberType.SHARED_COST,
        phonenumbers.PhoneNumberType.UNKNOWN
    ]
    
    if number_type in risky_types:
        return "⚠️ Medium Risk (Suspicious Number Type)"
    
    return "✅ Low Risk (Appears Legitimate)"

def format_enhanced_number_info(num_obj) -> str:
    """Return comprehensive multi-line string with enhanced phone number info."""
    # Basic formatting
    intl = phonenumbers.format_number(num_obj, PhoneNumberFormat.INTERNATIONAL)
    e164 = phonenumbers.format_number(num_obj, PhoneNumberFormat.E164)
    nat = phonenumbers.format_number(num_obj, PhoneNumberFormat.NATIONAL)
    
    # Enhanced details
    region = phonenumbers.region_code_for_number(num_obj) or "Unknown"
    valid = phonenumbers.is_valid_number(num_obj)
    possible = phonenumbers.is_possible_number(num_obj)
    ptype = phonenumbers.number_type(num_obj)
    ptype_str = PHONE_TYPE_MAP.get(ptype, f"❓ {ptype}")
    carrier_name = carrier.name_for_number(num_obj, "en") or "Unknown"
    carrier_emoji = get_carrier_emoji(carrier_name)
    location = geocoder.description_for_number(num_obj, "en") or "Unknown"
    tzs = timezone.time_zones_for_number(num_obj) or []
    tzs_str = ", ".join(tzs) if tzs else "Unknown"
    risk_assessment = get_number_risk_assessment(num_obj)
    
    # Name/username lookup
    name_info = lookup_name_info(e164)
    name = name_info.get("name", "Not Available")
    username = name_info.get("username", "Not Available")
    
    # Format output with emojis and better structure
    parts = [
        "🔍 *Advanced Phone Number Analysis* 🔍",
        "",
        "📊 *Basic Information:*",
        f"• International: `{intl}`",
        f"• E.164: `{e164}`",
        f"• National: `{nat}`",
        "",
        "🌍 *Geographic Details:*",
        f"• Country/Region: `{region}`",
        f"• Location: `{location}`",
        f"• Timezones: `{tzs_str}`",
        "",
        "📡 *Carrier & Type:*",
        f"• Carrier: {carrier_emoji} `{carrier_name}`",
        f"• Number Type: {ptype_str}",
        "",
        "👤 *Identity Information:*",
        f"• Name: `{name}`",
        f"• Username: `{username}`",
        "",
        "⚡ *Validation & Security:*",
        f"• Valid Number: {'✅ Yes' if valid else '❌ No'}",
        f"• Possible Number: {'✅ Yes' if possible else '❌ No'}",
        f"• Risk Assessment: {risk_assessment}",
        "",
        "💡 *Notes:*",
        "_Name/username data is simulated. Real implementation requires API integration._",
        "_Carrier and location data are approximate and may not be 100% accurate._"
    ]
    
    return "\n".join(parts)

def extract_all_numbers_from_text(text: str, default_region: str) -> List:
    """Extract all phone numbers from text."""
    numbers = []
    try:
        for match in phonenumbers.PhoneNumberMatcher(text, default_region):
            numbers.append(match.number)
    except Exception as e:
        logger.error(f"Error extracting numbers: {e}")
    return numbers

# ---- Enhanced Telegram Handlers ----
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced start command with better formatting."""
    welcome_text = """
👋 *Welcome to Advanced Number Info Bot!* 🔍

I can analyze phone numbers and provide comprehensive information including:

📊 *Basic Details* - International, E.164, National formats
🌍 *Geographic Info* - Country, location, timezone
📡 *Carrier & Type* - Service provider and number classification
👤 *Identity Data* - Name and username lookup
⚡ *Security Analysis* - Validation and risk assessment

*How to use:*
• Send a phone number directly
• Use `/info +1234567890`
• Reply to a message with `/info`

*Examples:*
• `/info +14155552671`
• `/info +44 20 7946 0958`
• Just send `+919876543210`

*Privacy Note:* Name/username data is simulated for demonstration.
    """
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced info command with multiple number support."""
    text = " ".join(context.args).strip()
    
    # Check if replying to a message
    if not text and update.message.reply_to_message:
        if update.message.reply_to_message.text:
            text = update.message.reply_to_message.text.strip()
        elif update.message.reply_to_message.caption:
            text = update.message.reply_to_message.caption.strip()
    
    if not text:
        await update.message.reply_text(
            "Usage: `/info <phone-number>`\nExample: `/info +1 415-555-2671`\nOr reply to a message with `/info`",
            parse_mode="Markdown"
        )
        return
    
    # Extract all numbers from text
    numbers = extract_all_numbers_from_text(text, DEFAULT_REGION)
    
    if not numbers:
        await update.message.reply_text(
            "❌ No valid phone numbers found in the provided text.\n"
            "Make sure to include country code (e.g., +1, +44) and proper formatting."
        )
        return
    
    # Process each found number
    for i, num_obj in enumerate(numbers):
        if i >= 3:  # Limit to 3 numbers per message to avoid spam
            await update.message.reply_text("ℹ️ Additional numbers omitted for brevity.")
            break
            
        reply = format_enhanced_number_info(num_obj)
        await update.message.reply_text(reply, parse_mode="Markdown")

async def batch_info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process multiple numbers at once."""
    text = " ".join(context.args).strip()
    
    if not text:
        await update.message.reply_text(
            "Usage: `/batchinfo <numbers separated by commas or spaces>`\n"
            "Example: `/batchinfo +14155552671, +442079460958`"
        )
        return
    
    numbers = extract_all_numbers_from_text(text, DEFAULT_REGION)
    
    if not numbers:
        await update.message.reply_text("❌ No valid phone numbers found.")
        return
    
    if len(numbers) > 5:
        await update.message.reply_text("⚠️ Please limit to 5 numbers at a time.")
        numbers = numbers[:5]
    
    summary = f"📋 *Batch Analysis Results* ({len(numbers)} numbers found)\n\n"
    
    for i, num_obj in enumerate(numbers, 1):
        intl = phonenumbers.format_number(num_obj, PhoneNumberFormat.INTERNATIONAL)
        carrier_name = carrier.name_for_number(num_obj, "en") or "Unknown"
        location = geocoder.description_for_number(num_obj, "en") or "Unknown"
        valid = "✅" if phonenumbers.is_valid_number(num_obj) else "❌"
        
        summary += f"{i}. `{intl}`\n"
        summary += f"   📍 {location} | 📡 {carrier_name} | {valid}\n\n"
    
    await update.message.reply_text(summary, parse_mode="Markdown")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct text messages containing phone numbers."""
    text = update.message.text or ""
    numbers = extract_all_numbers_from_text(text, DEFAULT_REGION)
    
    if numbers:
        for i, num_obj in enumerate(numbers):
            if i >= 2:  # Limit response for direct messages
                await update.message.reply_text(
                    "ℹ️ For analyzing multiple numbers, use `/batchinfo` command."
                )
                break
            reply = format_enhanced_number_info(num_obj)
            await update.message.reply_text(reply, parse_mode="Markdown")
    else:
        help_text = (
            "🔍 *Number Info Bot Help*\n\n"
            "Send me a phone number or use:\n"
            "• `/info <number>` - Detailed analysis\n"
            "• `/batchinfo <numbers>` - Multiple numbers\n"
            "• `/help` - This message\n\n"
            "Example: `+1 (415) 555-2671` or `/info +441234567890`"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced error handling."""
    logger.error(f"Update {update} caused error: {context.error}")
    
    if update and hasattr(update, 'message'):
        await update.message.reply_text(
            "❌ An error occurred while processing your request. "
            "Please try again or check the number format."
        )

# ---- Main Application ----
def main():
    """Initialize and run the bot."""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", start_cmd))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(CommandHandler("batchinfo", batch_info_cmd))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    logger.info("🤖 Advanced Number Info Bot started!")
    print("Bot features:")
    print("✅ Enhanced number analysis")
    print("✅ Name/username lookup (simulated)")
    print("✅ Multiple number processing")
    print("✅ Risk assessment")
    print("✅ Batch analysis commands")
    
    app.run_polling()

if __name__ == "__main__":
    main()

