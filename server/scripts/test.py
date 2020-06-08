import requests
import datetime


def crawl():
    url = 'http://localhost:8000/crawl'
    payload = {'max_articles': 10}
    res = requests.post(url, json=payload)
    print(res)


def translate():
    url = 'http://localhost:8000/translate'
    res = requests.post(url)
    print(res)


def query():
    url = 'http://localhost:8000/query'
    query_str = 'news'
    today = datetime.date.today()
    date_start = today - datetime.timedelta(days=1)
    date_end = today - datetime.timedelta(days=0)

    params = {
        'query': query_str,
        'date_start': str(date_start),
        'date_end': str(date_end)
    }

    res = requests.get(url, params=params)
    print(res)


if __name__ == '__main__':
    # crawl()
    # translate()
    query()