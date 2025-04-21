import os
from sqla_wrapper import SQLAlchemy

db_url = os.getenv("DATABASE_URL", "sqlite:///localhost.sqlite")
db = SQLAlchemy(db_url)