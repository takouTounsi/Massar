import { useQuery } from "@tanstack/react-query";
import { getResources } from "../api/resources";

export function useResources(projectId: string) {
  return useQuery({
    queryKey: ["resources", projectId],
    queryFn: () => getResources(projectId),
    enabled: Boolean(projectId),
    retry: 1
  });
}
