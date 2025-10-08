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
from web.api.query2 import fetch_articles_for_query, generate_sankey_data_with_llm_parallel


MATRIX_FILE = Path(__file__).parent.parent / "data" / "country_topic_matrix.csv"


def fetch_daily_topics(start_date: datetime = None, end_date: datetime = None) -> list[str]:
    """Fetch topics generated within a date range"""
    with conn.cursor() as cur:
        if start_date and end_date:
            cur.execute("""
                SELECT topic
                FROM daily_topics
                WHERE DATE(created_at) BETWEEN %s AND %s
                ORDER BY id
            """, (start_date.date(), end_date.date()))
        elif start_date:
            cur.execute("""
                SELECT topic
                FROM daily_topics
                WHERE DATE(created_at) >= %s
                ORDER BY id
            """, (start_date.date(),))
        elif end_date:
            cur.execute("""
                SELECT topic
                FROM daily_topics
                WHERE DATE(created_at) <= %s
                ORDER BY id
            """, (end_date.date(),))
        else:
            # Default to last 7 days
            cur.execute("""
                SELECT topic
                FROM daily_topics
                WHERE DATE(created_at) >= %s
                ORDER BY id
            """, ((datetime.now() - timedelta(days=7)).date(),))
        return [row[0] for row in cur.fetchall()]


def analyze_topic(topic: str, date_start: str, date_end: str) -> dict:
    """
    Call query2 function directly for a topic and extract country positions.

    Returns:
        {"USA": 3.2, "RUS": 1.8, ...} - just the means
    """
    print(f"  Querying: {topic}")

    # Fetch articles using semantic similarity
    articles_data = fetch_articles_for_query(topic, date_start, date_end)

    if not articles_data:
        print(f"  No articles found")
        return None

    # Convert to format expected by generate_sankey_data_with_llm_parallel
    articles_list = [
        {
            'title': article['title'],
            'title_embedding': None,  # Not needed for spectrum analysis
            'country': article['iso']
        }
        for article in articles_data
    ]

    # Calculate dynamic number of workers (max 30 articles per worker)
    num_articles = len(articles_list)
    num_workers = max(1, (num_articles + 29) // 30)  # Ceiling division
    print(f"  Using {num_workers} workers for {num_articles} articles")

    # Run spectrum analysis
    result = generate_sankey_data_with_llm_parallel(articles_list, num_workers=num_workers)

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


def build_matrix_for_date(start_date: datetime = None, end_date: datetime = None):
    """
    Build country × topic matrix for a given date range.

    Args:
        start_date: Start date for topics and articles (default: today - 3 days)
        end_date: End date for topics and articles (default: today)
    """
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=3)

    date_start = start_date.strftime("%Y-%m-%d")
    date_end = end_date.strftime("%Y-%m-%d")

    print(f"Building matrix from {date_start} to {date_end}")

    # Fetch topics for this date range
    topics = fetch_daily_topics(start_date, end_date)

    if not topics:
        print(f"No topics found for the specified date range")
        return

    print(f"  Found {len(topics)} topics")

    # Load existing matrix (countries × topics)
    df = load_matrix()

    topics_added = 0
    for topic in topics:
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
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD), default: today - 3 days')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD), default: today')
    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d") if args.start_date else None
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d") if args.end_date else None

    build_matrix_for_date(start_date, end_date)
    conn.close()

