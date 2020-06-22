import requests
import datetime

url_base = 'http://localhost:8000/'
# url_base = 'https://affine-news.appspot.com/'

def crawl():
    url = url_base + 'crawl'
    payload = {'max_articles': 10}
    res = requests.post(url, json=payload)
    print(res)


def translate():
    url = url_base + 'translate'
    res = requests.post(url)
    print(res)


def query():
    url = url_base + 'query'
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
    crawl()
    # translate()
    # query()