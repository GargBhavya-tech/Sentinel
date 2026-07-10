/**
 * useInvestigation — React hook that manages the full investigation lifecycle.
 *
 * Usage:
 *   const inv = useInvestigation();
 *   inv.startInvestigation({ description: '...', amount_at_risk: 1450000 });
 *   // → inv.state.agents update live, inv.state.verdict populated at end
 *
 * Design notes:
 * - All EventSource cleanup is handled in a useEffect cleanup function to prevent
 *   memory leaks on unmount or re-trigger.
 * - Agent statuses map SSE `agent_complete` events to the AgentStatus[] array,
 *   keeping the visual progress bars alive during the stream.
 * - Before any events arrive, all agents show as 'idle' with a pulsing state.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  startInvestigation as apiStartInvestigation,
  subscribeToInvestigation,
  InvestigatePayload,
} from '../api/sentinel';
import type {
  AgentStatus,
  TimelineEvent,
  InvestigationState,
  VerdictResult,
  BlastRadiusData,
  SynthesizedRule,
  FederationResult,
  ComplianceResult,
  HoneypotResult,
  ExpectedLoss,
} from '../types';

// ── Default idle agent list (shown before any SSE events arrive) ───────────────
const INITIAL_AGENTS: AgentStatus[] = [
  { id: 'vision',      name: 'Vision / OCR Agent',        role: 'Document Forensics',      status: 'idle', currentTask: 'Awaiting deployment…', progress: 0 },
  { id: 'finance',     name: 'Finance Agent',              role: 'Transaction Audit',       status: 'idle', currentTask: 'Awaiting deployment…', progress: 0 },
  { id: 'stylometric', name: 'Stylometric Agent',          role: 'Writing Fingerprint',     status: 'idle', currentTask: 'Awaiting deployment…', progress: 0 },
  { id: 'voice',       name: 'Voice Authenticity Agent',   role: 'Acoustic Forensics',      status: 'idle', currentTask: 'Awaiting deployment…', progress: 0 },
  { id: 'threat_intel',name: 'Threat Intel Agent',         role: 'Domain / IP Reputation',  status: 'idle', currentTask: 'Awaiting deployment…', progress: 0 },
  { id: 'nlp',         name: 'NLP Agent',                  role: 'Scam Classification',     status: 'idle', currentTask: 'Awaiting deployment…', progress: 0 },
  { id: 'policy',      name: 'Policy Agent',               role: 'Authority & Approval',    status: 'idle', currentTask: 'Awaiting deployment…', progress: 0 },
  { id: 'compliance',  name: 'Compliance Agent',           role: 'Regulatory RAG',          status: 'idle', currentTask: 'Awaiting deployment…', progress: 0 },
];

const INITIAL_STATE: InvestigationState = {
  caseId: null,
  shortId: null,
  isRunning: false,
  isComplete: false,
  agents: INITIAL_AGENTS,
  timeline: [],
  verdict: null,
  blastRadius: null,
  synthesizedRule: null,
  federation: null,
  compliance: null,
  honeypot: null,
  expectedLoss: null,
  redTeam: null,
  similarCases: [],
  error: null,
};

// ── Agent progress simulation (while an agent is 'analyzing') ─────────────────
const simulateProgress = (current: number): number =>
  Math.min(95, current + Math.floor(Math.random() * 12) + 3);

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useInvestigation() {
  const [state, setState] = useState<InvestigationState>(INITIAL_STATE);
  const cleanupRef = useRef<(() => void) | null>(null);
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Tick analyzing agents' progress bars forward while they run
  useEffect(() => {
    if (!state.isRunning) return;

    progressIntervalRef.current = setInterval(() => {
      setState(prev => ({
        ...prev,
        agents: prev.agents.map(a =>
          a.status === 'analyzing'
            ? { ...a, progress: simulateProgress(a.progress) }
            : a
        ),
      }));
    }, 900);

    return () => {
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    };
  }, [state.isRunning]);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      cleanupRef.current?.();
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    };
  }, []);

  // ── SSE event handler ────────────────────────────────────────────────────────
  const handleEvent = useCallback((eventType: string, data: Record<string, unknown>) => {
    setState(prev => {
      switch (eventType) {

        case 'case_created':
          return {
            ...prev,
            caseId: data.case_id as string,
            shortId: data.short_id as string,
          };

        case 'temporal_recall': {
          const similar = (data.similar_cases as Array<Record<string, unknown>> || []).map(c => ({
            caseId: (c.case_id as string) || '',
            similarity: (c.similarity as number) || 0,
            verdict: (c.verdict as string) || '',
          }));
          const timelineEntry: TimelineEvent | null = similar.length > 0 ? {
            id: `recall-${Date.now()}`,
            timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
            title: 'Prior Similar Case Found',
            type: 'info',
            description: `${similar.length} similar case(s) found in temporal memory. Top match: ${similar[0]?.similarity * 100 | 0}% similarity — verdict was ${similar[0]?.verdict}.`,
            sourceId: 'temporal_recall',
            agentName: 'Temporal_Recall_Engine',
          } : null;
          return {
            ...prev,
            similarCases: similar,
            timeline: timelineEntry ? [timelineEntry, ...prev.timeline] : prev.timeline,
          };
        }

        case 'agents_started': {
          // Set all agents to analyzing
          const updatedAgents = prev.agents.map(a => ({
            ...a,
            status: 'analyzing' as const,
            currentTask: 'Ingesting evidence streams…',
            progress: 5,
          }));
          return { ...prev, agents: updatedAgents };
        }

        case 'agent_complete': {
          const agentId = data.agent_id as string;
          const agentStatus = data.status as 'complete' | 'error';
          const claimsData = data.claims as Record<string, unknown> || {};
          const elapsed = data.elapsed_ms as number || 0;

          const updatedAgents = prev.agents.map(a =>
            a.id === agentId
              ? {
                  ...a,
                  status: agentStatus === 'error' ? ('alert' as const) : ('complete' as const),
                  progress: 100,
                  currentTask: agentStatus === 'error'
                    ? `Error: ${(data.error as string || 'unknown').slice(0, 60)}`
                    : agentStatus === 'complete' && claimsData.should_file_sar !== undefined
                    ? `SAR required: ${claimsData.should_file_sar}. Compliance checked.`
                    : `Analysis complete — ${claimsData.claim_count || 0} claim(s) in ${elapsed | 0}ms`,
                }
              : a
          );

          const timelineEntry: TimelineEvent = {
            id: `agent-${agentId}-${Date.now()}`,
            timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
            title: `${data.agent_name} Complete`,
            type: agentStatus === 'error' ? 'warning' : 'info',
            description: agentStatus === 'error'
              ? `Agent encountered an error: ${(data.error as string || '').slice(0, 100)}`
              : `Analysis finished in ${elapsed | 0}ms. Claims: ${
                  JSON.stringify(claimsData).slice(0, 80)
                }`,
            sourceId: agentId,
            agentName: (data.agent_name as string) || agentId,
          };

          return {
            ...prev,
            agents: updatedAgents,
            timeline: [timelineEntry, ...prev.timeline],
          };
        }

        case 'silence_triggered': {
          const timelineEntry: TimelineEvent = {
            id: `silence-${Date.now()}`,
            timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
            title: 'Confidence-Calibrated Silence',
            type: 'warning',
            description: data.reason as string || 'Insufficient evidence to render a verdict.',
            sourceId: 'contradiction_engine',
            agentName: 'Contradiction_Engine',
          };
          const silenceVerdict: VerdictResult = {
            caseId: prev.caseId || '',
            shortId: prev.shortId || '',
            verdict: 'NEED_MORE_INFO',
            risk: 0,
            contradictions: [],
            counterfactual: data.reason as string || null,
            redTeamDefense: null,
            ruleId: null,
          };
          return {
            ...prev,
            verdict: silenceVerdict,
            timeline: [timelineEntry, ...prev.timeline],
          };
        }

        case 'contradiction_result': {
          const contradictions = (data.contradictions as Array<Record<string, unknown>> || []).map(c => ({
            axis: c.axis as string,
            detail: c.detail as string,
            weight: c.weight as number,
            evidence: (c.evidence as string[]) || [],
          }));

          const timelineEntry: TimelineEvent = {
            id: `contradiction-${Date.now()}`,
            timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
            title: 'Contradiction Engine Result',
            type: data.verdict === 'FRAUD_LIKELY' ? 'threat'
                : data.verdict === 'REVIEW' ? 'warning' : 'success',
            description: `Verdict: ${data.verdict} — Risk: ${((data.risk as number) * 100) | 0}%. ${
              contradictions.length} contradiction axis(es) fired.`,
            sourceId: 'contradiction_engine',
            agentName: 'Contradiction_Engine',
          };

          return {
            ...prev,
            verdict: {
              caseId: prev.caseId || '',
              shortId: prev.shortId || '',
              verdict: data.verdict as VerdictResult['verdict'],
              risk: data.risk as number,
              contradictions,
              counterfactual: (data.counterfactual as string) || null,
              redTeamDefense: null,
              ruleId: null,
            },
            timeline: [timelineEntry, ...prev.timeline],
          };
        }

        case 'blast_radius': {
          const blastRadius: BlastRadiusData = {
            nodes: (data.nodes as BlastRadiusData['nodes']) || [],
            edges: (data.edges as BlastRadiusData['edges']) || [],
            summary: (data.summary as string) || '',
            totalReached: (data.total_reached as number) || 0,
            superSpreader: (data.super_spreader as string) || null,
            campaignClusterCount: (data.campaign_cluster_count as number) || 0,
          };
          const timelineEntry: TimelineEvent = {
            id: `blast-${Date.now()}`,
            timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
            title: 'Blast Radius Mapped',
            type: 'warning',
            description: blastRadius.summary || `Pattern reached ${blastRadius.totalReached} node(s).`,
            sourceId: 'blast_radius',
            agentName: 'Graph_Analytics_Engine',
          };
          return { ...prev, blastRadius, timeline: [timelineEntry, ...prev.timeline] };
        }

        case 'rule_synthesized': {
          const rule: SynthesizedRule = {
            ruleId: (data.rule_id as string) || '',
            description: (data.description as string) || '',
            status: (data.status as SynthesizedRule['status']) || 'shadow',
            conditions: (data.conditions as Record<string, unknown>) || {},
          };
          const timelineEntry: TimelineEvent = {
            id: `rule-${Date.now()}`,
            timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
            title: 'Detection Rule Synthesized',
            type: 'success',
            description: `Rule "${rule.description.slice(0, 80)}" written as shadow. Awaiting promotion.`,
            sourceId: 'rule_engine',
            agentName: 'Self_Writing_Rule_Engine',
          };
          return { ...prev, synthesizedRule: rule, timeline: [timelineEntry, ...prev.timeline] };
        }

        case 'federation_check': {
          const fed: FederationResult = {
            matchesFound: (data.matches_found as number) || 0,
            matches: ((data.matches as Array<Record<string, unknown>>) || []).map(m => ({
              patternType: m.pattern_type as string,
              orgsFlagged: m.orgs_flagged as number,
              firstSeenDaysAgo: m.first_seen_days_ago as number,
              confidence: m.confidence as number,
              description: m.description as string,
            })),
            simulated: (data.simulated as boolean) ?? true,
            disclaimer: (data.disclaimer as string) || '',
            summary: (data.summary as string) || '',
          };
          if (fed.matchesFound > 0) {
            const timelineEntry: TimelineEvent = {
              id: `fed-${Date.now()}`,
              timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
              title: 'Federated Pattern Match [SIMULATED]',
              type: 'warning',
              description: fed.summary,
              sourceId: 'federation',
              agentName: 'Federated_Network',
            };
            return { ...prev, federation: fed, timeline: [timelineEntry, ...prev.timeline] };
          }
          return { ...prev, federation: fed };
        }

        case 'compliance_check': {
          const compliance: ComplianceResult = {
            shouldFileSar: (data.should_file_sar as boolean) || false,
            sarRationale: (data.sar_rationale as string) || '',
            dualApprovalRequired: (data.dual_approval_required as boolean) || false,
            freezeRecommended: (data.freeze_recommended as boolean) || false,
            answer: (data.answer as string) || '',
            citations: (data.citations as string[]) || [],
          };
          const timelineEntry: TimelineEvent = {
            id: `compliance-${Date.now()}`,
            timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
            title: `Compliance: SAR ${compliance.shouldFileSar ? 'REQUIRED' : 'Not Required'}`,
            type: compliance.shouldFileSar ? 'threat' : 'info',
            description: compliance.answer.slice(0, 150),
            sourceId: 'compliance',
            agentName: 'Compliance_Agent',
          };
          return { ...prev, compliance, timeline: [timelineEntry, ...prev.timeline] };
        }

        case 'red_team': {
          const timelineEntry: TimelineEvent = {
            id: `redteam-${Date.now()}`,
            timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
            title: 'Red Team Defense Generated',
            type: 'info',
            description: `Red Team argues: "${((data.defense as string) || '').slice(0, 120)}"`,
            sourceId: 'red_team',
            agentName: 'Red_Team_Agent',
          };
          return {
            ...prev,
            redTeam: { defense: data.defense as string || '', trackRecord: data.track_record as string || '' },
            verdict: prev.verdict ? { ...prev.verdict, redTeamDefense: data.defense as string || null } : prev.verdict,
            timeline: [timelineEntry, ...prev.timeline],
          };
        }

        case 'honeypot_result': {
          const hp: HoneypotResult = {
            caseId: (data.case_id as string) || '',
            trackingToken: (data.tracking_token as string) || '',
            simulated: (data.simulated as boolean) ?? true,
            disclaimer: (data.disclaimer as string) || '',
            extractionAttemptsDetected: (data.extraction_attempts_detected as string[]) || [],
            dialogue: ((data.dialogue as Array<Record<string, unknown>>) || []).map(t => ({
              turn: t.turn as number,
              attackerSimulation: t.attacker_simulation as string,
              decoyResponse: t.decoy_response as string,
              extractionAttempt: t.extraction_attempt as string,
              trackingSignal: t.tracking_signal as string,
            })),
            summary: (data.summary as string) || '',
          };
          const timelineEntry: TimelineEvent = {
            id: `honeypot-${Date.now()}`,
            timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
            title: 'Honeypot Exchange [SIMULATED]',
            type: 'info',
            description: `Attacker probed: ${hp.extractionAttemptsDetected.join(', ')}. Token: ${hp.trackingToken}`,
            sourceId: 'honeypot',
            agentName: 'Honeypot_Agent',
          };
          return { ...prev, honeypot: hp, timeline: [timelineEntry, ...prev.timeline] };
        }

        case 'expected_loss': {
          const el: ExpectedLoss = {
            amountAtRisk: (data.amount_at_risk as number) || 0,
            riskProbability: (data.risk_probability as number) || 0,
            expectedLoss: (data.expected_loss as number) || 0,
            attackerEconomics: {
              estimatedSetupCost: ((data.attacker_economics as Record<string, number>)?.estimated_setup_cost) || 0,
              estimatedPayout: ((data.attacker_economics as Record<string, number>)?.estimated_payout) || 0,
              attackerRoiX: ((data.attacker_economics as Record<string, number>)?.attacker_roi_x) || 0,
            },
            triagePriority: (data.triage_priority as ExpectedLoss['triagePriority']) || 'LOW',
          };
          const timelineEntry: TimelineEvent = {
            id: `loss-${Date.now()}`,
            timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
            title: `Expected Loss: $${el.expectedLoss.toLocaleString()} [${el.triagePriority}]`,
            type: el.triagePriority === 'CRITICAL' || el.triagePriority === 'HIGH' ? 'threat' : 'warning',
            description: `Amount at risk: $${el.amountAtRisk.toLocaleString()} × ${(el.riskProbability * 100) | 0}% risk = $${el.expectedLoss.toLocaleString()} expected loss. Attacker ROI: ${el.attackerEconomics.attackerRoiX}x.`,
            sourceId: 'expected_loss',
            agentName: 'Economic_Triage_Engine',
          };
          return { ...prev, expectedLoss: el, timeline: [timelineEntry, ...prev.timeline] };
        }

        case 'verdict': {
          const updatedAgents = prev.agents.map(a =>
            a.status === 'analyzing' ? { ...a, status: 'complete' as const, progress: 100 } : a
          );
          const timelineEntry: TimelineEvent = {
            id: `verdict-${Date.now()}`,
            timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
            title: `Final Verdict: ${data.verdict}`,
            type: data.verdict === 'FRAUD_LIKELY' ? 'threat'
                : data.verdict === 'REVIEW' ? 'warning'
                : data.verdict === 'CLEAR' ? 'success' : 'info',
            description: `Risk: ${((data.risk as number) * 100) | 0}%. ${
              (data.contradictions as Array<Record<string, unknown>> || []).length
            } contradiction axis(es). ${data.counterfactual ? `Counterfactual: ${data.counterfactual}` : ''}`,
            sourceId: 'verdict',
            agentName: 'SENTINEL_CORE',
          };
          return {
            ...prev,
            isComplete: true,
            isRunning: false,
            agents: updatedAgents,
            verdict: {
              caseId: (data.case_id as string) || prev.caseId || '',
              shortId: (data.short_id as string) || prev.shortId || '',
              verdict: data.verdict as VerdictResult['verdict'],
              risk: data.risk as number,
              contradictions: ((data.contradictions as Array<Record<string, unknown>>) || []).map(c => ({
                axis: c.axis as string,
                detail: c.detail as string,
                weight: c.weight as number,
                evidence: [],
              })),
              counterfactual: (data.counterfactual as string) || null,
              redTeamDefense: (data.red_team_defense as Record<string, string>)?.defense || prev.redTeam?.defense || null,
              ruleId: (data.rule_id as string) || null,
            },
            timeline: [timelineEntry, ...prev.timeline],
          };
        }

        case 'stream_end':
          return { ...prev, isRunning: false, isComplete: true };

        case 'error':
          return {
            ...prev,
            isRunning: false,
            error: (data.message as string) || 'Investigation failed',
          };

        default:
          return prev;
      }
    });
  }, []);

  // ── Start investigation ──────────────────────────────────────────────────────
  const startInvestigation = useCallback(async (payload: InvestigatePayload) => {
    // Close any existing stream
    cleanupRef.current?.();
    cleanupRef.current = null;

    setState({
      ...INITIAL_STATE,
      isRunning: true,
      agents: INITIAL_AGENTS.map(a => ({ ...a, status: 'idle', currentTask: 'Preparing…', progress: 0 })),
    });

    try {
      const { case_id } = await apiStartInvestigation(payload);

      setState(prev => ({ ...prev, caseId: case_id, shortId: case_id.slice(0, 8) }));

      const cleanup = subscribeToInvestigation(
        case_id,
        handleEvent,
        () => {
          setState(prev => ({ ...prev, isRunning: false, isComplete: true }));
        },
      );
      cleanupRef.current = cleanup;
    } catch (err) {
      setState(prev => ({
        ...prev,
        isRunning: false,
        error: err instanceof Error ? err.message : 'Failed to start investigation',
      }));
    }
  }, [handleEvent]);

  const resetInvestigation = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setState(INITIAL_STATE);
  }, []);

  return { state, startInvestigation, resetInvestigation };
}
