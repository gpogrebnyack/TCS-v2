Technical Specification: Tripo Content Studio
Project Overview
An SMM assistant for generating text posts and image/video prompts for specific rubrics using AI.

Technology Stack
Backend: Python + Flask
Frontend: Tailwind CSS
AI Model: Google Gemini Flash 3 Preview via OpenRouter
Language: English (entire project)
UI Style: Minimalist design
Project Structure
/
├── app.py                 # Main Flask application
├── .env                   # Environment variables
├── Data.json             # Storage for saved posts
├── TOV_prompts.md        # Tone of voice guidelines
├── Posts_propts.json     # Rubric-specific prompts
├── templates/
│   ├── index.html        # Screen 1: Rubric selection
│   └── result.html       # Screen 2: Generated content
└── static/
    └── styles.css        # Tailwind CSS (if needed)
Environment Configuration (.env)
OPENROUTER_API_KEY=your_api_key_here
AI_MODEL=google/gemini-flash-3.0-preview
Screen 1: Rubric Selection
UI Components
Header: Service name/logo
Rubric Grid: Clickable cards with emoji icons for each rubric:
📍 On Location
🗓️ One Day In
📅 Weekend In
📸 City Today
💡 Best Prompts
🤔 The Ask
🎉 Occasion
✨ Tripo Horoscope
📌 Tripo Finds (Place)
📚 Tripo Finds (Collection)
Behavior
On click → trigger generation process → navigate to Screen 2
Show loading indicator during generation
Screen 2: Generation Result
UI Components
Content Blocks:

Title - Generated post title
Text for Post - Main post content
Prompt for Image/Video - Generation prompt (label changes based on rubric's image_prompt_type)
Action Buttons:

Try Again - Regenerate content for same rubric
Save Post - Save to Data.json and return to Screen 1
Back to Topics - Return to Screen 1 without saving
Behavior
Try Again: Call generation endpoint again, update display
Save Post: Add post to Data.json with:
Auto-increment ID
Current timestamp (ISO 8601 format)
Selected rubric name
Generated title, post_text, image_prompt
Back to Topics: Navigate to Screen 1
Generation Logic
Input Assembly
For each generation request, construct prompt with:

Tone of Voice (from TOV_prompts.md)

Load entire file content
Example Posts (from Data.json)

Filter posts by selected rubric
Include 3-5 most recent examples
Format: "Example 1: [title] [post_text] [image_prompt]"
Rubric Prompt (from Posts_propts.json)

Extract rubric-specific instructions from rubrics[selected_rubric]
Include: description, format, requirements, tone specifications
Prompt Structure
System Prompt:
{content from TOV_prompts.md}

User Prompt:
You are generating content for the "{rubric_name}" rubric.

RUBRIC GUIDELINES:
{rubric-specific instructions from Posts_propts.json}

EXAMPLES FROM THIS RUBRIC:
{3-5 recent posts from Data.json filtered by rubric}

Generate new content following the same style, tone, and format. Return ONLY valid JSON with these fields:
{
  "title": "...",
  "post_text": "...",
  "image_prompt": "..."
}
API Call
import requests

response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": tov_content},
            {"role": "user", "content": generation_prompt}
        ]
    }
)
Data Management
Reading Data.json
Load as Python list on startup
Filter by rubric when needed
Writing to Data.json
Generate new ID: max(existing IDs) + 1
Create timestamp: datetime.now(timezone.utc).isoformat()
Append new post object
Write back to file (pretty-printed JSON)
Post Object Structure
{
  "id": 40,
  "created_at": "2026-01-11T13:30:00.000000+00:00",
  "rubric": "Selected Rubric Name",
  "title": "Generated Title",
  "post_text": "Generated post content...",
  "image_prompt": "Generated image/video prompt..."
}
Key Implementation Details
Rubric Configuration
Each rubric in Posts_propts.json has image_prompt_type field:
"image" → Display "Prompt for Image"
"video" → Display "Prompt for Video"
"none" → Display "Prompt for Image" (default)
Error Handling
API failures: Show error message, allow retry
Invalid JSON response: Parse and retry
File I/O errors: Log and show user-friendly message
Response Parsing
Extract JSON from AI response
Validate required fields (title, post_text, image_prompt)
Handle edge cases (nested JSON, markdown code blocks)
UI/UX Guidelines
Design Principles
Clean, minimalist interface
Ample white space
Clear typography hierarchy
Subtle hover states on interactive elements
Loading states for async operations
Responsive Behavior
Mobile-first approach
Grid layout adapts to screen size
Buttons stack on small screens
Future Considerations
Session management for multiple users
Post editing capability
Export functionality (CSV, JSON)
Analytics dashboard
Version control for prompts
A/B testing different prompt structures
This specification provides the foundation for building the Tripo Content Studio SMM assistant.