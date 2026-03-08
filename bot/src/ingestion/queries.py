"""
This is an inventory of queries to use for data manipulation in MessageBuffer.
Each constant is a usable SQL query for Postgres.
"""

INSERT_DOCUMENT = """
    INSERT INTO documents (content, embedding, channel_id, source_type, created_at)
    VALUES (%(content)s, %(embedding)s, %(channel_id)s, %(source_type)s, %(created_at)s)
"""
