import logging
import nltk
import json

from flask import Flask, request, render_template, Response, jsonify
from flask_executor import Executor
from server.db.initialize import init
from server.db.update import update
from server.services.crawl import get_paper_uuids, crawl_paper_by_uuid
from server.services.translate import translate_paper_by_uuid
from server.services.query import run as run_query
from google.cloud import tasks_v2

app = Flask(__name__)
app.config['EXECUTOR_PROPAGATE_EXCEPTIONS'] = True

project = 'affine-news'
queue = 'crawl'
location = 'us-central1'

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

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(project, location, queue)

    paper_uuids = get_paper_uuids()
    for paper_uuid in paper_uuids:
        url = 'https://affine-news.appspot.com/crawl/' + paper_uuid
        payload = {'max_articles': max_articles}
        payload = json.dumps(payload)
        converted_payload = payload.encode()

        task = {
            'http_request': {
                'http_method': 'POST',
                'url': url,
                'headers': {'Content-type': 'application/json'},
                'body': converted_payload
            }
        }

        response = client.create_task(parent, task)
        print('Created task {}'.format(response.name))

    return Response(
        response="OK",
        status=200
    )


@app.route('/crawl/<uuid>', methods=['POST'])
def crawl_paper(uuid):
    body = request.get_json(force=True)
    print('Received task with payload: {}'.format(body))

    if 'max_articles' in body:
        max_articles = body['max_articles']
    else:
        max_articles = None

    # executor.submit(crawl_paper_by_uuid, uuid, max_articles=max_articles)
    crawl_paper_by_uuid(uuid, max_articles=max_articles)

    return Response(
        response="OK",
        status=200
    )


@app.route('/translate', methods=['POST'])
def translate():
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(project, location, queue)

    paper_uuids = get_paper_uuids()
    for paper_uuid in paper_uuids:
        url = 'https://affine-news.appspot.com/translate/' + paper_uuid

        task = {
            'http_request': {
                'http_method': 'POST',
                'url': url
            }
        }

        response = client.create_task(parent, task)
        print('Created task {}'.format(response.name))

    return Response(
        response="OK",
        status=200
    )


@app.route('/translate/<uuid>', methods=['POST'])
def translate_paper(uuid):
    translate_paper_by_uuid(uuid)
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
