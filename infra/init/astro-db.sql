-- =============================================================================
-- astro-db schema
-- =============================================================================
-- Sections:
--   1. Subscription plans  — subscription_plans, features,
--                            subscription_plan_features
--   2. Core entities       — users, channels, streams, highlights,
--                            subscription_logs
--   3. Ingestion pipeline  — stream_message_logs
--   4. Indexes
-- =============================================================================


-- TODO: Add sequential internal ID + external UUID pattern later as a security
-- measure when designing API exposition.

-- =============================================================================
-- 1. Subscription plans
-- =============================================================================
-- Defined before core entities because users.subscription_plan_id references
-- subscription_plans. subscription_logs is in section 2 because it references users.

CREATE TABLE IF NOT EXISTS subscription_plans (
    id    SMALLINT    GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label VARCHAR(50) UNIQUE NOT NULL
);

COMMENT ON COLUMN subscription_plans.id    IS 'Auto-generated surrogate key. ID 1 is reserved for the free tier.';
COMMENT ON COLUMN subscription_plans.label IS 'Human-readable tier name (e.g. ''free'', ''pro'', ''enterprise'').';


CREATE TABLE IF NOT EXISTS features (
    id   INT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(70) UNIQUE NOT NULL
);

COMMENT ON COLUMN features.id   IS 'Auto-generated surrogate key.';
COMMENT ON COLUMN features.name IS 'Unique feature identifier used in access-control checks (e.g. ''highlights'', ''chat_analysis'').';


CREATE TABLE IF NOT EXISTS subscription_plan_features (
    feature_id           INT      NOT NULL REFERENCES features(id)           ON DELETE CASCADE,
    subscription_plan_id SMALLINT NOT NULL REFERENCES subscription_plans(id) ON DELETE CASCADE,
    PRIMARY KEY (feature_id, subscription_plan_id)
);

COMMENT ON COLUMN subscription_plan_features.feature_id           IS 'FK to features.id.';
COMMENT ON COLUMN subscription_plan_features.subscription_plan_id IS 'FK to subscription_plans.id.';


-- =============================================================================
-- 2. Core entities
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id                   UUID         PRIMARY KEY DEFAULT uuid_generate_v7(),
    email                VARCHAR(255) UNIQUE NOT NULL CHECK (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    password_hash        VARCHAR(255) NOT NULL CHECK (length(password_hash) >= 60),
    country_code         SMALLINT     CHECK (country_code BETWEEN 1 AND 999),
    phone_number         VARCHAR(20)  NULL,
    fullname             VARCHAR(100) NOT NULL,
    gender               VARCHAR(15)  NOT NULL,
    address              VARCHAR(255) NOT NULL DEFAULT '',
    additional_address   VARCHAR(255),
    city                 VARCHAR(150) NOT NULL,
    zip_code             VARCHAR(10)  NOT NULL,
    region               VARCHAR(255) NOT NULL,
    country              VARCHAR(70)  NOT NULL,
    available_credits    NUMERIC(9,2) NOT NULL DEFAULT 0.00 CHECK (available_credits >= 0.00),
    subscription_plan_id SMALLINT     NOT NULL DEFAULT 1 REFERENCES subscription_plans(id),
    is_verified          BOOLEAN      NOT NULL DEFAULT FALSE,
    joined_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ
);

COMMENT ON COLUMN users.id                   IS 'Auto-generated surrogate key.';
COMMENT ON COLUMN users.email                IS 'Unique login identifier; used for authentication and notifications.';
COMMENT ON COLUMN users.password_hash        IS 'Bcrypt/Argon2 hash of the user password; plaintext is never stored.';
COMMENT ON COLUMN users.country_code         IS 'ITU-T E.164 numeric dialing prefix (e.g. 1 for US, valid range 1–999); NULL until provided at registration.';
COMMENT ON COLUMN users.phone_number         IS 'Full phone number including country code and formatting (e.g. ''+57 315 123 4567''). NULL if not provided.';
COMMENT ON COLUMN users.fullname             IS 'Full name as provided at registration.';
COMMENT ON COLUMN users.gender               IS 'Self-reported gender string (e.g. ''male'', ''female'', ''non-binary'').';
COMMENT ON COLUMN users.address              IS 'Primary street address line.';
COMMENT ON COLUMN users.additional_address   IS 'Apartment, suite, floor, or other secondary address line.';
COMMENT ON COLUMN users.city                 IS 'City of residence.';
COMMENT ON COLUMN users.zip_code             IS 'Postal / ZIP code stored as text to preserve leading zeros (e.g. ''01234'' in New England, 6-digit codes in Colombia).';
COMMENT ON COLUMN users.region               IS 'State, province, or region.';
COMMENT ON COLUMN users.country              IS 'Full country name.';
COMMENT ON COLUMN users.available_credits    IS 'Prepaid credit balance in USD, used for pay-as-you-go features.';
COMMENT ON COLUMN users.subscription_plan_id IS 'Active plan; 1 = free tier. FK to subscription_plans.id.';
COMMENT ON COLUMN users.is_verified          IS 'TRUE once the user confirms their email address; unverified accounts have restricted access.';
COMMENT ON COLUMN users.joined_at            IS 'Timestamp of account creation.';
COMMENT ON COLUMN users.updated_at           IS 'Timestamp of the last profile change; NULL if never updated.';


