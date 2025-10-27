from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
import os
import psycopg2
from psycopg2.extras import DictCursor
from pgvector.psycopg2 import register_vector
import google.generativeai as genai
from pydantic import BaseModel
import numpy as np
import hashlib
from concurrent.futures import ThreadPoolExecutor
import random

# Cache functions using DATABASE_URL directly
def get_cached_spectrum_analysis(topic, topic_date):
    try:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            return None
        with psycopg2.connect(db_url) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("""
                    SELECT spectrum_name, spectrum_description, spectrum_points, articles_by_country
                    FROM topic_spectrum_cache
                    WHERE topic = %s AND topic_date = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (topic, topic_date))
                result = cur.fetchone()
                if result:
                    # spectrum_points and articles_by_country are already parsed as dicts/lists by psycopg2 JSONB
                    return {
                        'spectrum_name': result['spectrum_name'],
                        'spectrum_description': result['spectrum_description'],
                        'spectrum_points': result['spectrum_points'] if isinstance(result['spectrum_points'], list) else json.loads(result['spectrum_points']),
                        'articles': result['articles_by_country'] if isinstance(result['articles_by_country'], dict) else json.loads(result['articles_by_country'])
                    }
        return None
    except Exception as e:
        print(f"Cache lookup error: {e}")
        return None

def is_topic_predefined(topic):
    try:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            return False
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM daily_topics WHERE topic = %s", (topic,))
                return cur.fetchone()[0] > 0
    except Exception as e:
        print(f"Topic check error: {e}")
        return False

def cache_spectrum_analysis(topic, spectrum_name, spectrum_description, spectrum_points, articles_by_country, topic_date):
    try:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            return
        with psycopg2.connect(db_url) as conn:
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
                """, (topic, spectrum_name, spectrum_description,
                      json.dumps(spectrum_points), json.dumps(articles_by_country), topic_date))
                conn.commit()
    except Exception as e:
        print(f"Cache write error: {e}")

SIMILARITY_THRESHOLD = 0.63
NUM_WORKERS = 4  # Number of parallel workers for article classification
MIN_ARTICLES_PER_COUNTRY = 3  # Minimum articles to include a country

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set")

genai.configure(api_key=GEMINI_API_KEY)

# --- LLM Structured Output Schemas ---
class SpectrumPoint(BaseModel):
    point_id: int
    label: str
    description: str  # Brief description of this viewpoint

class ArticleSpectrumMapping(BaseModel):
    article_id: int
    point_id: int

class CountrySummaryItem(BaseModel):
    country: str
    summary: str

class LlmSankeyResult(BaseModel):
    spectrum_name: str
    spectrum_description: str
    spectrum_points: list[SpectrumPoint]
    mappings: list[ArticleSpectrumMapping]
    country_summaries: list[CountrySummaryItem] = []


def generate_country_summary_simple(country_name: str, articles: list) -> str:
    """
    Generate a simple summary for a country's articles (for uncached queries).
    """
    if not articles:
        return None

    # Limit to 10 articles for prompt size
    sample_articles = articles[:10]

    prompt = f"""Analyze news headlines from {country_name} and write a 1-3 sentence summary (max 80 words).

Describe the main themes or narrative framing in these headlines:
{chr(10).join(f"- {article['title']}" for article in sample_articles)}

Write only the summary, nothing else."""

    try:
        client = genai.GenerativeModel('gemini-2.5-flash-lite')
        response = client.generate_content(prompt)
        summary = response.text.strip()
        return summary if summary else None
    except Exception as e:
        print(f"Error generating summary for {country_name}: {e}")
        return None

