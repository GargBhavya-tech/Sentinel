// Extended types for real backend integration
// Existing types (EvidenceItem, TimelineEvent, AgentStatus, InvestigationMetric)
// are preserved below — do not remove them.

export interface EvidenceItem {
  id: string;
  type: 'voice' | 'document' | 'thread' | 'spreadsheet' | 'payment';
  title: string;
  source: string;
  status: 'unverified' | 'suspicious' | 'threat' | 'verified';
  timestamp: string;
  description: string;
  content: string;
  rawJson?: string;
  confidence: number;
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  title: string;
  type: 'warning' | 'info' | 'success' | 'threat';
  description: string;
  sourceId: string;
  agentName: string;
}

export interface AgentStatus {
  id: string;
  name: string;
  role: string;
  status: 'idle' | 'analyzing' | 'complete' | 'alert' | 'error';
  currentTask: string;
  progress: number;
}

export interface InvestigationMetric {
  scannedCount: number;
  threatCount: number;
  verifiedCount: number;
  averageConfidence: number;
}

// ── New types for real backend SSE stream ─────────────────────────────────────

export interface ContradictionAxis {
  axis: string;
  detail: string;
  weight: number;
  evidence: string[];
}

export interface VerdictResult {
  caseId: string;
  shortId: string;
  verdict: 'FRAUD_LIKELY' | 'REVIEW' | 'CLEAR' | 'NEED_MORE_INFO';
  risk: number;
  contradictions: ContradictionAxis[];
  counterfactual: string | null;
  redTeamDefense: string | null;
  ruleId: string | null;
}

export interface SynthesizedRule {
  ruleId: string;
  description: string;
  status: 'shadow' | 'enforced';
  conditions?: Record<string, unknown>;
  createdAt?: string;
}

export interface AuditEntry {
  entryId: number;
  caseId: string;
  eventType: string;
  payload: Record<string, unknown>;
  prevHash: string;
  entryHash: string;
  createdAt: string;
}

export interface BlastRadiusData {
  nodes: Array<{
    id: string;
    node_type: string;
    label: string;
    is_origin: boolean;
  }>;
  edges: Array<{
    source: string;
    target: string;
    edge_type: string;
    count: number;
  }>;
  summary: string;
  totalReached: number;
  superSpreader: string | null;
  campaignClusterCount: number;
}

export interface ExpectedLoss {
  amountAtRisk: number;
  riskProbability: number;
  expectedLoss: number;
  attackerEconomics: {
    estimatedSetupCost: number;
    estimatedPayout: number;
    attackerRoiX: number;
  };
  triagePriority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface FederationMatch {
  patternType: string;
  orgsFlagged: number;
  firstSeenDaysAgo: number;
  confidence: number;
  description: string;
}

export interface FederationResult {
  matchesFound: number;
  matches: FederationMatch[];
  simulated: boolean;
  disclaimer: string;
  summary: string;
}

export interface ComplianceResult {
  shouldFileSar: boolean;
  sarRationale: string;
  dualApprovalRequired: boolean;
  freezeRecommended: boolean;
  answer: string;
  citations: string[];
}

export interface HoneypotTurn {
  turn: number;
  attackerSimulation: string;
  decoyResponse: string;
  extractionAttempt: string;
  trackingSignal: string;
}

export interface HoneypotResult {
  caseId: string;
  trackingToken: string;
  simulated: boolean;
  disclaimer: string;
  extractionAttemptsDetected: string[];
  dialogue: HoneypotTurn[];
  summary: string;
}

export interface EvalMetrics {
  headline: string;
  engineOn: {
    precision: number;
    recall: number;
    f1: number;
    tp: number;
    fp: number;
    tn: number;
    fn: number;
    n: number;
  };
  engineOff: {
    precision: number;
    recall: number;
    f1: number;
    n: number;
  };
  recallGain: number;
  nCaughtByEngineOnly: number;
  totalCases: number;
}

// ── SSE Event union type ───────────────────────────────────────────────────────

export type SSEEventType =
  | 'case_created'
  | 'temporal_recall'
  | 'agents_started'
  | 'agent_complete'
  | 'silence_triggered'
  | 'contradiction_result'
  | 'blast_radius'
  | 'rule_synthesized'
  | 'federation_check'
  | 'compliance_check'
  | 'red_team'
  | 'honeypot_result'
  | 'expected_loss'
  | 'verdict'
  | 'evidence_ingested'
  | 'file_forensics'
  | 'mcp_baseline'
  | 'voice_analysis'
  | 'demo_signals_injected'
  | 'self_play'
  | 'error'
  | 'stream_end';

export interface VoiceAnalysis {
  spoofScore: number;
  voiceMismatch: number;
  detectorAuc: number | null;
  detail: string;
}

export interface FileForensics {
  suspicious: boolean;
  summary: string;
  hiddenPayloads: string[];
  entropyAnomalies: number;
}

export interface SSEEvent {
  event: SSEEventType;
  data: Record<string, unknown>;
  ts: number;
}

// ── Investigation state (managed by useInvestigation hook) ────────────────────

export interface InvestigationState {
  caseId: string | null;
  shortId: string | null;
  isRunning: boolean;
  isComplete: boolean;
  agents: AgentStatus[];
  timeline: TimelineEvent[];
  verdict: VerdictResult | null;
  blastRadius: BlastRadiusData | null;
  synthesizedRule: SynthesizedRule | null;
  federation: FederationResult | null;
  compliance: ComplianceResult | null;
  honeypot: HoneypotResult | null;
  expectedLoss: ExpectedLoss | null;
  redTeam: { defense: string; trackRecord: string } | null;
  similarCases: Array<{ caseId: string; similarity: number; verdict: string }>;
  error: string | null;
  voiceAnalysis?: VoiceAnalysis | null;
  fileForensics?: FileForensics | null;
}