CREATE TABLE IF NOT EXISTS channels (
    id          UUID         PRIMARY KEY DEFAULT uuid_generate_v7(),
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    platform    VARCHAR(50)  NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    user_id     UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_name_platform UNIQUE (name, platform)
);

COMMENT ON COLUMN channels.id          IS 'Auto-generated surrogate key.';
COMMENT ON COLUMN channels.name        IS 'Channel display name as it appears on the source platform.';
COMMENT ON COLUMN channels.description IS 'Optional free-text description of the channel.';
COMMENT ON COLUMN channels.platform    IS 'Source platform identifier (e.g. ''twitch'', ''youtube'').';
COMMENT ON COLUMN channels.created_at  IS 'Timestamp when the channel was registered in this system.';
COMMENT ON COLUMN channels.user_id     IS 'Owner of this channel. FK to users.id.';


CREATE TABLE IF NOT EXISTS streams (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v7(),
    title      TEXT        NOT NULL,
    duration   BIGINT      NOT NULL CHECK (duration >= 0),
    user_id    UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel_id UUID        NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL
);

COMMENT ON COLUMN streams.id         IS 'Auto-generated surrogate key.';
COMMENT ON COLUMN streams.title      IS 'Stream title at the time of broadcast.';
COMMENT ON COLUMN streams.duration   IS 'Total stream length in seconds.';
COMMENT ON COLUMN streams.user_id    IS 'Streamer who ran the session. FK to users.id.';
COMMENT ON COLUMN streams.channel_id IS 'Channel the stream aired on. FK to channels.id.';
COMMENT ON COLUMN streams.started_at IS 'UTC timestamp when the stream went live.';


CREATE TABLE IF NOT EXISTS highlights (
    id         UUID        PRIMARY KEY DEFAULT uuid_generate_v7(),
    summary    TEXT,
    started_at TIMESTAMPTZ,
    ended_at   TIMESTAMPTZ,
    stream_id  UUID        NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
    CHECK (
        (started_at IS NULL AND ended_at IS NULL)  -- in-progress
        OR (started_at IS NOT NULL AND ended_at IS NOT NULL AND ended_at > started_at)  -- completed
    )
);

COMMENT ON COLUMN highlights.id         IS 'Auto-generated surrogate key.';
COMMENT ON COLUMN highlights.summary    IS 'AI-generated or manually written description of the highlight segment.';
COMMENT ON COLUMN highlights.started_at IS 'Start of the highlighted segment; NULL while the highlight is being processed.';
COMMENT ON COLUMN highlights.ended_at   IS 'End of the highlighted segment; NULL while the highlight is being processed.';
COMMENT ON COLUMN highlights.stream_id  IS 'Parent stream this highlight belongs to. FK to streams.id.';


CREATE TABLE IF NOT EXISTS subscription_logs (
    id                   UUID        PRIMARY KEY DEFAULT uuid_generate_v7(),
    user_id              UUID             REFERENCES users(id) ON DELETE SET NULL,
    subscription_plan_id SMALLINT    NOT NULL REFERENCES subscription_plans(id),
    subscribed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action               VARCHAR(25) NOT NULL CHECK (action IN ('subscribe', 'cancel', 'upgrade', 'downgrade')),
    reason               VARCHAR(250)
);

COMMENT ON COLUMN subscription_logs.id                   IS 'UUID primary key for idempotent event processing.';
COMMENT ON COLUMN subscription_logs.user_id              IS 'User whose subscription changed. FK to users.id; SET NULL on user deletion to preserve billing history.';
COMMENT ON COLUMN subscription_logs.subscription_plan_id IS 'Plan involved in this event. FK to subscription_plans.id.';
COMMENT ON COLUMN subscription_logs.subscribed_at        IS 'Timestamp when the subscription event occurred.';
COMMENT ON COLUMN subscription_logs.action               IS 'Lifecycle event type: ''subscribe'', ''cancel'', ''upgrade'', ''downgrade''.';
COMMENT ON COLUMN subscription_logs.reason               IS 'Optional human-readable reason for the action (e.g. cancellation survey answer).';


