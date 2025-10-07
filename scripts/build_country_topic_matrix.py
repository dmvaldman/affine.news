"""
Build country × topic matrix from daily topics and spectrum analysis.
Saves as pandas DataFrame (CSV) with countries as rows, topics as columns.
"""
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from crawler.db.db import conn
from web.api.query2 import generate_sankey_data_with_llm_parallel


MATRIX_FILE = Path(__file__).parent.parent / "data" / "country_topic_matrix.csv"


def fetch_daily_topics(date: datetime) -> list[str]:
    """Fetch topics generated for a specific date"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT topic
            FROM daily_topics
            WHERE DATE(created_at) = %s
            ORDER BY id
        """, (date.date(),))
        return [row[0] for row in cur.fetchall()]


def analyze_topic(topic: str, date_start: str, date_end: str) -> dict:
    """
    Call query2 function directly for a topic and extract country positions.

    Returns:
        {"USA": 3.2, "RUS": 1.8, ...} - just the means
    """
    print(f"  Querying: {topic}")

    # Query articles directly from DB (limit to avoid slow queries)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                a.title_translated,
                a.title_embedding,
                p.iso as country_iso
            FROM article a
            JOIN paper p ON p.uuid = a.paper_uuid
            WHERE a.title_translated IS NOT NULL
            AND a.title_translated != ''
            AND a.title_embedding IS NOT NULL
            AND a.publish_at >= %s
            AND a.publish_at <= %s
            ORDER BY a.publish_at DESC
            LIMIT 50
        """, (date_start, date_end))
        articles_data = cur.fetchall()

    if not articles_data:
        print(f"  No articles found")
        return None

    # Convert to format expected by query2
    articles_list = [
        {
            'title': row[0],
            'title_embedding': row[1],
            'country': row[2]
        }
        for row in articles_data
    ]

    # Run spectrum analysis
    result = generate_sankey_data_with_llm_parallel(articles_list, num_workers=4)

    if not result or not result.spectrum_points:
        print(f"  No spectrum data returned")
        return None

    # Create mapping from article_id to country
    article_id_to_country = {}
    for i, article in enumerate(articles_list):
        article_id_to_country[i + 1] = article['country']  # article_id is 1-indexed

    # Calculate mean per country from mappings
    countries = {}
    country_point_ids = {}

    for mapping in result.mappings:
        country = article_id_to_country[mapping.article_id]
        point_id = mapping.point_id

        if country not in country_point_ids:
            country_point_ids[country] = []
        country_point_ids[country].append(point_id)

    # Calculate mean per country
    for country, point_ids in country_point_ids.items():
        if len(point_ids) < 3:  # Skip countries with too few articles
            continue

        countries[country] = float(np.mean(point_ids))

    return countries


def load_matrix() -> pd.DataFrame:
    """Load existing matrix from file"""
    if not MATRIX_FILE.exists():
        MATRIX_FILE.parent.mkdir(parents=True, exist_ok=True)
        return pd.DataFrame()

    return pd.read_csv(MATRIX_FILE, index_col=0)


def save_matrix(df: pd.DataFrame):
    """Save matrix to file"""
    df.to_csv(MATRIX_FILE)


def build_matrix_for_date(target_date: datetime = None):
    """
    Build country × topic matrix for a given date.

    Args:
        target_date: Date to process (default: today)
    """
    if target_date is None:
        target_date = datetime.now()

    date_str = target_date.strftime("%Y-%m-%d")
    date_end = target_date.strftime("%Y-%m-%d")
    date_start = (target_date - timedelta(days=3)).strftime("%Y-%m-%d")

    print(f"Building matrix for {date_str}")
    print(f"  Date range: {date_start} to {date_end}")

    # Fetch topics for this date
    topics = fetch_daily_topics(target_date)

    if not topics:
        print(f"No topics found for {date_str}")
        print("  Checking what dates have topics...")
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT DATE(created_at) as date FROM daily_topics ORDER BY date DESC LIMIT 10")
            dates = cur.fetchall()
            for date_row in dates:
                print(f"    {date_row[0]}")
        return

    print(f"  Found {len(topics)} topics")

    # Load existing matrix (countries × topics)
    df = load_matrix()

    # Analyze each topic (limit to 3 for debugging)
    topics_added = 0
    for topic in topics[:3]:
        # Skip if topic already exists
        if topic in df.columns:
            print(f"  Skipping '{topic}' (already exists)")
            continue

        result = analyze_topic(topic, date_start, date_end)

        if result:
            # Add new column for this topic
            df[topic] = pd.Series(result)
            print(f"    Added '{topic}' with {len(result)} countries")
            topics_added += 1
        else:
            print(f"    Skipped '{topic}' (no data)")

    # Save updated matrix
    save_matrix(df)
    print(f"\n✓ Matrix saved to {MATRIX_FILE}")
    print(f"  Shape: {df.shape[0]} countries × {df.shape[1]} topics")
    print(f"  Added {topics_added} new topics")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Build country × topic matrix')
    parser.add_argument('--date', type=str, help='Date to process (YYYY-MM-DD), default: today')
    args = parser.parse_args()

    target_date = datetime.strptime(args.date, "%Y-%m-%d") if args.date else None
    build_matrix_for_date(target_date)
    conn.close()

