import os
from urllib.parse import quote_plus


def get_database_url() -> str:
    # Load .env if present (for local dev / Supabase credentials)
    try:
        from dotenv import load_dotenv

        # Override any exported env vars (common when experimenting in shells)
        load_dotenv(override=True)
    except Exception:
        pass

    # Or construct from parts (avoids URL-encoding pitfalls for passwords with '@', ':', etc.)
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "postgres")
    sslmode = os.getenv("DB_SSLMODE", "require")

    if host and password:
        user_enc = quote_plus(user)
        pass_enc = quote_plus(password)
        return (
            f"postgresql+psycopg2://{user_enc}:{pass_enc}@{host}:{port}/{name}"
            f"?sslmode={sslmode}"
        )

    # Prefer full URL if provided.
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    # Cloud-first default: env-driven. Fallback to local SQLite for dev/tests.
    return "sqlite:///./local.db"

