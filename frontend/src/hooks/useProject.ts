import { useQuery } from "@tanstack/react-query";
import { listProjects } from "../api/projects";

export function useProject(projectId?: string) {
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects
  });
  const activeProject = projectsQuery.data?.find((project) => project.project_id === projectId) ?? projectsQuery.data?.[0] ?? null;
  return { projectsQuery, activeProject };
}
