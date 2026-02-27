# MyrientDL API

FastAPI backend for the MyrientDL web application.

## Setup

### Development (SQLite)

```bash
cd api
pip install -e .
cp .env.example .env
uvicorn api.main:app --reload
```

### Production (Supabase/PostgreSQL)

Set environment variables:
- `DATABASE_URL`: PostgreSQL connection string from Supabase
- `FRONTEND_URL`: Your frontend URL for CORS
- `PORT`: Port to run on (Render sets this automatically)

```bash
cd api
pip install -e .
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

## Deployment on Render

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Set build command: `cd api && pip install -e .`
4. Set start command: `cd api && uvicorn api.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables:
   - `DATABASE_URL` - Your Supabase PostgreSQL URL
   - `FRONTEND_URL` - Your Vercel frontend URL

## API Endpoints

- `GET /` - Health check
- `GET /api/collections` - List all collections with stats
- `POST /api/search` - Search games
- `GET /api/games` - List games with filters
- `GET /api/games/{id}` - Get game details
- `POST /api/crawl/start` - Start crawling Myrient
- `GET /api/crawl/status` - Get crawl status
- `POST /api/download` - Queue downloads
- `GET /api/download/status` - Get download status
- `GET /api/stats` - Get overall statistics
- `GET /api/consoles` - List all consoles
