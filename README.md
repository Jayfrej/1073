# MetaTrader 5 Visual Trading Automation

A powerful Python-based trading automation system that combines visual screen analysis with MetaTrader 5 API integration. The system captures trading charts, analyzes them using Google's Gemini AI, and executes trades automatically.

## 🏗️ System Architecture

```mermaid
graph TD
    %% Input Sources
    H[🌐 Streamlit UI] --> A
    I[⚙️ Batch Script] --> A
    
    %% Main Processing Flow
    A[📸 Screen Capture] --> B[🖼️ Image Processing]
    B --> C[🤖 Gemini AI Analysis]
    
    %% Data Sources
    D[💰 MT5 Price Feed] --> E[⚡ Decision Engine]
    C --> E
    
    %% Execution & Output
    E --> F[📈 Trade Execution]
    F --> G[📡 Webhook Notification]
    
    %% Styling
    classDef inputClass fill:#ff6b6b,stroke:#fff,stroke-width:2px,color:#fff
    classDef processClass fill:#4834d4,stroke:#fff,stroke-width:2px,color:#fff
    classDef aiClass fill:#00d2d3,stroke:#fff,stroke-width:2px,color:#fff
    classDef dataClass fill:#ff9ff3,stroke:#fff,stroke-width:2px,color:#fff
    classDef executeClass fill:#05c46b,stroke:#fff,stroke-width:2px,color:#fff
    classDef outputClass fill:#ffa502,stroke:#fff,stroke-width:2px,color:#fff
    classDef interfaceClass fill:#3742fa,stroke:#fff,stroke-width:2px,color:#fff
    
    class H,I interfaceClass
    class A inputClass
    class B processClass
    class C aiClass
    class D dataClass
    class E,F executeClass
    class G outputClass
```

## 🚀 Features

- **Visual Chart Analysis**: Captures specific trading windows and analyzes them with AI
- **MetaTrader 5 Integration**: Direct API connection for real-time price data and trade execution
- **AI-Powered Decisions**: Uses Google Gemini 1.5 Flash for intelligent trade analysis
- **Webhook Support**: Sends trading signals to external systems
- **Interactive Web Interface**: Streamlit-based GUI for manual testing and configuration
- **Automated Execution**: Batch file for scheduled or automated runs

## 📁 Project Structure

```
├── capture_task.py      # Main automation script (MT5 + AI analysis)
├── app.py              # Streamlit web interface
├── prompt.txt          # AI analysis prompt template
├── run_agent.bat       # Windows batch file for automation
├── requirements.txt    # Python dependencies
├── .env.example        # Environment configuration template
├── .env               # Environment configuration (create from .env.example)
└── README.md          # This file
```

## 🛠️ Installation

### Prerequisites

