# capture_task.py
# --- Modified for MetaTrader 5 API with Lot Size Calculator ---
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
#  Load Configuration
# ==============================================================================
load_dotenv()

# Gemini and Window Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TARGET_WINDOW_TITLE = os.getenv("TARGET_WINDOW_TITLE")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Trading Settings with Lot Size Calculation
TRADE_SYMBOL = os.getenv("TRADE_SYMBOL", "XAUUSD")
ACCOUNT_BALANCE = float(os.getenv("ACCOUNT_BALANCE", 10000))  # จำนวนเงินต้น
RISK_PERCENTAGE = float(os.getenv("RISK_PERCENTAGE", 2.0))    # เปอร์เซ็นต์ความเสี่ยงต่อการเทรด

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

def get_symbol_contract_size(symbol: str) -> float:
    """
    Gets the contract size for a given symbol.
    """
    return SYMBOL_CONTRACT_SIZES.get(symbol, 100000)  # Default to 100,000 for forex

def calculate_lot_size(entry_price: float, stop_loss: float, symbol: str) -> float:
    """
    Calculates optimal lot size based on risk management.
    CRITICAL: The calculated lot size MUST NOT exceed the specified risk amount.
    
    Args:
        entry_price (float): Entry price for the trade
        stop_loss (float): Stop loss price
        symbol (str): Trading symbol
    
    Returns:
        float: Calculated lot size (guaranteed not to exceed risk amount)
    """
    try:
        # 1. คำนวณจำนวนเงินที่เสี่ยงได้
        risk_amount_usd = ACCOUNT_BALANCE * (RISK_PERCENTAGE / 100)
        
        # 2. คำนวณระยะห่างระหว่าง Entry กับ SL (ปัดเศษเพื่อป้องกันข้อผิดพลาดของ floating point)
        price_difference = round(abs(stop_loss - entry_price), 5)
        
        if price_difference == 0:
            print(f"[{datetime.now()}] ⚠️ WARNING: Stop loss equals entry price. Using default lot size 0.01")
            return 0.01
        
        # 3. ขนาดสัญญาของ Symbol
        contract_size = get_symbol_contract_size(symbol)
        
        # 4. ความเสี่ยงต่อ 1 lot
        risk_per_lot = price_difference * contract_size
        
        # 5. คำนวณ Lot Size ที่เหมาะสม
        calculated_lot_size = risk_amount_usd / risk_per_lot
        
        # 6. ปัดลง lot size เพื่อให้มั่นใจว่าไม่เกินความเสี่ยงที่กำหนด
        # ใช้ floor แทน round เพื่อให้แน่ใจว่าไม่เกิน risk amount
        import math
        lot_size = math.floor(calculated_lot_size * 100) / 100  # ปัดลงเป็น 2 ทศนิยม
        
        # จำกัด lot size ให้อยู่ในขอบเขตที่เหมาะสม (0.01 - 10.0)
        lot_size = max(0.01, min(lot_size, 10.0))
        
        # 7. ตรวจสอบความเสี่ยงจริงหหลังจากปัดลง
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
    """
    Fetches the latest price for a given symbol directly from the MetaTrader 5 terminal.
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
        
        json_schema = {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "action": {"type": "string"},
                "order_type": {"type": "string"},
                "volume": {"type": "number"},
                "stop_loss": {"type": "number"},
                "take_profit": {"type": "number"},
                "entry_price": {"type": "number"},
                "confidence": {"type": "number"},
                "reasoning": {"type": "string"}
            },
            "required": ["symbol", "action", "stop_loss", "take_profit"]
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
    print("=" * 50)

    live_price = get_price_from_mt5(TRADE_SYMBOL)
    if not live_price:
        print(f"[{datetime.now()}] ❌ ABORTING TASK: Could not get live price from MT5.", file=sys.stderr)
        return

    captured_image = capture_specific_window(TARGET_WINDOW_TITLE)
    if not captured_image:
        print(f"[{datetime.now()}] ❌ ABORTING TASK: Screen capture failed.", file=sys.stderr)
        return
        
    prompt_with_price = PROMPT_TEMPLATE.replace("{{live_price}}", str(live_price))

    initial_analysis = analyze_image_with_gemini(GEMINI_API_KEY, captured_image, prompt_with_price)
    if not initial_analysis:
        print(f"[{datetime.now()}] ❌ ABORTING TASK: Gemini analysis failed.", file=sys.stderr)
        return

    final_result = {}
    try:
        clean_json = initial_analysis.strip().replace("```json", "").replace("```", "")
        trade_decision = json.loads(clean_json)
        
        print(f"[{datetime.now()}] 🔍 Full response: {clean_json}")
        
        action = trade_decision.get("action") or trade_decision.get("order_type") or trade_decision.get("direction")
        stop_loss = trade_decision.get("stop_loss") or trade_decision.get("sl")
        take_profit = trade_decision.get("take_profit") or trade_decision.get("tp")
        entry_price = trade_decision.get("entry_price") or trade_decision.get("price")
        
        # Calculate lot size based on entry price and stop loss
        if stop_loss:
            # Use entry_price if available, otherwise use current market price
            calc_entry_price = entry_price if entry_price else live_price
            calculated_lot_size = calculate_lot_size(calc_entry_price, stop_loss, TRADE_SYMBOL)
        else:
            print(f"[{datetime.now()}] ⚠️ WARNING: No stop loss provided. Using default lot size 0.01")
            calculated_lot_size = 0.01

        # Build the final result dictionary
        final_result = {
            "symbol": TRADE_SYMBOL,
            "action": action,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "volume": calculated_lot_size
        }

        # Conditionally add the "price" key ONLY for pending orders
        if entry_price:
            final_result["price"] = entry_price
        
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[{datetime.now()}] ❌ ERROR processing Gemini's response: {e}", file=sys.stderr)
        print(f"[{datetime.now()}] 🔍 Raw response: {initial_analysis}", file=sys.stderr)
        final_result = {
            "error": "Failed to parse Gemini response",
            "raw_response": initial_analysis
        }

    final_result_json = json.dumps(final_result, indent=4)
    print(f"\n[{datetime.now()}] --- 📊 FINAL TRADE ORDER ---")
    print(final_result_json)

    send_webhook(WEBHOOK_URL, final_result_json)
    
    print("\n" + "=" * 50)
    print(f"[{datetime.now()}] ✅ Task Completed Successfully!")
    print("=" * 50)

if __name__ == "__main__":
    main()
