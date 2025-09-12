# capture_task.py
# --- Modified for MetaTrader 5 API with Lot Size Calculator and Email Alerts ---
import os
import sys
import json
import time
from datetime import datetime
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Third-party libraries
import google.generativeai as genai
import pygetwindow as gw
import requests
import mss
from dotenv import load_dotenv
from PIL import Image

# Broker API Library (MetaTrader 5)
try:
    import MetaTrader5 as mt5
except ImportError:
    print("FATAL ERROR: MetaTrader5 is not installed. Please run 'pip install MetaTrader5'")
    mt5 = None

# ==============================================================================
#  Load Configuration
# ==============================================================================
load_dotenv()

# Gemini and Window Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TARGET_WINDOW_TITLE = os.getenv("TARGET_WINDOW_TITLE")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Trading Settings with Lot Size Calculation
TRADE_SYMBOL = os.getenv("TRADE_SYMBOL", "XAUUSD")
ACCOUNT_BALANCE = float(os.getenv("ACCOUNT_BALANCE", 10000))
RISK_PERCENTAGE = float(os.getenv("RISK_PERCENTAGE", 2.0))

# Email Configuration
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

# Contract sizes for different symbols (oz, shares, etc.)
SYMBOL_CONTRACT_SIZES = {
    "XAUUSD": 100,    # Gold: 100 oz per lot
    "XAGUSD": 5000,   # Silver: 5000 oz per lot
    "EURUSD": 100000, # Forex: 100,000 units per lot
    "GBPUSD": 100000,
    "USDJPY": 100000,
    "AUDUSD": 100000,
    "USDCAD": 100000,
    "USDCHF": 100000,
    "NZDUSD": 100000,
    # Add more symbols as needed
}

# Load the prompt from a separate file to avoid parsing errors in .env
try:
    with open("prompt.txt", "r", encoding="utf-8") as f:
        PROMPT_TEMPLATE = f.read()
except FileNotFoundError:
    print("FATAL ERROR: prompt.txt not found. Please create it in the same directory.", file=sys.stderr)
    sys.exit(1) # Exit the script if prompt is missing

# ==============================================================================
#  Email Functions
# ==============================================================================

def send_email_alert(subject: str, body: str, trade_data: dict = None, is_error: bool = False):
    """
    Sends a simplified email alert with only essential details for both success and error messages.
    
    Args:
        subject (str): Email subject
        body (str): Email body content
        trade_data (dict): Trading data to include in email
        is_error (bool): Whether this is an error notification
    """
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECIPIENT:
        print(f"[{datetime.now()}] ⚠️ Email configuration incomplete. Skipping email alert.")
        return False
    
    try:
        print(f"[{datetime.now()}] 📧 Sending email alert...")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECIPIENT
        msg['Subject'] = subject
        
        # For both success and error emails, send only the simple text format
        html_body = f"""
        <html>
        <head></head>
        <body>
            <pre style="font-family: 'Courier New', monospace; font-size: 14px; line-height: 1.4;">{body}</pre>
        </body>
        </html>
        """
        
        # Attach HTML body
        msg.attach(MIMEText(html_body, 'html'))
        
        # Connect to server and send email
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()  # Enable encryption
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, text)
        server.quit()
        
        print(f"[{datetime.now()}] ✅ Email alert sent successfully to {EMAIL_RECIPIENT}")
        return True
        
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to send email alert: {e}", file=sys.stderr)
        return False

# ==============================================================================
#  Core Trading Functions
# ==============================================================================

def get_symbol_contract_size(symbol: str) -> float:
    """Gets the contract size for a given symbol."""
    return SYMBOL_CONTRACT_SIZES.get(symbol, 100000)  # Default to 100,000 for forex

