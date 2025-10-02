"""
Extract country references and sentiment from translated articles.
Updates the country_comparisons table with positive/negative/neutral counts.
"""
import sys
import time
from psycopg2.extras import DictCursor
from crawler.db.db import conn
from crawler.services.country_extractor import extract_country_and_sentiment


def main():
    """
    Finds articles that have been translated but not yet analyzed for country references,
    extracts target country and sentiment, and updates the country_reference table.
    """
    start_time = time.time()
    print("Starting country reference extraction job...")

    # Get articles that are translated but don't have country references yet
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("""
            SELECT
                a.url,
                a.title_translated,
                p.iso as source_country_iso
            FROM article a
            JOIN paper p ON p.uuid = a.paper_uuid
            LEFT JOIN article_country_reference acr ON acr.article_url = a.url
            WHERE a.title_translated IS NOT NULL
            AND a.title_translated != ''
            AND a.publish_at >= NOW() - INTERVAL '2 day'
            AND acr.article_url IS NULL  -- Only unprocessed articles
            ORDER BY a.publish_at DESC
        """)
        articles = cur.fetchall()

    if not articles:
        print("No translated articles found to process.")
        return

    print(f"Found {len(articles)} articles to analyze for country references.")

    processed = 0
    skipped = 0

    for article in articles:
        url = article['url']
        title = article['title_translated']
        source_iso = article['source_country_iso']

        if not title or not source_iso:
            skipped += 1
            continue

        # Extract target country and sentiment
        target_iso, favorability = extract_country_and_sentiment(title, source_iso)

        print(f"SRC: {source_iso}, TGT: {target_iso}, FAV: {favorability}, TITLE: {title}")

        if target_iso:
            # Insert into article_country_reference (idempotent)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO article_country_reference (
                        article_url,
                        source_country_iso,
                        target_country_iso,
                        favorability
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (article_url, target_country_iso)
                    DO UPDATE SET
                        favorability = EXCLUDED.favorability,
                        source_country_iso = EXCLUDED.source_country_iso
                """, (url, source_iso, target_iso, favorability))

            conn.commit()
            processed += 1

            if processed % 10 == 0:
                print(f"  Processed {processed} articles with country references...")
        else:
            skipped += 1

    # Refresh the materialized view with aggregated stats
    if processed > 0:
        print("\nRefreshing country_comparisons materialized view...")
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY country_comparisons")
        conn.commit()
        print("  ✓ Materialized view refreshed")

    end_time = time.time()
    print(f"\nCountry reference extraction complete:")
    print(f"  - Processed: {processed} articles with country references")
    print(f"  - Skipped: {skipped} articles (no foreign country or missing data)")
    print(f"  - Total time: {end_time - start_time:.2f} seconds")


if __name__ == '__main__':
    main()