def generate_country_summaries_parallel(articles_by_iso: dict, max_workers: int = 4) -> None:
    """
    Generate summaries for countries with 3+ articles in parallel.
    Updates articles_by_iso dict in place.
    """
    print("Generating country summaries in parallel...")

    # Find countries that need summaries
    countries_to_summarize = [
        (iso, country_data['country'], country_data['articles'])
        for iso, country_data in articles_by_iso.items()
        if len(country_data['articles']) >= 3
    ]

    if countries_to_summarize:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(countries_to_summarize))) as executor:
            # Use map to process all countries in parallel
            summaries = executor.map(
                lambda x: generate_country_summary_simple(x[1], x[2]),
                countries_to_summarize
            )

            # Assign summaries back to articles_by_iso
            for (iso, _, _), summary in zip(countries_to_summarize, summaries):
                articles_by_iso[iso]['summary'] = summary

    # Set None for countries with < 3 articles
    for iso, country_data in articles_by_iso.items():
        if len(country_data['articles']) < 3:
            country_data['summary'] = None

def generate_country_summaries_batch(articles_data: list, mappings: list[ArticleSpectrumMapping],
                                     spectrum_name: str, spectrum_points: list[SpectrumPoint]) -> list[CountrySummaryItem]:
    """
    Generate summaries for all countries in a single LLM call.
    """
    # Group articles by country with their classifications
    countries_data = {}
    mapping_dict = {m.article_id: m.point_id for m in mappings}

    for i, article in enumerate(articles_data):
        article_id = i + 1
        point_id = mapping_dict.get(article_id)
        country = article['country']

        if country not in countries_data:
            countries_data[country] = {
                'articles': [],
                'point_ids': []
            }

        countries_data[country]['articles'].append(article)
        if point_id is not None:
            countries_data[country]['point_ids'].append(point_id)

    # Filter countries with at least 3 articles
    countries_to_summarize = {
        country: data for country, data in countries_data.items()
        if len(data['articles']) >= 3 and len(data['point_ids']) > 0
    }

    if not countries_to_summarize:
        return []

    # Calculate averages
    country_avgs = {}
    for country, data in countries_to_summarize.items():
        country_avgs[country] = sum(data['point_ids']) / len(data['point_ids'])

    overall_avg = sum(country_avgs.values()) / len(country_avgs)
    sorted_points = sorted(spectrum_points, key=lambda x: x.point_id)

    # Build prompt for all countries
    prompt_parts = [
        f"You are analyzing international news coverage about: {spectrum_name}",
        f"",
        f"The political spectrum has {len(spectrum_points)} points:",
    ]

    for point in sorted_points:
        prompt_parts.append(f"  {point.point_id}. {point.label}: {point.description}")

    prompt_parts.extend([
        "",
        f"Overall average position across all countries: {overall_avg:.1f}",
        "",
        "For each country below, write a 1-2 sentence summary (max 40 words) that:",
        "1. Describes the main narrative or framing in that country's coverage",
        "2. Notes how it compares to other countries if notably different",
        "",
        "Countries and their coverage:",
        ""
    ])

    for country, data in countries_to_summarize.items():
        avg = country_avgs[country]
        relative = "similar" if abs(avg - overall_avg) < 0.3 else ("lower" if avg < overall_avg else "higher")

        prompt_parts.append(f"--- {country} ---")
        prompt_parts.append(f"Position: {avg:.1f} ({relative} than average)")
        prompt_parts.append(f"Articles ({len(data['articles'])}):")
        for article in data['articles'][:8]:  # Limit to 8 articles per country
            prompt_parts.append(f"  - {article['title']}")
        prompt_parts.append("")

    prompt = "\n".join(prompt_parts)

    try:
        client = genai.GenerativeModel('gemini-2.5-flash-lite')
        response = client.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=list[CountrySummaryItem]
            )
        )
        summaries = [CountrySummaryItem(**s) for s in json.loads(response.text)]
        print(f"Generated {len(summaries)} country summaries")
        return summaries
    except Exception as e:
        print(f"Error generating country summaries: {e}")
        return []

