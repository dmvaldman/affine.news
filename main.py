import datetime
from flask import Flask, request
from services.crawl import run as run_crawl
from services.translate import run as run_translate
from services.query import run as run_query

app = Flask(__name__)

@app.route('/crawl', methods=['POST'])
def crawl():
    max_articles = request.args.get('max_articles')
    run_crawl(max_artices=max_articles)

@app.route('/translate', methods=['POST'])
def translate():
    run_translate()

@app.route('/query', methods=['POST'])
def query():
    query_str = request.args.get('query')
    date_start = request.args.get('date_start')
    date_end = request.args.get('date_end')

    if not date_start:
        date_start = datetime.date.today() - datetime.timedelta(days=1)

    if not date_end:
        date_end = datetime.date.today().isoformat()

    run_query(date_start, date_end, query_str)