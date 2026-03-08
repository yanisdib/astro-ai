# Ingestion Pipeline

The ingestion pipeline captures Twitch chat messages, converts them into vector embeddings, and stores them in PostgreSQL for RAG (Retrieval-Augmented Generation) retrieval.

---

## Overview

```
Twitch Chat
    │
    ▼
TwitchChatListener          src/providers/twich_listener.py
    │  builds ChatMessage DTO
    ▼
MessageBuffer.queue_message()   src/ingestion/message_buffer.py
    │
    ├── active queue not full → wait
    │
    └── active queue full (BATCH_LIMIT) OR timer fires (FLUSH_INTERVAL)
            │
            ▼
        _rotate_queues()        promotes active → commit queue
            │
            ▼
        EmbeddingService        src/ingestion/embeddings.py
        .get_embeddings_batch() (runs in thread pool via asyncio.to_thread)
            │  single OpenAI API call → list of vectors
            ▼
        _store_batch()          INSERT INTO documents (pgvector)
```

---

## Modules

### `src/models/chat_message.py` — ChatMessage

Immutable DTO wrapping a single Twitch chat event. Created by `TwitchChatListener` and passed through the pipeline without modification.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique message identifier |
| `content` | `str` | Raw message text |
| `user_id` | `str` | Twitch user ID |
| `username` | `str` | Twitch username |
| `is_bot` | `bool` | Whether the sender is a bot |
| `is_mod` | `bool` | Whether the sender is a moderator |
| `is_command` | `bool` | Whether the message is a bot command |
| `created_at` | `int` | Unix timestamp of the original message |
| `extra_metadata` | `Dict[str, Any]` | Arbitrary metadata — pipeline expects `channel_id` and `source_type` here |

---

### `src/ingestion/embeddings.py` — EmbeddingService

Wraps the OpenAI embeddings API. Newlines are stripped from all input texts before encoding to avoid tokenization artifacts.

**`get_embedding(text, model) → list[float] | None`**
Converts a single string to a vector. Returns `None` for empty input. Use for one-off embedding lookups.

**`get_embeddings_batch(texts, model) → list[list[float]]`**
Converts a list of strings in a single API call. The returned list preserves input order, making it safe to `zip` with the source messages. Returns `[]` for empty input. This is the method used by `MessageBuffer`.

**Model:** `config.EMBEDDING_MODEL` (default: `text-embedding-3-small`)

---

### `src/ingestion/message_buffer.py` — MessageBuffer

Asynchronous double-buffer queue that decouples message ingestion from batch processing. Two flush triggers run in parallel:

| Trigger | Constant | Behaviour |
|---|---|---|
| Batch size | `BATCH_LIMIT = 10` | Flushes immediately when the active queue reaches 10 messages |
| Time interval | `FLUSH_INTERVAL = 120s` | Background task flushes every 120 seconds regardless of queue size |

**Double-buffer design**

The class maintains two lists:
- `_active_message_queue` — receives incoming messages while a flush is in progress
- `_commit_message_queue` — holds the batch currently being embedded and stored

`_rotate_queues()` transfers the active list reference to the commit slot and resets the active queue to a new empty list. This means ingestion continues uninterrupted during a flush — no messages are dropped or delayed.

**Flush sequence (`_flush`)**

1. `_rotate_queues()` — snapshot the active batch
2. `EmbeddingService.get_embeddings_batch()` — called via `asyncio.to_thread` to keep the event loop free during the synchronous OpenAI HTTP call
3. Build document dicts: `{ content, embedding, channel_id, source_type, created_at }`
4. `_store_batch()` — atomic INSERT via psycopg `executemany`
5. `finally` — clear the commit queue to release memory

**Shutdown (`stop`)**

Cancels the background flush task, awaits its termination, then performs a final flush of any remaining messages before the process exits.

---

### `src/ingestion/queries.py` — SQL

| Constant | Table | Operation |
|---|---|---|
| `INSERT_DOCUMENT` | `documents` | Inserts one embedded message row |

Schema expected by `INSERT_DOCUMENT`:

```sql
INSERT INTO documents (content, embedding, channel_id, source_type, created_at)
VALUES (%(content)s, %(embedding)s, %(channel_id)s, %(source_type)s, %(created_at)s)
```

The `embedding` column is a `pgvector` vector field. Vector dimensionality must match the embedding model output (1536 for `text-embedding-3-small`).

---

## Configuration

All tunable constants are defined in `src/core/config.py` and overridable via environment variables.

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Required. OpenAI API key |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `BATCH_SIZE` | `10` | Messages per batch before immediate flush |
| `FLUSH_INTERVAL` | `30` | Seconds between background flushes |

> **Note:** `BATCH_LIMIT` and `FLUSH_INTERVAL` are currently hardcoded as module-level constants in `message_buffer.py`. A future improvement is to read them from `config` to allow runtime tuning without code changes.

---

## Error Handling

| Failure point | Behaviour |
|---|---|
| OpenAI API error | Exception propagates to `_flush`, logged via `logger.exception`, batch is dropped |
| DB write error | `_store_batch` catches, logs, returns `False` — batch is dropped |
| Embedding/message count mismatch | `zip(strict=True)` raises `ValueError`, caught by `_flush`, batch is dropped |
| Periodic task crash | Caught by `_periodic_flush`, logged, task sleeps 5 seconds and retries |

> A retry-with-jitter decorator on `_store_batch` is planned but not yet implemented.

---

## Dependencies

| Library | Version | Role |
|---|---|---|
| `openai` | 2.21.0 | Embedding API client |
| `psycopg` | 3.3.3 | Async PostgreSQL driver |
| `pgvector` | 0.4.2 | Vector column support |
