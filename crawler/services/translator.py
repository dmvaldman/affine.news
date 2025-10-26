import os
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
