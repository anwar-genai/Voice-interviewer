## 🎤 AI Interview Coach (FastAPI + React)

A production-ready real-time interview practice agent using FastAPI backend and React frontend. Features AI-powered mock interviews with personalized feedback, analytics, and structured conversation flow.

Reference: Interviewer Voice Agent with LiveKit (Cerebras) — see the Cookbook page: `https://inference-docs.cerebras.ai/cookbook/agents/livekit`.

### ✨ Features
- **Real-time Voice Interviews**: Conduct mock interviews with AI interviewer
- **AI-Powered Feedback**: Get detailed performance analysis and improvement suggestions
- **Smart Job Parsing**: Extract job requirements from URLs or pasted descriptions using Cerebras LLM
- **Resume Analysis**: Upload and parse PDF resumes for personalized interview questions
- **Session Analytics**: Track interview performance over time with metrics and trends
- **Structured Interview Flow**: Introduction → Technical → Deep dive → Wrap-up phases
- **STAR Method Questions**: Behavioral questions using Situation, Task, Action, Result format
- **Optimized Audio**: Fast TTS/STT with minimal interruptions and high quality
- **Beautiful UI**: Modern, responsive interface with real-time status indicators

### 📁 Repo Structure
- `backend/`
  - `app/main.py`: FastAPI app factory with CORS and health check
  - `app/routers/`: API endpoints
    - `utils.py`: Job parsing and PDF processing endpoints
    - `agent.py`: LiveKit room creation and join token generation
    - `feedback.py`: AI-powered interview feedback generation
    - `analytics.py`: Session tracking and performance analytics
  - `app/agents/interviewer.py`: Core interview agent logic
  - `run_agent.py`: Standard agent worker
  - `run_agent_improved.py`: Enhanced agent with better audio and features
  - `requirements.txt`: Backend dependencies with LiveKit agents
  - `env.example`: Environment variable template
- `frontend/`
  - Modern React + TypeScript app with beautiful UI
  - Real-time LiveKit client integration
  - File upload for resume processing
  - Audio visualization and controls

### 🛠️ Prerequisites
- Python 3.9+ (recommended 3.11+)
- Node.js 18+ and npm/pnpm/yarn
- LiveKit Cloud account (free tier available)
- Cerebras API key
- Deepgram API key

### 🚀 Quick Start

#### 1. Backend Setup
```bash
# Navigate to project root
cd voice-interviewer

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment
cp backend/env.example backend/.env
# Edit backend/.env with your API keys
```

#### 2. Environment Variables
Required in `backend/.env`:
```env
# LiveKit Cloud (get from cloud.livekit.io)
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret  
LIVEKIT_URL=wss://your-project.livekit.cloud

# AI Providers
CEREBRAS_API_KEY=your_cerebras_key
DEEPGRAM_API_KEY=your_deepgram_key

# Optional
CEREBRAS_MODEL=llama3.3-70b
AGENT_TEMPERATURE=0.7
DEEPGRAM_TTS_MODEL=aura-asteria-en
```

#### 3. Start Services

**Terminal 1 - Backend API:**
```bash
cd voice-interviewer
.venv\Scripts\activate
cd backend
uvicorn uvicorn_app:app --reload --port 8000
```

**Terminal 2 - Agent Worker (Required!):**
```bash
cd voice-interviewer
.venv\Scripts\activate
cd backend
python run_agent_improved.py dev  # Use improved version for better audio
```

**Terminal 3 - Frontend:**
```bash
cd voice-interviewer/frontend
npm install
npm run dev
```

#### 4. Access the App
Open http://localhost:5173 and start practicing!

### 🎯 How to Use

1. **Setup Job Information**
   - Option A: Paste job URL (works for public pages)
   - Option B: Copy/paste job description text (recommended for LinkedIn)

2. **Upload Resume**
   - Click "Choose PDF file" and select your resume
   - Click "Upload & Parse" to extract text

3. **Start Interview**
   - Click "🚀 Start Mock Interview"
   - Allow microphone access when prompted
   - Wait for "Connected" status

4. **Conduct Interview**
   - AI will greet you and ask questions
   - Respond naturally - AI listens and responds
   - Use mute/unmute controls as needed
   - Interview follows structured phases

5. **Get Feedback** (Coming Soon)
   - Review AI-generated feedback after interview
   - Track performance metrics over time
   - Get personalized improvement suggestions

### 🔧 API Endpoints

#### Core Interview
- `POST /utils/parse-link-llm` - Parse job descriptions from URLs
- `POST /utils/parse-job-text-llm` - Parse pasted job descriptions
- `POST /utils/parse-pdf-upload` - Upload and parse resume PDFs
- `POST /agent/join-token` - Get LiveKit room access token

#### Analytics & Feedback
- `POST /feedback/generate` - Generate AI-powered interview feedback
- `POST /analytics/session/start` - Start tracking interview session
- `POST /analytics/session/end` - End session with metrics
- `GET /analytics/sessions` - View all interview history
- `GET /analytics/analytics` - Overall performance analytics

### 🚀 Advanced Features

#### Interview Types
- **Technical Interviews**: Focus on coding skills and technical knowledge
- **Behavioral Interviews**: STAR method questions for soft skills
- **Leadership Interviews**: Management and team leadership scenarios
- **Company-Specific**: Customized questions based on company culture

#### Audio Optimization
- **Fast TTS**: Optimized for minimal latency and interruptions
- **Smart STT**: Accurate transcription with punctuation
- **Noise Cancellation**: Built-in audio processing
- **Real-time Processing**: Low-latency voice pipeline

### 🛠️ Troubleshooting

#### Agent doesn't greet you
- Ensure agent worker is running: `python run_agent_improved.py dev`
- Check LiveKit credentials in `.env`
- Verify all API keys are valid

#### Audio interruptions
- Use the improved agent: `run_agent_improved.py`
- Check Deepgram API key and limits
- Try different TTS models in environment variables

#### Connection issues
- Verify LiveKit URL format: `wss://your-project.livekit.cloud`
- Check firewall settings for WebSocket connections
- Ensure all three services are running

### 🔮 Future Enhancements
- **Interview Recording**: Save audio/video for review
- **Real-time Transcription**: Live text display of conversation
- **Custom Interview Templates**: Role-specific question sets
- **Performance Analytics Dashboard**: Detailed metrics and trends
- **Multi-language Support**: Interviews in different languages
- **Integration APIs**: Connect with ATS systems

### 📚 Credits
- Based on the [Cerebras Cookbook: Interviewer Voice Agent with LiveKit](https://inference-docs.cerebras.ai/cookbook/agents/livekit)
- Built with [LiveKit Agents](https://docs.livekit.io/agents/), [Cerebras Cloud](https://cerebras.ai/), and [Deepgram](https://deepgram.com/)


