import os
import sqlalchemy
from dotenv import load_dotenv

load_dotenv()

_engine: sqlalchemy.engine.Engine | None = None


def get_engine() -> sqlalchemy.engine.Engine:
    global _engine
    if _engine is None:
        host     = os.environ.get("DB_HOST", "localhost")
        port     = int(os.environ.get("DB_PORT", 5432))
        database = os.environ.get("DB_NAME", "dev_findata")
        user     = os.environ.get("DB_USER", "postgres")
        password = os.environ["DB_PASSWORD"]
        url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
        _engine = sqlalchemy.create_engine(url, pool_pre_ping=True)
    return _engine
