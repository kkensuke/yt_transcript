import os
import sys
import json
import argparse
import re
from datetime import timedelta
import yt_dlp
from urllib.parse import urlparse, parse_qs

# ===== CONFIGURATION =====
# Add your Gemini API key here
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL")
# GEMINI_MODEL = "gemini-flash-latest"

MAX_SUMMARY_LENGTH = 50000  # Max characters for summary input
# =========================


def extract_video_id(url):
    """
    Extracts the YouTube video ID from a variety of URL formats.
    Handles standard, shortened, embed, shorts, live, and music URLs,
    as well as regional domains and mobile versions.
    """
    if not url:
        return None

    # Handle the case where the input is just the 11-character video ID
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url

    # Prepend 'http://' if no scheme is present to help urlparse
    if not re.match(r'http(s)?://', url):
        url = 'http://' + url

    parsed_url = urlparse(url)
    hostname = parsed_url.hostname

    # A regex to match youtube.com, youtu.be, and regional/mobile variations
    # e.g., www.youtube.com, m.youtube.co.uk, music.youtube.com, youtu.be
    if not hostname or not re.match(r'(?:www\.|m\.|music\.)?youtube\.co(m|\.uk|\.jp|\.de|.\w{2})|youtu\.be', hostname):
        return None

    # Case 1: Standard /watch url (e.g., youtube.com/watch?v=VIDEO_ID)
    if parsed_url.path == '/watch':
        query_params = parse_qs(parsed_url.query)
        return query_params.get('v', [None])[0]

    # Case 2: Shortened URL (e.g., youtu.be/VIDEO_ID)
    if hostname == 'youtu.be':
        # The ID is the first part of the path, ignore query params
        return parsed_url.path.split('/')[1].split('?')[0]

    # Case 3: Embed, Shorts, Live, or old /v/ urls
    # (e.g., /embed/VIDEO_ID, /shorts/VIDEO_ID, /live/VIDEO_ID, /v/VIDEO_ID)
    path_parts = parsed_url.path.split('/')
    if len(path_parts) > 2 and path_parts[1] in ['embed', 'shorts', 'live', 'v']:
        # The ID is the second part of the path, ignore query params
        return path_parts[2].split('?')[0]

    return None

