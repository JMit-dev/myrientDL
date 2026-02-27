import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { statsApi, crawlApi } from "../api/queries";

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: () => statsApi.get(),
    refetchInterval: 30000, // Refetch every 30 seconds
  });
}

export function useCrawlStatus() {
  return useQuery({
    queryKey: ["crawl-status"],
    queryFn: () => crawlApi.getStatus(),
    refetchInterval: 5000, // Refetch every 5 seconds when running
  });
}

export function useStartCrawl() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => crawlApi.start(),
    onSuccess: () => {
      // Invalidate crawl status and stats
      queryClient.invalidateQueries({ queryKey: ["crawl-status"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}
