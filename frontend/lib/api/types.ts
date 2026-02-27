import { z } from "zod";

// Zod schemas for API validation
export const GameFileSchema = z.object({
  id: z.number(),
  url: z.string(),
  name: z.string(),
  size: z.number().nullable(),
  console: z.string().nullable(),
  region: z.string().nullable(),
  collection: z.string(),
  file_format: z.string().nullable(),
  requires_conversion: z.boolean(),
  status: z.enum(["pending", "downloading", "completed", "failed", "paused"]),
  bytes_downloaded: z.number(),
  download_progress: z.number(),
  formatted_size: z.string(),
});

export const CollectionSchema = z.object({
  name: z.string(),
  game_count: z.number(),
  total_size: z.number(),
  update_frequency: z.string(),
  content_type: z.string(),
});

export const StatsSchema = z.object({
  total_games: z.number(),
  total_size: z.number(),
  downloaded_games: z.number(),
  downloaded_size: z.number(),
  pending_games: z.number(),
  failed_games: z.number(),
  collections_count: z.number(),
  consoles_count: z.number(),
});

export const CrawlStatusSchema = z.object({
  is_running: z.boolean(),
  games_found: z.number(),
  last_crawl: z.string().nullable(),
  current_url: z.string().nullable(),
  progress_percentage: z.number(),
});

// TypeScript types
export type GameFile = z.infer<typeof GameFileSchema>;
export type Collection = z.infer<typeof CollectionSchema>;
export type Stats = z.infer<typeof StatsSchema>;
export type CrawlStatus = z.infer<typeof CrawlStatusSchema>;

export interface SearchRequest {
  query: string;
  console?: string;
  collection?: string;
  limit?: number;
}

export interface DownloadRequest {
  game_ids: number[];
}
