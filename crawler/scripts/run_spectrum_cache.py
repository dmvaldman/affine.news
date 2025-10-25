#!/usr/bin/env python3
"""
Spectrum analysis caching cron job.
Runs after topic generation to precompute spectrum analysis for new topics.
"""
import os
import sys
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta
import time

# Add paths to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../web/api')))

from db.db import conn
from query2 import generate_sankey_data_with_llm_parallel, fetch_articles_for_query, NUM_WORKERS  # type: ignore
from spectrum_cache import cache_spectrum_analysis  # type: ignore

def get_topics_needing_spectrum_analysis():
    """
    Get topics from the last day that don't have cached spectrum analysis.
    """
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT dt.topic, DATE(dt.created_at) as topic_date, dt.created_at
                FROM daily_topics dt
                LEFT JOIN topic_spectrum_cache tsc ON dt.topic = tsc.topic AND DATE(dt.created_at) = tsc.topic_date
                WHERE dt.created_at >= NOW() - INTERVAL '1 day'
                AND tsc.topic IS NULL
                ORDER BY dt.created_at DESC
            """)
            return [(row['topic'], row['topic_date']) for row in cur.fetchall()]
    except Exception as e:
        print(f"Error fetching topics: {e}")
        return []

def precompute_spectrum_analysis(topics_with_dates):
    """
    Precompute spectrum analysis for topics by calling query2 functions directly.
    """
    if not topics_with_dates:
        print("No topics need spectrum analysis.")
        return

    date_end = datetime.now().strftime("%Y-%m-%d")
    date_start = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

    print(f"Precomputing spectrum analysis for {len(topics_with_dates)} topics...")
    print(f"Date range: {date_start} to {date_end}")

    successful = 0
    failed = 0

    for i, (topic, topic_date) in enumerate(topics_with_dates):
        try:
            print(f"[{i+1}/{len(topics_with_dates)}] Processing: {topic} (created: {topic_date})")

            # Fetch articles for this topic
            articles_data = fetch_articles_for_query(topic, date_start, date_end)

            if not articles_data:
                print(f"  ⚠ No articles found")
                failed += 1
                continue

            print(f"  Found {len(articles_data)} articles")

            # Generate spectrum analysis
            analysis_result = generate_sankey_data_with_llm_parallel(articles_data, NUM_WORKERS)

            if not analysis_result:
                print(f"  ✗ Failed to generate spectrum analysis")
                failed += 1
                continue

            # Format articles by country
            mapping_dict = {m.article_id: m.point_id for m in analysis_result.mappings}
            articles_by_iso = {}

            for idx, article in enumerate(articles_data):
                article_id_llm = idx + 1
                point_id = mapping_dict.get(article_id_llm)
                iso = article['iso']

                if iso not in articles_by_iso:
                    articles_by_iso[iso] = {
                        "country": article['country'],
                        "articles": [],
                        "summary": None
                    }

                articles_by_iso[iso]["articles"].append({
                    "title": article['title'],
                    "url": article['url'],
                    "publish_at": article['publish_at'],
                    "lang": article['lang'],
                    "point_id": point_id
                })

            # Add summaries from the analysis result
            print("  Adding country summaries...")
            summary_dict = {s.country: s.summary for s in analysis_result.country_summaries}
            for iso, country_data in articles_by_iso.items():
                country_name = country_data['country']
                country_data['summary'] = summary_dict.get(country_name)

            # Cache the results
            cache_spectrum_analysis(
                topic,
                analysis_result.spectrum_name,
                analysis_result.spectrum_description,
                [{"point_id": p.point_id, "label": p.label, "description": p.description}
                 for p in sorted(analysis_result.spectrum_points, key=lambda x: x.point_id)],
                articles_by_iso,
                str(topic_date)
            )

            print(f"  ✓ Successfully cached spectrum analysis")
            successful += 1

        except Exception as e:
            print(f"  ✗ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

        # Small delay between topics
        if i < len(topics_with_dates) - 1:
            time.sleep(2)

    print(f"\nSpectrum analysis precomputation complete:")
    print(f"  ✓ Successful: {successful}")
    print(f"  ✗ Failed: {failed}")
    print(f"  📊 Success rate: {successful/(successful+failed)*100:.1f}%")

def main():
    """Main function to run spectrum analysis caching."""
    print(f"Starting spectrum analysis caching at {datetime.now()}")

    try:
        # Get topics that need spectrum analysis
        topics_with_dates = get_topics_needing_spectrum_analysis()

        if topics_with_dates:
            precompute_spectrum_analysis(topics_with_dates)
        else:
            print("No new topics found that need spectrum analysis.")

        print(f"Spectrum analysis caching completed at {datetime.now()}")

    except Exception as e:
        print(f"Error in spectrum analysis caching: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