-- =============================================================================
-- 3. Ingestion pipeline
-- =============================================================================

CREATE TABLE IF NOT EXISTS stream_message_logs (
    id                UUID         PRIMARY KEY DEFAULT uuid_generate_v7(),
    message_id     VARCHAR(64)  UNIQUE NOT NULL,
    content           TEXT         NOT NULL,
    username          VARCHAR(25)  NOT NULL CHECK (username ~ '^[a-zA-Z0-9_]{1,25}$'),
    stream_id         UUID                  REFERENCES streams(id) ON DELETE CASCADE,
    channel_id        UUID                  REFERENCES channels(id) ON DELETE CASCADE,
    status            VARCHAR(15)  NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'embedded')),
    moderation_status VARCHAR(20)  CHECK (moderation_status IN ('safe', 'flagged')),
    embedding         vector(1536),
    embedded_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN stream_message_logs.id                IS 'UUID v7 primary key; time-ordered for efficient index inserts.';
COMMENT ON COLUMN stream_message_logs.message_id        IS 'Stream-assigned message ID; UNIQUE prevents duplicate ingestion.';
COMMENT ON COLUMN stream_message_logs.content           IS 'Raw chat message text as received from Twitch.';
COMMENT ON COLUMN stream_message_logs.username          IS 'Twitch username of the sender (1–25 chars, alphanumeric + underscores).';
COMMENT ON COLUMN stream_message_logs.stream_id         IS 'Stream during which the message was sent. FK to streams.id.';
COMMENT ON COLUMN stream_message_logs.channel_id        IS 'Channel the message belongs to. FK to channels.id.';
COMMENT ON COLUMN stream_message_logs.status            IS 'Ingestion pipeline state: ''pending'' (received) → ''embedded'' (vectorized).';
COMMENT ON COLUMN stream_message_logs.moderation_status IS 'Result from the OpenAI moderation gate (e.g. ''safe'', ''flagged''). NULL until checked.';
COMMENT ON COLUMN stream_message_logs.embedding         IS 'pgvector column storing the text-embedding-3-small (1536-dim) vector. NULL until embedded.';
COMMENT ON COLUMN stream_message_logs.embedded_at       IS 'Timestamp when the embedding was written. NULL while pending.';
COMMENT ON COLUMN stream_message_logs.created_at        IS 'Timestamp when the message was captured.';

--- pgvector documents table
CREATE TABLE IF NOT EXISTS documents (
    id  UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    message_id VARCHAR(64) UNIQUE NOT NULL,
    message_content TEXT NOT NULL,
    shared_stream BOOLEAN NOT NULL DEFAULT FALSE,
    channel_id VARCHAR(64) NOT NULL,
    source VARCHAR(50) NOT NULL,

    -- author
    user_id         TEXT NOT NULL,
    username        TEXT NOT NULL,
    is_astro        BOOLEAN NOT NULL DEFAULT FALSE,
    is_bot          BOOLEAN NOT NULL DEFAULT FALSE,
    is_mod          BOOLEAN NOT NULL DEFAULT FALSE,
    is_broadcaster  BOOLEAN NOT NULL DEFAULT FALSE,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    is_partner      BOOLEAN NOT NULL DEFAULT FALSE,
    is_affiliate    BOOLEAN NOT NULL DEFAULT FALSE,
    is_subscriber   BOOLEAN NOT NULL DEFAULT FALSE,
    with_prime      BOOLEAN NOT NULL DEFAULT FALSE,
    subscriber_tier TEXT,

    -- semantics
    embedding       vector(1536) NOT NULL,
    intent_category TEXT,
    topics          TEXT[],
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CHECK (NOT with_prime OR is_subscriber),
    CHECK (subscriber_tier IS NULL OR is_subscriber)
);

COMMENT ON TABLE documents IS 'Denormalized vector store for RAG retrieval. Each row is an embedded chat message snapshot, ready for cosine similarity search via the HNSW index.';

