# AGENTS.md — Nova AI Assistant

## Project Overview
Full-stack agentic AI assistant built with three skills:
1. Chat: streaming replies, local Ollama models first, cloud fallback (Anthropic, OpenAI, Gemini, Grok, Meta)
2. Photos: attach, paste, drag-drop or capture photos and ask vision models about them
3. Voice: LiveKit voice mode that uses the same model and fallback as typed chat

Placeholder user name in UI and docs is "Rizwan" unless told otherwise. Do not invent other person names.

## Architecture
- `api/`   : FastAPI, Python 3.13, uv, ruff, pytest, ollama/anthropic/openai SDKs
- `web/`   : Next.js 16, React 19, TypeScript, Tailwind 4, shadcn/ui
- `agent/` : LiveKit Agents voice worker (Python, uv)
- Flow: Browser -> /api (rewrite) -> FastAPI -> Provider (Ollama or cloud). Voice: Browser <-> LiveKit <-> agent -> POST /api/voice/chat (the "brain").

## Commands
- API:   `cd api && uv sync && uv run fastapi dev app/main.py`   (port 8000)
- Web:   `cd web && npm install && npm run dev`   (port 3000)
- Agent: `cd agent && uv run python voice_agent.py download-files && uv run python voice_agent.py dev`
- API checks: `cd api && uv run ruff check && uv run ruff format --check && uv run pytest`
- Web checks: `cd web && npm run typecheck && npm run build`
- Local model: `ollama pull llama3.2` (text) and `ollama pull gemma3` (vision)

## Environment Variables (names only; never commit real values)
- `api/.env`: provider API keys, CLOUD_PRIORITY, MAX_IMAGES_PER_MESSAGE, MAX_IMAGE_BYTES, LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, VOICE_AGENT_NAME, VOICE_AGENT_TOKEN
- `agent/.env`: same LIVEKIT_* values, same VOICE_AGENT_NAME and VOICE_AGENT_TOKEN
- `web/.env.local`: API_URL
Keep `.env.example` files updated.

## Agent Skills (read BEFORE working on a feature)
Each skill is a folder with SKILL.md, scripts/, assets/, references/.
- Scaffold / chat -> `.claude/skills/fullstack-ai-assistant/SKILL.md`
- Photos          -> `.claude/skills/add-photos/SKILL.md`
- Voice           -> `.claude/skills/livekit-voice-mode/SKILL.md`
Use the skills' scripts (scaffold.py, install_photos.py, install_voice.py, verify scripts). Do not rebuild these features from memory.

## Subagents (`.claude/agents/`)
- `api-builder`   : backend work in api/ and agent/
- `web-builder`   : frontend work in web/
- `code-reviewer` : read-only review before every commit
Workflow: build with api-builder / web-builder, then run code-reviewer before every commit.

## Code Rules
- SDK types stay inside `api/app/providers/`. Routes are thin; logic in `services/`.
- Settings come from `request.app.state.settings`, not global `get_settings()` in routes.
- Keep `web/lib/types.ts` in sync with `api/app/schemas.py`.
- UI: shadcn/ui, neutral palette, no gradients.
- Tests use `FakeProvider`; no network in tests.
- Python: type hints, async endpoints. TypeScript: strict mode, functional components.
- Error messages are short and never leak keys or stack traces.

## Safety Rules
- Never modify or commit `.env` files.
- Ask before adding new dependencies or changing the architecture.
- Photos: bytes to Ollama, never strings; trust file signatures, not declared types; limit before decoding.
- Voice: `/api/voice/session` goes behind login and VOICE_AGENT_TOKEN is set when the API is public.

## Definition of Done
Feature works end to end, ruff + pytest + typecheck + build are green, docs updated, code-reviewer reports no Critical issues.