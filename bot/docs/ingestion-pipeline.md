# Ingestion Pipeline

Captures Twitch chat messages, moderates them, converts them into vector embeddings, and persists them to PostgreSQL for RAG (Retrieval-Augmented Generation) retrieval.

---

## Overview

```
Twitch Chat
    │
    ▼
TwitchChatListener.event_message()          providers/twitch_listener.py
    │  ChatMessage → TwitchUser (badge parse) → TwitchMessage
    ▼
MessageBuffer.queue_message()               ingestion/message_buffer.py
    │
    ├── OpenAI Moderation API  ← _moderation_semaphore (max BATCH_SIZE concurrent)
    │       flagged → DISCARD
    │       safe    → append to _active_message_queue
    │
    ├── queue not full → wait for size threshold or timer
    │
    └── queue full (BATCH_SIZE) OR timer fires (FLUSH_INTERVAL)
            │
            ▼
        _rotate_queues()          active → commit queue, fresh active queue
            │
            ▼
        sort batch by created_at  (preserves chronology across concurrent moderation)
            │
            ▼
        asyncio.create_task(_commit_batch)    fire-and-forget + _on_commit_done callback
            │
            ▼
        _persist_lock             serialises concurrent commit tasks
            │
            ▼
        @retry(OpenAI errors)
        EmbeddingService.get_embeddings_batch()     single OpenAI API call → list[list[float]]
            │
            ▼
        StreamEvent.from_twitch_message()   TwitchMessage + embedding → StreamEvent
            │
            ▼
        @retry(DB errors)
        _store_embeddings()       executemany INSERT_DOCUMENT → PostgreSQL (pgvector)
```

---

## Startup Sequence

`main()` initialises components in order before any messages are processed:

1. **Config validation** — `settings.validate_config()` checks required env vars, exits on missing
2. **Database pool** — `init_db()` opens the `AsyncConnectionPool`, registers the `pgvector` extension; retries up to 10 times with a 3-second delay to handle container startup races
3. **MessageBuffer** — `MessageBuffer.start()` launches the `_periodic_flush` background task
4. **TwitchIO bot** — `TwitchChatListener.start()` connects to Twitch; `event_ready` fires once the connection is established and checks whether the stream is currently live

Shutdown (finally block) runs in reverse: MessageBuffer final flush → pool close.

---

## Phase 1 — Message Reception

**`TwitchChatListener.event_message(message: ChatMessage)`**

1. Guard: if `message.metadata` is absent, discard silently
2. Build user snapshot: `TwitchUser.from_chatter(message.chatter, settings.TWITCH_BOT_ID)`
   - `TwitchBadge.parse_all()` walks the badge list once and returns `{TwitchBadge: details}`
   - Derives all boolean flags (`is_mod`, `is_bot`, `is_verified`, `is_partner`, `is_affiliate`, `is_subscriber`, `with_prime`) from that mapping
3. Build `TwitchMessage` DTO from message fields, author snapshot, and shared-chat metadata
4. Call `await message_buffer.queue_message(message)`

---

## Phase 2 — Moderation

**`MessageBuffer.queue_message(message: TwitchMessage)`**

```
Acquire _moderation_semaphore
    │  (max BATCH_SIZE concurrent calls — prevents OpenAI overload)
    ▼
openai_client.moderations.create(input=content)
    │
    ├── flagged=True  → log debug, return (message discarded)
    └── flagged=False → proceed
            │
            ▼
        Acquire _flush_lock
        Append to _active_message_queue
        If len >= BATCH_SIZE → _flush()
```

Moderation failures are not retried; the message is silently dropped (safe-fail).

---

## Phase 3 — Flush Triggers

Two independent triggers both call `_flush()` under `_flush_lock`:

| Trigger | Condition |
|---------|-----------|
| Size threshold | `len(_active_message_queue) >= settings.BATCH_SIZE` (inline in `queue_message`) |
| Periodic timer | `_periodic_flush` background task, every `settings.FLUSH_INTERVAL` seconds |

`_periodic_flush` catches all non-cancellation exceptions, logs them, and sleeps 5 seconds before retrying — guaranteeing the loop never permanently dies.

---

## Phase 4 — Queue Rotation & Commit Task

**`MessageBuffer._flush()`**

1. `_rotate_queues()` — transfers the active list reference to `_commit_message_queue`, resets `_active_message_queue` to `[]`; new messages continue arriving into the fresh queue without interruption
2. Sort `batch` by `created_at` — restores chronological order after concurrent moderation delays
3. `asyncio.create_task(_commit_batch(batch))` — fire-and-forget; flush returns immediately
4. `task.add_done_callback(_on_commit_done)` — surfaces any unhandled exception via `logger.exception`

---

## Phase 5 — Embedding & Storage

**`MessageBuffer._commit_batch(batch)`**

Acquires `_persist_lock` before calling `_embed_and_store_batch`. This serialises concurrent commit tasks so they don't race each other when writing to the database.

**`MessageBuffer._embed_and_store_batch(batch)`** — `@retry(APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)`

1. `EmbeddingService.get_embeddings_batch([msg.content for msg in batch])`
   - Strips newlines from all inputs (avoids tokenisation artifacts)
   - Single `POST /embeddings` call with `text-embedding-3-small` → `list[list[float]]` (1536-dim)
