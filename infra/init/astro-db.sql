-- =============================================================================
-- astro-db schema
-- =============================================================================
-- Sections:
--   1. Core entities       — users, channels, streams, highlights
--   2. Subscription system — subscription_plans, features,
--                            subscription_plan_features, subscription_logs
--   3. Ingestion pipeline  — stream_message_logs
-- =============================================================================


-- =============================================================================
-- 1. Core entities
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id                   BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email                VARCHAR(255) NOT NULL,
    password_hash        VARCHAR(255) NOT NULL,
    country_code         SMALLINT     NOT NULL DEFAULT 0,
    phone_number         VARCHAR(20)  NULL,
    fullname             VARCHAR(100) NOT NULL,
    gender               VARCHAR(15)  NOT NULL,
    address              VARCHAR(255) NOT NULL,
    additional_address   VARCHAR(255) NOT NULL,
    city                 VARCHAR(150) NOT NULL,
    zip_code             VARCHAR(10)  NOT NULL,
    region               VARCHAR(255) NOT NULL,
    country              VARCHAR(70)  NOT NULL,
    available_credits    NUMERIC(9,2) NOT NULL DEFAULT 0.00,
    subscription_plan_id SMALLINT     NOT NULL DEFAULT 1,
    is_verified          BOOLEAN      NOT NULL DEFAULT FALSE,
    joined_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ           DEFAULT NULL
);

COMMENT ON COLUMN users.id                  IS 'Auto-generated surrogate key.';
COMMENT ON COLUMN users.email               IS 'Unique login identifier; used for authentication and notifications.';
COMMENT ON COLUMN users.password_hash       IS 'Bcrypt/Argon2 hash of the user password; plaintext is never stored.';
COMMENT ON COLUMN users.country_code        IS 'ITU-T E.164 numeric dialing prefix (e.g. 1 for US), not an ISO alpha-2 code.';
COMMENT ON COLUMN users.phone_number        IS 'Full phone number including country code and formatting (e.g. ''+57 315 123 4567''). NULL if not provided.';
COMMENT ON COLUMN users.fullname            IS 'Display name as provided at registration.';
COMMENT ON COLUMN users.gender              IS 'Self-reported gender string (e.g. ''male'', ''female'', ''non-binary'').';
COMMENT ON COLUMN users.address             IS 'Primary street address line.';
COMMENT ON COLUMN users.additional_address  IS 'Apartment, suite, floor, or other secondary address line.';
COMMENT ON COLUMN users.city                IS 'City of residence.';
COMMENT ON COLUMN users.zip_code            IS 'Postal / ZIP code stored as text to preserve leading zeros (e.g. ''01234'' in New England, 6-digit codes in Colombia).';
COMMENT ON COLUMN users.region              IS 'State, province, or region.';
COMMENT ON COLUMN users.country             IS 'Full country name.';
COMMENT ON COLUMN users.available_credits   IS 'Prepaid credit balance in USD, used for pay-as-you-go features.';
COMMENT ON COLUMN users.subscription_plan_id IS 'Active plan; 1 = free tier. FK to subscription_plans.id.';
COMMENT ON COLUMN users.is_verified         IS 'TRUE once the user confirms their email address; unverified accounts have restricted access.';
COMMENT ON COLUMN users.joined_at           IS 'Timestamp of account creation.';
COMMENT ON COLUMN users.updated_at          IS 'Timestamp of the last profile change; NULL if never updated.';


CREATE TABLE IF NOT EXISTS channels (
    id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    platform    VARCHAR(50)  NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL,
    user_id     BIGINT       NOT NULL
);

COMMENT ON COLUMN channels.id          IS 'Auto-generated surrogate key.';
COMMENT ON COLUMN channels.name        IS 'Channel display name as it appears on the source platform.';
COMMENT ON COLUMN channels.description IS 'Optional free-text description of the channel.';
COMMENT ON COLUMN channels.platform    IS 'Source platform identifier (e.g. ''twitch'', ''youtube'').';
COMMENT ON COLUMN channels.created_at  IS 'Timestamp when the channel was registered in this system.';
COMMENT ON COLUMN channels.user_id     IS 'Owner of this channel. FK to users.id.';


CREATE TABLE IF NOT EXISTS streams (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title      TEXT        NOT NULL,
    duration   BIGINT      NOT NULL,
    user_id    BIGINT      NOT NULL,
    channel_id BIGINT      NOT NULL,
    started_at TIMESTAMPTZ NOT NULL
);

COMMENT ON COLUMN streams.id         IS 'Auto-generated surrogate key.';
COMMENT ON COLUMN streams.title      IS 'Stream title at the time of broadcast.';
COMMENT ON COLUMN streams.duration   IS 'Total stream length in seconds.';
COMMENT ON COLUMN streams.user_id    IS 'Streamer who ran the session. FK to users.id.';
COMMENT ON COLUMN streams.channel_id IS 'Channel the stream aired on. FK to channels.id.';
COMMENT ON COLUMN streams.started_at IS 'UTC timestamp when the stream went live.';


