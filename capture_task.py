# capture_task.py
# --- Modified for MetaTrader 5 API ---
import os
import sys
import json
import time
from datetime import datetime
import io

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
#  Load Configuration from .env file
# ==============================================================================
load_dotenv()

# Gemini and Window Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TARGET_WINDOW_TITLE = os.getenv("TARGET_WINDOW_TITLE")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PROMPT_TEMPLATE = os.getenv("PROMPT_TEMPLATE")
# ==============================================================================

def get_price_from_mt5() -> float | None:
    """
    Fetches the latest price for XAUUSD directly from the MetaTrader 5 terminal.
    """
    if not mt5:
        print(f"[{datetime.now()}] ❌ ERROR: MetaTrader5 library is not available.", file=sys.stderr)
        return None

    print(f"[{datetime.now()}] 📈 Connecting to MetaTrader 5 terminal...")
    
    if not mt5.initialize():
        print(f"[{datetime.now()}] ❌ ERROR: initialize() failed, error code = {mt5.last_error()}", file=sys.stderr)
        print(f"[{datetime.now()}] 💡 Please ensure the MetaTrader 5 terminal is running and logged in.", file=sys.stderr)
        return None

    try:
        symbol = "XAUUSD"
        tick = mt5.symbol_info_tick(symbol)
        mt5.shutdown() 

        if tick is None:
            print(f"[{datetime.now()}] ❌ ERROR: Could not fetch tick for {symbol}.", file=sys.stderr)
            print(f"[{datetime.now()}] 💡 Please ensure '{symbol}' is visible in your MT5 Market Watch.", file=sys.stderr)
            return None
        
        price = tick.ask
        print(f"[{datetime.now()}] ✅ Price from MT5 for {symbol}: ${price:.3f}")
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
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
        
        img_byte_arr = io.BytesIO()
        image_object.save(img_byte_arr, format='PNG')
        image_part = {"mime_type": "image/png", "data": img_byte_arr.getvalue()}
        
        response = model.generate_content([text_prompt, image_part])
        print(f"[{datetime.now()}] ✅ Analysis successful!")
        return response.text
    except Exception as e:
        print(f"[{datetime.now()}] ❌ ERROR with Gemini API: {e}", file=sys.stderr)
        return None
        
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

    live_price = get_price_from_mt5()
    if not live_price:
        print(f"[{datetime.now()}] ❌ ABORTING TASK: Could not get live price from MT5.", file=sys.stderr)
        return

    captured_image = capture_specific_window(TARGET_WINDOW_TITLE)
    if not captured_image:
        print(f"[{datetime.now()}] ❌ ABORTING TASK: Screen capture failed.", file=sys.stderr)
        return

    initial_analysis = analyze_image_with_gemini(GEMINI_API_KEY, captured_image, PROMPT_TEMPLATE)
    if not initial_analysis:
        print(f"[{datetime.now()}] ❌ ABORTING TASK: Gemini analysis failed.", file=sys.stderr)
        return

    try:
        clean_json = initial_analysis.strip().replace("```json", "").replace("```", "")
        trade_decision = json.loads(clean_json)
        
        # Print what Gemini returned for debugging
        print(f"[{datetime.now()}] 🔍 Full response: {clean_json}")
        
        # Use Gemini's response directly but standardize the format
        action = trade_decision.get("action") or trade_decision.get("direction") or trade_decision.get("order_type", "")
        action = action.upper().strip() if action else ""
        
        # Different JSON format for market orders (BUY/SELL) vs pending orders
        if action in ["BUY", "SELL"]:
            # Market orders - include sl/tp but no price
            final_result = {
                "symbol": trade_decision.get("symbol", "XAUUSD"),
                "action": action.lower(),  # lowercase for market orders
                "volume": str(trade_decision.get("volume") or trade_decision.get("vol", "0.01")),
                "sl": trade_decision.get("sl") or trade_decision.get("stop_loss"),
                "tp": trade_decision.get("tp") or trade_decision.get("take_profit")
            }
        else:
            # Full format for pending orders (LIMIT/STOP) - include price, sl, tp
            final_result = {
                "symbol": trade_decision.get("symbol", "XAUUSD"),
                "action": action,
                "volume": str(trade_decision.get("volume") or trade_decision.get("vol", "0.01")),
                "price": trade_decision.get("price") or trade_decision.get("entry_price"),
                "sl": trade_decision.get("sl") or trade_decision.get("stop_loss"),
                "tp": trade_decision.get("tp") or trade_decision.get("take_profit")
            }
            
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[{datetime.now()}] ❌ ERROR processing Gemini's response: {e}", file=sys.stderr)
        print(f"[{datetime.now()}] 🔍 Raw response: {initial_analysis}", file=sys.stderr)
        # Return raw response if JSON parsing fails
        final_result = {
            "error": "Failed to parse Gemini response",
            "raw_response": initial_analysis,
            "current_price": live_price
        }

    # Always output the full result from Gemini
    final_result_json = json.dumps(final_result, indent=4)
    print(f"\n[{datetime.now()}] --- 📊 FULL GEMINI RESPONSE ---")
    print(final_result_json)

    send_webhook(WEBHOOK_URL, final_result_json)
    
    print("\n" + "=" * 50)
    print(f"[{datetime.now()}] ✅ Task Completed Successfully!")
    print("=" * 50)

if __name__ == "__main__":
    main()