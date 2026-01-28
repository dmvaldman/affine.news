import os
import google.generativeai as genai
from typing import List

from dotenv import load_dotenv
load_dotenv()

def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generates embeddings for a list of texts using the Gemini API.

    Args:
        texts: A list of strings to embed.

    Returns:
        A list of embeddings, where each embedding is a list of floats.
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    genai.configure(api_key=api_key)

    try:
        # Use 768 dimensions to match existing DB embeddings
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=texts,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768
        )
        return result['embedding']
    except Exception as e:
        print(f"An error occurred while generating embeddings: {e}")
        return []