CREATE TABLE IF NOT EXISTS highlights (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    summary    TEXT,
    started_at TIMESTAMPTZ,
    ended_at   TIMESTAMPTZ,
    stream_id  BIGINT NOT NULL
);

COMMENT ON COLUMN highlights.id         IS 'Auto-generated surrogate key.';
COMMENT ON COLUMN highlights.summary    IS 'AI-generated or manually written description of the highlight segment.';
COMMENT ON COLUMN highlights.started_at IS 'Start of the highlighted segment within the stream.';
COMMENT ON COLUMN highlights.ended_at   IS 'End of the highlighted segment within the stream.';
COMMENT ON COLUMN highlights.stream_id  IS 'Parent stream this highlight belongs to. FK to streams.id.';


-- =============================================================================
-- 2. Subscription system
-- =============================================================================

CREATE TABLE IF NOT EXISTS subscription_plans (
    id    SMALLINT     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label VARCHAR(50)  NOT NULL DEFAULT 'free'
);

COMMENT ON COLUMN subscription_plans.id    IS 'Auto-generated surrogate key. ID 1 is reserved for the free tier.';
COMMENT ON COLUMN subscription_plans.label IS 'Human-readable tier name (e.g. ''free'', ''pro'', ''enterprise'').';


CREATE TABLE IF NOT EXISTS features (
    id   INT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(70) NOT NULL
);

COMMENT ON COLUMN features.id   IS 'Auto-generated surrogate key.';
COMMENT ON COLUMN features.name IS 'Unique feature identifier used in access-control checks (e.g. ''highlights'', ''chat_analysis'').';


CREATE TABLE IF NOT EXISTS subscription_plan_features (
    feature_id           INT      NOT NULL,
    subscription_plan_id SMALLINT NOT NULL,
    PRIMARY KEY (feature_id, subscription_plan_id)
);

COMMENT ON COLUMN subscription_plan_features.feature_id           IS 'FK to features.id.';
COMMENT ON COLUMN subscription_plan_features.subscription_plan_id IS 'FK to subscription_plans.id.';


CREATE TABLE IF NOT EXISTS subscription_logs (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              BIGINT      NOT NULL,
    subscription_plan_id BIGINT      NOT NULL,
    subscribed_at        TIMESTAMPTZ NOT NULL,
    action               VARCHAR(25) NOT NULL,
    reason               VARCHAR(250)
);

COMMENT ON COLUMN subscription_logs.id                   IS 'UUID primary key for idempotent event processing.';
COMMENT ON COLUMN subscription_logs.user_id              IS 'User whose subscription changed. FK to users.id.';
COMMENT ON COLUMN subscription_logs.subscription_plan_id IS 'Plan involved in this event. FK to subscription_plans.id.';
COMMENT ON COLUMN subscription_logs.subscribed_at        IS 'Timestamp when the action was recorded.';
COMMENT ON COLUMN subscription_logs.action               IS 'Lifecycle event type: ''subscribe'', ''cancel'', ''upgrade'', ''downgrade''.';
COMMENT ON COLUMN subscription_logs.reason               IS 'Optional human-readable reason for the action (e.g. cancellation survey answer).';


-- =============================================================================
-- 3. Ingestion pipeline
-- =============================================================================

CREATE TABLE IF NOT EXISTS stream_message_logs (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    twitch_msg_id     VARCHAR(64)  UNIQUE NOT NULL,
    content           TEXT         NOT NULL,
    username          VARCHAR(50)  NOT NULL,
    stream_id         INT          REFERENCES streams(id),
    channel_id        INT          REFERENCES channels(id),
    status            VARCHAR(15)  NOT NULL DEFAULT 'pending',
    moderation_status VARCHAR(20)           DEFAULT NULL,
    embedding         vector(1536),
    embedded_at       TIMESTAMPTZ           DEFAULT NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN stream_message_logs.id                IS 'UUID primary key for idempotent ingestion.';
COMMENT ON COLUMN stream_message_logs.twitch_msg_id     IS 'Twitch-assigned message ID; UNIQUE prevents duplicate ingestion.';
COMMENT ON COLUMN stream_message_logs.content           IS 'Raw chat message text as received from Twitch.';
COMMENT ON COLUMN stream_message_logs.username          IS 'Twitch username of the sender.';
COMMENT ON COLUMN stream_message_logs.stream_id         IS 'Stream during which the message was sent. FK to streams.id.';
COMMENT ON COLUMN stream_message_logs.channel_id        IS 'Channel the message belongs to. FK to channels.id.';
COMMENT ON COLUMN stream_message_logs.status            IS 'Ingestion pipeline state: ''pending'' (received) → ''embedded'' (vectorised).';
COMMENT ON COLUMN stream_message_logs.moderation_status IS 'Result from the OpenAI moderation gate (e.g. ''safe'', ''flagged''). NULL until checked.';
COMMENT ON COLUMN stream_message_logs.embedding         IS 'pgvector column storing the text-embedding-3-small (1536-dim) vector. NULL until embedded.';
COMMENT ON COLUMN stream_message_logs.embedded_at       IS 'Timestamp when the embedding was written. NULL while pending.';
COMMENT ON COLUMN stream_message_logs.created_at        IS 'Timestamp when the message was captured.';
