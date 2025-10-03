# 🚀 Quick Start Guide - Voice Interviewer

## Prerequisites
- Python 3.9+ with pip
- Node.js 18+ with npm
- LiveKit Cloud account (free tier works)
- Cerebras API key
- Deepgram API key

## Step 1: Backend Setup

### 1.1 Install Dependencies
```bash
cd backend
python -m venv venv
# Windows
.\venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 1.2 Configure Environment
Create `backend/.env` file:
```env
# LiveKit (from cloud.livekit.io)
LIVEKIT_API_KEY=your_api_key_here
LIVEKIT_API_SECRET=your_api_secret_here
LIVEKIT_URL=wss://your-project.livekit.cloud

# AI Providers
CEREBRAS_API_KEY=your_cerebras_key
DEEPGRAM_API_KEY=your_deepgram_key

# Optional
CEREBRAS_MODEL=llama3.3-70b
AGENT_TEMPERATURE=0.7
```

### 1.3 Test Configuration
```bash
cd backend
python test_connection.py
```
All checks should pass ✅

## Step 2: Start Services

### Terminal 1: Backend API
```bash
cd backend
.\venv\Scripts\activate  # or source venv/bin/activate
uvicorn uvicorn_app:app --reload --port 8000
```
Should see: "Uvicorn running on http://127.0.0.1:8000"

### Terminal 2: Agent Worker (IMPORTANT!)
```bash
cd backend
.\venv\Scripts\activate  # or source venv/bin/activate
python run_agent.py dev
```
Should see: 
```
INFO: Starting agent worker...
INFO: LiveKit URL: wss://...
INFO: Worker started successfully
```

### Terminal 3: Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

## Step 3: Run Interview

1. **Input Job Details**
   - Option A: Paste job URL (may fail for LinkedIn)
   - Option B: Copy/paste job description text (recommended)

2. **Upload Resume**
   - Click "Choose PDF file" and select your resume
   - Click "Upload & Parse"

3. **Start Interview**
   - Click "🚀 Start Mock Interview"
   - Allow microphone access when prompted
   - Wait for "Connected" status

4. **Interview**
   - You should hear the AI greet you
   - Speak naturally - the AI will respond
   - Use Mute/Unmute as needed
   - Click "End Interview" when done

## Troubleshooting

### Agent doesn't greet me
- Check Terminal 2 - the agent worker must be running
- Look for "Agent joining room" message when you start interview
- Verify all API keys are correct in .env

### Connection timeout
- Check LiveKit credentials are correct
- Ensure agent worker is running (`python run_agent.py dev`)
- Check firewall isn't blocking WebSocket connections

### No audio/Can't hear agent
- Check browser microphone permissions
- Ensure Deepgram API key is valid
- Look for errors in agent worker terminal

### Parse errors
- LinkedIn blocks scraping - use paste option
- Ensure Cerebras API key is valid for LLM parsing

## Common Issues

1. **"Missing LiveKit credentials"**
   - Double-check backend/.env has all required keys
   - Get keys from cloud.livekit.io

2. **"Failed to import LiveKit agents"**
   - Run: `pip install livekit-agents[openai,silero,deepgram,turn-detector]`

3. **Agent worker crashes**
   - Check all API keys are valid
   - Ensure Python 3.9+ is used
   - Try: `pip install --upgrade livekit-agents`

## Test Without LiveKit Cloud
For local testing without cloud:
```bash
cd backend
python test_interview.py
```

## Support
- LiveKit docs: https://docs.livekit.io
- Cerebras docs: https://inference-docs.cerebras.ai
- Deepgram docs: https://developers.deepgram.com