def calculate_lot_size(entry_price: float, stop_loss: float, symbol: str) -> float:
    """
    Calculates optimal lot size based on risk management.
    CRITICAL: The calculated lot size MUST NOT exceed the specified risk amount.
    """
    try:
        # 1. Calculate risk amount
        risk_amount_usd = ACCOUNT_BALANCE * (RISK_PERCENTAGE / 100)
        
        # 2. Calculate price difference (rounded to prevent floating point errors)
        price_difference = round(abs(stop_loss - entry_price), 5)
        
        if price_difference == 0:
            print(f"[{datetime.now()}] ⚠️ WARNING: Stop loss equals entry price. Using default lot size 0.01")
            return 0.01
        
        # 3. Get symbol contract size
        contract_size = get_symbol_contract_size(symbol)
        
        # 4. Calculate risk per lot
        risk_per_lot = price_difference * contract_size
        
        # 5. Calculate optimal lot size
        calculated_lot_size = risk_amount_usd / risk_per_lot
        
        # 6. Floor the lot size to ensure we don't exceed risk amount
        import math
        lot_size = math.floor(calculated_lot_size * 100) / 100  # Round down to 2 decimals
        
        # 7. Ensure lot size is within reasonable bounds (0.01 - 10.0)
        lot_size = max(0.01, min(lot_size, 10.0))
        
        # 8. Verify actual risk after flooring
        actual_risk = lot_size * risk_per_lot
        risk_check = "✅ SAFE" if actual_risk <= risk_amount_usd else "❌ EXCEEDS LIMIT"
        
        print(f"[{datetime.now()}] 📊 LOT SIZE CALCULATION:")
        print(f"  Symbol: {symbol}")
        print(f"  Account Balance: ${ACCOUNT_BALANCE:,.2f}")
        print(f"  Risk Percentage: {RISK_PERCENTAGE}%")
        print(f"  Max Risk Amount: ${risk_amount_usd:.2f}")
        print(f"  Entry Price: {entry_price}")
        print(f"  Stop Loss: {stop_loss}")
        print(f"  Price Difference: {price_difference}")
        print(f"  Contract Size: {contract_size}")
        print(f"  Risk per Lot: ${risk_per_lot:.2f}")
        print(f"  Raw Calculation: {calculated_lot_size:.4f}")
        print(f"  Final Lot Size: {lot_size}")
        print(f"  Actual Risk: ${actual_risk:.2f} ({risk_check})")
        print(f"  Risk Safety Margin: ${risk_amount_usd - actual_risk:.2f}")
        
        return lot_size
        
    except Exception as e:
        print(f"[{datetime.now()}] ❌ ERROR calculating lot size: {e}", file=sys.stderr)
        return 0.01  # Return minimum lot size as fallback

def get_price_from_mt5(symbol: str) -> float | None:
    """Fetches the latest price for a given symbol directly from the MetaTrader 5 terminal."""
    if not mt5:
        print(f"[{datetime.now()}] ❌ ERROR: MetaTrader5 library is not available.", file=sys.stderr)
        return None

    print(f"[{datetime.now()}] 📈 Connecting to MetaTrader 5 terminal...")
    
    if not mt5.initialize():
        print(f"[{datetime.now()}] ❌ ERROR: initialize() failed, error code = {mt5.last_error()}", file=sys.stderr)
        print(f"[{datetime.now()}] 💡 Please ensure the MetaTrader 5 terminal is running and logged in.", file=sys.stderr)
        return None

    try:
        tick = mt5.symbol_info_tick(symbol)
        mt5.shutdown() 

        if tick is None:
            print(f"[{datetime.now()}] ❌ ERROR: Could not fetch tick for {symbol}.", file=sys.stderr)
            print(f"[{datetime.now()}] 💡 Please ensure '{symbol}' is visible in your MT5 Market Watch.", file=sys.stderr)
            return None
        
        price = tick.ask
        print(f"[{datetime.now()}] ✅ Price from MT5 for {symbol}: ${price:.5f}")
        return price

    except Exception as e:
        print(f"[{datetime.now()}] ❌ ERROR fetching price from MT5: {e}", file=sys.stderr)
        mt5.shutdown()
        return None

def capture_specific_window(partial_title: str) -> Image.Image | None:
    """Finds and captures a specific window."""
    print(f"[{datetime.now()}] Searching for a window containing: '{partial_title}'...")
    try:
        target_window = next((w for w in gw.getAllWindows() if partial_title in w.title and w.visible), None)
        if not target_window:
            raise Exception(f"No visible window containing '{partial_title}' was found.")
        
        if target_window.isMinimized: target_window.restore()
        target_window.activate()
        time.sleep(0.5)

        with mss.mss() as sct:
            monitor = {"top": target_window.top, "left": target_window.left, "width": target_window.width, "height": target_window.height}
            sct_img = sct.grab(monitor)
        
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        print(f"[{datetime.now()}] Window '{target_window.title}' captured successfully!")
        return img
    except Exception as e:
        print(f"[{datetime.now()}] ❌ ERROR during screen capture: {e}", file=sys.stderr)
        return None

