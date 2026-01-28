import sys
import time
from psycopg2.extras import DictCursor

from crawler.models.Paper import Papers
from crawler.db.db import conn
from crawler.services.translator import get_translator, translate_text, translate_batch


target_lang = 'en'

def get_papers() -> Papers:
    papers = Papers()
    papers.load()
    return papers

def translate_paper(paper):
    """
    Finds all untranslated articles for a given paper and translates their titles.
    """
    try:
        translate_client = get_translator()
    except (ImportError, Exception) as e:
        print(f"Could not initialize translator, skipping translation. Error: {e}")
        return

    # Get articles to translate (only from last 3 days to prioritize recent content)
    with conn.cursor(cursor_factory=DictCursor) as c:
        c.execute('''
            SELECT a.url, a.lang, a.title FROM article a
            JOIN paper p on p.uuid = a.paper_uuid
            WHERE a.title_translated IS NULL
            AND p.uuid=%s
            AND a.publish_at >= NOW() - INTERVAL '2 days'
        ''', (paper.uuid,))
        results = c.fetchall()

    num_results = len(results)
    if num_results > 0:
        print(f'Found {num_results} articles to translate for {paper}')

    # Prepare batch translation data
    texts_with_info = []
    url_map = []  # Map index to URL for updating

    for result in results:
        title_to_translate = result['title']
        if not title_to_translate:
            print(f"Skipping article with no title: {result['url']}")
            continue

        texts_with_info.append((title_to_translate, result['lang'], result['url']))
        url_map.append(result['url'])

    if texts_with_info:
        # Translate all titles in batches
        try:
            translated_titles = translate_batch(
                translate_client,
                texts_with_info,
                target_lang=target_lang
            )

            # Update database with translations
            with conn.cursor() as c:
                for url, translated_title in zip(url_map, translated_titles):
                    if translated_title:
                        c.execute('''
                            UPDATE article SET title_translated=%s WHERE url=%s
                        ''', (translated_title, url))
                        print(f"  -> Translated title for {url}")
        except Exception as e:
            print(f"Error translating batch for {paper}: {e}")
            # Fallback to individual translations if batch fails
            print("Falling back to individual translations...")
            for result in results:
                source_lang = result['lang']
                title_to_translate = result['title']

                if not title_to_translate:
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
                        continue
                else:
                    translated_title = title_to_translate

                if translated_title:
                    with conn.cursor() as c:
                        c.execute('''
                            UPDATE article SET title_translated=%s WHERE url=%s
                        ''', (translated_title, result['url']))

    # Commit all translations for this paper in one transaction
    conn.commit()
    print(f'Finished translation for {paper}')


def main():
    """
    Main function to run the translation process for all papers.
    - Fetches all paper UUIDs.
    - Iterates through each paper and translates untranslated articles.
    """
    start_time = time.time()
    print("Starting translation job...")

    papers = get_papers()

    if not papers:
        print("No papers found in the database to translate.")
        return

    print(f"Found {len(papers)} papers to process.")

    for paper in papers:
        try:
            translate_paper(paper)
        except Exception as e:
            print(f"An error occurred while processing paper {paper}: {e}", file=sys.stderr)
            # Continue to the next paper

    end_time = time.time()
    print("Translation job finished.")
    print(f"Total time elapsed: {end_time - start_time:.2f} seconds")


if __name__ == '__main__':
    main()
