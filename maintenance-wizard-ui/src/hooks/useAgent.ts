import { useMutation } from '@tanstack/react-query';
import { streamAgentChat, postAgentDiagnose } from '@/api/agentApi';
import type { ChatRequest, DiagnoseRequest } from '@/models/types';

export function useAgentChat() {
  return useMutation({
    mutationFn: (request: ChatRequest) => streamAgentChat(request),
  });
}

export function useAgentDiagnose() {
  return useMutation({
    mutationFn: (request: DiagnoseRequest) => postAgentDiagnose(request),
  });
}
