import os
from google.cloud import translate

def get_translator():
    """
    Initializes and returns a translator client based on environment variables.
    Currently supports Google Cloud Translate.
    """
    provider = os.environ.get('TRANSLATE_PROVIDER', 'google')

    if provider == 'google':
        # The library automatically uses GOOGLE_API_KEY if it's set,
        # or falls back to other authentication methods.
        # For GitHub Actions, we will provide an API key.
        # No need for service account JSON file anymore.
        api_key = os.environ.get('GOOGLE_TRANSLATE_API_KEY')
        if not api_key:
            # For local dev or other auth methods, this might not be set.
            # The client can sometimes still work if gcloud is configured.
            print("Warning: GOOGLE_TRANSLATE_API_KEY not set. Translation may fail.")

        # The client uses Application Default Credentials by default,
        # which can include an API key set in the environment.
        # Let's be explicit if we can.
        # Note: google-cloud-translate v2 doesn't directly accept an api_key in constructor.
        # It relies on GOOGLE_API_KEY env var or `gcloud auth application-default login`.
        # For our use case, setting the env var in the GitHub Action is the way.
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
