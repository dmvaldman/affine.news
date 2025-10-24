#!/usr/bin/env python3
"""
Spectrum analysis caching cron job.
Runs after topic generation to precompute spectrum analysis for new topics.
"""
import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta
import requests
import time

# Add crawler directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db.db import conn

def get_topics_needing_spectrum_analysis():
    """
    Get topics from the last day that don't have cached spectrum analysis.
    """
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT dt.topic, DATE(dt.created_at) as topic_date
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
    Precompute spectrum analysis for topics by calling the query2 API.
    """
    if not topics_with_dates:
        print("No topics need spectrum analysis.")
        return

    api_base_url = "https://affine-news.vercel.app"
    date_end = datetime.now().strftime("%Y-%m-%d")
    date_start = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

    print(f"Precomputing spectrum analysis for {len(topics_with_dates)} topics...")
    print(f"Date range: {date_start} to {date_end}")
    print(f"API endpoint: {api_base_url}")

    successful = 0
    failed = 0

    for i, (topic, topic_date) in enumerate(topics_with_dates):
        try:
            print(f"[{i+1}/{len(topics_with_dates)}] Processing: {topic} (created: {topic_date})")

            # Call the query2 API endpoint
            url = f"{api_base_url}/api/query2"
            params = {
                'query': topic,
                'date_start': date_start,
                'date_end': date_end
            }

            # Add timeout and retry logic
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    response = requests.get(url, params=params, timeout=300)  # 5 minute timeout
                    break
                except requests.exceptions.Timeout:
                    if attempt < max_retries:
                        print(f"  ⚠ Timeout (attempt {attempt + 1}), retrying...")
                        time.sleep(10)  # Wait 10 seconds before retry
                        continue
                    else:
                        raise

            if response.status_code == 200:
                result = response.json()
                if result.get('spectrum_name') and result.get('articles'):
                    print(f"  ✓ Successfully cached spectrum analysis")
                    successful += 1
                else:
                    print(f"  ⚠ No spectrum data returned")
                    failed += 1
            else:
                print(f"  ✗ HTTP {response.status_code}: {response.text[:100]}")
                failed += 1

        except requests.exceptions.Timeout:
            print(f"  ✗ Timeout after {max_retries + 1} attempts")
            failed += 1
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Request error: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ Unexpected error: {e}")
            failed += 1

        # Small delay between requests to avoid overwhelming the API
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
