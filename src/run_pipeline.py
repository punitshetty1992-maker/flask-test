import os
from sqlalchemy import create_engine, text

def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL env var is missing")

    engine = create_engine(db_url)

    with engine.connect() as conn:
        val = conn.execute(text("select 1")).scalar()
        print("DB OK:", val)

if __name__ == "__main__":
    main()
