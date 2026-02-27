import { useQuery } from "@tanstack/react-query";
import { collectionsApi, consolesApi } from "../api/queries";

export function useCollections() {
  return useQuery({
    queryKey: ["collections"],
    queryFn: () => collectionsApi.list(),
  });
}

export function useConsoles() {
  return useQuery({
    queryKey: ["consoles"],
    queryFn: () => consolesApi.list(),
  });
}
