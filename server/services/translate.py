from google.cloud import translate
from server.db.db import conn
from psycopg2.extras import DictCursor


target_lang = 'en'


def run():
    translate_client = translate.TranslationServiceClient.from_service_account_json('env/affine-news-97580ef473e5.json')
    parent = translate_client.location_path("affine-news", "global")

    with conn.cursor(cursor_factory=DictCursor) as c:
        c.execute('''
            SELECT url, lang, keywords, title, text, title_translated FROM article
            WHERE title_translated is NULL        
        ''')

        results = c.fetchall()

    num_results = len(results)
    print('Number of articles to translate', num_results)

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