COMMENT ON COLUMN documents.id              IS 'UUID v7 primary key; time-ordered for efficient index inserts.';
COMMENT ON COLUMN documents.message_id      IS 'Platform-assigned message ID (e.g. Twitch message UUID); UNIQUE prevents duplicate ingestion.';
COMMENT ON COLUMN documents.message_content IS 'Raw chat message text used as the embedding input.';
COMMENT ON COLUMN documents.shared_stream   IS 'TRUE if the source stream was a shared/co-stream rather than a solo broadcast.';
COMMENT ON COLUMN documents.channel_id      IS 'Platform channel identifier the message originated from.';
COMMENT ON COLUMN documents.source          IS 'Platform the message came from (e.g. ''twitch'', ''youtube'').';

COMMENT ON COLUMN documents.user_id         IS 'Platform user ID of the message author.';
COMMENT ON COLUMN documents.username        IS 'Display name of the message author at ingestion time.';
COMMENT ON COLUMN documents.is_astro        IS 'TRUE if the author is the Astro bot account itself.';
COMMENT ON COLUMN documents.is_bot          IS 'TRUE if the platform flagged the author as a bot.';
COMMENT ON COLUMN documents.is_mod          IS 'TRUE if the author held moderator status in the channel at message time.';
COMMENT ON COLUMN documents.is_broadcaster  IS 'TRUE if the author is the channel owner/broadcaster.';
COMMENT ON COLUMN documents.is_verified     IS 'TRUE if the platform has verified the author''s account.';
COMMENT ON COLUMN documents.is_partner      IS 'TRUE if the author is a platform Partner at ingestion time.';
COMMENT ON COLUMN documents.is_affiliate    IS 'TRUE if the author is a platform Affiliate at ingestion time.';
COMMENT ON COLUMN documents.is_subscriber   IS 'TRUE if the author was subscribed to the channel at message time.';
COMMENT ON COLUMN documents.with_prime      IS 'TRUE if the subscription was paid via Amazon Prime Gaming rather than a direct sub.';
COMMENT ON COLUMN documents.subscriber_tier IS 'Twitch sub tier at message time (''1000'', ''2000'', ''3000''). NULL for non-subscribers.';

COMMENT ON COLUMN documents.embedding       IS 'text-embedding-3-small 1536-dim vector; queried via the HNSW cosine index for RAG retrieval.';
COMMENT ON COLUMN documents.intent_category IS 'Classifier-assigned intent label (e.g. ''question'', ''hype'', ''complaint''). NULL if not yet classified.';
COMMENT ON COLUMN documents.topics          IS 'Array of topic tags extracted from the message (e.g. ''{gameplay, economy}''). NULL if not yet tagged.';
COMMENT ON COLUMN documents.created_at      IS 'Timestamp when the document was written to the vector store.';
-- =============================================================================
-- 4. Indexes
-- =============================================================================

-- channels
CREATE INDEX IF NOT EXISTS idx_channels_user_id  ON channels (user_id);
CREATE INDEX IF NOT EXISTS idx_channels_platform ON channels (platform);

-- streams
CREATE INDEX IF NOT EXISTS idx_streams_user_id    ON streams (user_id);
CREATE INDEX IF NOT EXISTS idx_streams_channel_id ON streams (channel_id);
CREATE INDEX IF NOT EXISTS idx_streams_started_at ON streams (started_at);

-- highlights
CREATE INDEX IF NOT EXISTS idx_highlights_stream_id ON highlights (stream_id);

-- subscription_logs
CREATE INDEX IF NOT EXISTS idx_subscription_logs_user_id      ON subscription_logs (user_id, subscribed_at DESC);
CREATE INDEX IF NOT EXISTS idx_subscription_logs_deleted_users ON subscription_logs (subscribed_at)
    WHERE user_id IS NULL;

-- stream_message_logs
CREATE INDEX IF NOT EXISTS idx_sml_channel_id     
ON stream_message_logs (channel_id);

CREATE INDEX IF NOT EXISTS idx_sml_stream_id      
ON stream_message_logs (stream_id);

CREATE INDEX IF NOT EXISTS idx_sml_created_at     
ON stream_message_logs (created_at);

CREATE INDEX IF NOT EXISTS idx_sml_status_pending 
ON stream_message_logs (status)
WHERE status = 'pending';

-- stream_message_logs (vector) — partial: skip pending rows with no embedding yet
CREATE INDEX IF NOT EXISTS idx_sml_embedding
ON stream_message_logs
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;

-- documents (vector)
CREATE INDEX IF NOT EXISTS documents_embedding_hnsw_idx
ON documents
USING hnsw (embedding vector_cosine_ops);

-- documents (topics array)
CREATE INDEX IF NOT EXISTS idx_documents_topics
ON documents
USING GIN (topics);
