import os
import sys
from dotenv import load_dotenv

load_dotenv()

import psycopg2

database_url = os.environ.get('DATABASE_URL')
if not database_url:
    # Allow import for non-DB tasks, but fail on connect
    print('DATABASE_URL not set, DB connection will fail', file=sys.stderr)
    conn = None
else:
    try:
        conn = psycopg2.connect(database_url)
    except psycopg2.OperationalError as e:
        print(f"DB connection failed: {e}", file=sys.stderr)
        conn = None