def define_spectrum(articles_data: list) -> tuple[str, str, list[SpectrumPoint]] | None:
    """
    Phase 1: Define the spectrum using a sample of articles.
    Returns (spectrum_name, spectrum_description, spectrum_points) or None.
    """
    print("\nPhase 1: Defining spectrum...")

    # Sample diverse articles (max 50 for speed)
    sample_size = min(50, len(articles_data))
    sample = random.sample(articles_data, sample_size)

    prompt_parts = [
        "You are a political analyst analyzing international news coverage.",
        "Below are headlines from various countries about the same topic.",
        "Your task:",
        "1. Identify the single MOST IMPORTANT political dimension or axis of debate in these headlines.",
        "2. Give this spectrum a clear name and brief description.",
        "3. Define an ordered political spectrum of 2 to 4 points for this dimension.",
        "   The spectrum must span from one extreme viewpoint to the opposite.",
        "4. For each point, provide:",
        "   - point_id: sequential number (1, 2, 3, etc.)",
        "   - label: concise 2-8 word label",
        "   - description: 1-2 sentence explanation of this viewpoint",
        "---",
        "HEADLINES:"
    ]

    for i, article in enumerate(sample):
        prompt_parts.append(f"{i+1}. {article['title']} ({article['country']})")

    prompt = "\n".join(prompt_parts)

    class SpectrumDefinition(BaseModel):
        spectrum_name: str
        spectrum_description: str
        spectrum_points: list[SpectrumPoint]

    try:
        client = genai.GenerativeModel('gemini-2.5-flash')
        response = client.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=SpectrumDefinition
            )
        )
        result = SpectrumDefinition(**json.loads(response.text))
        print(f"Spectrum defined: {result.spectrum_name}")
        return (result.spectrum_name, result.spectrum_description, result.spectrum_points)
    except Exception as e:
        print(f"Error defining spectrum: {e}")
        return None


def classify_articles_batch(batch: list, batch_start_id: int, spectrum_points: list[SpectrumPoint]) -> list[ArticleSpectrumMapping]:
    """
    Phase 2: Classify a batch of articles to the predefined spectrum.
    """
    if not batch:
        return []

    prompt_parts = [
        "You are classifying news headlines to a predefined political spectrum.",
        f"The spectrum has {len(spectrum_points)} points:",
        ""
    ]

    for point in sorted(spectrum_points, key=lambda x: x.point_id):
        prompt_parts.append(f"Point {point.point_id}: {point.label}")

    prompt_parts.extend([
        "",
        "Classify each headline below to the most appropriate point on this spectrum.",
        "---",
        "HEADLINES:"
    ])

    for i, article in enumerate(batch):
        article_num = batch_start_id + i + 1
        prompt_parts.append(f"{article_num}. {article['title']}")

    prompt = "\n".join(prompt_parts)

    try:
        client = genai.GenerativeModel('gemini-2.5-flash')
        response = client.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=list[ArticleSpectrumMapping]
            )
        )
        return [ArticleSpectrumMapping(**m) for m in json.loads(response.text)]
    except Exception as e:
        print(f"Error classifying batch: {e}")
        return []


