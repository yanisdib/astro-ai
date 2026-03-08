# Backend Architect — Project Memory

## Project: astro-ai/bot

A Twitch chat bot with RAG/AI capabilities. Captures Twitch messages, embeds them via OpenAI,
and stores them in PostgreSQL (pgvector) for retrieval-augmented generation.

### Stack
- Python 3.13, Poetry, psycopg3 (async), pgvector, OpenAI, TwitchIO 3.x
- FastAPI + Uvicorn declared but not yet wired in
- Redis declared but not yet used in source
- Supabase Realtime in docker-compose for WAL-based CDC

### Key File Paths
- `/Users/yanisdib/Documents/Workspace/ai/astro-ai/bot/src/core/config.py` — env config class
- `/Users/yanisdib/Documents/Workspace/ai/astro-ai/bot/src/core/database.py` — psycopg pool singleton
- `/Users/yanisdib/Documents/Workspace/ai/astro-ai/bot/src/ingestion/message_buffer.py` — double-buffer flush pipeline
- `/Users/yanisdib/Documents/Workspace/ai/astro-ai/bot/src/ingestion/embeddings.py` — OpenAI embedding wrapper
- `/Users/yanisdib/Documents/Workspace/ai/astro-ai/bot/src/ingestion/queries.py` — SQL constants
- `/Users/yanisdib/Documents/Workspace/ai/astro-ai/bot/src/models/chat_message.py` — frozen DTO
- `/Users/yanisdib/Documents/Workspace/ai/astro-ai/bot/src/providers/twich_listener.py` — scaffold only (typo: "twich")
- `/Users/yanisdib/Documents/Workspace/ai/astro-ai/bot/tests/` — comprehensive unit tests
- `/Users/yanisdib/Documents/Workspace/ai/astro-ai/bot/docs/ingestion-pipeline.md` — pipeline doc

### Known Bugs (from full review, 2026-03-08)
See `debugging.md` for full detail.

1. CRITICAL: `bot.src.*` import paths fail — `bot` package not installed, no `__init__.py` in src/
2. CRITICAL: `conninfo` URI in `database.py` is malformed (missing `:`, `@`, `/` separators)
3. CRITICAL: `FLUSH_INTERVAL` hardcoded to 120s in message_buffer but Config defaults to 30s; constant names diverge (BATCH_LIMIT vs BATCH_SIZE)
4. CRITICAL: `asyncio.create_task` called in `__init__` (no running event loop at construction time)
5. Security: `.env.dev` baked into Docker image layer
6. Bug: `_store_batch` return value ignored by `_flush` — silent data loss on DB errors
7. Bug: `Config.validate_config` does not validate DB credentials
8. Bug: `Path.joinpath("/")` in config.py always resolves to root — dead code

### Architecture Decisions Confirmed
- Double-buffer design (active/commit queue) is correct for decoupling ingestion from batch processing
- `asyncio.to_thread` for synchronous OpenAI calls is the right pattern
- Frozen dataclass for ChatMessage DTO is correct
- psycopg_pool.AsyncConnectionPool with open=False (lazy open) is the right singleton pattern
- Parameterized SQL via psycopg named placeholders (`%(field)s`) prevents SQL injection

### Developer Preferences Observed
- Class-based test organization (TestXxx classes per module)
- Security tests explicitly labeled as SECURITY in test files
- Thorough docstrings on all public methods
- Uses `strict=True` on zip() for embedding/message alignment guard
