import logging
import nltk
import os

from flask import Flask, request, render_template, Response, jsonify
from flask_executor import Executor
from server.db.initialize import init
from server.db.update import update
from server.services.crawl import run as run_crawl
from server.services.translate import run as run_translate
from server.services.query import run as run_query


app = Flask(__name__)
app.config['EXECUTOR_PROPAGATE_EXCEPTIONS'] = True

executor = Executor(app)
logger = logging.getLogger()


@app.before_first_request
def create_tables():
    # Create tables (if they don't already exist)
    # init()
    nltk.download('punkt')
    update()
    return True


@app.route('/')
def root():
    return render_template('index.html')


@app.route('/crawl', methods=['POST'])
def crawl():
    body = request.get_json(force=True)
    if 'max_articles' in body:
        max_articles = body['max_articles']
    else:
        max_articles = None

    print('max_articles:', max_articles)
    print('\n')

    executor.submit(run_crawl, max_articles)

    return Response(
        response="OK",
        status=200
    )


@app.route('/translate', methods=['POST'])
def translate():
    executor.submit(run_translate)
    return Response(
        response="OK",
        status=200
    )


@app.route('/query', methods=['GET'])
def query():
    query_str = request.args.get('query')
    date_start = request.args.get('date_start')
    date_end = request.args.get('date_end')

    print('query route hit with', query_str, date_start, date_end)
    query_result = run_query(query_str, date_start, date_end)

    print('result is')
    print(jsonify(query_result))
    print('')

    return jsonify(query_result)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True)