def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS format."""
    return str(timedelta(seconds=int(seconds)))


def detect_video_language(title, description=""):
    """Simple language detection based on title and description."""
    text = (title + " " + description).lower()
    
    # Japanese detection - look for hiragana, katakana, or common Japanese words
    japanese_indicators = ['を', 'は', 'が', 'に', 'で', 'と', 'の', 'です', 'ます', 'した', 'する', 'ある', 'いる']
    if any(indicator in text for indicator in japanese_indicators):
        return 'ja'
    
    # Could add more language detection here
    return 'en'  # Default to English


def get_video_info_and_transcript(video_id):
    """Get video info and transcript using yt-dlp."""
    
    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'cookiesfrombrowser': ('chrome',),
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("Extracting video information...")
            info = ydl.extract_info(video_id, download=False)
            
            title = info.get('title', 'Unknown Title')
            video_id = info.get('id', 'Unknown ID')
            duration = info.get('duration', 0)
            description = info.get('description', '')
            
            print(f"Title: {title}")
            print(f"Video ID: {video_id}")
            print(f"Duration: {format_timestamp(duration)}")
            
            # Detect video language
            detected_language = detect_video_language(title, description)
            print(f"Detected language: {detected_language}")
            
            # Look for subtitles
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            
            print(f"\nAvailable manual subtitles: {list(subtitles.keys())}")
            print(f"Available auto captions (first 10): {list(automatic_captions.keys())[:10]}...")
            
            # Choose language based on detection
            if detected_language == 'ja':
                preferred_languages = ['ja', 'ja-JP', 'en', 'en-US', 'en-GB']
            else:
                preferred_languages = ['en', 'en-US', 'en-GB', 'ja', 'ja-JP']
            
            transcript_data = None
            transcript_type = None
            
            # Try manual subtitles first
            for lang_code in preferred_languages:
                if lang_code in subtitles:
                    transcript_data = subtitles[lang_code]
                    transcript_type = f"Manual ({lang_code})"
                    break
            
            # Then try automatic captions
            if not transcript_data:
                for lang_code in preferred_languages:
                    if lang_code in automatic_captions:
                        transcript_data = automatic_captions[lang_code]
                        transcript_type = f"Auto-generated ({lang_code})"
                        break
            
            # If still no match, try any available language
            if not transcript_data:
                if subtitles:
                    lang_code = list(subtitles.keys())[0]
                    transcript_data = subtitles[lang_code]
                    transcript_type = f"Manual ({lang_code})"
                elif automatic_captions:
                    lang_code = list(automatic_captions.keys())[0]
                    transcript_data = automatic_captions[lang_code]
                    transcript_type = f"Auto-generated ({lang_code})"
            
            if transcript_data:
                print(f"Using transcript: {transcript_type}")
                return info, transcript_data
            else:
                print("No transcripts found")
                return info, None
                
    except Exception as e:
        print(f"Error extracting video info: {str(e)}")
        return None, None


def download_and_parse_transcript(transcript_data):
    """Download and parse the transcript file."""
    import urllib.request
    import urllib.error
    
    # Find the best format (prefer json, then vtt, then srt)
    best_format = None
    for item in transcript_data:
        ext = item.get('ext', '')
        if ext == 'json3':
            best_format = item
            break
        elif ext == 'vtt' and not best_format:
            best_format = item
        elif ext == 'srv1' and not best_format:
            best_format = item
    
    if not best_format:
        print("No suitable transcript format found")
        return None
    
    print(f"Downloading transcript in {best_format.get('ext')} format...")
    
    try:
        # Directly fetch the transcript URL
        transcript_url = best_format['url']
        print(f"Fetching from: {transcript_url}")
        
        # Download only the transcript file (small file)
        with urllib.request.urlopen(transcript_url) as response:
            content = response.read().decode('utf-8')
        
        print(f"Downloaded transcript ({len(content)} characters)")
        
        # Parse based on format
        if best_format.get('ext') == 'json3':
            return parse_json3_transcript(content)
        elif best_format.get('ext') == 'vtt':
            return parse_vtt_transcript(content)
        else:
            return parse_srv1_transcript(content)
                    
    except Exception as e:
        print(f"Error downloading transcript: {str(e)}")
        return None


def parse_json3_transcript(content):
    """Parse JSON3 format transcript."""
    try:
        data = json.loads(content)
        transcript = []
        
        events = data.get('events', [])
        for event in events:
            if 'segs' in event:
                start_time = event.get('tStartMs', 0) / 1000.0
                text_parts = []
                for seg in event['segs']:
                    if 'utf8' in seg:
                        text_parts.append(seg['utf8'])
                
                text = ''.join(text_parts).strip()
                if text:
                    transcript.append({
                        'text': text,
                        'start': start_time,
                        'duration': event.get('dDurationMs', 0) / 1000.0
                    })
        
        return transcript
    except Exception as e:
        print(f"Error parsing JSON3 transcript: {str(e)}")
        return None


def parse_vtt_transcript(content):
    """Parse VTT format transcript."""
    try:
        transcript = []
        lines = content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for timestamp lines
            if '-->' in line:
                time_parts = line.split(' --> ')
                start_time = vtt_time_to_seconds(time_parts[0])
                
                # Get the text (next non-empty lines)
                i += 1
                text_parts = []
                while i < len(lines) and lines[i].strip():
                    text_parts.append(lines[i].strip())
                    i += 1
                
                text = ' '.join(text_parts)
                # Remove VTT tags
                text = re.sub(r'<[^>]+>', '', text)
                
                if text:
                    transcript.append({
                        'text': text,
                        'start': start_time,
                        'duration': 0  # VTT doesn't always have duration
                    })
            
            i += 1
        
        return transcript
    except Exception as e:
        print(f"Error parsing VTT transcript: {str(e)}")
        return None


def parse_srv1_transcript(content):
    """Parse SRV1 (XML) format transcript."""
    try:
        import xml.etree.ElementTree as ET
        
        root = ET.fromstring(content)
        transcript = []
        
        for text_elem in root.findall('.//text'):
            start_time = float(text_elem.get('start', 0))
            duration = float(text_elem.get('dur', 0))
            text = text_elem.text or ''
            text = text.strip()
            
            if text:
                transcript.append({
                    'text': text,
                    'start': start_time,
                    'duration': duration
                })
        
        return transcript
    except Exception as e:
        print(f"Error parsing SRV1 transcript: {str(e)}")
        return None


def vtt_time_to_seconds(time_str):
    """Convert VTT timestamp to seconds."""
    try:
        # Remove milliseconds part if present
        time_str = time_str.split('.')[0]
        parts = time_str.split(':')
        
        if len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        else:
            return int(parts[0])
    except:
        return 0


def clean_japanese_text(text):
    """Clean Japanese transcript text by removing music tags and unnecessary spaces."""
    import re
    
    # Remove common Japanese music/sound tags
    music_tags = ['[音楽]', '♪', '♫', '♬', '♩', '[拍手]', '[笑い]', '[笑]', '[音響効果]', '[効果音]']
    for tag in music_tags:
        text = text.replace(tag, '')
    
    # Remove spaces between Japanese characters
    # This regex matches spaces that are between Japanese characters (hiragana, katakana, kanji)
    # Unicode ranges: Hiragana (3040-309F), Katakana (30A0-30FF), CJK Unified Ideographs (4E00-9FAF)
    japanese_char_pattern = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]'
    
    # Remove spaces between Japanese characters
    text = re.sub(f'({japanese_char_pattern})\\s+({japanese_char_pattern})', r'\1\2', text)
    
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove leading/trailing spaces
    text = text.strip()
    
    return text


def transcript_to_markdown(transcript, video_info, include_timestamps=True):
    """Convert transcript to markdown format."""
    title = video_info.get('title', 'Unknown Title')
    video_id = video_info.get('id', 'Unknown ID')
    
    # Detect if this is Japanese content
    is_japanese = detect_video_language(title) == 'ja'
    
    markdown = f"# {title}\n\n"
    markdown += f"**Video ID:** {video_id}  \n"
    markdown += f"**YouTube URL:** https://www.youtube.com/watch?v={video_id}\n\n"
    markdown += "---\n\n"
    
    if not transcript:
        markdown += "*No transcript available for this video.*\n"
        return markdown
    
    # Group transcript entries into paragraphs
    current_paragraph = ""
    current_start_time = None
    
    for entry in transcript:
        text = entry['text'].strip()
        
        if not text:
            continue
        
        # Clean Japanese text if needed
        if is_japanese:
            text = clean_japanese_text(text)
            if not text:  # Skip if text becomes empty after cleaning
                continue
            
        if current_start_time is None:
            current_start_time = entry['start']
        
        current_paragraph += text + " "
        
        # Start new paragraph if text ends with sentence punctuation
        if text.endswith(('.', '!', '?', '。', '！', '？')) or len(current_paragraph) > 500:
            if include_timestamps:
                timestamp = format_timestamp(current_start_time)
                final_text = current_paragraph.strip()
                if is_japanese:
                    final_text = clean_japanese_text(final_text)
                markdown += f"**[{timestamp}]** {final_text}\n\n"
            else:
                final_text = current_paragraph.strip()
                if is_japanese:
                    final_text = clean_japanese_text(final_text)
                markdown += f"{final_text}\n\n"
            
            current_paragraph = ""
            current_start_time = None
    
    # Add any remaining text
    if current_paragraph.strip():
        final_text = current_paragraph.strip()
        if is_japanese:
            final_text = clean_japanese_text(final_text)
        
        if final_text:  # Only add if text remains after cleaning
            if include_timestamps and current_start_time is not None:
                timestamp = format_timestamp(current_start_time)
                markdown += f"**[{timestamp}]** {final_text}\n\n"
            else:
                markdown += f"{final_text}\n\n"
    
    return markdown


def call_gemini_api(text, api_key, language='auto'):
    """Call Gemini API to summarize the transcript."""
    import json
    import urllib.request
    import urllib.error
    
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


def main():
    parser = argparse.ArgumentParser(description='Extract YouTube transcript using yt-dlp')
    parser.add_argument('url', help='YouTube URL or video ID')
    parser.add_argument('-o', '--output', help='Output file (default: video_id_transcript.md)')
    parser.add_argument('--no-timestamps', action='store_true', help='Exclude timestamps from output')
    parser.add_argument('--no-summary', action='store_true', help='Skip summary generation')
    parser.add_argument('--summary-lang', choices=['auto', 'en', 'ja'], default='auto', 
                       help='Summary language: auto (same as original), en (English), ja (Japanese)')
    
    args = parser.parse_args()
    
    # Extract video ID for filename if needed
    video_id = extract_video_id(args.url)
    if not video_id:
        print(f"Error: Could not extract a valid YouTube video ID from '{args.url}'")
        sys.exit(1)
    
    # Get video info and transcript
    video_info, transcript_data = get_video_info_and_transcript(video_id)
    
    if not video_info:
        print("Failed to get video information")
        sys.exit(1)
    
    if not transcript_data:
        print("No transcript data available")
        sys.exit(1)
    
    # Download and parse transcript
    transcript = download_and_parse_transcript(transcript_data)
    
    if not transcript:
        print("Failed to parse transcript")
        sys.exit(1)
    
    print(f"Successfully parsed {len(transcript)} transcript entries")
    
    # Convert to markdown
    include_timestamps = not args.no_timestamps
    markdown = transcript_to_markdown(transcript, video_info, include_timestamps)
    
    # Save original transcript to file
    output_file = args.output or f"{video_id}_transcript.md"
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown)
        print(f"Transcript saved to: {output_file}")
    except Exception as e:
        print(f"Error saving file: {str(e)}")
        print("\n--- Transcript Content ---")
        print(markdown)
        return
    
    # Generate summary if API key is configured and not disabled
    if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY" and not args.no_summary:
        print("\nGenerating summary...")
        
        # Limit text length for API (Gemini has token limits)
        if len(markdown) > MAX_SUMMARY_LENGTH:
            markdown = markdown[:MAX_SUMMARY_LENGTH] + "... [transcript truncated for summarization]"
            print(f"Transcript truncated to {MAX_SUMMARY_LENGTH} characters for summarization")
        
        # Call Gemini API with language preference
        summary = call_gemini_api(markdown, GEMINI_API_KEY, args.summary_lang)

        if summary:
            # Create summary markdown
            summary_markdown = create_summary_markdown(video_info, summary)
            
            # Save summary to file
            summary_file = f"{video_id}_summarized.md"
            
            try:
                with open(summary_file, 'w', encoding='utf-8') as f:
                    f.write(summary_markdown)
                print(f"Summary saved to: {summary_file}")
            except Exception as e:
                print(f"Error saving summary file: {str(e)}")
                print("\n--- Summary Content ---")
                print(summary_markdown)
        else:
            print("Failed to generate summary")
    elif args.no_summary:
        print("Summary generation skipped (--no-summary flag used)")
    elif not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        print("No Gemini API key configured. Set GEMINI_API_KEY in the script to enable summarization.")
    else:
        print("Summarization disabled")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Usage: python yt_dlp_transcript.py <YouTube_URL_or_Video_ID>")
        print("Example: python yt_dlp_transcript.py 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'")
        print("\nOptions:")
        print("  --no-timestamps    Exclude timestamps from output")
        print("  --no-summary       Skip summary generation")
        print("  --summary-lang     Summary language: auto (default), en, ja")
        print("  -o FILE            Output filename")
        print("\nExamples:")
        print("  python yt_dlp_transcript.py 'VIDEO_URL'")
        print("  python yt_dlp_transcript.py 'VIDEO_URL' --summary-lang ja")
        print("  python yt_dlp_transcript.py 'VIDEO_URL' --summary-lang en")
        sys.exit(1)
    
    main()