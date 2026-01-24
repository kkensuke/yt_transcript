import json
import os
import urllib.request
import urllib.error
from utils import format_timestamp

GEMINI_MODEL: str = os.getenv("GEMINI_MODEL")
# GEMINI_MODEL = "gemini-flash-latest"

def call_gemini_api(text, api_key, language='auto'):
    """Call Gemini API to summarize the transcript."""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    
    # Detect language if auto
    if language == 'auto':
        # Simple detection based on Japanese characters
        japanese_chars = sum(1 for char in text if '\u3040' <= char <= '\u309F' or '\u30A0' <= char <= '\u30FF' or '\u4E00' <= char <= '\u9FAF')
        total_chars = len([char for char in text if char.isalpha() or '\u3040' <= char <= '\u9FAF'])
        
        if total_chars > 0 and japanese_chars / total_chars > 0.3:  # If >30% Japanese characters
            language = 'ja'
        else:
            language = 'en'
    
    # Prepare language-specific prompts
    if language == 'ja':
        # PROMPT FOR JAPANESE
        prompt = f"""
        提供された動画の文字起こしを、読みやすく構造化され、かつ学術的に正確なマークダウン形式の要約ドキュメントに変換してください。
        
        【前処理ルール】
        - 文字起こしに同音異義語などの誤字・ASR誤認識があれば文脈で修正・削除して自然な日本語にしてください。ただし、**不確かな解釈箇所は[不確か]タグ**を付けて示してください。
        - 専門用語は原語（英語）が存在する場合は原語を括弧で併記してください（例：経験的リスク（empirical risk））。
        - 数式・アルゴリズムは可能な限りLaTeX形式で示してください（`$$...$$`）。
        
        ---
        要約する文字起こしは以下の通りです：
        {text}
        """
    else:  # Default to English
        # PROMPT FOR ENGLISH
        prompt = f"""
        Provide a well-structured, readable, and academically accurate summary document in Markdown format based on the provided video transcript.
        
        ### Preprocessing Rules
        * If there are typos, homophones, or ASR misrecognitions in the transcript, correct or remove them based on context to produce natural language. However, for **uncertain interpretations, mark them with the [Uncertain] tag**.
        * Represent mathematical formulas or algorithms in LaTeX format whenever possible (`$$...$$`).
        
        ---
        
        The transcript to summarize is as follows:
        {text}
        """
    
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    
    try:
        # Prepare the request
        json_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=json_data)
        req.add_header('Content-Type', 'application/json')
        
        print(f"Calling Gemini API for summarization (language: {language})...")
        
        # Make the request
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            
        # Extract the generated text
        if 'candidates' in result and len(result['candidates']) > 0:
            candidate = result['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                summary = candidate['content']['parts'][0]['text']
                print("Successfully generated summary")
                return summary
            else:
                print("Unexpected API response structure")
                return None
        else:
            print("No candidates in API response")
            return None
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"HTTP Error {e.code}: {error_body}")
        return None
    except Exception as e:
        print(f"Error calling Gemini API: {str(e)}")
        return None


def create_summary_markdown(video_info, summary):
    """Create a markdown file with the Gemini-generated summary."""
    title = video_info.get('title', 'Unknown Title')
    video_id = video_info.get('id', 'Unknown ID')
    duration = video_info.get('duration', 0)
    
    markdown = f"# {title} - Summary\n\n"
    markdown += f"**Video ID:** {video_id}  \n"
    markdown += f"**YouTube URL:** https://www.youtube.com/watch?v={video_id}  \n"
    markdown += f"**Duration:** {format_timestamp(duration)}\n\n"
    markdown += "---\n\n"
    
    if summary:
        markdown += summary
    else:
        markdown += "*Failed to generate summary.*\n"
    
    markdown += "\n\n---\n\n"
    markdown += "*Summary generated using Gemini AI*\n"
    
    return markdown