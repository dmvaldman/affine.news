import os
import json
import google.generativeai as genai
from typing import List
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()

class Topic(BaseModel):
    """A single, short, engaging topic label."""
    label: str

def generate_topics(grouped_headlines: dict) -> List[str]:
    """
    Uses the Gemini API to generate a concise topic label for each group of headlines.

    Args:
        grouped_headlines: A dictionary where keys are topic identifiers and
                           values are lists of representative headlines for that topic.

    Returns:
        A list of short, 3-5 word topic labels, corresponding to the input groups.
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash-lite')

    prompt_parts = [
        "You are a news editor. Read the following groups of headlines. Each group represents a distinct news event.",
        "Your task is to generate one short (2-5 words typically), engaging topic label for each group.",
        "Some headlines may be noisy or irrelevant. Ignore them. Ignore sports and entertainment headlines.",
        "Avoid unnecessary adjectives/verbs unless necessary. Stick to the proper nouns.",
        "We especially want labels for events that are controversial.",
        "Use first and last names of people when applicable.",
        "If a label is generic (10 people killed, etc), ignore it. We want labels that call out specific events/people/places.",
        "Return a list of topic labels, at least 2 and at most 6, however many you think are relevant.",
        ""
    ]

    for i, (topic_id, headlines) in enumerate(grouped_headlines.items()):
        prompt_parts.append(f"--- TOPIC GROUP {i+1} ---")
        for headline in headlines:
            prompt_parts.append(f"- {headline}")
        prompt_parts.append("")

    prompt = "\n".join(prompt_parts)

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=list[Topic],
            )
        )

        return json.loads(response.text)

    except Exception as e:
        print(f"An error occurred while generating topic with Gemini: {e}")
        return [] # Return an empty list on error
