# Deployment Guide: Tripo Content Studio on Vercel

This guide will help you deploy the Tripo Content Studio application to Vercel using Supabase for data storage.

## Prerequisites

- GitHub account
- Vercel account (sign up at https://vercel.com)
- Supabase account (sign up at https://supabase.com)
- OpenRouter API key (get from https://openrouter.ai/)

## Step 1: Set Up Supabase

1. Go to [Supabase](https://supabase.com) and create a new project
2. Wait for the project to be fully provisioned (takes a few minutes)
3. Go to **SQL Editor** in your Supabase dashboard
4. Copy and paste the contents of `supabase_migration.sql`
5. Run the SQL script to create all required tables:
   - `posts` - stores generated content posts
   - `rubrics` - stores rubric configurations
   - `settings` - stores application settings (cities, tags, metadata)
6. Go to **Settings** → **API** in your Supabase dashboard
7. Copy the following:
   - **Project URL** (e.g., `https://xxxxx.supabase.co`)
   - **anon/public key** (under "Project API keys")

## Step 2: Prepare Your Repository

1. Make sure all changes are committed:
   ```bash
   git add .
   git commit -m "Prepare for Vercel deployment with Supabase"
   ```

2. Push to GitHub:
   ```bash
   git push origin main
   ```

## Step 3: Deploy to Vercel

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click **Add New Project**
3. Import your GitHub repository
4. Vercel will auto-detect Flask - click **Deploy** (don't change settings yet)
5. Wait for the first deployment to complete (it will fail, that's expected)

## Step 4: Configure Environment Variables

1. In your Vercel project, go to **Settings** → **Environment Variables**
2. Add the following variables:

   ```
   OPENROUTER_API_KEY=your_openrouter_api_key
   AI_MODEL=google/gemini-flash-3.0-preview
   SECRET_KEY=generate_a_secure_random_key
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=your_secure_password
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your_supabase_anon_key
   ```

3. To generate a secure SECRET_KEY, run:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

4. Make sure to add these variables for **Production**, **Preview**, and **Development** environments

## Step 5: Redeploy

1. Go to **Deployments** tab in Vercel
2. Click the **⋯** menu on the latest deployment
3. Click **Redeploy**
4. Wait for deployment to complete

## Step 6: Test Your Deployment

1. Visit your Vercel deployment URL (e.g., `https://your-project.vercel.app`)
2. Test the following:
   - Generate a new post
   - Save a post
   - Access admin panel at `/admin`
   - Create/edit/delete rubrics in admin panel
   - Verify all data is being saved to Supabase

## Troubleshooting

### Deployment fails

- Check Vercel build logs for errors
- Verify all environment variables are set correctly
- Ensure `requirements.txt` includes all dependencies

### Posts not saving

- Verify Supabase credentials are correct
- Check Supabase dashboard to see if tables exist
- Check Vercel function logs for errors

### Rubrics not saving

- Verify `rubrics` table exists in Supabase
- Check that `settings` table exists
- Verify admin panel has proper authentication

### Static files not loading

- Verify `public/css/styles.css` exists
- Check that templates use `/css/styles.css` (not `url_for('static', ...)`)

### Database connection errors

- Verify SUPABASE_URL and SUPABASE_KEY are correct
- Check Supabase project is active
- Verify all tables (`posts`, `rubrics`, `settings`) exist in Supabase

## Data Storage

All data is stored in Supabase PostgreSQL database:

- **Posts**: Generated content posts are stored in the `posts` table
- **Rubrics**: Rubric configurations are stored in the `rubrics` table
- **Settings**: Application settings (cities, tags, metadata) are stored in the `settings` table

The application no longer uses local JSON files (`Data.json`, `Posts_propts.json`) in production. These files are ignored by Git and only used as fallback for local development without Supabase.

## Local Development

For local development:

1. Set up your `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env and add your credentials
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

**Note**: If `SUPABASE_URL` and `SUPABASE_KEY` are not set in `.env`, the application will attempt to use local JSON files as fallback. However, for full functionality, Supabase should be configured.

## Project Structure

```
/
├── app.py                    # Main Flask application
├── requirements.txt          # Python dependencies
├── vercel.json              # Vercel configuration
├── supabase_migration.sql   # SQL script for Supabase tables
├── .env.example             # Environment variables template
├── .gitignore              # Git ignore rules
├── public/                 # Static files (served by Vercel)
│   └── css/
│       └── styles.css
├── templates/              # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── result.html
│   └── admin/
│       ├── dashboard.html
│       ├── login.html
│       └── rubric_form.html
├── TOV_prompts.md         # Tone of voice guidelines (read-only)
└── Task.md                # Project specification
```

## Support

If you encounter issues:
1. Check Vercel function logs
2. Check Supabase logs
3. Verify all environment variables are set
4. Review the deployment guide above
5. Ensure all Supabase tables are created correctly
