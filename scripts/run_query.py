#!/usr/bin/env python3
"""
Test script to run query2 logic locally.
"""
import sys
import os
from datetime import datetime, timedelta
import json

# Add paths to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../web/api')))

from query2 import execute as execute_query # type: ignore

def run_query(search_query: str, days_back: int = 3):
    """
    Run a query locally and print results.

    Args:
        search_query: The search query string
        days_back: Number of days to look back (default 3)
    """
    # Calculate date range
    date_end = datetime.now().strftime("%Y-%m-%d")
    date_start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    print(f"Query: {search_query}")
    print(f"Date range: {date_start} to {date_end}")
    print("-" * 60)

    # Execute the query
    result = execute_query(search_query, date_start, date_end)

    # Print results
    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"Spectrum: {result.get('spectrum_name')}")
    print(f"Description: {result.get('spectrum_description')}")
    print(f"Countries: {len(result.get('articles', {}))}")

    # Print spectrum points
    if result.get('spectrum_points'):
        print(f"\nSpectrum Points:")
        for point in result['spectrum_points']:
            print(f"  {point['point_id']}: {point['label']}")

    # Print countries with articles and summaries
    if result.get('articles'):
        print(f"\n{'='*60}")
        print(f"COUNTRIES")
        print(f"{'='*60}")

        for iso, data in sorted(result['articles'].items(), key=lambda x: len(x[1]['articles']), reverse=True):
            print(f"\n\n{data['country']} ({iso}): {len(data['articles'])} articles")

            # Show summary if available
            if data.get('summary'):
                print(f"\nSummary: {data['summary']}")

            # Show first 3 article titles
            print(f"\nTitles:")
            for article in data['articles'][:3]:
                print(f"  - {article['title']}")
            if len(data['articles']) > 3:
                print(f"  ... and {len(data['articles']) - 3} more")

    print("\n" + "=" * 60)

def main():
    """Main function."""
    # Edit these values to test different queries
    search_query = "Trump tariffs"
    days_back = 3

    run_query(search_query, days_back)

if __name__ == "__main__":
    main()

