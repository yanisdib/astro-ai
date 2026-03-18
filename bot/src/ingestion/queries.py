"""
This is an inventory of queries to use for data manipulation in MessageBuffer.
Each constant is a usable SQL query for Postgres.
"""

INSERT_DOCUMENT = """
    INSERT INTO documents (
        message_id,
        content,
        embedding,
        user_id,
        username,
        channel_id,
        source,
        is_host,
        is_bot,
        is_moderator,
        is_verified,
        is_shared,
        intent_category,
        topics,
        created_at
    ) VALUES (
        %(message_id)s,
        %(content)s,
        %(embedding)s,
        %(user_id)s,
        %(username)s,
        %(channel_id)s,
        %(source)s,
        %(is_host)s,
        %(is_bot)s,
        %(is_moderator)s,
        %(is_verified)s,
        %(is_shared)s,
        %(intent_category)s,
        %(topics)s,
        %(created_at)s
    )
"""
