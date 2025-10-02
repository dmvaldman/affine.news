"""
Service for extracting target countries and sentiment from news articles using LLM.
"""
import os
import google.generativeai as genai
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")

genai.configure(api_key=GEMINI_API_KEY)


# Structured output schema
class CountryReference(BaseModel):
    target_country_iso: Optional[str]  # 3-letter ISO code or None
    favorability: Optional[int]  # -1, 0, or 1


def extract_country_and_sentiment(title: str, source_country_iso: str) -> tuple[str | None, int]:
    """
    Extract the main foreign country being discussed and sentiment toward it.

    Args:
        title: Translated article title
        source_country_iso: ISO code of the country publishing the article

    Returns:
        Tuple of (target_country_iso, favorability) where:
        - target_country_iso is a 3-letter ISO code or None
        - favorability is 1 (positive), -1 (negative), or 0 (neutral)
    """

    prompt = f"""Analyze this news article title and extract:
1. The main FOREIGN country being discussed (not the source country {source_country_iso})
2. The sentiment/favorability toward that country

e.g., "Charlie Kirk's death: What he said before the fatal shooting" -> "USA, 0"

Article title: "{title}"

Rules:
- Only identify ONE foreign country (the most prominent one)
- You are only given the title, so must infer the country as many titles are implicit, naming only people, events, regions, etc.
- Use ISO 3166-1 alpha-3 country codes (e.g., USA, CHN, RUS, JPN)
- Set target_country_iso to null if no foreign country is mentioned or if the article is about {source_country_iso} itself
- ALWAYS set favorability: 1 if positive/supportive, -1 if negative/critical, 0 if neutral/factual or if no foreign country
- Both fields are required in the response"""

    try:
        model = genai.GenerativeModel(
            'gemini-2.5-flash-lite',
            generation_config=genai.GenerationConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=CountryReference,
            )
        )

        response = model.generate_content(prompt)
        print(f"  LLM response: {response.text}")

        # Parse JSON manually to handle missing fields
        import json
        json_data = json.loads(response.text)
        target_iso = json_data.get('target_country_iso')
        favorability = json_data.get('favorability', 0)  # Default to 0 if missing

        # Validate target_country_iso (must be 3 characters or None)
        if target_iso and len(target_iso) != 3:
            print(f"Warning: Invalid ISO code '{target_iso}', setting to None")
            target_iso = None

        # Validate favorability
        if favorability not in [-1, 0, 1]:
            print(f"Warning: Invalid favorability '{favorability}', defaulting to 0")
            favorability = 0

        return target_iso, favorability

    except Exception as e:
        print(f"Error extracting country/sentiment: {e}")
        return None, 0


def batch_extract_country_sentiment(articles: list[dict]) -> list[dict]:
    """
    Extract country references and sentiment for multiple articles.

    Args:
        articles: List of dicts with 'title_translated' and 'source_country_iso'

    Returns:
        List of dicts with added 'target_country_iso' and 'favorability' fields
    """
    results = []

    for article in articles:
        target_country, favorability = extract_country_and_sentiment(
            article['title_translated'],
            article['source_country_iso']
        )

        results.append({
            **article,
            'target_country_iso': target_country,
            'favorability': favorability
        })

    return results

