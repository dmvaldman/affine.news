import datetime
from services.query import run as run_query

query = 'corona'
today = datetime.date.today()
date_start = today - datetime.timedelta(days=3)
date_end = today - datetime.timedelta(days=0)

run_query(query, date_start, date_end, country='us')
