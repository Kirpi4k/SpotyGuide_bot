import psycopg2
from config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT

conn = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT
)

cursor = conn.cursor()

def save_user_token(user_id, access_token, refresh_token):
    cursor.execute(
        """
        INSERT INTO spotify_tokens (user_id, access_token, refresh_token)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET access_token = EXCLUDED.access_token, refresh_token = EXCLUDED.refresh_token;
        """,
        (user_id, access_token, refresh_token)
    )
    conn.commit()

def get_user_token(user_id):
    cursor.execute(
        "SELECT access_token, refresh_token FROM spotify_tokens WHERE user_id=%s",
        (user_id,)
    )
    row = cursor.fetchone()
    return row if row else None