| Component | Requirement |
|-----------|-------------|
| Python | 3.8+ ([Download](https://www.python.org/downloads/)) |
| MetaTrader 5 | Installed and configured ([Download](https://www.metatrader5.com/en/download)) |
| Google Gemini | API key required ([Get API Key](https://makersuite.google.com/app/apikey)) |
| Operating System | Windows 10+ (recommended for window capture) |
| Broker Account | MT5 demo/live account with XAUUSD symbol |
| Internet | Stable connection for API calls and data feed |

### Step 1: Download and Setup

Extract the project files to:
```bash
C:\Users\User\Downloads\1073
```

Navigate to the project directory:
```bash
cd C:\Users\User\Downloads\1073
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Environment Configuration

Create environment file from template:

```bash
cd C:\Users\User\Downloads\1073
copy .env.example .env
```

Then edit the `.env` file with your settings:

```env
# Google Gemini AI API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Target window to capture (partial title match)
TARGET_WINDOW_TITLE=MetaTrader 5

# Trading Symbol and Volume
TRADE_SYMBOL=XAUUSD
TRADE_VOLUME=1.0

# Optional: Webhook URL for sending trade signals
WEBHOOK_URL=https://your-webhook-url.com/endpoint
```

### Step 4: MetaTrader 5 Setup

1. **Install MT5**: Download and install MetaTrader 5
2. **Login**: Connect to your broker account
3. **Enable API**: In MT5, go to `Tools > Options > Expert Advisors` and enable:
   - ✅ Allow automated trading
   - ✅ Allow DLL imports
   - ✅ Allow imports of external experts
4. **Add Symbol**: Ensure XAUUSD (Gold) is visible in Market Watch

## 🎮 Usage

### Method 1: Manual Execution

Run the main automation script:

```bash
cd C:\Users\User\Downloads\1073
python capture_task.py
```

Or use the Windows batch file:
```bash
cd C:\Users\User\Downloads\1073
run_agent.bat
```

### Method 2: Interactive Web Interface

Launch the Streamlit interface:

```bash
cd C:\Users\User\Downloads\1073
streamlit run app.py
```

Then:
1. Enter your Gemini API key in the sidebar
2. Select the MetaTrader 5 window from the dropdown
3. Type `/capture` in the chat to analyze the current chart

### Method 3: Automated Scheduling

Set up daily automated execution using Windows Task Scheduler.

#### Windows Task Scheduler

**Step 1: Open Task Scheduler**
- Press `Windows + R`, type `taskschd.msc`, press Enter
- Or search "Task Scheduler" in Start menu

**Step 2: Create Basic Task**
1. Click "Create Basic Task..." in the right panel
2. **Name**: `MT5 Trading Bot`
3. **Description**: `Daily automated trading analysis`
4. Click "Next"

**Step 3: Set Trigger**
1. Select "Daily"
2. Set your preferred time (e.g., 9:00 AM for market open)
3. **Recur every**: 1 days
4. Click "Next"

**Step 4: Set Action**
1. Select "Start a program"
2. **Program/script**: `C:\Users\User\Downloads\1073\run_agent.bat`
3. **Start in**: `C:\Users\User\Downloads\1073`
4. Click "Next" then "Finish"

**Step 5: Advanced Settings (Recommended)**
- Right-click your task → "Properties"
- **Security options**: ✅ "Run whether user is logged on or not"
- **Settings**: ✅ "Run task as soon as possible after a scheduled start is missed"
- **Conditions**: Uncheck "Start the task only if the computer is on AC power"

#### Multiple Daily Runs

For multiple analyses per day, create separate tasks for each time slot:
- Task 1: 9:00 AM (Market Open)
- Task 2: 12:00 PM (Midday)
- Task 3: 4:00 PM (Market Close)

#### Enhanced Logging for Scheduled Tasks

Create `run_agent_scheduled.bat` in `C:\Users\User\Downloads\1073\`:
```batch
@echo off
cd /d C:\Users\User\Downloads\1073

if not exist "logs" mkdir logs

echo [%date% %time%] Starting scheduled trading task... >> logs\schedule.log
python capture_task.py >> logs\output.log 2>> logs\errors.log
echo [%date% %time%] Task completed. >> logs\schedule.log
```

## 🔧 Configuration Options

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key for AI analysis | ✅ Yes |
| `TARGET_WINDOW_TITLE` | Partial window title to capture | ✅ Yes |
| `TRADE_SYMBOL` | Trading symbol (default: XAUUSD) | ✅ Yes |
| `TRADE_VOLUME` | Trade volume size | ✅ Yes |
| `WEBHOOK_URL` | URL to send trade signals | ❌ Optional |

### Prompt Template

The system uses `prompt.txt` file for AI analysis instructions. The current prompt focuses on:
- Multi-timeframe analysis (1h, 30m, 1m)
- Price action patterns
- Support and resistance levels
- Risk management with stop loss and take profit

## 📊 Output Format

The system outputs trading decisions in JSON format:

### Market Orders (BUY/SELL)
```json
{
    "symbol": "XAUUSD",
    "action": "BUY",
    "volume": 1.0,
    "stop_loss": 2650.50,
    "take_profit": 2680.00
}
```

### Pending Orders (LIMIT/STOP)
```json
{
    "symbol": "XAUUSD",
    "action": "SELL_LIMIT",
    "price": 2670.00,
    "volume": 1.0,
    "stop_loss": 2675.00,
    "take_profit": 2655.00
}
```

## 🐛 Troubleshooting

### Common Issues

**MetaTrader 5 Connection Failed**
- Ensure MT5 is running and logged in
- Check that automated trading is enabled
- Verify XAUUSD symbol is in Market Watch

**Screen Capture Returns Black Image**
- Disable hardware acceleration in your browser/MT5
- Run the script as administrator
- Check if window is minimized or behind other windows

**Gemini API Errors**
- Verify your API key is correct
- Check your API quota and billing
- Ensure stable internet connection

**Window Not Found**
- Update `TARGET_WINDOW_TITLE` to match your MT5 window title
- Use the Streamlit interface to see available windows
- Try partial window titles (e.g., "MetaTrader" instead of full title)

**Module Not Found Error**
```bash
cd C:\Users\User\Downloads\1073
pip install -r requirements.txt
```

### Debug Mode

Enable detailed logging by running:

```bash
cd C:\Users\User\Downloads\1073
python -c "import logging; logging.basicConfig(level=logging.DEBUG)" && python capture_task.py
```

## ⚠️ Risk Disclaimer

**IMPORTANT**: This is an automated trading system that can place real trades with real money.

- Always test on a demo account first
- Use appropriate position sizing
- Monitor the system regularly
- Understand that AI predictions are not guaranteed
- Past performance does not indicate future results
- Use proper risk management at all times

## 🔒 Security

- Store API keys in `.env` file (never commit to version control)
- Use webhook authentication if sending signals externally
- Regularly rotate API keys
- Monitor trading activity for unusual behavior

## 📝 Logging

The system provides detailed console logging:

```
[2025-01-15 10:30:15] 🚀 Starting Visual Automation Trading Task (MT5 API Mode)
[2025-01-15 10:30:16] 📈 Connecting to MetaTrader 5 terminal...
[2025-01-15 10:30:17] ✅ Price from MT5 for XAUUSD: $2665.430
[2025-01-15 10:30:18] Window 'MetaTrader 5' captured successfully!
[2025-01-15 10:30:20] ✅ Analysis successful!
[2025-01-15 10:30:21] ✅ Task Completed Successfully!
```

## 📞 Support

For issues and questions:
- Check the troubleshooting section above
- Review MetaTrader 5 API documentation
- Consult Google Gemini API documentation

---
