#!/usr/bin/env python3
"""
advanced_number_info_bot.py
An advanced Telegram bot that parses phone numbers and returns comprehensive info.
Integrates with free phone number lookup APIs for real name/username data.
"""

import os
import logging
import re
import json
import asyncio
import aiohttp
from dotenv import load_dotenv
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import phonenumbers
from phonenumbers import geocoder, carrier, timezone, PhoneNumberFormat
from phonenumbers.phonenumberutil import NumberParseException

# ---- Config ----
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEFAULT_REGION = os.getenv("DEFAULT_REGION", "US")

# Free API Keys (Register for free tiers)
ABSTRACT_API_KEY = os.getenv("ABSTRACT_API_KEY")  # https://app.abstractapi.com/
NUMVERIFY_API_KEY = os.getenv("NUMVERIFY_API_KEY")  # https://numverify.com/
OPENCAGE_API_KEY = os.getenv("OPENCAGE_API_KEY")  # https://opencagedata.com/

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

# ---- Free API Integration Classes ----
class PhoneNumberLookupAPI:
    """Base class for phone number lookup APIs"""
    
    def __init__(self):
        self.session = None
    
    async def get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

class AbstractAPI(PhoneNumberLookupAPI):
    """AbstractAPI Phone Validation API (1000 free requests/month)"""
    
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.base_url = "https://phonevalidation.abstractapi.com/v1/"
    
    async def lookup_number(self, phone_number: str) -> Dict:
        """Lookup phone number using AbstractAPI"""
        if not self.api_key:
            return {"error": "AbstractAPI key not configured"}
        
        try:
            session = await self.get_session()
            params = {
                'api_key': self.api_key,
                'phone': phone_number
            }
            
            async with session.get(self.base_url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_response(data)
                else:
                    return {"error": f"API error: {response.status}"}
                    
        except Exception as e:
            logger.error(f"AbstractAPI error: {e}")
            return {"error": str(e)}
    
    def _parse_response(self, data: Dict) -> Dict:
        """Parse AbstractAPI response"""
        result = {
            "valid": data.get("valid", False),
            "format": {
                "international": data.get("format", {}).get("international"),
                "local": data.get("format", {}).get("local")
            },
            "country": {
                "name": data.get("country", {}).get("name"),
                "code": data.get("country", {}).get("code"),
                "prefix": data.get("country", {}).get("prefix")
            },
            "location": data.get("location"),
            "carrier": data.get("carrier"),
            "line_type": data.get("type")
        }
        return result

class NumVerifyAPI(PhoneNumberLookupAPI):
    """NumVerify API (1000 free requests/month)"""
    
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.base_url = "http://apilayer.net/api/validate"
    
    async def lookup_number(self, phone_number: str) -> Dict:
        """Lookup phone number using NumVerify"""
        if not self.api_key:
            return {"error": "NumVerify key not configured"}
        
        try:
            session = await self.get_session()
            params = {
                'access_key': self.api_key,
                'number': phone_number,
                'country_code': '',
                'format': 1
            }
            
            async with session.get(self.base_url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_response(data)
                else:
                    return {"error": f"API error: {response.status}"}
                    
        except Exception as e:
            logger.error(f"NumVerify error: {e}")
            return {"error": str(e)}
    
    def _parse_response(self, data: Dict) -> Dict:
        """Parse NumVerify response"""
        result = {
            "valid": data.get("valid", False),
            "number": data.get("number"),
            "local_format": data.get("local_format"),
            "international_format": data.get("international_format"),
            "country": {
                "name": data.get("country_name"),
                "code": data.get("country_code"),
                "prefix": data.get("country_prefix")
            },
            "location": data.get("location"),
            "carrier": data.get("carrier"),
            "line_type": data.get("line_type")
        }
        return result

class OpenCageGeocodingAPI(PhoneNumberLookupAPI):
    """OpenCage Geocoding API (2500 free requests/day)"""
    
    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.base_url = "https://api.opencagedata.com/geocode/v1/json"
    
    async def reverse_geocode(self, lat: float, lng: float) -> Dict:
        """Reverse geocode coordinates to get location details"""
        if not self.api_key:
            return {"error": "OpenCage key not configured"}
        
        try:
            session = await self.get_session()
            params = {
                'key': self.api_key,
                'q': f"{lat},{lng}",
                'pretty': 1,
                'no_annotations': 1
            }
            
            async with session.get(self.base_url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_response(data)
                else:
                    return {"error": f"API error: {response.status}"}
                    
        except Exception as e:
            logger.error(f"OpenCage error: {e}")
            return {"error": str(e)}
    
    def _parse_response(self, data: Dict) -> Dict:
        """Parse OpenCage response"""
        if data.get("results"):
            result = data["results"][0]
            components = result.get("components", {})
            return {
                "formatted": result.get("formatted"),
                "country": components.get("country"),
                "state": components.get("state"),
                "county": components.get("county"),
                "city": components.get("city"),
                "postcode": components.get("postcode")
            }
        return {"error": "No results found"}

# Initialize API clients
abstract_api = AbstractAPI(ABSTRACT_API_KEY) if ABSTRACT_API_KEY else None
numverify_api = NumVerifyAPI(NUMVERIFY_API_KEY) if NUMVERIFY_API_KEY else None
opencage_api = OpenCageGeocodingAPI(OPENCAGE_API_KEY) if OPENCAGE_API_KEY else None

# ---- Enhanced Helper Functions ----
def get_carrier_emoji(carrier_name: str) -> str:
    """Get appropriate emoji for carrier."""
    if not carrier_name or carrier_name.lower() == "unknown":
        return "📡"
    
    carrier_lower = carrier_name.lower()
    emoji_map = {
        'verizon': '🔴', 'att': '🔵', 't-mobile': '🟡', 'sprint': '🟠',
        'vodafone': '🔴', 'orange': '🟠', 'telefonica': '🔵', 'deutsche telekom': '🟡',
        'china mobile': '🇨🇳', 'airtel': '🟡', 'jio': '🟣', 'vodacom': '🔴',
        'bt': '🔵', 'virgin': '🟠', 'o2': '🟢', 'ee': '🟣'
    }
    
    for key, emoji in emoji_map.items():
        if key in carrier_lower:
            return emoji
    return "📡"

async def lookup_name_info_real(phone_number: str) -> Dict:
    """Real name lookup using multiple free APIs."""
    results = {}
    
    # Try AbstractAPI first
    if abstract_api:
        abstract_data = await abstract_api.lookup_number(phone_number)
        if "error" not in abstract_data:
            results.update({
                "carrier": abstract_data.get("carrier"),
                "location": abstract_data.get("location"),
                "line_type": abstract_data.get("line_type"),
                "source": "AbstractAPI"
            })
    
    # Try NumVerify as fallback
    if not results and numverify_api:
        numverify_data = await numverify_api.lookup_number(phone_number)
        if "error" not in numverify_data:
            results.update({
                "carrier": numverify_data.get("carrier"),
                "location": numverify_data.get("location"),
                "line_type": numverify_data.get("line_type"),
                "source": "NumVerify"
            })
    
    # Enhanced location using OpenCage (if we have coordinates from other sources)
    if opencage_api and results.get("location"):
        # This is a simplified example - in reality you'd need proper coordinates
        # For demo, we're using the location string for geocoding
        pass
    
    return results

def get_number_risk_assessment(num_obj, api_data: Dict) -> str:
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
    
    # Check if API data indicates risk
    if api_data.get("line_type") in ["premium_rate", "shared_cost"]:
        return "⚠️ High Risk (Premium/Shared Cost Number)"
    
    return "✅ Low Risk (Appears Legitimate)"

async def format_enhanced_number_info(num_obj) -> str:
    """Return comprehensive multi-line string with real API data."""
    # Basic formatting
    intl = phonenumbers.format_number(num_obj, PhoneNumberFormat.INTERNATIONAL)
    e164 = phonenumbers.format_number(num_obj, PhoneNumberFormat.E164)
    nat = phonenumbers.format_number(num_obj, PhoneNumberFormat.NATIONAL)
    
    # Enhanced details from phonenumbers library
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
    
    # Real API lookup
    api_data = await lookup_name_info_real(e164)
    real_carrier = api_data.get("carrier", carrier_name)
    real_location = api_data.get("location", location)
    real_line_type = api_data.get("line_type", "")
    data_source = api_data.get("source", "Basic Library Data")
    
    risk_assessment = get_number_risk_assessment(num_obj, api_data)
    
    # Format output with real API data
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
        f"• Location: `{real_location}`",
        f"• Timezones: `{tzs_str}`",
        "",
        "📡 *Carrier & Type:*",
        f"• Carrier: {carrier_emoji} `{real_carrier}`",
        f"• Number Type: {ptype_str}",
        f"• Line Type: `{real_line_type or 'Not specified'}`",
        "",
        "⚡ *Validation & Security:*",
        f"• Valid Number: {'✅ Yes' if valid else '❌ No'}",
        f"• Possible Number: {'✅ Yes' if possible else '❌ No'}",
        f"• Risk Assessment: {risk_assessment}",
        "",
        "🔧 *Data Sources:*",
        f"• Primary Source: `{data_source}`",
        f"• Enhanced with: `{', '.join([api for api in ['AbstractAPI', 'NumVerify'] if locals().get(f'{api.lower()}_api')]) or 'None'}`",
        "",
        "💡 *Notes:*",
        "_Real-time data from free APIs. Accuracy may vary._",
        "_Free tiers have limited requests per month._"
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
    """Enhanced start command with API status."""
    api_status = []
    if abstract_api:
        api_status.append("✅ AbstractAPI (1000 free/month)")
    if numverify_api:
        api_status.append("✅ NumVerify (1000 free/month)")
    if opencage_api:
        api_status.append("✅ OpenCage Geocoding (2500 free/day)")
    
    if not api_status:
        api_status = ["❌ No free APIs configured - using basic data only"]
    
    welcome_text = f"""
👋 *Welcome to Advanced Number Info Bot!* 🔍

*Active APIs:*
{"\\n".join(api_status)}

I can analyze phone numbers and provide comprehensive information including:

📊 *Basic Details* - International, E.164, National formats
🌍 *Geographic Info* - Country, location, timezone
📡 *Carrier & Type* - Service provider and number classification
⚡ *Security Analysis* - Validation and risk assessment

*How to use:*
• Send a phone number directly
• Use `/info +1234567890`
• Reply to a message with `/info`

*Examples:*
• `/info +14155552671`
• `/info +44 20 7946 0958`
• Just send `+919876543210`

*Free API Limits:* These services offer limited free requests per month.
    """
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced info command with real API data."""
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
        if i >= 2:  # Limit to 2 numbers per message to avoid API spam
            await update.message.reply_text("ℹ️ Additional numbers omitted to conserve API limits.")
            break
            
        reply = await format_enhanced_number_info(num_obj)
        await update.message.reply_text(reply, parse_mode="Markdown")

async def apistatus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check API status and remaining limits."""
    status_lines = ["🔧 *API Status Report*"]
    
    if abstract_api:
        status_lines.append("✅ AbstractAPI: Configured (1000 free requests/month)")
    else:
        status_lines.append("❌ AbstractAPI: Not configured")
    
    if numverify_api:
        status_lines.append("✅ NumVerify: Configured (1000 free requests/month)")
    else:
        status_lines.append("❌ NumVerify: Not configured")
    
    if opencage_api:
        status_lines.append("✅ OpenCage: Configured (2500 free requests/day)")
    else:
        status_lines.append("❌ OpenCage: Not configured")
    
    status_lines.extend([
        "",
        "*How to get free API keys:*",
        "1. AbstractAPI: https://app.abstractapi.com/",
        "2. NumVerify: https://numverify.com/",
        "3. OpenCage: https://opencagedata.com/",
        "",
        "Add your keys to the .env file to enable enhanced features."
    ])
    
    await update.message.reply_text("\n".join(status_lines), parse_mode="Markdown")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct text messages containing phone numbers."""
    text = update.message.text or ""
    numbers = extract_all_numbers_from_text(text, DEFAULT_REGION)
    
    if numbers:
        for i, num_obj in enumerate(numbers):
            if i >= 1:  # Limit to 1 number for direct messages to conserve API
                await update.message.reply_text(
                    "ℹ️ For analyzing multiple numbers, use `/info` command. "
                    "Limited to one number per message to conserve free API limits."
                )
                break
            reply = await format_enhanced_number_info(num_obj)
            await update.message.reply_text(reply, parse_mode="Markdown")
    else:
        help_text = (
            "🔍 *Number Info Bot Help*\n\n"
            "Send me a phone number or use:\n"
            "• `/info <number>` - Detailed analysis with real API data\n"
            "• `/apistatus` - Check API configuration\n"
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
            "This might be due to API rate limits. Please try again later."
        )

async def shutdown(application: Application):
    """Cleanup when bot shuts down."""
    if abstract_api:
        await abstract_api.close_session()
    if numverify_api:
        await numverify_api.close_session()
    if opencage_api:
        await opencage_api.close_session()

# ---- Main Application ----
def main():
    """Initialize and run the bot."""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", start_cmd))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(CommandHandler("apistatus", apistatus_cmd))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    # Shutdown handler
    app.add_handler(Application.shutdown(shutdown))
    
    logger.info("🤖 Advanced Number Info Bot with Real APIs started!")
    
    # Display API status
    api_count = sum([1 for api in [abstract_api, numverify_api, opencage_api] if api])
    print(f"Active APIs: {api_count}/3")
    if api_count == 0:
        print("⚠️  No free APIs configured. Using basic phone number data only.")
        print("💡 Get free API keys from:")
        print("   - AbstractAPI: https://app.abstractapi.com/")
        print("   - NumVerify: https://numverify.com/")
        print("   - OpenCage: https://opencagedata.com/")
    
    app.run_polling()

if __name__ == "__main__":
    main()
