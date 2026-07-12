# One image for both backend processes — same code, different command:
#   API:    uvicorn uvicorn_app:app --host 0.0.0.0 --port 8000
#   Worker: python run_agent.py start
# fly.toml picks the command per process group. The frontend is static and
# deploys to a CDN host (Vercel/Cloudflare Pages), not a container.
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Run as non-root; the model cache below lands in /home/app/.cache.
RUN useradd -m app
COPY --chown=app:app . .
USER app

# Bake the turn-detector model into the image so worker cold-starts don't
# download ~100MB from HuggingFace. download-files never connects to LiveKit,
# but main() validates config first — dummy values satisfy it at build time.
RUN LIVEKIT_URL=wss://build LIVEKIT_API_KEY=build LIVEKIT_API_SECRET=build \
    CEREBRAS_API_KEY=build DEEPGRAM_API_KEY=build \
    python run_agent.py download-files

EXPOSE 8000
CMD ["uvicorn", "uvicorn_app:app", "--host", "0.0.0.0", "--port", "8000"]
