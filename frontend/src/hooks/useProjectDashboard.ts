import { useQuery } from "@tanstack/react-query";
import { getProjectDashboard } from "../api/projects";

export function useProjectDashboard(projectId: string) {
  return useQuery({
    queryKey: ["project-dashboard", projectId],
    queryFn: () => getProjectDashboard(projectId),
    enabled: Boolean(projectId),
    retry: 1
  });
}
