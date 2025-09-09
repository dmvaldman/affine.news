import os
from google.cloud import translate

def get_translator():
    """
    Initializes and returns a translator client based on environment variables.
    Currently supports Google Cloud Translate.
    """
    provider = os.environ.get('TRANSLATE_PROVIDER', 'google')

    if provider == 'google':
        return translate.TranslationServiceClient()
    else:
        raise NotImplementedError(f"Translator provider '{provider}' is not supported.")

def translate_text(client, text, target_lang='en', source_lang=None):
    """
    Translates a single text string.
    """
    # This is your Google Project ID or number
    project_id = os.environ.get('GOOGLE_PROJECT_ID')
    if not project_id:
        raise ValueError("GOOGLE_PROJECT_ID environment variable not set.")

    location = "global"
    parent = f"projects/{project_id}/locations/{location}"

    response = client.translate_text(
        parent=parent,
        contents=[text],
        mime_type="text/plain",
        source_language_code=source_lang,
        target_language_code=target_lang,
    )

    if response.translations:
        return response.translations[0].translated_text
    return None
