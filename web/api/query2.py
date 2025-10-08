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

class LlmSankeyResult(BaseModel):
    spectrum_name: str
    spectrum_description: str
    spectrum_points: list[SpectrumPoint]
    mappings: list[ArticleSpectrumMapping]


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
    Two-phase approach:
    1. Define spectrum using sample of articles
    2. Classify all articles in parallel batches
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

    return LlmSankeyResult(
        spectrum_name=spectrum_name,
        spectrum_description=spectrum_description,
        spectrum_points=spectrum_points,
        mappings=all_mappings
    )


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
            # Fetch articles using semantic similarity
            print("Fetching articles for query...")
            articles_data = fetch_articles_for_query(search_query, date_start, date_end)

            if not articles_data:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "spectrum_name": None,
                    "spectrum_description": None,
                    "spectrum_points": [],
                    "articles": {}
                }).encode('utf-8'))
                return

            print(f"Found {len(articles_data)} articles.")

            # 3. Generate spectrum analysis using LLM (parallel)
            print("Step 3: Generating spectrum analysis...")
            analysis_result = generate_sankey_data_with_llm_parallel(articles_data, NUM_WORKERS)

            if not analysis_result:
                raise ValueError("Could not get analysis from LLM")

            print(f"Spectrum: {analysis_result.spectrum_name}")

            # 4. Format response
            print("Step 4: Formatting response...")
            mapping_dict = {m.article_id: m.point_id for m in analysis_result.mappings}

            # Group articles by ISO
            articles_by_iso = {}
            for i, article in enumerate(articles_data):
                article_id_llm = i + 1
                point_id = mapping_dict.get(article_id_llm)
                iso = article['iso']

                if iso not in articles_by_iso:
                    articles_by_iso[iso] = {
                        "country": article['country'],
                        "articles": []
                    }

                articles_by_iso[iso]["articles"].append({
                    "title": article['title'],
                    "url": article['url'],
                    "publish_at": article['publish_at'],
                    "lang": article['lang'],
                    "point_id": point_id
                })

            final_response = {
                "spectrum_name": analysis_result.spectrum_name,
                "spectrum_description": analysis_result.spectrum_description,
                "spectrum_points": [
                    {"point_id": p.point_id, "label": p.label, "description": p.description}
                    for p in sorted(analysis_result.spectrum_points, key=lambda x: x.point_id)
                ],
                "articles": articles_by_iso
            }

            # 5. Send response with caching headers
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
