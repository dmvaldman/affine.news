import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASS")
db_name = os.getenv("DB_NAME")
env = os.getenv("ENV")


if env == 'DEV':
    # local
    conn = psycopg2.connect(database=db_name, user=db_user, password=db_pass, host="127.0.0.1", port="5432")
elif env == 'PROD':
    # Remote
    conn = psycopg2.connect(database=db_name, user=db_user, password=db_pass,
                            host="/cloudsql/affine-news:us-central1:affine")


