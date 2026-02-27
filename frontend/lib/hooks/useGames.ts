import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { gamesApi, downloadApi } from "../api/queries";
import type { SearchRequest } from "../api/types";

export function useGames(params?: {
  console?: string;
  collection?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ["games", params],
    queryFn: () => gamesApi.list(params),
  });
}

export function useGame(id: number) {
  return useQuery({
    queryKey: ["game", id],
    queryFn: () => gamesApi.getById(id),
    enabled: !!id,
  });
}

export function useSearchGames() {
  return useMutation({
    mutationFn: (request: SearchRequest) => gamesApi.search(request),
  });
}

export function useQueueDownload() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (gameIds: number[]) => downloadApi.queue({ game_ids: gameIds }),
    onSuccess: () => {
      // Invalidate games query to refresh status
      queryClient.invalidateQueries({ queryKey: ["games"] });
    },
  });
}
