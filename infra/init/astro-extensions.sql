-- Enable pgvector for semantic search / embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable uuid-ossp for uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_uuidv7 for uuid_generate_v7() (time-ordered UUIDs for stream_message_logs)
CREATE EXTENSION IF NOT EXISTS pg_uuidv7;
