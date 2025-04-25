from deep_translator import GoogleTranslator

# Dictionary containing Indian & Top Global Languages
language_map = {
    # Indian Languages
    'assamese': 'as', 'bengali': 'bn', 'gujarati': 'gu', 'hindi': 'hi', 'kannada': 'kn',
    'kashmiri': 'ks', 'konkani': 'gom', 'malayalam': 'ml', 'manipuri': 'mni-Mtei', 'marathi': 'mr',
    'nepali': 'ne', 'oriya': 'or', 'punjabi': 'pa', 'sanskrit': 'sa', 'sindhi': 'sd', 'tamil': 'ta',
    'telugu': 'te', 'urdu': 'ur', 'bodo': 'brx', 'maithili': 'mai', 'santhali': 'sat', 'dogri': 'doi',

    # Top 10 Global Languages
    'english': 'en', 'chinese': 'zh-CN', 'spanish': 'es', 'french': 'fr', 'arabic': 'ar',
    'russian': 'ru', 'portuguese': 'pt', 'german': 'de', 'japanese': 'ja', 'korean': 'ko'
}

def translate_text(text, target_language):
    target_language = target_language.lower()
    
    # Convert full language name to language code
    if target_language in language_map:
        target_language = language_map[target_language]
    
    translator = GoogleTranslator(target=target_language)
    return translator.translate(text)

if __name__ == "__main__":
    source_text = input("Enter text to translate: ")
    target_language = input("Enter target language (e.g., 'Hindi', 'French', 'Spanish'): ")
    
    try:
        translated_text = translate_text(source_text, target_language)
        print(f"Translated Text: {translated_text}")
    except Exception as e:
        print(f"Error: {e}")