def fetch_articles_for_query(search_query: str, date_start: str, date_end: str) -> list[dict]:
    """
    Fetch articles matching a search query using semantic similarity.

    Args:
        search_query: The query to search for
        date_start: Start date (YYYY-MM-DD)
        date_end: End date (YYYY-MM-DD)

    Returns:
        List of article dictionaries with metadata
    """
    try:
        # 1. Embed the search query
        query_embedding_response = genai.embed_content(
            model="models/embedding-001",
            content=search_query,
            task_type="retrieval_query"
        )
        query_embedding = query_embedding_response['embedding']

        # 2. Query the database
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL not set")

        articles_data = []
        with psycopg2.connect(db_url) as conn:
            register_vector(conn)
            with conn.cursor(cursor_factory=DictCursor) as cur:
                # Fetch paper metadata
                cur.execute("SELECT uuid, iso, country, lang FROM paper")
                papers_data = {row['uuid']: {'iso': row['iso'], 'country': row['country'], 'lang': row['lang']} for row in cur.fetchall()}

                # Query articles WITHOUT embeddings (only similarity score)
                cur.execute(
                    """
                    SELECT
                        url,
                        title_translated,
                        paper_uuid,
                        publish_at,
                        lang,
                        1 - (title_embedding <=> %s) AS similarity
                    FROM article
                    WHERE
                        publish_at BETWEEN %s AND %s
                        AND title_embedding IS NOT NULL
                        AND 1 - (title_embedding <=> %s) > %s
                    ORDER BY similarity DESC
                    LIMIT 200;
                    """,
                    (np.array(query_embedding), date_start, date_end, np.array(query_embedding), SIMILARITY_THRESHOLD)
                )
                results = cur.fetchall()

                for row in results:
                    paper_info = papers_data.get(row['paper_uuid'])
                    if paper_info:
                        articles_data.append({
                            "title": row['title_translated'],
                            "url": row['url'],
                            "iso": paper_info['iso'],
                            "country": paper_info['country'],
                            "publish_at": row['publish_at'].isoformat() if row['publish_at'] else None,
                            "lang": row['lang'] if row['lang'] else paper_info['lang'],
                            "similarity": float(row['similarity'])
                        })

        # Filter out countries with < MIN_ARTICLES_PER_COUNTRY articles
        articles_by_iso_temp = {}
        for article in articles_data:
            iso = article['iso']
            if iso not in articles_by_iso_temp:
                articles_by_iso_temp[iso] = []
            articles_by_iso_temp[iso].append(article)

        filtered_articles_data = []
        for iso, articles in articles_by_iso_temp.items():
            if len(articles) >= MIN_ARTICLES_PER_COUNTRY:
                filtered_articles_data.extend(articles)

        return filtered_articles_data

    except Exception as e:
        print(f"Error fetching articles: {e}")
        return []


def generate_sankey_data_with_llm_parallel(articles_data: list, num_workers: int = 4) -> LlmSankeyResult | None:
    """
    Three-phase approach:
    1. Define spectrum using sample of articles
    2. Classify all articles in parallel batches
    3. Generate country summaries in a single batch
    """
    # Phase 1: Define spectrum
    spectrum_result = define_spectrum(articles_data)
    if not spectrum_result:
        return None

    spectrum_name, spectrum_description, spectrum_points = spectrum_result

    # Phase 2: Classify articles in parallel batches
    print(f"\nPhase 2: Classifying {len(articles_data)} articles using {num_workers} workers...")
    batch_size = max(10, len(articles_data) // num_workers)  # At least 10 per batch
    batches = []
    for i in range(0, len(articles_data), batch_size):
        batch = articles_data[i:i+batch_size]
        batches.append((batch, i))

    all_mappings = []
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(classify_articles_batch, batch, start_id, spectrum_points)
            for batch, start_id in batches
        ]
        for future in futures:
            mappings = future.result()
            all_mappings.extend(mappings)

    print(f"Classified {len(all_mappings)} articles")

    # Phase 3: Generate country summaries
    print("\nPhase 3: Generating country summaries...")
    country_summaries = generate_country_summaries_batch(
        articles_data, all_mappings, spectrum_name, spectrum_points
    )

    return LlmSankeyResult(
        spectrum_name=spectrum_name,
        spectrum_description=spectrum_description,
        spectrum_points=spectrum_points,
        mappings=all_mappings,
        country_summaries=country_summaries
    )


