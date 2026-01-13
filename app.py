import os
import json
import re
import requests
import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Set secret key for sessions
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
AI_MODEL = os.getenv('AI_MODEL', 'google/gemini-flash-3.0-preview')
DATA_FILE = 'Data.json'
TOV_FILE = 'TOV_prompts.md'
PROMPTS_FILE = 'Posts_propts.json'

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

# Initialize Supabase client if credentials are available
supabase = None
if USE_SUPABASE:
    try:
        from supabase import create_client, Client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase client initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize Supabase client: {e}")
        print("Falling back to file-based storage")
        USE_SUPABASE = False
else:
    print("Supabase credentials not found, using file-based storage")

# Cache for loaded data
tov_content = None
prompts_data = None
posts_data = None

# Admin credentials
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')


def admin_required(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def load_tov():
    """Load Tone of Voice guidelines"""
    global tov_content
    if tov_content is None:
        try:
            with open(TOV_FILE, 'r', encoding='utf-8') as f:
                tov_content = f.read()
        except FileNotFoundError:
            raise Exception(f"File {TOV_FILE} not found")
    return tov_content


def load_prompts():
    """Load rubric prompts configuration from Supabase or Posts_propts.json"""
    global prompts_data
    if prompts_data is None:
        # Use Supabase if available
        if USE_SUPABASE and supabase:
            try:
                # Load rubrics
                rubrics_response = supabase.table('rubrics').select('*').execute()
                rubrics_dict = {}
                if rubrics_response.data:
                    for rubric in rubrics_response.data:
                        name = rubric.pop('name')
                        rubric.pop('created_at', None)
                        rubric.pop('updated_at', None)
                        rubrics_dict[name] = {k: v for k, v in rubric.items() if v is not None}
                
                # Load settings (common and metadata)
                settings_response = supabase.table('settings').select('*').execute()
                common_data = {}
                metadata_data = {}
                
                if settings_response.data:
                    for setting in settings_response.data:
                        if setting['key'] == 'common':
                            common_data = setting['value']
                        elif setting['key'] == 'metadata':
                            metadata_data = setting['value']
                
                # Construct prompts_data structure
                prompts_data = {
                    'version': metadata_data.get('version', '2.0'),
                    'metadata': metadata_data,
                    'common': common_data,
                    'rubrics': rubrics_dict
                }
                return prompts_data
            except Exception as e:
                print(f"Error loading prompts from Supabase: {e}")
                print("Falling back to file-based storage")
                # Fall through to file-based loading
        
        # Fallback to file-based storage
        try:
            with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
                prompts_data = json.load(f)
        except FileNotFoundError:
            raise Exception(f"File {PROMPTS_FILE} not found")
    return prompts_data


def load_data():
    """Load posts from Supabase or Data.json (fallback)"""
    global posts_data
    
    # Use Supabase if available
    if USE_SUPABASE and supabase:
        try:
            response = supabase.table('posts').select('*').order('created_at', desc=True).execute()
            posts_data = response.data if response.data else []
            # Convert created_at from string to ensure consistency
            for post in posts_data:
                if isinstance(post.get('created_at'), str):
                    # Keep as string for consistency with file-based format
                    pass
            return posts_data
        except Exception as e:
            print(f"Error loading data from Supabase: {e}")
            print("Falling back to file-based storage")
            # Fall through to file-based loading
    
    # Fallback to file-based storage
    if posts_data is None:
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                posts_data = json.load(f)
            # Ensure it's a list
            if not isinstance(posts_data, list):
                posts_data = []
        except FileNotFoundError:
            posts_data = []
        except json.JSONDecodeError:
            print(f"Warning: {DATA_FILE} contains invalid JSON. Initializing as empty list.")
            posts_data = []
    return posts_data


def save_data(posts_list):
    """Save posts to Supabase or Data.json (fallback)"""
    # Note: This function is kept for backward compatibility
    # In practice, we save individual posts directly to Supabase
    # This is mainly used for admin operations that modify multiple posts
    
    # Use Supabase if available
    if USE_SUPABASE and supabase:
        try:
            # For bulk operations, we'd need to handle this differently
            # For now, this is mainly a fallback for file-based storage
            print("Warning: save_data() called with Supabase enabled. Individual saves should use Supabase directly.")
            return True
        except Exception as e:
            print(f"Error saving data to Supabase: {e}")
            # Fall through to file-based saving
    
    # Fallback to file-based storage
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(posts_list, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving data: {e}")
        return False


def get_examples_by_rubric(rubric_name, count=5):
    """Get recent examples for a specific rubric"""
    # Use Supabase if available for better performance
    if USE_SUPABASE and supabase:
        try:
            response = supabase.table('posts')\
                .select('*')\
                .eq('rubric', rubric_name)\
                .order('created_at', desc=True)\
                .limit(count)\
                .execute()
            return response.data if response.data else []
        except Exception as e:
            print(f"Error fetching examples from Supabase: {e}")
            # Fall through to file-based loading
    
    # Fallback to file-based storage
    posts = load_data()
    filtered = [p for p in posts if p.get('rubric') == rubric_name]
    # Sort by created_at descending
    filtered.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return filtered[:count]


def rubric_requires_city(rubric_name):
    """Check if a rubric requires city parameter"""
    # Rubrics that don't require city
    rubrics_without_city = {
        'Best Prompts',
        'The Ask',
        'Tripo Horoscope',
        'Occasion'
    }
    return rubric_name not in rubrics_without_city


def determine_prompt_type(rubric_name):
    """Determine if rubric uses video_prompt or image_prompt"""
    prompts = load_prompts()
    rubric = prompts.get('rubrics', {}).get(rubric_name)
    if not rubric:
        return 'image'  # default
    
    # Check if rubric has video_prompt field
    if 'video_prompt' in rubric:
        return 'video'
    
    # Check if additional field says to return '—' for image_prompt
    additional = rubric.get('additional', '')
    if "Return '—' for image_prompt" in additional or "Return '—' for image_prompt field" in additional:
        return 'none'
    
    return 'image'


def construct_generation_prompt(rubric_name, examples, city=None, previous_title=None):
    """Construct the user prompt for AI generation"""
    prompts = load_prompts()
    rubric = prompts.get('rubrics', {}).get(rubric_name)
    
    if not rubric:
        raise ValueError(f"Rubric '{rubric_name}' not found")
    
    # Get next month and year for rubrics that need it (Tripo Horoscope, Occasion)
    next_month_info = None
    if rubric_name in ['Tripo Horoscope', 'Occasion']:
        now = datetime.now(timezone.utc)
        # Calculate next month
        if now.month == 12:
            next_month = 1
            next_year = now.year + 1
        else:
            next_month = now.month + 1
            next_year = now.year
        # Month names list (index 0 is empty, months start at index 1)
        month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']
        next_month_info = {
            'month': month_names[next_month],
            'year': next_year
        }
        print(f"{rubric_name}: Current month is {month_names[now.month]} {now.year}, generating content for {next_month_info['month']} {next_month_info['year']}")
        print(f"DEBUG: next_month={next_month}, next_year={next_year}, month_name='{next_month_info['month']}'")
    
    # Component 1: Build rubric prompt from Posts_propts.json
    rubric_prompt_parts = []
    if 'title_prompt' in rubric:
        title_prompt = rubric['title_prompt']
        # Replace city placeholders in title_prompt if city is provided
        if city:
            city_trimmed = city.strip()
            title_prompt = title_prompt.replace('{city}', city_trimmed)
            title_prompt = title_prompt.replace('{City}', city_trimmed)
            title_prompt = title_prompt.replace('{CITY}', city_trimmed.upper())
        # Replace month/year placeholders for Tripo Horoscope
        if next_month_info:
            title_prompt = title_prompt.replace('{Month}', next_month_info['month'])
            title_prompt = title_prompt.replace('{Year}', str(next_month_info['year']))
        rubric_prompt_parts.append(f"TITLE PROMPT:\n{title_prompt}")
    
    if 'post_prompt' in rubric:
        post_prompt = rubric['post_prompt']
        # Replace city placeholders in post_prompt if city is provided
        if city:
            city_trimmed = city.strip()
            post_prompt = post_prompt.replace('{city}', city_trimmed)
            post_prompt = post_prompt.replace('{City}', city_trimmed)
            post_prompt = post_prompt.replace('{CITY}', city_trimmed.upper())
        # Replace month/year placeholders for Tripo Horoscope
        if next_month_info:
            post_prompt = post_prompt.replace('{Month}', next_month_info['month'])
            post_prompt = post_prompt.replace('{Year}', str(next_month_info['year']))
        rubric_prompt_parts.append(f"\nPOST PROMPT:\n{post_prompt}")
    
    if 'video_prompt' in rubric:
        video_prompt = rubric['video_prompt']
        # Replace city placeholders in video_prompt if city is provided
        if city:
            city_trimmed = city.strip()
            video_prompt = video_prompt.replace('{city}', city_trimmed)
            video_prompt = video_prompt.replace('{City}', city_trimmed)
            video_prompt = video_prompt.replace('{CITY}', city_trimmed.upper())
        rubric_prompt_parts.append(f"\nVIDEO PROMPT:\n{video_prompt}")
    elif 'image_prompt' in rubric:
        image_prompt = rubric['image_prompt']
        # Replace city placeholders in image_prompt if city is provided
        if city:
            city_trimmed = city.strip()
            image_prompt = image_prompt.replace('{city}', city_trimmed)
            image_prompt = image_prompt.replace('{City}', city_trimmed)
            image_prompt = image_prompt.replace('{CITY}', city_trimmed.upper())
        rubric_prompt_parts.append(f"\nIMAGE PROMPT:\n{image_prompt}")
    
    if 'additional' in rubric:
        additional = rubric['additional']
        # Replace city placeholders in additional if city is provided
        if city:
            city_trimmed = city.strip()
            additional = additional.replace('{city}', city_trimmed)
            additional = additional.replace('{City}', city_trimmed)
            additional = additional.replace('{CITY}', city_trimmed.upper())
        # Replace month/year placeholders for Tripo Horoscope
        if next_month_info:
            additional = additional.replace('{Month}', next_month_info['month'])
            additional = additional.replace('{Year}', str(next_month_info['year']))
        rubric_prompt_parts.append(f"\nADDITIONAL:\n{additional}")
    
    rubric_prompt = '\n'.join(rubric_prompt_parts)
    
    # Debug: verify city replacement
    if city:
        city_trimmed = city.strip()
        print(f"City replacement: Using city '{city_trimmed}' for rubric '{rubric_name}'")
        if '{city}' in rubric_prompt or '{City}' in rubric_prompt or '{CITY}' in rubric_prompt:
            print(f"WARNING: City placeholders still present in prompt after replacement!")
            print(f"Remaining placeholders: {[p for p in ['{city}', '{City}', '{CITY}'] if p in rubric_prompt]}")
    
    # Debug: verify month/year replacement for Tripo Horoscope
    if next_month_info:
        if '{Month}' in rubric_prompt or '{Year}' in rubric_prompt:
            print(f"WARNING: Month/Year placeholders still present in prompt after replacement!")
            print(f"Remaining placeholders: {[p for p in ['{Month}', '{Year}'] if p in rubric_prompt]}")
        else:
            print(f"Month/Year replacement verified: {next_month_info['month']} {next_month_info['year']}")
    
    # Component 2: Examples from Data.json
    examples_text = ""
    if examples:
        examples_text = "\n\nEXAMPLES FROM THIS RUBRIC:\n"
        for i, example in enumerate(examples, 1):
            title = example.get('title', '')
            post_text = example.get('post_text', '')
            image_prompt = example.get('image_prompt', '')
            examples_text += f"\n--- Example {i} ---\n"
            examples_text += f"Title: {title}\n\n"
            examples_text += f"Post Text:\n{post_text}\n\n"
            examples_text += f"Image Prompt: {image_prompt}\n"
            examples_text += "\n" + "="*60 + "\n"
    
    # Component 3: TOV is passed as system prompt, so we only need to combine rubric prompt and examples
    city_info = ""
    city_instruction = ""
    if city:
        city_clean = city.strip()
        city_info = f"\n\nCRITICAL: You MUST generate content specifically for the city: {city_clean}. All references to cities in your generated content must use '{city_clean}' as the city name. Do not use placeholder names or example cities - use '{city_clean}' throughout.\n"
        city_instruction = f" Use the specified city name ({city_clean}) in your generated content."
    
    # Add explicit month/year instruction for rubrics that need it
    month_year_instruction = ""
    if next_month_info:
        if rubric_name == 'Tripo Horoscope':
            month_year_instruction = f"\n\nCRITICAL FOR TRIPO HOROSCOPE: The title MUST use EXACTLY '{next_month_info['month']}, {next_month_info['year']}'. Do NOT use any other month or year. The title must be: 'Travel Horoscope: {next_month_info['month']}, {next_month_info['year']}'. This is the NEXT month after the current month.\n"
        elif rubric_name == 'Occasion':
            # Get list of recent events from examples to avoid repetition
            recent_events = []
            recent_cities = []
            if examples:
                for ex in examples:
                    title = ex.get('title', '')
                    if title:
                        # Extract event name from title (before the dash)
                        event_part = title.split('—')[0].strip() if '—' in title else title.strip()
                        recent_events.append(event_part)
                        # Try to extract city from title or post_text
                        post_text = ex.get('post_text', '')
                        for city in ['Barcelona', 'Istanbul', 'New York', 'San Francisco']:
                            if city in title or city in post_text:
                                recent_cities.append(city)
                                break
            
            # Add previous title if provided (from Try Again) - this is the most important to avoid
            if previous_title:
                event_part = previous_title.split('—')[0].strip() if '—' in previous_title else previous_title.strip()
                recent_events.insert(0, event_part)  # Put at beginning as most recent
                # Also try to extract city from previous title
                for city in ['Barcelona', 'Istanbul', 'New York', 'San Francisco']:
                    if city in previous_title:
                        recent_cities.insert(0, city)
                        break
            
            # Create diversity instruction with specific alternatives
            import random
            all_cities = ['Istanbul', 'Barcelona', 'New York', 'San Francisco']
            available_cities = [c for c in all_cities if c not in recent_cities] if recent_cities else all_cities
            preferred_city = random.choice(available_cities) if available_cities else random.choice(all_cities)
            
            event_types = ['art exhibition', 'music festival', 'sporting event', 'cultural festival', 'conference', 'holiday celebration', 'food festival', 'film festival', 'design week', 'fashion week']
            preferred_event_type = random.choice(event_types)
            
            diversity_note = f"\n\nCRITICAL DIVERSITY REQUIREMENT: You MUST choose a DIFFERENT event than any shown in the examples. "
            if recent_events:
                diversity_note += f"DO NOT use: {', '.join(recent_events[:3])}. "
            diversity_note += f"STRONGLY PREFER: an event in {preferred_city} (or another city if {preferred_city} has no suitable events). "
            diversity_note += f"STRONGLY PREFER event type: {preferred_event_type} (or similar). "
            diversity_note += f"Rotate between all 4 cities. Vary event types significantly. If you see 'Mobile World Congress' or 'conference' in examples, choose a festival, exhibition, or sporting event instead. Be creative and diverse.\n"
            
            month_year_instruction = f"\n\nCRITICAL FOR OCCASION: You MUST find a significant event happening in {next_month_info['month']} {next_month_info['year']} in one of the 4 cities (Istanbul, Barcelona, New York, San Francisco). The event dates in the title MUST be in {next_month_info['month']} {next_month_info['year']}. Do NOT use events from other months. Focus on major events: F1/sporting events, concerts, music festivals, art exhibitions, cultural events, conferences, holiday celebrations happening specifically in {next_month_info['month']} {next_month_info['year']}.{diversity_note}"
    
    # Adjust instruction based on whether examples exist
    if examples:
        instruction_text = "Generate new content following the same style, tone, and format as the examples."
    else:
        instruction_text = "Generate new content following the rubric prompt instructions above."
    
    user_prompt = f"""You are generating content for the "{rubric_name}" rubric.{city_info}{month_year_instruction}
RUBRIC PROMPT:
{rubric_prompt}{examples_text}

{instruction_text}{city_instruction} Return ONLY valid JSON with these fields:
{{
  "title": "...",
  "post_text": "...",
  "image_prompt": "..."
}}"""
    
    return user_prompt


def parse_ai_response(response_text):
    """Extract and parse JSON from AI response"""
    if not response_text:
        raise ValueError("Empty response from AI")
    
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find JSON object directly
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = response_text.strip()
    
    # Clean up the JSON string
    json_str = json_str.strip()
    # Remove leading/trailing whitespace and newlines
    json_str = re.sub(r'^\s+|\s+$', '', json_str, flags=re.MULTILINE)
    
    try:
        data = json.loads(json_str)
        # Validate required fields
        if not all(key in data for key in ['title', 'post_text', 'image_prompt']):
            raise ValueError("Missing required fields in response")
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in response: {e}")


def call_openrouter_api(system_prompt, user_prompt):
    """Call OpenRouter API to generate content"""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in environment")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Add temperature for more diversity, especially for Occasion rubric
    temperature = 0.9  # Higher temperature for more creative/diverse outputs
    
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        # Extract content from response
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            return content
        else:
            raise ValueError("Unexpected API response format")
    except requests.exceptions.RequestException as e:
        raise Exception(f"API request failed: {str(e)}")


@app.route('/css/<path:filename>')
def serve_css(filename):
    """Serve CSS files from public directory for local development and Vercel"""
    from flask import send_from_directory, Response, make_response
    import os
    
    # Get the base directory (project root)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    public_path = os.path.join(base_dir, 'public', 'css')
    file_path = os.path.join(public_path, filename)
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
            
            response = make_response(css_content)
            response.headers['Content-Type'] = 'text/css; charset=utf-8'
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
        except Exception as e:
            print(f"Error serving CSS file: {e}")
            return Response(f'Error: {str(e)}', status=500, mimetype='text/plain')
    else:
        return Response(f'File not found: {filename}', status=404, mimetype='text/plain')


@app.route('/')
def index():
    """Render rubric selection screen"""
    try:
        prompts = load_prompts()
        rubrics = prompts.get('rubrics', {})
        return render_template('index.html', rubrics=rubrics)
    except Exception as e:
        print(f"Error rendering index.html: {e}")
        return f"Error loading page: {str(e)}", 500


@app.route('/favicon.ico')
def favicon():
    """Handle favicon requests"""
    return '', 204  # No content


@app.route('/api/cities/search', methods=['GET'])
def search_cities():
    """Search for cities using OpenStreetMap Nominatim API"""
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 2:
        return jsonify({'cities': []})
    
    try:
        # Use Nominatim API for city search
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': query,  # Use query as-is, don't add "city"
            'format': 'json',
            'limit': 20,  # Get more results to filter better
            'addressdetails': 1,
            # Don't restrict to 'city' featuretype - it's too strict
            # Instead filter in code
            'dedupe': 1  # Deduplicate results
        }
        headers = {
            'User-Agent': 'Tripo Content Studio'  # Required by Nominatim
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        results = response.json()
        
        # Debug: log results count
        print(f"Search query: '{query}', Results count: {len(results)}")
        
        cities = []
        seen_names = set()
        query_lower = query.lower().strip()
        
        for result in results:
            address = result.get('address', {})
            display_name_full = result.get('display_name', '')
            class_type = result.get('class', '')
            place_type = result.get('type', '')
            
            # Skip if it's clearly not a city (like a street, building, etc.)
            # But be lenient - include administrative boundaries, places, etc.
            if class_type in ['highway', 'building', 'amenity', 'shop', 'leisure']:
                continue
            
            # Try to get city name from different fields, prioritizing 'city'
            city_name = (address.get('city') or 
                        address.get('town') or 
                        address.get('village') or 
                        address.get('municipality') or
                        address.get('county') or
                        address.get('state_district'))
            
            # If no city name in address, try to extract from display_name
            # This is important for cities like Istanbul that might not have proper address fields
            if not city_name and display_name_full:
                # Extract first part before comma (usually city name)
                parts = display_name_full.split(',')
                if parts:
                    potential_city = parts[0].strip()
                    # Remove common suffixes that aren't part of city name
                    potential_city = potential_city.replace(' Province', '').replace(' Province', '')
                    # Only use if it looks like a city name
                    if len(potential_city) < 50 and len(potential_city) > 1:
                        city_name = potential_city
            
            country = address.get('country', '')
            
            if city_name:
                # Normalize city name (handle Turkish characters like İ -> i)
                city_name_normalized = city_name.lower()
                # Replace Turkish İ with regular i for comparison
                city_name_normalized = city_name_normalized.replace('ı', 'i').replace('ş', 's').replace('ğ', 'g').replace('ü', 'u').replace('ö', 'o').replace('ç', 'c')
                query_normalized = query_lower.replace('ı', 'i').replace('ş', 's').replace('ğ', 'g').replace('ü', 'u').replace('ö', 'o').replace('ç', 'c')
                
                # Better filtering: prioritize exact or close matches
                # Check if query matches the beginning of city name (most relevant)
                starts_with = city_name_normalized.startswith(query_normalized)
                contains = query_normalized in city_name_normalized
                
                # More lenient filtering - include if:
                # 1. City starts with query (best match)
                # 2. City contains query anywhere (still relevant)
                # This ensures we find cities like Istanbul for "Istan"
                should_include = starts_with or contains
                
                # Use normalized version for comparison, but keep original for display
                city_name_lower = city_name_normalized
                
                if should_include:
                    # Avoid duplicates
                    city_key = f"{city_name}_{country}".lower()
                    if city_key not in seen_names:
                        seen_names.add(city_key)
                        
                        # Create display name
                        if country:
                            display_name = f"{city_name}, {country}"
                        else:
                            display_name = city_name
                        
                        # Calculate relevance score
                        importance = float(result.get('importance', 0))
                        relevance = 0
                        
                        if starts_with:
                            # Cities starting with query get highest score
                            # Combine with importance for better ranking
                            relevance = 10000 + (importance * 100) - len(city_name)
                        elif contains:
                            # Cities containing query get lower score
                            pos = city_name_lower.find(query_normalized)
                            relevance = 5000 + (importance * 50) - pos - len(city_name) * 0.1
                        
                        cities.append({
                            'name': city_name,
                            'display': display_name,
                            'country': country,
                            'relevance': relevance
                        })
        
        # Sort by relevance (higher first), then alphabetically
        cities.sort(key=lambda x: (-x['relevance'], x['name'].lower()))
        
        # Remove relevance from response
        for city in cities:
            city.pop('relevance', None)
        
        # If no results found, try a broader search without restrictions
        if len(cities) == 0 and len(query) >= 3:
            print(f"No cities found, trying broader search for '{query}'")
            # Try again with more lenient parameters
            params_broad = {
                'q': query,
                'format': 'json',
                'limit': 15,
                'addressdetails': 1,
                'dedupe': 1
            }
            try:
                response_broad = requests.get(url, params=params_broad, headers=headers, timeout=5)
                response_broad.raise_for_status()
                results_broad = response_broad.json()
                
                # Process with same logic but more lenient
                for result in results_broad:
                    address = result.get('address', {})
                    city_name = (address.get('city') or 
                                address.get('town') or 
                                address.get('village') or 
                                address.get('municipality'))
                    
                    if not city_name:
                        display_name_full = result.get('display_name', '')
                        if display_name_full:
                            parts = display_name_full.split(',')
                            if parts:
                                city_name = parts[0].strip()
                    
                    if city_name:
                        city_name_lower = city_name.lower()
                        if query_lower in city_name_lower:
                            city_key = f"{city_name}_{address.get('country', '')}".lower()
                            if city_key not in seen_names:
                                seen_names.add(city_key)
                                country = address.get('country', '')
                                display_name = f"{city_name}, {country}" if country else city_name
                                importance = float(result.get('importance', 0))
                                
                                starts_with = city_name_lower.startswith(query_lower)
                                relevance = 10000 + (importance * 100) if starts_with else 5000 + (importance * 50)
                                
                                cities.append({
                                    'name': city_name,
                                    'display': display_name,
                                    'country': country,
                                    'relevance': relevance
                                })
                
                # Sort again
                cities.sort(key=lambda x: (-x['relevance'], x['name'].lower()))
                for city in cities:
                    city.pop('relevance', None)
                    
            except Exception as e2:
                print(f"Error in fallback search: {e2}")
        
        print(f"Final cities found: {len(cities)}")
        return jsonify({'cities': cities[:5]})  # Return top 5 most relevant
    
    except Exception as e:
        print(f"Error searching cities: {e}")
        return jsonify({'cities': [], 'error': str(e)}), 500


@app.route('/api/cities/validate', methods=['POST'])
def validate_city():
    """Validate that a city exists using OpenStreetMap Nominatim API"""
    data = request.get_json()
    city_name = data.get('city', '').strip()
    
    if not city_name:
        return jsonify({'valid': False, 'error': 'City name is required'}), 400
    
    try:
        # Use Nominatim API to validate city
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': city_name,
            'format': 'json',
            'limit': 1,
            'addressdetails': 1,
            'featuretype': 'city'
        }
        headers = {
            'User-Agent': 'Tripo Content Studio'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        results = response.json()
        
        if results:
            address = results[0].get('address', {})
            found_city = address.get('city') or address.get('town') or address.get('village') or address.get('municipality')
            country = address.get('country', '')
            
            # Check if the found city matches the input (case-insensitive)
            if found_city and city_name.lower() in found_city.lower() or found_city.lower() in city_name.lower():
                return jsonify({
                    'valid': True,
                    'city': found_city,
                    'country': country,
                    'display': f"{found_city}, {country}" if country else found_city
                })
        
        return jsonify({'valid': False, 'error': 'City not found'}), 404
    
    except Exception as e:
        print(f"Error validating city: {e}")
        return jsonify({'valid': False, 'error': f'Validation failed: {str(e)}'}), 500


@app.route('/generate', methods=['POST'])
def generate():
    """Generate content for selected rubric"""
    try:
        data = request.get_json()
        rubric_name = data.get('rubric')
        city = data.get('city')
        
        if not rubric_name:
            return jsonify({'error': 'Rubric name is required'}), 400
        
        # Check if rubric requires city
        requires_city = rubric_requires_city(rubric_name)
        
        if requires_city:
            if not city or not city.strip():
                return jsonify({'error': 'City is required'}), 400
            city = city.strip()
            print(f"Generating content for rubric '{rubric_name}' with city '{city}'")
        else:
            city = None
            print(f"Generating content for rubric '{rubric_name}' (city not required)")
        
        # Load TOV content
        tov = load_tov()
        
        # Get examples for this rubric (use 3 for better focus on structure)
        examples = get_examples_by_rubric(rubric_name, count=3)
        
        # Get previous title if provided (for Try Again functionality, especially for Occasion)
        previous_title = data.get('previous_title')
        
        # Construct generation prompt
        user_prompt = construct_generation_prompt(rubric_name, examples, city=city, previous_title=previous_title)
        print(f"Generated prompt length: {len(user_prompt)} characters")
        
        # Call OpenRouter API
        ai_response = call_openrouter_api(tov, user_prompt)
        
        # Parse response
        parsed_data = parse_ai_response(ai_response)
        
        # Add rubric name and prompt type to response
        parsed_data['rubric'] = rubric_name
        parsed_data['prompt_type'] = determine_prompt_type(rubric_name)
        
        return jsonify(parsed_data)
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Generation failed: {str(e)}'}), 500


@app.route('/save', methods=['POST'])
def save():
    """Save generated post to Supabase or Data.json"""
    global posts_data
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['rubric', 'title', 'post_text', 'image_prompt']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Use Supabase if available
        if USE_SUPABASE and supabase:
            try:
                # Create new post object (id will be auto-generated by Supabase)
                new_post = {
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'rubric': data['rubric'],
                    'title': data['title'],
                    'post_text': data['post_text'],
                    'image_prompt': data['image_prompt']
                }
                
                # Insert into Supabase
                response = supabase.table('posts').insert(new_post).execute()
                
                if response.data and len(response.data) > 0:
                    saved_post = response.data[0]
                    new_id = saved_post.get('id')
                    
                    # Clear cache to force reload on next request
                    posts_data = None
                    
                    return jsonify({'success': True, 'id': new_id})
                else:
                    return jsonify({'error': 'Failed to save post to Supabase'}), 500
            except Exception as e:
                print(f"Error saving to Supabase: {e}")
                return jsonify({'error': f'Failed to save post: {str(e)}'}), 500
        
        # Fallback to file-based storage
        # Load existing posts
        posts = load_data()
        
        # Generate new ID
        if posts:
            new_id = max(p['id'] for p in posts) + 1
        else:
            new_id = 1
        
        # Create new post object
        new_post = {
            'id': new_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'rubric': data['rubric'],
            'title': data['title'],
            'post_text': data['post_text'],
            'image_prompt': data['image_prompt']
        }
        
        # Insert at the beginning of the list (newest first)
        posts.insert(0, new_post)
        if save_data(posts):
            # Update cache
            posts_data = posts
            return jsonify({'success': True, 'id': new_id})
        else:
            return jsonify({'error': 'Failed to save post'}), 500
    
    except Exception as e:
        return jsonify({'error': f'Save failed: {str(e)}'}), 500


@app.route('/result')
def result():
    """Render result display screen"""
    # Get data from query parameters or session
    # For now, we'll pass data via JavaScript after generation
    return render_template('result.html')


# ==================== ADMIN ROUTES ====================

@app.route('/admin')
def admin_index():
    """Redirect to admin dashboard"""
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'error')
            return render_template('admin/login.html'), 401
    
    # If already logged in, redirect to dashboard
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/login.html')


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


def save_prompts(data):
    """Save prompts data to Supabase or Posts_propts.json"""
    global prompts_data
    # Use Supabase if available
    if USE_SUPABASE and supabase:
        try:
            rubrics = data.get('rubrics', {})
            
            # Save/update each rubric
            for rubric_name, rubric_data in rubrics.items():
                rubric_record = {
                    'name': rubric_name,
                    'icon': rubric_data.get('icon'),
                    'title_prompt': rubric_data.get('title_prompt'),
                    'post_prompt': rubric_data.get('post_prompt'),
                    'image_prompt': rubric_data.get('image_prompt'),
                    'video_prompt': rubric_data.get('video_prompt'),
                    'additional': rubric_data.get('additional'),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }
                # Remove None values
                rubric_record = {k: v for k, v in rubric_record.items() if v is not None}
                
                # Upsert (insert or update)
                supabase.table('rubrics').upsert(rubric_record, on_conflict='name').execute()
            
            # Save common settings
            if 'common' in data:
                supabase.table('settings').upsert({
                    'key': 'common',
                    'value': data['common'],
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }, on_conflict='key').execute()
            
            # Save metadata
            if 'metadata' in data:
                supabase.table('settings').upsert({
                    'key': 'metadata',
                    'value': data['metadata'],
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }, on_conflict='key').execute()
            
            # Clear cache
            prompts_data = None
            return True
        except Exception as e:
            print(f"Error saving prompts to Supabase: {e}")
            return False
    
    # Fallback to file-based storage
    try:
        with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # Clear cache to force reload
        prompts_data = None
        return True
    except Exception as e:
        print(f"Error saving prompts: {e}")
        return False


def get_rubric(rubric_name):
    """Get a specific rubric by name"""
    prompts = load_prompts()
    rubrics = prompts.get('rubrics', {})
    return rubrics.get(rubric_name)


def validate_rubric_data(data, exclude_name=None):
    """Validate rubric data"""
    errors = []
    
    rubric_name = data.get('name', '').strip()
    if not rubric_name:
        errors.append('Rubric name is required')
    
    # Check for duplicate names (when adding new rubric)
    if exclude_name is None:
        prompts = load_prompts()
        rubrics = prompts.get('rubrics', {})
        if rubric_name in rubrics:
            errors.append(f'Rubric with name "{rubric_name}" already exists')
    
    return errors


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard with list of rubrics"""
    prompts = load_prompts()
    rubrics = prompts.get('rubrics', {})
    return render_template('admin/dashboard.html', rubrics=rubrics)


@app.route('/admin/rubric/add', methods=['GET', 'POST'])
@admin_required
def admin_add_rubric():
    """Add new rubric"""
    if request.method == 'POST':
        data = request.form.to_dict()
        
        # Validate
        errors = validate_rubric_data(data)
        if errors:
            return render_template('admin/rubric_form.html', 
                                 errors=errors, 
                                 form_data=data, 
                                 mode='add'), 400
        
        rubric_name = data.get('name', '').strip()
        
        # Build rubric object
        rubric_data = {}
        if data.get('icon'):
            rubric_data['icon'] = data.get('icon').strip()
        if data.get('title_prompt'):
            rubric_data['title_prompt'] = data.get('title_prompt').strip()
        if data.get('post_prompt'):
            rubric_data['post_prompt'] = data.get('post_prompt').strip()
        if data.get('image_prompt'):
            rubric_data['image_prompt'] = data.get('image_prompt').strip()
        if data.get('video_prompt'):
            rubric_data['video_prompt'] = data.get('video_prompt').strip()
        if data.get('additional'):
            rubric_data['additional'] = data.get('additional').strip()
        
        # Load and update prompts
        prompts = load_prompts()
        if 'rubrics' not in prompts:
            prompts['rubrics'] = {}
        
        prompts['rubrics'][rubric_name] = rubric_data
        
        if save_prompts(prompts):
            flash(f'Rubric "{rubric_name}" successfully added', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Error saving rubric', 'error')
            return render_template('admin/rubric_form.html', 
                                 errors=['Save error'], 
                                 form_data=data, 
                                 mode='add'), 500
    
    return render_template('admin/rubric_form.html', mode='add', form_data={})


@app.route('/admin/rubric/edit/<path:rubric_name>', methods=['GET', 'POST'])
@admin_required
def admin_edit_rubric(rubric_name):
    """Edit existing rubric"""
    prompts = load_prompts()
    rubrics = prompts.get('rubrics', {})
    
    if rubric_name not in rubrics:
        flash(f'Rubric "{rubric_name}" not found', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        data = request.form.to_dict()
        new_name = data.get('name', '').strip()
        
        # Validate
        errors = []
        if not new_name:
            errors.append('Rubric name is required')
        
        # Check for duplicate names (if name changed)
        if new_name != rubric_name and new_name in rubrics:
            errors.append(f'Rubric with name "{new_name}" already exists')
        
        if errors:
            rubric_data = rubrics[rubric_name]
            form_data = {
                'name': new_name or rubric_name,
                'icon': rubric_data.get('icon', ''),
                'title_prompt': rubric_data.get('title_prompt', ''),
                'post_prompt': rubric_data.get('post_prompt', ''),
                'image_prompt': rubric_data.get('image_prompt', ''),
                'video_prompt': rubric_data.get('video_prompt', ''),
                'additional': rubric_data.get('additional', '')
            }
            return render_template('admin/rubric_form.html', 
                                 errors=errors, 
                                 form_data=form_data, 
                                 mode='edit',
                                 original_name=rubric_name), 400
        
        # Build updated rubric object
        rubric_data = {}
        if data.get('icon'):
            rubric_data['icon'] = data.get('icon').strip()
        if data.get('title_prompt'):
            rubric_data['title_prompt'] = data.get('title_prompt').strip()
        if data.get('post_prompt'):
            rubric_data['post_prompt'] = data.get('post_prompt').strip()
        if data.get('image_prompt'):
            rubric_data['image_prompt'] = data.get('image_prompt').strip()
        if data.get('video_prompt'):
            rubric_data['video_prompt'] = data.get('video_prompt').strip()
        if data.get('additional'):
            rubric_data['additional'] = data.get('additional').strip()
        
        # Update prompts
        if new_name != rubric_name:
            # Name changed - remove old and add new
            del rubrics[rubric_name]
        
        rubrics[new_name] = rubric_data
        
        if save_prompts(prompts):
            flash(f'Rubric successfully updated', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Error saving rubric', 'error')
            rubric_data = rubrics.get(new_name, {})
            form_data = {
                'name': new_name,
                'icon': rubric_data.get('icon', ''),
                'title_prompt': rubric_data.get('title_prompt', ''),
                'post_prompt': rubric_data.get('post_prompt', ''),
                'image_prompt': rubric_data.get('image_prompt', ''),
                'video_prompt': rubric_data.get('video_prompt', ''),
                'additional': rubric_data.get('additional', '')
            }
            return render_template('admin/rubric_form.html', 
                                 errors=['Save error'], 
                                 form_data=form_data, 
                                 mode='edit',
                                 original_name=new_name), 500
    
    # GET request - show form with current data
    rubric_data = rubrics[rubric_name]
    form_data = {
        'name': rubric_name,
        'icon': rubric_data.get('icon', ''),
        'title_prompt': rubric_data.get('title_prompt', ''),
        'post_prompt': rubric_data.get('post_prompt', ''),
        'image_prompt': rubric_data.get('image_prompt', ''),
        'video_prompt': rubric_data.get('video_prompt', ''),
        'additional': rubric_data.get('additional', '')
    }
    return render_template('admin/rubric_form.html', 
                         mode='edit', 
                         form_data=form_data,
                         original_name=rubric_name)


@app.route('/admin/rubric/delete/<path:rubric_name>', methods=['POST'])
@admin_required
def admin_delete_rubric(rubric_name):
    """Delete rubric"""
    prompts = load_prompts()
    rubrics = prompts.get('rubrics', {})
    
    if rubric_name not in rubrics:
        flash(f'Rubric "{rubric_name}" not found', 'error')
        return redirect(url_for('admin_dashboard'))
    
    del rubrics[rubric_name]
    
    if save_prompts(prompts):
        flash(f'Rubric "{rubric_name}" successfully deleted', 'success')
    else:
        flash('Error deleting rubric', 'error')
    
    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    # Pre-load data on startup
    try:
        load_tov()
        load_prompts()
        load_data()
        print("Application initialized successfully")
    except Exception as e:
        print(f"Warning: Error during initialization: {e}")
    
    # Use port 5001 instead of 5000 to avoid conflict with AirPlay Receiver on macOS
    app.run(debug=True, port=5001, host='127.0.0.1')
