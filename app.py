# app.py
import streamlit as st
from PIL import Image, ImageStat
import google.generativeai as genai
import io
import pyautogui
import pygetwindow as gw
import requests
import json
import platform
import time

# --- Page Configuration ---
st.set_page_config(page_title="Cortana AI", layout="wide")
st.title("Cortana AI")
st.caption("Jay's Personal Assistant")

# --- Core Functions ---

def get_window_titles():
    """Gets titles of all non-minimized windows and filters out empty ones."""
    if platform.system() != "Windows":
        return ["Window capture only available on Windows"]
    try:
        # Filter out windows with no title or that are minimized
        return [
            title for title in gw.getAllTitles() 
            if title and not gw.getWindowsWithTitle(title)[0].isMinimized
        ]
    except Exception:
        return []

def is_image_blank(image: Image.Image, threshold=10) -> bool:
    """Check if an image is mostly a single solid color (like black)."""
    # Get the min and max pixel values for each band (R, G, B)
    extrema = image.getextrema()
    for i in range(len(extrema)):
        # If the difference between max and min is large, it's not a blank image
        if extrema[i][1] - extrema[i][0] > threshold:
            return False
    return True

def capture_specific_window(window_title: str) -> Image.Image | None:
    """Captures a screenshot of a specific window by its title."""
    if platform.system() != "Windows":
        st.error("Automated window capture is optimized for Windows only.")
        return None
    
    try:
        # Find the window
        windows = gw.getWindowsWithTitle(window_title)
        if not windows:
            st.error(f"No window with title '{window_title}' found.")
            return None
        
        target_window = windows[0]
        st.info(f"Found window: {target_window.title}")
        
        # Check if window is minimized and restore it
        if target_window.isMinimized:
            st.info("Window is minimized, restoring...")
            target_window.restore()
            time.sleep(0.5)  # Wait for restore animation
        
        # Activate the window
        st.info("Activating window...")
        target_window.activate()
        time.sleep(0.5)  # Wait for the window to become active
        
        # Get window coordinates
        left = target_window.left
        top = target_window.top
        width = target_window.width
        height = target_window.height
        
        st.info(f"Window coordinates: left={left}, top={top}, width={width}, height={height}")
        
        # Validate window dimensions
        if width <= 0 or height <= 0:
            st.error(f"Invalid window dimensions: {width}x{height}")
            return None
        
        # Ensure coordinates are valid (not negative and within screen bounds)
        if left < 0:
            width += left
            left = 0
        if top < 0:
            height += top
            top = 0
            
        if width <= 0 or height <= 0:
            st.error("Window is outside visible screen area")
            return None
        
        st.info(f"Taking screenshot with region: ({left}, {top}, {width}, {height})")
        
        # Disable PyAutoGUI fail-safe temporarily
        pyautogui.FAILSAFE = False
        
        # Capture the screenshot
        screenshot = pyautogui.screenshot(region=(left, top, width, height))
        
        # Re-enable fail-safe
        pyautogui.FAILSAFE = True
        
        # Validate the captured image
        if screenshot is None:
            st.error("Screenshot capture returned None")
            return None
        
        st.success(f"Screenshot captured successfully: {screenshot.size}")
        return screenshot
        
    except Exception as e:
        # Re-enable fail-safe in case of error
        pyautogui.FAILSAFE = True
        
        # More detailed error information
        error_msg = str(e)
        error_type = type(e).__name__
        
        st.error(f"Error during screen capture ({error_type}): {error_msg}")
        
        # If it's a Windows error, try to provide more context
        if "Error code from Windows" in error_msg and "0" in error_msg:
            st.info("Windows reports success but screenshot failed. This might be due to:")
            st.info("1. Hardware acceleration in the target application")
            st.info("2. Protected content (DRM)")
            st.info("3. Fullscreen exclusive applications")
            st.info("4. Windows display scaling issues")
            
            # Try a full screen capture as fallback
            st.info("Attempting full screen capture as fallback...")
            try:
                full_screenshot = pyautogui.screenshot()
                if full_screenshot:
                    st.info("Full screen capture successful - the issue is with window-specific capture")
                    return full_screenshot
            except:
                pass
        
        return None

