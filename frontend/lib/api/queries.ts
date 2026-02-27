import { apiClient } from "./client";
import {
  GameFile,
  GameFileSchema,
  Collection,
  CollectionSchema,
  Stats,
  StatsSchema,
  CrawlStatus,
  CrawlStatusSchema,
  SearchRequest,
  DownloadRequest,
} from "./types";
import { z } from "zod";

// API functions with Zod validation
export const gamesApi = {
  list: async (params?: {
    console?: string;
    collection?: string;
    limit?: number;
    offset?: number;
  }): Promise<GameFile[]> => {
    const { data } = await apiClient.get("/api/games", { params });
    return z.array(GameFileSchema).parse(data);
  },

  getById: async (id: number): Promise<GameFile> => {
    const { data } = await apiClient.get(`/api/games/${id}`);
    return GameFileSchema.parse(data);
  },

  search: async (request: SearchRequest): Promise<GameFile[]> => {
    const { data } = await apiClient.post("/api/search", request);
    return z.array(GameFileSchema).parse(data);
  },
};

export const collectionsApi = {
  list: async (): Promise<Collection[]> => {
    const { data } = await apiClient.get("/api/collections");
    return z.array(CollectionSchema).parse(data);
  },
};

export const consolesApi = {
  list: async (): Promise<string[]> => {
    const { data } = await apiClient.get("/api/consoles");
    return z.array(z.string()).parse(data);
  },
};

export const statsApi = {
  get: async (): Promise<Stats> => {
    const { data } = await apiClient.get("/api/stats");
    return StatsSchema.parse(data);
  },
};

export const crawlApi = {
  start: async (): Promise<{ status: string; message: string }> => {
    const { data } = await apiClient.post("/api/crawl/start");
    return data;
  },

  getStatus: async (): Promise<CrawlStatus> => {
    const { data } = await apiClient.get("/api/crawl/status");
    return CrawlStatusSchema.parse(data);
  },
};

export const downloadApi = {
  queue: async (
    request: DownloadRequest
  ): Promise<{ status: string; queued_count: number; game_ids: number[] }> => {
    const { data } = await apiClient.post("/api/download", request);
    return data;
  },

  getStatus: async (): Promise<{
    is_running: boolean;
    queue_length: number;
    active_downloads: number;
  }> => {
    const { data } = await apiClient.get("/api/download/status");
    return data;
  },
};
