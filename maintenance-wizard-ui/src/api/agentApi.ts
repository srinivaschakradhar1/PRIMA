import { httpClient } from './httpClient';
import type { ChatRequest, ChatResponse, DiagnoseRequest, DiagnoseResponse } from '@/models/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

interface SseEvent {
  event: string;
  data: string;
}

/** Parse a single raw SSE event block (fields separated by single newlines). */
function parseSseEvent(raw: string): SseEvent | null {
  let event = 'message';
  const dataLines: string[] = [];

  for (const line of raw.split('\n')) {
    if (line === '' || line.startsWith(':')) continue; // blank line or comment
    const colon = line.indexOf(':');
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? '' : line.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') event = value;
    else if (field === 'data') dataLines.push(value);
  }

  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join('\n') };
}

function parseErrorMessage(data: string): string {
  try {
    const parsed = JSON.parse(data);
    return parsed?.message || parsed?.detail || 'The assistant ran into an error.';
  } catch {
    return data || 'The assistant ran into an error.';
  }
}

/**
 * Streams the maintenance copilot response over Server-Sent Events.
 *
 * The backend emits periodic `heartbeat` events to keep the connection alive,
 * then a terminal `message` event (success) or `error` event (failure).
 * Resolves with the chat payload on `message`; rejects on `error` or a dropped
 * connection.
 */
export async function streamAgentChat(
  request: ChatRequest,
  signal?: AbortSignal
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/agent/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`The assistant request failed (status ${response.status}).`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // Normalize CRLF and accumulate; SSE events are separated by a blank line.
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');

      let separator: number;
      while ((separator = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, separator);
        buffer = buffer.slice(separator + 2);

        const parsed = parseSseEvent(rawEvent);
        if (!parsed || parsed.event === 'heartbeat') continue;

        if (parsed.event === 'error') {
          throw new Error(parseErrorMessage(parsed.data));
        }
        if (parsed.event === 'message') {
          return JSON.parse(parsed.data) as ChatResponse;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }

  throw new Error('The assistant closed the connection without a response.');
}

export async function postAgentDiagnose(request: DiagnoseRequest): Promise<DiagnoseResponse> {
  const { data } = await httpClient.post<DiagnoseResponse>('/agent/diagnose', request);
  return data;
}