def analyze_image_with_gemini(api_key: str, image_object: Image.Image, text_prompt: str):
    """Sends image to Gemini for analysis."""
    print(f"[{datetime.now()}] Sending image to Gemini API for analysis...")
    try:
        genai.configure(api_key=api_key)
        
        # FIXED JSON SCHEMA - Removed unsupported 'minimum' and 'maximum' properties
        json_schema = {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "action": {"type": "string", "enum": ["BUY", "SELL", "BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"]},
                "order_type": {"type": "string", "enum": ["MARKET", "LIMIT", "STOP"]},
                "volume": {"type": "number"},
                "stop_loss": {"type": "number"},
                "take_profit": {"type": "number"},
                "entry_price": {
                    "type": "number",
                    "description": "MANDATORY: Entry price is REQUIRED for ALL orders. For market orders, use current market price. For pending orders (LIMIT/STOP), use the specific entry level."
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence level between 0 and 100"
                },
                "reasoning": {"type": "string"}
            },
            "required": ["symbol", "action", "entry_price", "stop_loss", "take_profit"],
            "description": "CRITICAL: entry_price field is MANDATORY and must ALWAYS be provided for every trade signal, regardless of order type."
        }
        
        model = genai.GenerativeModel(
            'gemini-1.5-flash', 
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": json_schema
            }
        )
        
        img_byte_arr = io.BytesIO()
        image_object.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        image_part = genai.types.BlobDict(
            mime_type="image/png",
            data=img_byte_arr.getvalue()
        )
        
        response = model.generate_content([text_prompt, image_part])
        print(f"[{datetime.now()}] ✅ Analysis successful!")
        return response.text
        
    except Exception as e:
        print(f"[{datetime.now()}] ❌ ERROR with Gemini API: {e}", file=sys.stderr)
        return None

def validate_and_fix_trade_data(trade_decision: dict, live_price: float) -> dict:
    """
    Validates trade data and ensures entry_price is always present.
    If entry_price is missing, it will be set based on order type.
    """
    print(f"[{datetime.now()}] 🔍 Validating trade data...")
    
    # Get action/order type
    action = trade_decision.get("action") or trade_decision.get("order_type") or trade_decision.get("direction")
    entry_price = trade_decision.get("entry_price") or trade_decision.get("price")
    
    # If entry_price is missing, calculate it based on action
    if not entry_price:
        print(f"[{datetime.now()}] ⚠️ WARNING: entry_price is missing! Attempting to fix...")
        
        if action in ["BUY", "SELL"]:
            # Market orders use current price
            entry_price = live_price
            print(f"[{datetime.now()}] 🔧 FIX: Set entry_price to current market price: {entry_price}")
        elif action in ["BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"]:
            # For pending orders, we can't guess the entry price - this is an error
            print(f"[{datetime.now()}] ❌ CRITICAL ERROR: Pending order {action} requires explicit entry_price!")
            print(f"[{datetime.now()}] 🔧 FALLBACK: Using current market price, but this may not be correct!")
            entry_price = live_price
        else:
            entry_price = live_price
            print(f"[{datetime.now()}] 🔧 FIX: Unknown action '{action}', using market price: {entry_price}")
        
        # Update the trade decision
        trade_decision["entry_price"] = entry_price
    
    print(f"[{datetime.now()}] ✅ Trade data validation complete!")
    return trade_decision
        
def send_webhook(webhook_url: str, data: str):
    if not webhook_url: return
    print(f"[{datetime.now()}] Sending data to webhook...")
    try:
        payload = json.loads(data)
        requests.post(webhook_url, json=payload, timeout=10)
        print(f"[{datetime.now()}] ✅ Webhook sent successfully!")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ ERROR sending webhook: {e}", file=sys.stderr)

