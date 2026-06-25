import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { generateRoadmap, getRoadmap, regenerateRoadmap, updateRoadmapAction } from "../api/roadmap";

export function useRoadmap(projectId: string) {
  const queryClient = useQueryClient();
  const roadmapQuery = useQuery({
    queryKey: ["roadmap", projectId],
    queryFn: () => getRoadmap(projectId),
    enabled: Boolean(projectId),
    retry: 1
  });
  const generateMutation = useMutation({
    mutationFn: () => generateRoadmap(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roadmap", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project-dashboard", projectId] });
    }
  });
  const regenerateMutation = useMutation({
    mutationFn: () => regenerateRoadmap(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roadmap", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project-dashboard", projectId] });
    }
  });
  const updateActionMutation = useMutation({
    mutationFn: ({ actionId, status }: { actionId: string; status: string }) =>
      updateRoadmapAction(projectId, actionId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roadmap", projectId] });
      queryClient.invalidateQueries({ queryKey: ["project-dashboard", projectId] });
    }
  });
  return { roadmapQuery, generateMutation, regenerateMutation, updateActionMutation };
}
