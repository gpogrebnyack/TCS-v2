# Tripo Content Studio

An AI-powered SMM assistant for generating text posts and image/video prompts for specific rubrics using AI.

## Features

- **AI-Powered Content Generation**: Generate posts using Google Gemini Flash 3.0 via OpenRouter
- **Multiple Rubrics**: Support for various content types (City Today, One Day In, Weekend In, etc.)
- **Admin Panel**: Manage rubrics and configurations through a web interface
- **Supabase Integration**: All data stored in PostgreSQL database
- **Serverless Deployment**: Ready for deployment on Vercel

## Tech Stack

- **Backend**: Python + Flask
- **Frontend**: Tailwind CSS
- **Database**: Supabase (PostgreSQL)
- **AI Model**: Google Gemini Flash 3.0 Preview via OpenRouter
- **Deployment**: Vercel

## Quick Start

### Prerequisites

- Python 3.11+
- Supabase account
- OpenRouter API key

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd "Tripo Content Sudio v2.2"
   ```

2. Create virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env and add your credentials
   ```

5. Set up Supabase:
   - Create a Supabase project
   - Run `supabase_migration.sql` in SQL Editor
   - Add `SUPABASE_URL` and `SUPABASE_KEY` to `.env`

6. Run the application:
   ```bash
   python app.py
   ```

7. Open your browser:
   ```
   http://localhost:5001
   ```

## Configuration

### Environment Variables

See `.env.example` for all required environment variables:

- `OPENROUTER_API_KEY` - Your OpenRouter API key
- `AI_MODEL` - AI model to use (default: `google/gemini-flash-3.0-preview`)
- `SECRET_KEY` - Flask session secret key
- `ADMIN_USERNAME` - Admin panel username
- `ADMIN_PASSWORD` - Admin panel password
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Your Supabase anon/public key

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions on Vercel.

## Project Structure

```
/
├── app.py                    # Main Flask application
├── requirements.txt          # Python dependencies
├── vercel.json              # Vercel configuration
├── supabase_migration.sql   # SQL script for Supabase
├── .env.example             # Environment variables template
├── public/                  # Static files
│   └── css/
│       └── styles.css
├── templates/               # HTML templates
└── TOV_prompts.md          # Tone of voice guidelines
```

## Features Overview

### Content Generation

- Select a rubric (content type)
- Optionally specify a city
- Generate AI-powered content
- Save generated posts

### Admin Panel

- Manage rubrics (add, edit, delete)
- Configure prompts for each rubric
- Access at `/admin` (requires authentication)

### Data Storage

All data is stored in Supabase:
- **Posts**: Generated content
- **Rubrics**: Content type configurations
- **Settings**: Application settings

## License

© 2026, Developed by Zhora Pogrebnyak