def main():
    """Main function to orchestrate the trading task."""
    print("=" * 50)
    print(f"[{datetime.now()}] 🚀 Starting Visual Automation Trading Task (MT5 API Mode)")
    print("=" * 50)
    
    print(f"[{datetime.now()}] 📊 TRADING CONFIGURATION:")
    print(f"  Symbol: {TRADE_SYMBOL}")
    print(f"  Account Balance: ${ACCOUNT_BALANCE:,.2f}")
    print(f"  Risk Percentage: {RISK_PERCENTAGE}%")
    print(f"  Risk Amount: ${ACCOUNT_BALANCE * (RISK_PERCENTAGE / 100):,.2f}")
    
    # Check email configuration
    if EMAIL_SENDER and EMAIL_PASSWORD and EMAIL_RECIPIENT:
        print(f"  📧 Email Alerts: ENABLED ({EMAIL_RECIPIENT})")
    else:
        print(f"  📧 Email Alerts: DISABLED (missing configuration)")
    
    print("=" * 50)

    try:
        # Step 1: Get live price from MT5
        live_price = get_price_from_mt5(TRADE_SYMBOL)
        if not live_price:
            error_msg = "Could not get live price from MT5. Please ensure MT5 is running and symbol is available."
            print(f"[{datetime.now()}] ❌ ABORTING TASK: {error_msg}", file=sys.stderr)
            
            # Send error email
            send_email_alert(
                subject=f"🚨 MT5 Trading Bot ERROR - Price Feed Failed ({TRADE_SYMBOL})",
                body=f"Failed to retrieve live price data:\n\n{error_msg}\n\nPlease check:\n• MetaTrader 5 is running\n• You are logged into your account\n• {TRADE_SYMBOL} is in Market Watch\n• Internet connection is stable",
                is_error=True
            )
            return

        # Step 2: Capture trading window
        captured_image = capture_specific_window(TARGET_WINDOW_TITLE)
        if not captured_image:
            error_msg = f"Screen capture failed for window '{TARGET_WINDOW_TITLE}'."
            print(f"[{datetime.now()}] ❌ ABORTING TASK: {error_msg}", file=sys.stderr)
            
            # Send error email
            send_email_alert(
                subject=f"🚨 MT5 Trading Bot ERROR - Screen Capture Failed",
                body=f"Failed to capture trading window:\n\n{error_msg}\n\nPlease check:\n• Target window is open and visible\n• Window title matches configuration\n• No applications blocking screen capture",
                is_error=True
            )
            return
            
        # Step 3: Enhanced prompt with current price
        enhanced_prompt = f"""
{PROMPT_TEMPLATE}

CRITICAL REQUIREMENTS:
- You MUST provide "entry_price" field in EVERY response, without exception
- For MARKET orders (BUY/SELL): entry_price = current market price ({live_price})
- For PENDING orders (BUY_LIMIT/SELL_LIMIT/BUY_STOP/SELL_STOP): entry_price = your specified entry level
- The "entry_price" field is mandatory and must be a numeric value
- Current market price is: {live_price}
- Confidence should be between 0 and 100

Remember: entry_price is REQUIRED for risk management and lot size calculation!
"""
        
        # Step 4: Analyze image with Gemini
        initial_analysis = analyze_image_with_gemini(GEMINI_API_KEY, captured_image, enhanced_prompt)
        if not initial_analysis:
            error_msg = "Gemini AI analysis failed. Please check API key and internet connection."
            print(f"[{datetime.now()}] ❌ ABORTING TASK: {error_msg}", file=sys.stderr)
            
            # Send error email
            send_email_alert(
                subject=f"🚨 MT5 Trading Bot ERROR - AI Analysis Failed",
                body=f"Gemini AI analysis failed:\n\n{error_msg}\n\nPlease check:\n• Gemini API key is valid\n• API quota is not exceeded\n• Internet connection is stable\n• Image was captured successfully",
                is_error=True
            )
            return

        # Step 5: Process and validate trade decision
        final_result = {}
        try:
            clean_json = initial_analysis.strip().replace("```json", "").replace("```", "")
            trade_decision = json.loads(clean_json)
            
            print(f"[{datetime.now()}] 🔍 Raw Gemini response: {clean_json}")
            
            # VALIDATE AND FIX TRADE DATA
            trade_decision = validate_and_fix_trade_data(trade_decision, live_price)
            
            action = trade_decision.get("action") or trade_decision.get("order_type") or trade_decision.get("direction")
            stop_loss = trade_decision.get("stop_loss") or trade_decision.get("sl")
            take_profit = trade_decision.get("take_profit") or trade_decision.get("tp")
            entry_price = trade_decision.get("entry_price") or trade_decision.get("price")
            
            # Validate that we have entry_price
            if not entry_price:
                print(f"[{datetime.now()}] ❌ CRITICAL ERROR: entry_price is still missing after validation!")
                entry_price = live_price
                print(f"[{datetime.now()}] 🔧 EMERGENCY FALLBACK: Using market price {entry_price}")
            
            # Calculate lot size using entry price
            if stop_loss:
                calculated_lot_size = calculate_lot_size(entry_price, stop_loss, TRADE_SYMBOL)
            else:
                print(f"[{datetime.now()}] ⚠️ WARNING: No stop loss provided. Using default lot size 0.01")
                calculated_lot_size = 0.01

            # Build the final result dictionary
            final_result = {
                "symbol": TRADE_SYMBOL,
                "action": action,
                "entry_price": entry_price,  # ALWAYS include entry_price
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "volume": calculated_lot_size
            }

            # For backward compatibility, also add "price" field for pending orders
            if action and action in ["BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"]:
                final_result["price"] = entry_price
                
            # Add additional analysis data if available
            for key in ["confidence", "reasoning"]:
                if key in trade_decision:
                    final_result[key] = trade_decision[key]
            
        except (json.JSONDecodeError, ValueError) as e:
            error_msg = f"Failed to parse Gemini response: {e}"
            print(f"[{datetime.now()}] ❌ ERROR processing Gemini's response: {error_msg}", file=sys.stderr)
            print(f"[{datetime.now()}] 🔍 Raw response: {initial_analysis}", file=sys.stderr)
            
            final_result = {
                "error": "Failed to parse Gemini response",
                "raw_response": initial_analysis
            }
            
            # Send error email
            send_email_alert(
                subject=f"🚨 MT5 Trading Bot ERROR - Invalid AI Response",
                body=f"Failed to parse AI analysis result:\n\n{error_msg}\n\nRaw Response:\n{initial_analysis}\n\nThis might indicate:\n• Malformed JSON response\n• Missing required fields\n• API response format changes",
                is_error=True
            )
            return

        # Step 6: Display final results
        final_result_json = json.dumps(final_result, indent=4)
        print(f"\n[{datetime.now()}] --- 📊 FINAL TRADE ORDER ---")
        print(final_result_json)

        # Step 7: Send webhook
        send_webhook(WEBHOOK_URL, final_result_json)
        
        # Step 8: Send success email with simplified format
        if "error" not in final_result:
            success_msg = f"Trading analysis completed successfully!\n\nGenerated trade signal for {TRADE_SYMBOL}:\n• Action: {final_result.get('action', 'N/A')}\n• Entry: ${final_result.get('entry_price', 'N/A')}\n• Stop Loss: ${final_result.get('stop_loss', 'N/A')}\n• Take Profit: ${final_result.get('take_profit', 'N/A')}\n• Volume: {final_result.get('volume', 'N/A')} lots"
            
            if final_result.get("confidence"):
                success_msg += f"\n• Confidence: {final_result['confidence']}%"
            
            if final_result.get("reasoning"):
                success_msg += f"\n\nReasoning: {final_result['reasoning']}"
                
            send_email_alert(
                subject=f"✅ MT5 Trading Bot SUCCESS - Signal Generated ({TRADE_SYMBOL})",
                body=success_msg,
                trade_data=final_result,
                is_error=False
            )
        
        print("\n" + "=" * 50)
        print(f"[{datetime.now()}] ✅ Task Completed Successfully!")
        print("=" * 50)

    except Exception as e:
        # Catch-all error handler
        error_msg = f"Unexpected error in main execution: {str(e)}"
        print(f"[{datetime.now()}] ❌ CRITICAL ERROR: {error_msg}", file=sys.stderr)
        
        # Send critical error email
        send_email_alert(
            subject=f"🚨 MT5 Trading Bot CRITICAL ERROR - System Failure",
            body=f"A critical system error occurred:\n\n{error_msg}\n\nThis is an unexpected error that requires investigation. Please check:\n• System logs\n• Dependencies\n• Configuration files\n• System resources",
            is_error=True
        )

if __name__ == "__main__":
    main()
