import sqlite3
import os
from google.cloud import translate

path = os.path.dirname(os.path.abspath(__file__))
db = os.path.join(path, '../db/paper.db')

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
c = conn.cursor()

target_lang = 'en'

def run():
    translate_client = translate.TranslationServiceClient.from_service_account_json('env/plural-news-1564928671096-8e6de93f2996.json')
    parent = translate_client.location_path("plural-news-1564928671096", "global")

    c.execute('''
        SELECT url, lang, keywords, title, text, title_translated FROM article
        WHERE keywords_translated is NULL        
    ''')

    results = c.fetchall()

    num_results = len(results)
    print('Number of articles to translate', num_results)

    for index, result in enumerate(results):
        if result['title_translated']:
            continue

        source_lang = result['lang']

        if source_lang != target_lang:
            to_translate = [
                result['title'],
                result['keywords']
            ]

            if not (result['title'] and result['keywords'] and result['text']):
                continue

            print('num keywords', len(result['keywords']))

            if len(result['title']) + len(result['keywords']) > 2000:
                print('length too long')
                continue

            keywords_translated = translate_client.translate_text(
                parent=parent,
                contents=to_translate,
                mime_type="text/plain",
                source_language_code=source_lang,
                target_language_code=target_lang)

            title_text = keywords_translated.translations[0].translated_text
            keywords_text = keywords_translated.translations[1].translated_text.lower()
            # text_translated = keywords_translated.translations[2].translated_text
        else:
            title_text = result['title']
            keywords_text = result['keywords'].lower()
            # text_translated = result['text']

        print(result['url'], title_text)

        c.execute('''
            UPDATE article SET 
                keywords_translated=:keywords_text,                  
                title_translated=:title_translated
            WHERE url=:url
        ''', {
            "keywords_text": keywords_text,
            "title_translated": title_text,
            "url": result['url']
        })

        conn.commit()

        if index % 10 == 0:
            print('Progress:', index/num_results)

    conn.commit()
    conn.close()
