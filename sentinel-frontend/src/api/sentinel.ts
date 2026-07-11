/**
 * Sentinel API client — typed calls to the FastAPI backend.
 *
 * All paths use relative URLs so the Vite proxy forwards them to :8000.
 * No direct cross-origin requests; no CORS issues.
 */

import type {
  SynthesizedRule,
  AuditEntry,
  EvalMetrics,
} from '../types';

const BASE = '';  // relative — Vite proxy handles forwarding

// ── Health ─────────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}

// ── Investigations ─────────────────────────────────────────────────────────────

export interface InvestigatePayload {
  description: string;
  amount_at_risk?: number;
  file_url?: string;
  channel?: string;
  reporter?: string;
  demo_case?: boolean;
}

export interface InvestigateResponse {
  case_id: string;
  short_id: string;
  stream_url: string;
  status: string;
}

export async function startInvestigation(
  payload: InvestigatePayload
): Promise<InvestigateResponse> {
  const res = await fetch(`${BASE}/api/investigate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to start investigation: ${res.status} ${text}`);
  }
  return res.json();
}

/**
 * Open an SSE EventSource for a running investigation.
 *
 * @param caseId  The case UUID returned by startInvestigation
 * @param onEvent Called for every parsed SSE event
 * @param onEnd   Called when the stream closes (stream_end or error)
 * @returns Cleanup function — call it to close the EventSource
 */
export function subscribeToInvestigation(
  caseId: string,
  onEvent: (eventType: string, data: Record<string, unknown>) => void,
  onEnd: () => void,
): () => void {
  const url = `${BASE}/api/investigate/${caseId}/stream`;
  const es = new EventSource(url);

  const eventTypes = [
    'case_created', 'temporal_recall', 'agents_started', 'agent_complete',
    'silence_triggered', 'contradiction_result', 'blast_radius',
    'rule_synthesized', 'federation_check', 'compliance_check',
    'red_team', 'honeypot_result', 'expected_loss', 'verdict',
    // Newer backend beats — must be registered or EventSource drops them.
    'evidence_ingested', 'file_forensics', 'mcp_baseline',
    'voice_analysis', 'demo_signals_injected', 'self_play',
    'error', 'stream_end',
  ];

  const handlers: Array<[string, EventListener]> = [];

  for (const evType of eventTypes) {
    const handler: EventListener = (e) => {
      try {
        const parsed = JSON.parse((e as MessageEvent).data);
        onEvent(evType, parsed.data ?? parsed);
        if (evType === 'stream_end' || evType === 'error') {
          es.close();
          onEnd();
        }
      } catch (err) {
        console.error('SSE parse error', err);
      }
    };
    es.addEventListener(evType, handler);
    handlers.push([evType, handler]);
  }

  es.onerror = () => {
    console.error('SSE connection error');
    es.close();
    onEnd();
  };

  // Return cleanup function
  return () => {
    for (const [evType, handler] of handlers) {
      es.removeEventListener(evType, handler);
    }
    es.close();
  };
}

// ── Cases ──────────────────────────────────────────────────────────────────────

export async function listCases(limit = 20): Promise<{ cases: unknown[] }> {
  const res = await fetch(`${BASE}/cases?limit=${limit}`);
  if (!res.ok) return { cases: [] };
  return res.json();
}

export async function getCase(caseId: string): Promise<unknown> {
  const res = await fetch(`${BASE}/cases/${caseId}`);
  if (!res.ok) throw new Error(`Case not found: ${caseId}`);
  return res.json();
}

export async function getCaseAudit(caseId: string): Promise<{ entries: AuditEntry[] }> {
  const res = await fetch(`${BASE}/cases/${caseId}/audit`);
  if (!res.ok) return { entries: [] };
  return res.json();
}

// ── Rules ──────────────────────────────────────────────────────────────────────

export async function listRules(): Promise<{ rules: SynthesizedRule[] }> {
  const res = await fetch(`${BASE}/api/rules`);
  if (!res.ok) return { rules: [] };
  return res.json();
}

export async function promoteRule(ruleId: string): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/api/rules/${ruleId}/promote`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to promote rule ${ruleId}`);
  return res.json();
}

// ── Metrics ────────────────────────────────────────────────────────────────────

export async function getMetrics(): Promise<EvalMetrics | { error: string }> {
  const res = await fetch(`${BASE}/api/metrics`);
  if (!res.ok) return { error: 'Metrics unavailable' };
  return res.json();
}

// ── Active Learning ────────────────────────────────────────────────────────────

export async function getActiveLearningStatus(): Promise<unknown> {
  const res = await fetch(`${BASE}/api/active-learning/status`);
  if (!res.ok) return {};
  return res.json();
}

export async function submitLabel(caseId: string, label: 0 | 1): Promise<unknown> {
  const res = await fetch(`${BASE}/api/active-learning/label`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ case_id: caseId, label }),
  });
  if (!res.ok) throw new Error('Failed to submit label');
  return res.json();
}

// ── Graph Snapshot ─────────────────────────────────────────────────────────────

export async function getGraphSnapshot(): Promise<unknown> {
  const res = await fetch(`${BASE}/graph/snapshot`);
  if (!res.ok) return {};
  return res.json();
}

// ── Audit Verify ───────────────────────────────────────────────────────────────

export async function verifyAudit(): Promise<{ intact: boolean; message: string }> {
  const res = await fetch(`${BASE}/audit/verify`);
  if (!res.ok) return { intact: false, message: 'Verification endpoint unavailable' };
  return res.json();
}

// ── Annotate ──────────────────────────────────────────────────────────────────

export async function addAnnotation(caseId: string, description: string): Promise<unknown> {
  const res = await fetch(`${BASE}/cases/${caseId}/annotate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description }),
  });
  if (!res.ok) throw new Error('Failed to add annotation');
  return res.json();
}