def analyze_image_with_gemini(api_key: str, image_object: Image.Image, text_prompt: str):
    """Sends an image and a prompt to the Gemini API for analysis."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        img_byte_arr = io.BytesIO()
        image_object.save(img_byte_arr, format='PNG')
        image_part = {"mime_type": "image/png", "data": img_byte_arr.getvalue()}
        
        response = model.generate_content([image_part, text_prompt])
        return response.text
    except Exception as e:
        st.error(f"Error with Gemini API: {e}")
        return None

def send_webhook(webhook_url: str, data: str):
    """Sends the analysis result to a specified webhook URL."""
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        payload = {"text": data}

    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        st.success(f"Webhook sent successfully to {webhook_url}!")
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to send webhook: {e}")

# --- Streamlit UI ---

with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Gemini API Key", type="password", help="Enter your Google Gemini API key.")
    
    st.header("🎯 Target Window")
    # New dropdown for window selection
    window_options = get_window_titles()
    selected_window = st.selectbox(
        "Select the window to capture",
        options=window_options,
        help="Choose the application window you want to analyze."
    )
    st.button("Refresh Window List", on_click=st.rerun, use_container_width=True)
    
    st.header("⚙️ Advanced")
    webhook_url = st.text_input("Webhook URL", "", help="Optional: URL to send the analysis results to.")
    prompt_template = st.text_area(
        "Analysis Prompt",
        "Extract all visible text from this screenshot. If there are key-value pairs, format them as a JSON object.",
        height=150,
        help="Customize the prompt to guide Gemini's analysis of the image."
    )

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Welcome! Select a window from the sidebar, then type `/capture` to begin."}
    ]

# Display past messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if "image" in message:
            st.image(message["image"], caption=message.get("caption", "Captured Screenshot"), width=400)
        if "content" in message:
            st.markdown(message["content"])

# Handle user input
if prompt := st.chat_input("Type '/capture' to begin..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Main logic for the '/capture' command
    if prompt.strip().lower() == "/capture":
        if not api_key:
            st.warning("Please enter your Gemini API Key in the sidebar to proceed.")
        elif not selected_window or selected_window == "Window capture only available on Windows":
            st.warning("Please select a valid window from the sidebar.")
        else:
            with st.chat_message("assistant"):
                with st.spinner(f"Capturing '{selected_window}' and analyzing..."):
                    captured_image = capture_specific_window(selected_window)
                    
                    if captured_image:
                        # Check if the image is blank
                        if is_image_blank(captured_image):
                            error_message = (
                                "⚠️ **Capture Resulted in a Black Screen!**\n\n"
                                "This usually happens when the target application (like a web browser) "
                                "has **Hardware Acceleration** turned on.\n\n"
                                "**To fix this:**\n"
                                "1. Go to your application's settings (e.g., Chrome, Opera, Edge).\n"
                                "2. Find the 'System' section.\n"
                                "3. Turn **OFF** 'Use hardware acceleration when available'.\n"
                                "4. **Relaunch** the application and try again."
                            )
                            st.error(error_message)
                            st.session_state.messages.append({"role": "assistant", "content": error_message})
                        else:
                            # Display and store the valid image
                            st.image(captured_image, caption=f"Captured: {selected_window}", width=400)
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "image": captured_image, 
                                "caption": f"Captured: {selected_window}"
                            })

                            # Analyze the image
                            analysis_result = analyze_image_with_gemini(api_key, captured_image, prompt_template)
                            if analysis_result:
                                st.markdown(analysis_result)
                                st.session_state.messages.append({"role": "assistant", "content": analysis_result})
                                
                                # Send to webhook if URL is provided
                                if webhook_url:
                                    send_webhook(webhook_url, analysis_result)
                    else:
                        st.error("Failed to capture the selected window. Please try again.")
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": "Failed to capture the selected window. Please try again."
                        })