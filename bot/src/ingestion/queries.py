"""
This is an inventory of queries to use for data manipulation in MessageBuffer.
Each constant is a usable SQL query for Postgres.
"""

INSERT_DOCUMENT = """
    INSERT INTO documents (
        message_id,
        message_content,
        shared_stream,
        channel_id,
        source,
        user_id,
        username,
        is_astro,
        is_bot,
        is_mod,
        is_broadcaster,
        is_verified,
        is_partner,
        is_affiliate,
        is_subscriber,
        with_prime,
        subscriber_tier,
        embedding,
        intent_category,
        topics,
        created_at
    ) VALUES (
        %(message_id)s,
        %(message_content)s,
        %(shared_stream)s,
        %(channel_id)s,
        %(source)s,
        %(user_id)s,
        %(username)s,
        %(is_astro)s,
        %(is_bot)s,
        %(is_mod)s,
        %(is_broadcaster)s,
        %(is_verified)s,
        %(is_partner)s,
        %(is_affiliate)s,
        %(is_subscriber)s,
        %(with_prime)s,
        %(subscriber_tier)s,
        %(embedding)s,
        %(intent_category)s,
        %(topics)s,
        %(created_at)s
    )
"""
