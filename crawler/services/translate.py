from psycopg2.extras import DictCursor

from crawler.db.db import conn
from crawler.services.translator import get_translator, translate_text


target_lang = 'en'

def translate_paper(paper):
    """
    Finds all untranslated articles for a given paper and translates their titles.
    """
    try:
        translate_client = get_translator()
    except (ImportError, Exception) as e:
        print(f"Could not initialize translator, skipping translation. Error: {e}")
        return

    # Get articles to translate
    with conn.cursor(cursor_factory=DictCursor) as c:
        c.execute('''
            SELECT a.url, a.lang, a.title FROM article a
            JOIN paper p on p.uuid = a.paper_uuid
            WHERE a.title_translated IS NULL
            AND p.uuid=%s
        ''', (paper.uuid,))
        results = c.fetchall()

    num_results = len(results)
    if num_results > 0:
        print(f'Found {num_results} articles to translate for {paper}')

    for index, result in enumerate(results):
        source_lang = result['lang']
        title_to_translate = result['title']

        if not title_to_translate:
            print(f"Skipping article with no title: {result['url']}")
            continue

        translated_title = None
        if source_lang != target_lang:
            try:
                translated_title = translate_text(
                    translate_client,
                    title_to_translate,
                    target_lang=target_lang,
                    source_lang=source_lang
                )
            except Exception as e:
                print(f"Error translating article {result['url']}: {e}")
                continue # Skip this article
        else:
            # If the source is already in the target language, just copy the title
            translated_title = title_to_translate

        if translated_title:
            print(f"  -> Translated title for {result['url']}")
            with conn.cursor() as c:
                c.execute('''
                    UPDATE article SET title_translated=%s WHERE url=%s
                ''', (translated_title, result['url']))

    # Commit all translations for this paper in one transaction
    conn.commit()
    print(f'Finished translation for {paper}')
