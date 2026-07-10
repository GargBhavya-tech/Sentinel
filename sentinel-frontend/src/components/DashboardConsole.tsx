import { useState, useEffect, FormEvent, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  ShieldAlert, ShieldCheck, HelpCircle, Activity, 
  Clock, Search, FileText, Phone, Mail, 
  TrendingUp, RefreshCw, ChevronRight, Terminal, Network, ArrowLeft, Send,
  AlertTriangle, Zap, Scale, Eye, EyeOff, CheckCircle, XCircle, BarChart3
} from 'lucide-react';
import { TimelineEvent, AgentStatus } from '../types';
import { useInvestigation } from '../hooks/useInvestigation';
import { promoteRule, verifyAudit, getMetrics } from '../api/sentinel';

interface DashboardConsoleProps {
  onExit: () => void;
  investigation: ReturnType<typeof useInvestigation>;
}

export default function DashboardConsole({ onExit, investigation }: DashboardConsoleProps) {
  const { state } = investigation;
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPanel, setSelectedPanel] = useState<string | null>(null);
  const [newNote, setNewNote] = useState('');
  const [currentTime, setCurrentTime] = useState('');
  const [auditToggle, setAuditToggle] = useState(false);
  const [auditIntact, setAuditIntact] = useState<boolean | null>(null);
  const [metricsData, setMetricsData] = useState<Record<string, unknown> | null>(null);
  const [promotingRule, setPromotingRule] = useState(false);
  const [localTimeline, setLocalTimeline] = useState<TimelineEvent[]>([]);

  // Real-time UTC clock
  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setCurrentTime(now.toUTCString().replace('GMT', 'UTC'));
    }, 1000);
    setCurrentTime(new Date().toUTCString().replace('GMT', 'UTC'));
    return () => clearInterval(timer);
  }, []);

  // Sync timeline from SSE state
  useEffect(() => {
    setLocalTimeline(state.timeline);
  }, [state.timeline]);

  // Fetch metrics in background when investigation completes
  useEffect(() => {
    if (state.isComplete && !metricsData) {
      getMetrics().then(m => setMetricsData(m as Record<string, unknown>)).catch(() => {});
    }
  }, [state.isComplete, metricsData]);

  // ── Derived display values ──────────────────────────────────────────────────

  const agents: AgentStatus[] = state.agents;
  const verdict = state.verdict;
  const blastRadius = state.blastRadius;
  const synthesizedRule = state.synthesizedRule;
  const expectedLoss = state.expectedLoss;
  const compliance = state.compliance;
  const federation = state.federation;
  const honeypot = state.honeypot;
  const redTeam = state.redTeam;

  // For evidence feed — map timeline events to evidence-like items for display
  const evidenceFeed = localTimeline
    .filter(t => !['temporal_recall', 'stream_end'].includes(t.sourceId))
    .slice(0, 10)
    .map(t => ({
      id: t.id,
      type: (t.type === 'threat' ? 'voice' : t.type === 'warning' ? 'document' : 'thread') as 'voice' | 'document' | 'thread' | 'spreadsheet' | 'payment',
      title: t.title,
      source: t.agentName,
      status: (
        t.type === 'threat' ? 'threat' :
        t.type === 'warning' ? 'suspicious' :
        t.type === 'success' ? 'verified' : 'unverified'
      ) as 'threat' | 'suspicious' | 'verified' | 'unverified',
      timestamp: t.timestamp,
      description: t.description,
      content: t.description,
      confidence: t.type === 'threat' ? 92 : t.type === 'warning' ? 64 : t.type === 'success' ? 99 : 50,
    }));

  const filteredFeed = evidenceFeed.filter(item =>
    !searchTerm ||
    item.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.source.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const [selectedFeedId, setSelectedFeedId] = useState<string | null>(null);
  const selectedFeedItem = filteredFeed.find(i => i.id === selectedFeedId) || filteredFeed[0];

  // ── Risk display ────────────────────────────────────────────────────────────

  const riskPct = verdict ? Math.round(verdict.risk * 100) : 0;
  const verdictLabel = verdict?.verdict || (state.isRunning ? 'ANALYZING…' : 'STANDBY');
  const verdictColor =
    verdict?.verdict === 'FRAUD_LIKELY' ? '#EF4444' :
    verdict?.verdict === 'REVIEW' ? '#F59E0B' :
    verdict?.verdict === 'CLEAR' ? '#22C55E' :
    verdict?.verdict === 'NEED_MORE_INFO' ? '#38BDF8' :
    '#38BDF8';

  // ── Actions ─────────────────────────────────────────────────────────────────

  const handleAddNote = (e: FormEvent) => {
    e.preventDefault();
    if (!newNote.trim()) return;
    const timestamp = new Date().toUTCString().split(' ')[4] + ' UTC';
    const newEvent: TimelineEvent = {
      id: 'manual-' + Date.now(),
      timestamp,
      title: 'Manual Investigator Annotation',
      type: 'info',
      description: newNote,
      sourceId: state.caseId || 'manual',
      agentName: 'Secure_Human_Desk',
    };
    setLocalTimeline(prev => [newEvent, ...prev]);
    setNewNote('');
  };

  const handlePromoteRule = useCallback(async () => {
    if (!synthesizedRule) return;
    setPromotingRule(true);
    try {
      await promoteRule(synthesizedRule.ruleId);
      const note: TimelineEvent = {
        id: 'promote-' + Date.now(),
        timestamp: new Date().toUTCString().split(' ')[4] + ' UTC',
        title: 'Detection Rule Promoted to Enforced',
        type: 'success',
        description: `Rule ${synthesizedRule.ruleId.slice(0, 8)} promoted. Future cases will be fast-pathed.`,
        sourceId: 'rule_engine',
        agentName: 'Rule_Promotion_Audit',
      };
      setLocalTimeline(prev => [note, ...prev]);
    } catch (e) {
      console.error('Promote rule failed', e);
    } finally {
      setPromotingRule(false);
    }
  }, [synthesizedRule]);

  const handleVerifyAudit = useCallback(async () => {
    const result = await verifyAudit();
    setAuditIntact(result.intact);
  }, []);

  // ── Graph rendering ─────────────────────────────────────────────────────────

  const renderBlastRadiusGraph = () => {
    const nodes = blastRadius?.nodes || [];
    const edges = blastRadius?.edges || [];

    if (nodes.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center h-full gap-3 opacity-40">
          <Network className="w-8 h-8 text-electric-cyan animate-pulse" />
          <span className="font-mono text-[9px] text-slate-white/50 tracking-widest uppercase">
            {state.isRunning ? 'MAPPING BLAST RADIUS…' : 'AWAITING INVESTIGATION'}
          </span>
        </div>
      );
    }

    // Simple force-directed layout using fixed positions in a 200×200 viewBox
    const positionedNodes = nodes.map((n, idx) => {
      const angle = (idx / nodes.length) * 2 * Math.PI;
      const r = n.is_origin ? 0 : 75;
      const cx = 100 + r * Math.cos(angle);
      const cy = 100 + r * Math.sin(angle);
      return { ...n, cx, cy };
    });

    const nodeMap = Object.fromEntries(positionedNodes.map(n => [n.id, n]));

    return (
      <svg className="w-full h-full max-h-[320px]" viewBox="0 0 200 200">
        {edges.map((edge, idx) => {
          const src = nodeMap[edge.source];
          const tgt = nodeMap[edge.target];
          if (!src || !tgt) return null;
          return (
            <line
              key={idx}
              x1={src.cx} y1={src.cy}
              x2={tgt.cx} y2={tgt.cy}
              stroke={verdictColor}
              strokeWidth="1.5"
              strokeOpacity="0.4"
              strokeDasharray="3 1"
            />
          );
        })}
        {positionedNodes.map(node => {
          const color = node.is_origin ? '#EF4444' :
            node.node_type === 'channel' ? '#38BDF8' :
            node.node_type === 'file' ? '#F59E0B' : '#22C55E';
          return (
            <g key={node.id}>
              <circle
                cx={node.cx} cy={node.cy}
                r={node.is_origin ? 12 : 8}
                fill="#07080B"
                stroke={color}
                strokeWidth={node.is_origin ? 2.5 : 1.5}
                className="transition-all duration-300"
              />
              <circle cx={node.cx} cy={node.cy} r="3" fill={color} className={node.is_origin ? "animate-pulse" : ""} />
              <text
                x={node.cx}
                y={node.cy + (node.is_origin ? -15 : 18)}
                fontSize="5.5"
                fill="#F8FAFC"
                textAnchor="middle"
                fontFamily="monospace"
                opacity="0.6"
              >
                {node.label.slice(0, 14)}
              </text>
            </g>
          );
        })}
      </svg>
    );
  };

  // ── Metrics card ─────────────────────────────────────────────────────────────

  const renderMetricsCard = () => {
    if (!metricsData || (metricsData as { error?: string }).error) return null;
    const on = (metricsData.engine_on as Record<string, number>) || {};
    const nCaught = (metricsData.n_caught_by_engine_only as number) || 0;
    return (
      <div className="glass-panel p-4 rounded-xs border border-electric-cyan/10 mt-4">
        <div className="flex items-center gap-2 mb-3">
          <BarChart3 className="w-3.5 h-3.5 text-electric-cyan" />
          <span className="font-mono text-[9px] text-electric-cyan tracking-widest uppercase">[ EVAL HARNESS — TICKET #34 ]</span>
        </div>
        <div className="grid grid-cols-3 gap-3 mb-2">
          {[
            { label: 'PRECISION', value: `${((on.precision || 0) * 100).toFixed(0)}%` },
            { label: 'RECALL', value: `${((on.recall || 0) * 100).toFixed(0)}%` },
            { label: 'F1', value: `${((on.f1 || 0) * 100).toFixed(0)}%` },
          ].map(m => (
            <div key={m.label} className="text-center">
              <span className="font-mono text-[7px] text-slate-white/30 uppercase tracking-widest block">{m.label}</span>
              <span className="font-mono text-sm font-bold text-electric-cyan">{m.value}</span>
            </div>
          ))}
        </div>
        <p className="font-mono text-[8px] text-slate-white/40 leading-relaxed">
          Contradiction engine caught <span className="text-electric-cyan font-bold">{nCaught}</span> fraud(s) that single-model scoring missed.
        </p>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-obsidian text-slate-white flex flex-col font-sans select-none overflow-hidden h-screen">
      
      {/* 1. Header */}
      <header className="border-b border-slate-white/10 bg-obsidian/90 px-6 py-4 shrink-0 flex flex-col md:flex-row md:items-center justify-between gap-4 z-20">
        
        {/* Left identity branding */}
        <div className="flex items-center gap-4">
          <button 
            onClick={onExit}
            className="flex items-center gap-2 font-mono text-[10px] tracking-widest text-slate-white/40 hover:text-electric-cyan transition-colors duration-200 uppercase cursor-pointer focus:outline-none"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            [ EXIT CONSOLE ]
          </button>
          
          <div className="h-6 w-[1px] bg-slate-white/10 hidden md:block" />
          
          <div>
            <span className="font-display font-black text-sm tracking-[0.25em] text-slate-white uppercase block">
              SENTINEL COGNITIVE CONSOLE
            </span>
            <span className="font-mono text-[9px] tracking-wider text-slate-white/30 block mt-0.5">
              {state.caseId
                ? `CASE #${state.shortId} // ${state.isRunning ? 'ANALYZING' : state.isComplete ? 'VERDICT READY' : 'STANDBY'}`
                : 'FORENSIC AUDITING WORKSPACE // ACTIVE_PORT_3000'}
            </span>
          </div>
        </div>

        {/* Global Realtime System Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 md:gap-8 border border-slate-white/5 bg-slate-white/[0.01] rounded-xs px-5 py-2.5 max-w-2xl">
          <div className="flex flex-col">
            <span className="font-mono text-[8px] text-slate-white/30 tracking-widest uppercase">AGENTS ACTIVE</span>
            <span className="font-mono text-xs font-semibold text-slate-white">
              {agents.filter(a => a.status === 'analyzing').length}/{agents.length}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-[8px] text-evidence-crimson tracking-widest uppercase">RISK SCORE</span>
            <span className="font-mono text-xs font-semibold text-evidence-crimson animate-pulse">
              {state.isRunning ? '…' : `${riskPct}%`}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-[8px] text-cyber-emerald tracking-widest uppercase">VERDICT</span>
            <span className="font-mono text-xs font-semibold text-cyber-emerald" style={{ color: verdictColor }}>
              {verdictLabel}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-[8px] text-electric-cyan tracking-widest uppercase">SYSTEM CLOCK</span>
            <span className="font-mono text-[10px] text-electric-cyan whitespace-nowrap overflow-hidden text-ellipsis max-w-[130px] font-semibold">{currentTime}</span>
          </div>
        </div>
      </header>

      {/* 2. Live Agent Synapse Monitor Strip */}
      <section className="bg-obsidian border-b border-slate-white/5 px-6 py-2 shrink-0 flex items-center justify-between overflow-x-auto no-scrollbar gap-6">
        <div className="flex items-center gap-2 shrink-0">
          <Activity className="w-3.5 h-3.5 text-electric-cyan animate-pulse" />
          <span className="font-mono text-[9px] text-electric-cyan font-bold tracking-widest uppercase">ACTIVE AGENTS WORKFORCE:</span>
        </div>
        
        <div className="flex items-center gap-8 min-w-0 flex-1 pl-4">
          {agents.map((agent) => (
            <div key={agent.id} className="flex flex-col min-w-[200px] flex-1 max-w-[280px]">
              <div className="flex justify-between items-center mb-1">
                <span className="font-mono text-[9px] text-slate-white/60 truncate font-semibold">
                  {agent.name}
                </span>
                <span className={`font-mono text-[8px] tracking-widest ${
                  agent.status === 'alert' ? 'text-evidence-crimson' :
                  agent.status === 'analyzing' ? 'text-electric-cyan animate-pulse' :
                  agent.status === 'complete' ? 'text-cyber-emerald' :
                  agent.status === 'error' ? 'text-evidence-crimson' :
                  'text-slate-white/30'
                }`}>
                  {agent.status === 'idle' && state.isRunning ? '●' : agent.status.toUpperCase()}
                </span>
              </div>
              <div className="w-full bg-slate-white/5 h-1 rounded-full overflow-hidden mb-0.5">
                <div 
                  className={`h-full transition-all duration-700 ${
                    agent.status === 'alert' || agent.status === 'error' ? 'bg-evidence-crimson' :
                    agent.status === 'complete' ? 'bg-cyber-emerald' :
                    agent.status === 'idle' ? 'bg-slate-white/10' :
                    'bg-electric-cyan'
                  }`}
                  style={{
                    width: `${agent.status === 'idle' ? 0 : agent.progress}%`,
                  }}
                />
              </div>
              <span className="font-mono text-[8px] text-slate-white/30 truncate block">
                {agent.currentTask}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* 3. Three-column Operations layout */}
      <div className="flex-1 flex flex-col lg:flex-row min-h-0 relative">
        
        {/* PANEL A: LEFT COLUMN - Evidence / Timeline Feed */}
        <div className="w-full lg:w-[320px] xl:w-[360px] shrink-0 border-r border-slate-white/10 flex flex-col bg-obsidian/45 min-h-0">
          
          {/* Header & Search */}
          <div className="p-4 border-b border-slate-white/5 shrink-0">
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-[10px] text-slate-white/40 tracking-widest uppercase">
                {state.isRunning ? '[ LIVE EVIDENCE FEED ]' : '[ EVIDENCE FEED ]'}
              </span>
              <span className="font-mono text-[9px] text-slate-white/20">{filteredFeed.length} vectors</span>
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-white/30" />
              <input 
                type="text" 
                placeholder="Search events, agents..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="w-full bg-obsidian border border-slate-white/10 rounded-xs py-2 pl-9 pr-4 font-mono text-[11px] text-slate-white placeholder-slate-white/20 focus:outline-none focus:border-electric-cyan/40 transition-colors"
              />
            </div>
          </div>

          {/* Evidence Queue list scroll */}
          <div className="flex-1 overflow-y-auto no-scrollbar p-3 space-y-2">
            {/* Loading shimmer when running but no events yet */}
            {state.isRunning && filteredFeed.length === 0 && (
              <>
                {[1, 2, 3].map(i => (
                  <div key={i} className="p-4 border border-slate-white/5 rounded-xs bg-slate-white/[0.01] animate-pulse">
                    <div className="h-2 bg-slate-white/10 rounded mb-2 w-3/4" />
                    <div className="h-2 bg-slate-white/5 rounded w-1/2" />
                  </div>
                ))}
              </>
            )}
            
            {filteredFeed.map((item) => {
              const isActive = item.id === selectedFeedId;
              return (
                <button
                  key={item.id}
                  onClick={() => setSelectedFeedId(item.id)}
                  className={`w-full text-left p-4 border rounded-xs transition-all duration-300 block relative overflow-hidden cursor-pointer ${
                    isActive 
                      ? 'border-electric-cyan bg-electric-cyan/[0.03] shadow-[0_0_15px_rgba(56,189,248,0.02)]' 
                      : 'border-slate-white/5 bg-slate-white/[0.01] hover:border-slate-white/15'
                  }`}
                >
                  {/* Semantic top status bar */}
                  <div 
                    className="absolute top-0 left-0 right-0 h-[2px]" 
                    style={{
                      backgroundColor: 
                        item.status === 'threat' ? '#EF4444' : 
                        item.status === 'suspicious' ? '#F59E0B' : 
                        item.status === 'verified' ? '#22C55E' : '#38BDF8'
                    }}
                  />

                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-[9px] text-slate-white/30 font-semibold">{item.source}</span>
                    <span className={`font-mono text-[8px] font-bold tracking-widest uppercase ${
                      item.status === 'threat' ? 'text-evidence-crimson' : 
                      item.status === 'suspicious' ? 'text-amber-warning' : 
                      item.status === 'verified' ? 'text-cyber-emerald' : 'text-slate-white/40'
                    }`}>
                      {item.status}
                    </span>
                  </div>

                  <h4 className="font-display font-medium text-xs tracking-wider text-slate-white uppercase mb-1 truncate">
                    {item.title}
                  </h4>

                  <div className="flex justify-between items-center pt-2 border-t border-slate-white/5 text-[9px] font-mono text-slate-white/30">
                    <span>{item.timestamp}</span>
                    <ChevronRight className={`w-3.5 h-3.5 transition-transform ${isActive ? "text-electric-cyan translate-x-0.5" : "text-slate-white/20"}`} />
                  </div>
                </button>
              );
            })}

            {/* Verdict summary card */}
            {verdict && (
              <div className={`p-4 border rounded-xs mt-2 ${
                verdict.verdict === 'FRAUD_LIKELY' ? 'border-evidence-crimson/30 bg-evidence-crimson/5' :
                verdict.verdict === 'REVIEW' ? 'border-amber-500/30 bg-amber-500/5' :
                verdict.verdict === 'CLEAR' ? 'border-cyber-emerald/30 bg-cyber-emerald/5' :
                'border-electric-cyan/20 bg-electric-cyan/5'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  {verdict.verdict === 'FRAUD_LIKELY' ? <ShieldAlert className="w-4 h-4 text-evidence-crimson" /> :
                   verdict.verdict === 'CLEAR' ? <ShieldCheck className="w-4 h-4 text-cyber-emerald" /> :
                   <HelpCircle className="w-4 h-4 text-electric-cyan" />}
                  <span className="font-mono text-[10px] font-bold tracking-widest" style={{ color: verdictColor }}>
                    {verdict.verdict}
                  </span>
                </div>
                <div className="w-full bg-slate-white/5 h-1.5 rounded-full overflow-hidden mb-2">
                  <div
                    className="h-full rounded-full transition-all duration-1000"
                    style={{ width: `${riskPct}%`, backgroundColor: verdictColor }}
                  />
                </div>
                <span className="font-mono text-[8px] text-slate-white/40">
                  RISK: {riskPct}% · {verdict.contradictions.length} CONTRADICTION(S)
                </span>
              </div>
            )}

            {/* Expected loss card */}
            {expectedLoss && (
              <div className="p-3 border border-amber-500/20 bg-amber-500/5 rounded-xs">
                <div className="flex items-center gap-2 mb-1">
                  <TrendingUp className="w-3.5 h-3.5 text-amber-400" />
                  <span className="font-mono text-[9px] text-amber-400 uppercase tracking-wider font-bold">
                    EXPECTED LOSS [{expectedLoss.triagePriority}]
                  </span>
                </div>
                <span className="font-mono text-xs font-bold text-slate-white">
                  ${expectedLoss.expectedLoss.toLocaleString()}
                </span>
                <span className="font-mono text-[8px] text-slate-white/40 block mt-0.5">
                  ${expectedLoss.amountAtRisk.toLocaleString()} × {(expectedLoss.riskProbability * 100) | 0}%
                </span>
              </div>
            )}

            {/* Rule card with promote button */}
            {synthesizedRule && (
              <div className="p-3 border border-electric-cyan/20 bg-electric-cyan/5 rounded-xs">
                <div className="flex items-center gap-2 mb-1">
                  <Zap className="w-3.5 h-3.5 text-electric-cyan" />
                  <span className="font-mono text-[9px] text-electric-cyan uppercase tracking-wider font-bold">
                    RULE SYNTHESIZED [{synthesizedRule.status.toUpperCase()}]
                  </span>
                </div>
                <p className="font-mono text-[9px] text-slate-white/60 mb-2 leading-relaxed">
                  {synthesizedRule.description.slice(0, 80)}
                </p>
                {synthesizedRule.status === 'shadow' && (
                  <button
                    onClick={handlePromoteRule}
                    disabled={promotingRule}
                    className="w-full py-1.5 bg-electric-cyan text-obsidian font-mono text-[9px] font-bold uppercase tracking-widest rounded-xs hover:bg-electric-cyan/80 transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {promotingRule ? 'PROMOTING…' : '→ PROMOTE TO ENFORCED'}
                  </button>
                )}
                {synthesizedRule.status === 'enforced' && (
                  <div className="flex items-center gap-1 text-cyber-emerald">
                    <CheckCircle className="w-3 h-3" />
                    <span className="font-mono text-[8px] uppercase tracking-wider">ENFORCED — ACTIVE</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* PANEL B: MIDDLE COLUMN - Active Case Forensics */}
        <div className="flex-1 flex flex-col min-h-0 bg-obsidian border-r border-slate-white/10">
          
          {/* Active Case Header */}
          <div className="p-6 border-b border-slate-white/10 shrink-0">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[11px] font-bold text-electric-cyan bg-electric-cyan/5 border border-electric-cyan/15 rounded-xs px-2 py-0.5">
                  {state.shortId ? `#${state.shortId}` : '#—'}
                </span>
                <span className="font-mono text-[10px] text-slate-white/30">FORENSIC RECORD SUMMARY</span>
              </div>
              <div className="flex items-center gap-3">
                {/* Audit view toggle */}
                <button
                  onClick={() => { setAuditToggle(v => !v); if (!auditIntact) handleVerifyAudit(); }}
                  className="flex items-center gap-1.5 bg-obsidian border border-slate-white/10 px-2.5 py-1 rounded-xs hover:border-electric-cyan/30 transition-colors cursor-pointer"
                >
                  {auditToggle ? <EyeOff className="w-3 h-3 text-electric-cyan" /> : <Eye className="w-3 h-3 text-slate-white/40" />}
                  <span className="font-mono text-[8px] text-slate-white/40 uppercase tracking-wider">
                    AUDIT VIEW
                  </span>
                </button>
                {/* Verdict status indicator */}
                <div className="flex items-center gap-1.5 bg-obsidian border border-slate-white/5 px-2.5 py-1 rounded-xs">
                  <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: verdictColor }} />
                  <span className="font-mono text-[9px] font-bold text-slate-white/60 tracking-wider uppercase">
                    {verdictLabel}
                  </span>
                </div>
              </div>
            </div>

            {/* Case title — from selected feed item or verdict */}
            <h3 className="font-display font-bold text-lg md:text-xl tracking-widest text-slate-white uppercase mb-2">
              {selectedFeedItem?.title || (state.isRunning ? 'INVESTIGATION IN PROGRESS…' : 'SENTINEL FORENSIC CONSOLE')}
            </h3>
            <p className="font-sans text-xs text-slate-white/50 tracking-wider leading-relaxed">
              {selectedFeedItem?.description || (
                state.isRunning
                  ? 'Specialist agents are cross-examining evidence in parallel. Results stream in real-time.'
                  : 'Click "Deploy Investigator" to begin a multi-agent cross-examination.'
              )}
            </p>
          </div>

          {/* Details Container */}
          <div className="flex-1 overflow-y-auto no-scrollbar p-6 space-y-6">
            
            {/* Audit view mode */}
            <AnimatePresence>
              {auditToggle && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="glass-panel p-4 rounded-xs border border-electric-cyan/20"
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-[9px] text-electric-cyan uppercase tracking-widest">[ HASH-CHAINED AUDIT LOG ]</span>
                    {auditIntact !== null && (
                      <div className={`flex items-center gap-1 ${auditIntact ? 'text-cyber-emerald' : 'text-evidence-crimson'}`}>
                        {auditIntact ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        <span className="font-mono text-[8px] uppercase">{auditIntact ? 'INTACT' : 'TAMPERED'}</span>
                      </div>
                    )}
                  </div>
                  <p className="font-mono text-[9px] text-slate-white/40 leading-relaxed">
                    Every verdict, override, rule-promotion and quarantine action is written to the hash-chained
                    audit log (Merkle-style). Each entry stores SHA-256(prev_hash + event_type + payload).
                    Tamper-evident — editing any past entry breaks all subsequent hashes.
                  </p>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Contradiction axes */}
            {verdict && verdict.contradictions.length > 0 && (
              <div className="glass-panel p-5 rounded-xs relative">
                <div className="absolute top-2 right-3 font-mono text-[8px] text-slate-white/20 uppercase tracking-widest">[ CROSS-EXAMINATION AXES ]</div>
                <h4 className="font-mono text-[10px] text-slate-white/40 uppercase tracking-wider mb-3">CONTRADICTION ENGINE FINDINGS:</h4>
                <div className="space-y-3">
                  {verdict.contradictions.map((c, idx) => (
                    <div key={idx} className="flex gap-3 p-3 bg-obsidian/40 border border-slate-white/5 rounded-xs">
                      <div className="w-1 rounded-full bg-evidence-crimson shrink-0" />
                      <div>
                        <span className="font-mono text-[9px] font-bold text-evidence-crimson uppercase tracking-wider block mb-1">
                          {c.axis.replace(/_/g, ' ')} — {Math.round(c.weight * 100)}% weight
                        </span>
                        <p className="font-mono text-[10px] text-slate-white/70 leading-relaxed">{c.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
                {verdict.counterfactual && (
                  <div className="mt-3 p-3 bg-electric-cyan/5 border border-electric-cyan/10 rounded-xs">
                    <span className="font-mono text-[8px] text-electric-cyan uppercase tracking-wider block mb-1">COUNTERFACTUAL:</span>
                    <p className="font-mono text-[9px] text-slate-white/60">{verdict.counterfactual}</p>
                  </div>
                )}
              </div>
            )}

            {/* Red Team defense */}
            {redTeam && (
              <div className="glass-panel p-4 rounded-xs border border-slate-white/5">
                <div className="flex items-center gap-2 mb-2">
                  <Scale className="w-3.5 h-3.5 text-electric-cyan" />
                  <span className="font-mono text-[9px] text-electric-cyan uppercase tracking-wider">RED TEAM DEFENSE</span>
                  <span className="font-mono text-[8px] text-slate-white/30">{redTeam.trackRecord}</span>
                </div>
                <p className="font-mono text-[10px] text-slate-white/60 leading-relaxed italic">
                  "{redTeam.defense}"
                </p>
              </div>
            )}

            {/* Compliance card */}
            {compliance && (
              <div className={`p-4 border rounded-xs ${compliance.shouldFileSar ? 'border-evidence-crimson/30 bg-evidence-crimson/5' : 'border-slate-white/10 bg-slate-white/[0.01]'}`}>
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className={`w-3.5 h-3.5 ${compliance.shouldFileSar ? 'text-evidence-crimson' : 'text-slate-white/40'}`} />
                  <span className="font-mono text-[9px] uppercase tracking-wider font-bold" style={{ color: compliance.shouldFileSar ? '#EF4444' : '#94A3B8' }}>
                    SAR {compliance.shouldFileSar ? 'REQUIRED' : 'NOT REQUIRED'} · COMPLIANCE ANALYSIS
                  </span>
                </div>
                <p className="font-mono text-[9px] text-slate-white/55 leading-relaxed mb-2">{compliance.answer.slice(0, 200)}</p>
                {compliance.citations.length > 0 && (
                  <div className="space-y-1">
                    {compliance.citations.slice(0, 2).map((c, i) => (
                      <span key={i} className="font-mono text-[8px] text-electric-cyan/70 block">↳ {c}</span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Federation result */}
            {federation && federation.matchesFound > 0 && (
              <div className="p-4 border border-amber-500/20 bg-amber-500/5 rounded-xs">
                <div className="flex items-center gap-2 mb-2">
                  <Network className="w-3.5 h-3.5 text-amber-400" />
                  <span className="font-mono text-[9px] text-amber-400 uppercase tracking-wider font-bold">
                    FEDERATED MATCH [{federation.matches[0]?.orgsFlagged} ORGS] [SIMULATED]
                  </span>
                </div>
                <p className="font-mono text-[9px] text-slate-white/60 leading-relaxed">{federation.summary}</p>
                <p className="font-mono text-[7px] text-slate-white/25 mt-1">{federation.disclaimer}</p>
              </div>
            )}

            {/* Honeypot */}
            {honeypot && (
              <div className="p-4 border border-slate-white/10 bg-slate-white/[0.01] rounded-xs">
                <div className="flex items-center gap-2 mb-3">
                  <Terminal className="w-3.5 h-3.5 text-electric-cyan" />
                  <span className="font-mono text-[9px] text-electric-cyan uppercase tracking-wider">SCRIPTED HONEYPOT [SIMULATED]</span>
                  <span className="font-mono text-[8px] text-slate-white/30">Token: {honeypot.trackingToken}</span>
                </div>
                <div className="space-y-2">
                  {honeypot.dialogue.slice(0, 2).map(turn => (
                    <div key={turn.turn} className="text-[8px] font-mono">
                      <span className="text-evidence-crimson/70 block">[ATTACKER T{turn.turn}]: {turn.attackerSimulation.slice(60, 120)}…</span>
                      <span className="text-cyber-emerald/70 block ml-4">[DECOY]: {turn.decoyResponse.slice(0, 80)}…</span>
                    </div>
                  ))}
                </div>
                <p className="font-mono text-[7px] text-slate-white/25 mt-2">{honeypot.disclaimer}</p>
              </div>
            )}

            {/* Fallback deep audit text block */}
            {selectedFeedItem && (
              <div className="glass-panel p-5 rounded-xs relative">
                <div className="absolute top-2 right-3 font-mono text-[8px] text-slate-white/20 uppercase tracking-widest">[ COGNITIVE DISCOVERIES ]</div>
                <h4 className="font-mono text-[10px] text-slate-white/40 uppercase tracking-wider mb-3">FACT FILE SPECIFICATIONS:</h4>
                <p className="font-mono text-[11px] text-slate-white/80 leading-relaxed tracking-wider bg-obsidian/40 border border-slate-white/5 rounded-xs p-4 whitespace-pre-wrap">
                  {selectedFeedItem.content}
                </p>
              </div>
            )}

            {/* Eval metrics (post-investigation) */}
            {renderMetricsCard()}

            {/* Chronological audit stream */}
            <div>
              <div className="flex items-center justify-between border-b border-slate-white/5 pb-2 mb-4">
                <span className="font-mono text-[10px] text-slate-white/40 tracking-widest uppercase">CHRONOLOGICAL AUDIT STREAM</span>
                <span className="font-mono text-[9px] text-slate-white/20">{localTimeline.length} entries</span>
              </div>

              {/* Loading shimmer */}
              {state.isRunning && localTimeline.length === 0 && (
                <div className="space-y-3">
                  {[1, 2].map(i => (
                    <div key={i} className="h-16 bg-slate-white/[0.02] border border-slate-white/5 rounded-xs animate-pulse" />
                  ))}
                </div>
              )}

              <div className="space-y-3">
                {localTimeline.slice(0, 15).map((evt) => (
                  <div 
                    key={evt.id} 
                    className="flex gap-4 p-4 border border-slate-white/5 bg-slate-white/[0.01] rounded-xs relative"
                  >
                    <div className="w-1 rounded-full shrink-0" style={{
                      backgroundColor: evt.type === 'threat' ? '#EF4444' : evt.type === 'warning' ? '#F59E0B' : evt.type === 'success' ? '#22C55E' : '#38BDF8'
                    }} />
                    <div className="flex-1">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-1.5">
                        <span className="font-display font-medium text-xs tracking-wider text-slate-white uppercase">
                          {evt.title}
                        </span>
                        <div className="flex items-center gap-2 font-mono text-[9px] text-slate-white/30">
                          <span className="bg-slate-white/5 px-1.5 py-0.5 rounded-xs">{evt.agentName}</span>
                          <span>{evt.timestamp}</span>
                        </div>
                      </div>
                      <p className="font-mono text-[10px] text-slate-white/55 leading-relaxed tracking-wide">
                        {evt.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Annotation Input Footer */}
          <div className="p-4 border-t border-slate-white/10 shrink-0 bg-obsidian/45">
            <form onSubmit={handleAddNote} className="flex gap-3">
              <input 
                type="text" 
                placeholder="Log manual investigator annotation..."
                value={newNote}
                onChange={e => setNewNote(e.target.value)}
                className="flex-1 bg-obsidian border border-slate-white/10 rounded-xs px-4 py-2.5 font-mono text-[11px] text-slate-white placeholder-slate-white/20 focus:outline-none focus:border-electric-cyan/40 transition-colors"
              />
              <button 
                type="submit"
                className="bg-slate-white text-obsidian px-4 py-2.5 rounded-xs font-mono text-xs font-bold uppercase flex items-center justify-center gap-1 hover:bg-electric-cyan hover:shadow-[0_0_15px_rgba(56,189,248,0.3)] transition-all cursor-pointer shrink-0"
              >
                <Send className="w-3.5 h-3.5" />
                ANNOTATE
              </button>
            </form>
          </div>
        </div>

        {/* PANEL C: RIGHT COLUMN - Blast Radius Graph */}
        <div className="w-full lg:w-[350px] xl:w-[400px] shrink-0 border-t lg:border-t-0 flex flex-col bg-obsidian/45 min-h-[300px] lg:min-h-0">
          
          <div className="p-4 border-b border-slate-white/5 shrink-0 flex justify-between items-center">
            <div>
              <span className="font-mono text-[10px] text-slate-white/40 tracking-widest uppercase block">[ BLAST RADIUS MAP ]</span>
              <span className="font-mono text-[9px] text-slate-white/20 block">
                {blastRadius ? blastRadius.summary.slice(0, 50) : 'Awaiting confirmed threat'}
              </span>
            </div>
            <Network className="w-4 h-4 text-slate-white/30" />
          </div>

          {/* Interactive Graph Render Area */}
          <div className="flex-1 relative flex items-center justify-center p-6 bg-obsidian/65">
            
            {/* Dynamic Grid Overlay inside map */}
            <div className="absolute inset-0 console-grid opacity-5 pointer-events-none" />
            
            {renderBlastRadiusGraph()}

            {/* Float helper status card */}
            {blastRadius && (
              <div className="absolute bottom-4 left-4 right-4 bg-obsidian border border-slate-white/5 rounded-xs p-3">
                <span className="font-mono text-[8px] text-slate-white/30 tracking-widest uppercase block mb-1">MAP FOCUS DIRECTORY</span>
                <p className="font-mono text-[9px] text-slate-white/60">
                  {blastRadius.summary.slice(0, 120)}
                </p>
                {blastRadius.superSpreader && (
                  <p className="font-mono text-[8px] text-evidence-crimson mt-1">
                    ▲ SUPER-SPREADER: {blastRadius.superSpreader}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
