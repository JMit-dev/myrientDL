# MyrientDL Frontend

Next.js web interface for MyrientDL game archive downloader.

## Tech Stack

- **Next.js 15** - React framework
- **TypeScript** - Type safety
- **Chakra UI** - Component library
- **Tailwind CSS** - Utility-first CSS
- **TanStack Query** - Data fetching and caching
- **Axios** - HTTP client
- **Zod** - Runtime type validation

## Development

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Visit `http://localhost:3000`

## Environment Variables

Create `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Deployment on Vercel

1. Push your code to GitHub
2. Import project on Vercel
3. Set environment variable:
   - `NEXT_PUBLIC_API_URL` = Your Render API URL (e.g., `https://your-api.onrender.com`)
4. Deploy

Vercel will automatically detect Next.js and configure build settings.

## Features

- Search games by name, console, or collection
- Browse all collections and consoles
- Queue multiple games for download
- View download status and progress
- Real-time stats dashboard
- Start crawl jobs from the UI

## Project Structure

```
frontend/
├── app/                    # Next.js app router
│   ├── layout.tsx         # Root layout with providers
│   ├── page.tsx           # Home page
│   ├── providers.tsx      # Chakra UI + TanStack Query
│   └── globals.css        # Global styles
├── components/            # React components
│   └── GameList.tsx       # Game table with selection
├── lib/
│   ├── api/              # API client
│   │   ├── client.ts     # Axios instance
│   │   ├── types.ts      # Zod schemas and TypeScript types
│   │   └── queries.ts    # API functions
│   └── hooks/            # React hooks
│       ├── useGames.ts
│       ├── useCollections.ts
│       └── useStats.ts
└── public/               # Static assets
```
