import os
import json
import google.generativeai as genai

# Configure Gemini API key
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")

genai.configure(api_key=GEMINI_API_KEY)

def get_translator():
    """
    Initializes and returns a translator client (Gemini model).
    """
    provider = os.environ.get('TRANSLATE_PROVIDER', 'gemini')

    if provider == 'gemini':
        return genai.GenerativeModel('gemini-2.5-flash-lite')
    else:
        raise NotImplementedError(f"Translator provider '{provider}' is not supported.")

def translate_text(client, text, target_lang='en', source_lang=None):
    """
    Translates a single text string using Gemini.
    """
    if not text or not text.strip():
        return None

    # Build translation prompt
    if source_lang and source_lang != target_lang:
        prompt = f"Translate the following text from {source_lang} to {target_lang}. Return only the translation, nothing else.\n\n{text}"
    else:
        prompt = f"Translate the following text to {target_lang}. Return only the translation, nothing else.\n\n{text}"

    try:
        response = client.generate_content(prompt)
        translated_text = response.text.strip()
        return translated_text if translated_text else None
    except Exception as e:
        print(f"Error translating text: {e}")
        return None

def translate_batch(client, texts_with_info: list[tuple[str, str, str]], target_lang='en') -> list[str | None]:
    """
    Translates multiple texts in a single API call.

    Args:
        client: Gemini client
        texts_with_info: List of tuples (text, source_lang, url) for tracking
        target_lang: Target language (default 'en')

    Returns:
        List of translated texts (or None if translation failed/not needed)
    """
    if not texts_with_info:
        return []

    # Filter out empty texts and texts already in target language
    texts_to_translate = []
    indices_to_translate = []
    results = [None] * len(texts_with_info)

    for i, (text, source_lang, url) in enumerate(texts_with_info):
        if not text or not text.strip():
            continue

        if source_lang == target_lang:
            # Already in target language, just copy
            results[i] = text.strip()
        else:
            texts_to_translate.append((i, text, source_lang))
            indices_to_translate.append(i)

    if not texts_to_translate:
        return results

    # Group by source language for better batching
    by_lang = {}
    for idx, text, source_lang in texts_to_translate:
        if source_lang not in by_lang:
            by_lang[source_lang] = []
        by_lang[source_lang].append((idx, text))

    # Translate each language group in batches (max 50 texts per batch to avoid token limits)
    BATCH_SIZE = 50

    for source_lang, lang_texts in by_lang.items():
        for batch_start in range(0, len(lang_texts), BATCH_SIZE):
            batch = lang_texts[batch_start:batch_start + BATCH_SIZE]

            # Build batch prompt
            prompt_parts = [
                f"Translate the following {len(batch)} texts from {source_lang} to {target_lang}.",
                "Return the translations in a list in the same order as its corresponding input texts.",
                "",
                "Texts to translate:"
            ]

            for i, (idx, text) in enumerate(batch, 1):
                prompt_parts.append(f"{i}. {text}")

            prompt = "\n".join(prompt_parts)

            try:
                # Use structured output with Pydantic model
                response = client.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        response_mime_type="application/json",
                        response_schema=list[str]
                    )
                )
                translations = json.loads(response.text)

                # Map translations back to original indices
                if isinstance(translations, list) and len(translations) == len(batch):
                    for (idx, _), translation in zip(batch, translations):
                        results[idx] = translation.strip() if translation else None
                else:
                    print(f"Warning: Expected {len(batch)} translations, got {len(translations) if isinstance(translations, list) else 'non-list'}")
                    # Mark batch as failed
                    for idx, _ in batch:
                        results[idx] = None
            except Exception as e:
                print(f"Error translating batch from {source_lang}: {e}")
                # Mark batch as failed
                for idx, _ in batch:
                    results[idx] = None

    return results