def execute(search_query: str, date_start: str, date_end: str) -> dict:
    """
    Execute a query and return the response data.
    This is the main logic that can be called directly or via HTTP handler.

    Returns:
        dict: The final response with spectrum analysis or article counts
    """
    # 1. Check cache first to avoid expensive DB query
    print(f"Step 1: Checking cache for query='{search_query}', date_end='{date_end}'...")
    cached_result = get_cached_spectrum_analysis(search_query, date_end)
    print(f"Cache result: {cached_result is not None} (type: {type(cached_result)})")

    if cached_result:
        print("✓ Using cached results")
        return cached_result

    # 2. Cache miss - fetch articles using semantic similarity
    print("✗ No cache found, fetching articles...")
    articles_data = fetch_articles_for_query(search_query, date_start, date_end)

    if not articles_data:
        return {
            "spectrum_name": None,
            "spectrum_description": None,
            "spectrum_points": [],
            "articles": {}
        }

    print(f"Found {len(articles_data)} articles.")
    print("✗ No cache found, using article count as spectrum...")
    # 4. Use article count as the spectrum dimension (no LLM calls)
    print("Step 4: Creating article count spectrum...")

    # Group articles by ISO
    articles_by_iso = {}
    for article in articles_data:
        iso = article['iso']

        if iso not in articles_by_iso:
            articles_by_iso[iso] = {
                "country": article['country'],
                "articles": [],
                "summary": None  # No summary for uncached queries
            }

        articles_by_iso[iso]["articles"].append({
            "title": article['title'],
            "url": article['url'],
            "publish_at": article['publish_at'],
            "lang": article['lang'],
            "point_id": None  # No classification for uncached queries
        })

    # Calculate article counts per country
    article_counts = [len(data['articles']) for data in articles_by_iso.values()]
    max_count = max(article_counts) if article_counts else 1
    min_count = min(article_counts) if article_counts else 0

    # Normalize counts to 1-4 scale
    for iso, country_data in articles_by_iso.items():
        count = len(country_data['articles'])
        if max_count > min_count:
            # Map count to 1-4 scale
            normalized = 1 + (count - min_count) / (max_count - min_count) * 3
            # Round to nearest integer (1, 2, 3, or 4)
            point_id = int(round(normalized))
        else:
            point_id = 1  # All countries have same count

        # Assign point_id to each article
        for article in country_data['articles']:
            article['point_id'] = point_id

    # Create spectrum points representing exact article counts
    spectrum_name = "Article Volume"
    spectrum_description = "Number of articles about this topic"

    # Calculate evenly spaced steps from min to max
    if max_count > min_count:
        step1 = min_count
        step2 = min_count + int((max_count - min_count) / 3)
        step3 = min_count + int(2 * (max_count - min_count) / 3)
        step4 = max_count
    else:
        step1 = step2 = step3 = step4 = min_count

    spectrum_points = [
        SpectrumPoint(point_id=1, label=f"{step1} article{'s' if step1 != 1 else ''}", description=""),
        SpectrumPoint(point_id=2, label=f"{step2} articles", description=""),
        SpectrumPoint(point_id=3, label=f"{step3} articles", description=""),
        SpectrumPoint(point_id=4, label=f"{step4} articles", description="")
    ]

    # Generate summaries for countries with 3+ articles (parallel LLM calls)
    generate_country_summaries_parallel(articles_by_iso, max_workers=4)

    final_response = {
        "spectrum_name": spectrum_name,
        "spectrum_description": spectrum_description,
        "spectrum_points": [
            {"point_id": p.point_id, "label": p.label, "description": p.description}
            for p in sorted(spectrum_points, key=lambda x: x.point_id)
        ],
        "articles": articles_by_iso
    }

    # Note: We don't cache uncached queries since they lack full classification
    return final_response


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse query parameters
        query_components = parse_qs(urlparse(self.path).query)
        search_query = query_components.get('query', [None])[0]
        date_start = query_components.get('date_start', [None])[0]
        date_end = query_components.get('date_end', [None])[0]

        if not search_query or not date_start or not date_end:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Missing required query parameters: query, date_start, date_end'}).encode('utf-8'))
            return

        try:
            # Execute the query logic
            final_response = execute(search_query, date_start, date_end)

            # Send response with caching headers
            body = json.dumps(final_response, sort_keys=True).encode('utf-8')
            etag = '"' + hashlib.sha1(body).hexdigest() + '"'

            if self.headers.get('if-none-match') == etag:
                self.send_response(304)
                self.end_headers()
                return

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'public, max-age=14400')  # 4 hours
            self.send_header('CDN-Cache-Control', 'public, s-maxage=14400')
            self.send_header('ETag', etag)
            self.end_headers()
            self.wfile.write(body)

        except Exception as e:
            print(f"An error occurred: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))

        return
