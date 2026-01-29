"""
Spectrum analysis caching module for precomputed topic results.
"""
import json
import sys
import os
from psycopg.rows import dict_row
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Add crawler path to import db connection
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../crawler')))
from db.db import conn  # type: ignore

def cache_spectrum_analysis(topic: str, spectrum_name: str, spectrum_description: str,
                          spectrum_points: list, articles_by_country: dict,
                          topic_date: str) -> bool:
    """
    Cache spectrum analysis results in the database.

    Args:
        topic: The topic string
        spectrum_name: Name of the spectrum
        spectrum_description: Description of the spectrum
        spectrum_points: List of spectrum points
        articles_by_country: Articles grouped by country
        topic_date: Date the topic was created (YYYY-MM-DD)

    Returns:
        bool: True if cached successfully, False otherwise
    """
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO topic_spectrum_cache (
                    topic, spectrum_name, spectrum_description,
                    spectrum_points, articles_by_country, topic_date
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (topic, topic_date)
                DO UPDATE SET
                    spectrum_name = EXCLUDED.spectrum_name,
                    spectrum_description = EXCLUDED.spectrum_description,
                    spectrum_points = EXCLUDED.spectrum_points,
                    articles_by_country = EXCLUDED.articles_by_country,
                    created_at = NOW()
            """, (
                topic,
                spectrum_name,
                spectrum_description,
                json.dumps(spectrum_points),
                json.dumps(articles_by_country),
                topic_date
            ))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error caching spectrum analysis: {e}")
        return False

def get_cached_spectrum_analysis(topic: str, topic_date: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached spectrum analysis results from the database.

    Args:
        topic: The topic string
        topic_date: Date the topic was created (YYYY-MM-DD)

    Returns:
        Dict with cached results or None if not found
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT spectrum_name, spectrum_description, spectrum_points, articles_by_country
                FROM topic_spectrum_cache
                WHERE topic = %s AND topic_date = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (topic, topic_date))

            result = cur.fetchone()
            if result:
                return {
                    'spectrum_name': result['spectrum_name'],
                    'spectrum_description': result['spectrum_description'],
                    'spectrum_points': json.loads(result['spectrum_points']),
                    'articles': json.loads(result['articles_by_country'])
                }
            return None
    except Exception as e:
        print(f"Error retrieving cached spectrum analysis: {e}")
        return None

def is_topic_predefined(topic: str) -> bool:
    """
    Check if a topic is predefined (exists in daily_topics table).

    Args:
        topic: The topic string

    Returns:
        bool: True if topic is predefined, False otherwise
    """
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM daily_topics WHERE topic = %s
            """, (topic,))
            count = cur.fetchone()[0]
            return count > 0
    except Exception as e:
        print(f"Error checking if topic is predefined: {e}")
        return False
