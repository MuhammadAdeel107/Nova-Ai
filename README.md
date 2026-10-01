# Nova Ai Assistant

## Voice mode (LiveKit)

Voice mode appears as a sound-wave button in the empty message box once the
API has LiveKit credentials. It needs a [LiveKit Cloud](https://cloud.livekit.io)
project, because speech-to-text, text-to-speech, turn detection and noise
cancellation run on LiveKit Inference.

```bash
# api/.env and agent/.env: the same three values from your LiveKit project
LIVEKIT_URL=wss://<your-project>.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...

# Voice agent (new terminal; API must be running)
cd agent
uv sync
uv run python voice_agent.py dev
```

With Docker: fill in agent/.env, then `docker compose --profile voice up --build`.

How a session flows:

```
Browser ──POST /api/voice/session──► API: new room + token that dispatches the agent
   │                                     (remembers the chosen model and earlier chat)
   └──WebRTC (mic + speaker)──► LiveKit ◄── agent: STT → turn detection → reply → TTS
                                                │
                                   POST /api/voice/chat  (same model dropdown,
                                   Ollama first, cloud fallback as text chat)
```

- Replies use the model picked in the dropdown, with the same fallback as
  text chat. The agent shows which model answered.
- Talking over the assistant interrupts it; **Stop** and **Esc** do too.
- Transcripts are saved into the chat (tagged *Spoken*), so a voice
  conversation can continue by typing and vice versa.
- If a model fails the assistant says so out loud and the UI shows the
  reason; if the agent is not running the UI says so after 20 seconds.
- Anyone who can reach `/api/voice/session` can start a (billed) voice
  session, so put it behind your login before going public, and set the same
  `VOICE_AGENT_TOKEN` in api/.env and agent/.env so only the agent can call
  `/api/voice/chat`.

Voice settings (agent/.env): `VOICE_STT_MODEL`, `VOICE_STT_LANGUAGE`,
`VOICE_TTS_MODEL`, `VOICE_TTS_VOICE`, `VOICE_GREETING`, `VOICE_INSTRUCTIONS`,
`VOICE_NOISE_CANCELLATION`, and `VOICE_LLM` (`app`, or a LiveKit Inference model
id to bypass the app). Offer a voice picker with `VOICE_VOICES` in api/.env.