2. `zip(batch, embeddings, strict=True)` — raises `ValueError` if counts don't match
3. `StreamEvent.from_twitch_message(message, embedding)` for each pair

**`MessageBuffer._store_embeddings(events)`** — `@retry(OperationalError, SerializationFailure)`

1. Builds a document dict per event (see [Document Shape](#document-shape))
2. `async with pool.connection()` → `crs.executemany(INSERT_DOCUMENT, documents)` → `conn.commit()`
3. Logs: `"Successfully stored N messages into Memory."`

---

## Data Models

### Transformation Chain

```
twitchio.ChatMessage
    │
    │  TwitchBadge.parse_all(chatter.badges) → {TwitchBadge: details}
    ▼
TwitchUser (frozen dataclass)           models/twitch_user.py
    id, username, is_astro, is_bot, is_mod, is_broadcaster,
    is_verified, is_partner, is_affiliate, is_subscriber,
    with_prime, subscriber_tier
    │
    │  TwitchMessage.__init__()
    ▼
TwitchMessage (frozen dataclass)        models/twitch_message.py
    id, content, author: TwitchUser, channel_id,
    is_command, created_at, extra_metadata
    │
    │  OpenAI text-embedding-3-small → list[float]
    │  StreamEvent.from_twitch_message(message, embedding)
    ▼
StreamEvent (frozen dataclass)          models/stream_event.py
    message_id, content, is_shared, created_at, channel_id,
    source: EventSource, author: TwitchUser,
    semantics: EventSemantics
        └─ embedding: list[float]
        └─ intent_category: IntentCategory  (default: CHATTING)
        └─ topics: list[str]                (default: [])
    │
    │  _store_embeddings() serialisation
    ▼
Document dict → PostgreSQL documents table
```

### Document Shape

```python
{
    "message_id": event.message_id,
    "content":    event.content,
    "is_shared":  event.is_shared,
    "created_at": event.created_at,
    "channel_id": event.channel_id,
    "source":     event.source.value,          # "twitch"
    "author": {
        "id":               event.author.id,
        "username":         event.author.username,
        "is_astro":         event.author.is_astro,
        "is_bot":           event.author.is_bot,
        "is_mod":           event.author.is_mod,
        "is_broadcaster":   event.author.is_broadcaster,
        "is_verified":      event.author.is_verified,
        "is_partner":       event.author.is_partner,
        "is_affiliate":     event.author.is_affiliate,
        "is_subscriber":    event.author.is_subscriber,
        "with_prime":       event.author.with_prime,
        "subscriber_tier":  event.author.subscriber_tier.value | None,
    },
    "semantics": {
        "embedding":        event.semantics.embedding,
        "intent_category":  event.semantics.intent_category.value | None,
        "topics":           event.semantics.topics,
    },
}
```

---

## Concurrency Model

| Primitive | Bound | Purpose |
|-----------|-------|---------|
| `_moderation_semaphore` | `BATCH_SIZE` | Caps concurrent OpenAI moderation calls |
| `_flush_lock` | — | Protects queue rotation; prevents append/flush races |
| `_persist_lock` | — | Serialises DB writes across concurrent fire-and-forget commit tasks |

**Task lifecycle:**

| Task | Created in | Lives until |
|------|-----------|-------------|
| `_flush_task` (periodic flush) | `start()` | `stop()` cancels it |
| `commit_task` (per batch) | `_flush()` | Completes after DB write |

---

## Error Handling

| Stage | Error | Behaviour |
|-------|-------|-----------|
| Moderation API | Any exception | Message discarded (safe-fail); no retry |
| Embedding API | Transient (`APIConnectionError`, `APITimeoutError`, `RateLimitError`, `InternalServerError`) | `@retry` — up to 3 attempts, exponential backoff + jitter |
| Embedding API | `ValueError` from `zip(strict=True)` | Batch dropped, logged via `_on_commit_done` |
| DB write | `OperationalError`, `SerializationFailure` | `@retry` — up to 3 attempts, exponential backoff + jitter |
| DB write | Other errors | Batch dropped, logged via `_on_commit_done` |
| Periodic flush loop | Any exception | Logged, 5-second sleep, loop continues |
| DB init | Connection refused | Retries up to 10 times, 3-second delay; raises on exhaustion |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Required |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI model (1536-dim output) |
| `BATCH_SIZE` | `10` | Queue size threshold for immediate flush; also bounds `_moderation_semaphore` |
| `FLUSH_INTERVAL` | `30` | Seconds between periodic flushes |
| `TWITCH_BOT_ID` | — | Required; used to flag `is_astro` on `TwitchUser` |
| `TWITCH_CHANNEL` | — | Required; channel to listen to |

---

## Open TODOs

| Location | Description |
|----------|-------------|
| `TwitchUser.from_chatter` | `subscriber_tier` not yet derived from badge data |
| `EventSemantics` | `intent_category` defaults to `CHATTING`; intent classification not wired in |
| `EventSemantics` | `topics` always `[]`; topic extraction not wired in |
| `MessageBuffer._persist_entities` | Stub — upsert users and channels into relational tables |
| `TwitchChatListener` | Bot account is currently Mako AI; needs a dedicated bot account |

---

## Dependencies

| Library | Role |
|---------|------|
| `twitchio` | Twitch chat WebSocket client |
| `openai` | Moderation and embeddings API client |
| `psycopg` | Async PostgreSQL driver |
| `pgvector` | Vector column support for similarity search |
