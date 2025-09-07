from google.cloud import translate
from psycopg2.extras import DictCursor

from crawler.db.db import conn
from crawler.models.Paper import Papers


target_lang = 'en'
project = 'affine-news'
location = 'global'


def location_path(project_id, location):
    # might as well use an f-string, the new library supports python >=3.6
    return f"projects/{project_id}/locations/{location}"


def get_paper_uuids():
    papers = Papers()
    papers.load()

    uuids = [paper.uuid for paper in papers]
    return uuids


def run():
    paper_uuids = get_paper_uuids()
    for paper_uuid in paper_uuids:
        translate(paper_uuid)


def translate_paper_by_uuid(paper_uuid):
    translate_client = translate.TranslationServiceClient.from_service_account_json('env/affine-news-97580ef473e5.json')
    parent = location_path(project, location)

    with conn.cursor(cursor_factory=DictCursor) as c:
        c.execute('''
            SELECT a.url, a.lang, a.title, a.text, a.title_translated FROM article a
            JOIN paper p on p.uuid = a.paper_uuid
            WHERE title_translated is NULL
            AND p.uuid=%s
        ''', (paper_uuid, ))

        results = c.fetchall()

    num_results = len(results)
    print('Number of articles to translate', num_results, paper_uuid)

    for index, result in enumerate(results):
        if result['title_translated']:
            print('title already translated', result['url'])
            continue

        source_lang = result['lang']

        if source_lang != target_lang:
            to_translate = [
                result['title']
            ]

            if not result['title']:
                print('no title', result['url'])
                continue

            if len(result['title']) > 2000:
                print('length too long', result['url'])
                continue

            keywords_translated = translate_client.translate_text(
                parent=parent,
                contents=to_translate,
                mime_type="text/plain",
                source_language_code=source_lang,
                target_language_code=target_lang)

            title_text = keywords_translated.translations[0].translated_text
        else:
            title_text = result['title']

        print('translation:', result['url'], title_text)

        with conn.cursor(cursor_factory=DictCursor) as c:
            c.execute('''
                UPDATE article SET
                    title_translated=%s
                WHERE url=%s
            ''', (
                title_text,
                result['url']
            ))

        if index % 10 == 0:
            print('Progress:', index/num_results)

    print('done')
    conn.commit()
