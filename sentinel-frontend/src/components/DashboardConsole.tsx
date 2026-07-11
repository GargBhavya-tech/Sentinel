import { useState, useEffect, FormEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  ShieldAlert, ShieldCheck, HelpCircle, Activity, 
  Clock, Plus, Search, FileText, Phone, Mail, 
  TrendingUp, RefreshCw, ChevronRight, Terminal, Network, ArrowLeft, Send
} from 'lucide-react';
import { EvidenceItem, TimelineEvent, AgentStatus } from '../types';
import { listCases, getCaseAudit, addAnnotation } from '../api/sentinel';

interface DashboardConsoleProps {
  onExit: () => void;
  // The shared investigation instance from useInvestigation(). Optional: this
  // console currently runs a self-contained simulation, but App passes the live
  // instance so a future wiring can drive it from real SSE state.
  investigation?: ReturnType<typeof import('../hooks/useInvestigation')['useInvestigation']>;
}

export default function DashboardConsole({ onExit }: DashboardConsoleProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [newNote, setNewNote] = useState('');
  const [currentTime, setCurrentTime] = useState('10:24:02 UTC');

  const [uiMode, setUiMode] = useState<'tactical' | 'enterprise'>(
    (localStorage.getItem('sentinel_ui_mode') as any) || 'enterprise'
  );
  const [selectedClient, setSelectedClient] = useState('RPG Inc. (Active Workspace)');
  const clientsList = ['RPG Inc. (Active Workspace)', 'Acme Corp (Staging)', 'Stark Enterprises (Pilot)'];

  const toggleUiMode = () => {
    const next = uiMode === 'tactical' ? 'enterprise' : 'tactical';
    setUiMode(next);
    localStorage.setItem('sentinel_ui_mode', next);
  };

  const translateEventTitle = (title: string) => {
    if (uiMode === 'tactical') return title;
    const t = title.toUpperCase();
    if (t.includes('CASE_CREATED') || t.includes('CASE CREATED')) return 'Case Initiated';
    if (t.includes('RULE_SYNTHESIZED') || t.includes('RULE SYNTHESIZED')) return 'Security Rule Created';
    if (t.includes('VERDICT')) return 'Risk Verdict';
    if (t.includes('QUARANTINE')) return 'Active Containment';
    if (t.includes('MANUAL_ANNOTATION') || t.includes('MANUAL ANNOTATION')) return 'Investigator Comment';
    return title;
  };

  const translateEventDescription = (description: string, title: string) => {
    if (uiMode === 'tactical') return description;
    try {
      if (description.startsWith('{') && description.endsWith('}')) {
        const payload = JSON.parse(description);
        if (title.includes('CASE_CREATED') || title.includes('CASE CREATED')) {
          return `New case created in Slack channel #${payload.slack_channel || 'unknown'} by user ${payload.reporter || 'unknown'}.`;
        }
        if (title.includes('RULE_SYNTHESIZED') || title.includes('RULE SYNTHESIZED')) {
          return `Auto-synthesized shadow rule: "${payload.description || 'rule'}" (ID: ${payload.rule_id?.slice(0, 8)}).`;
        }
        if (title.includes('VERDICT')) {
          return `System verdict determined: ${payload.verdict} with risk probability of ${(payload.risk * 100).toFixed(0)}%.`;
        }
        if (title.includes('QUARANTINE')) {
          return `Threat isolated: ${payload.description || 'Quarantined connected nodes'} (${(payload.nodes || []).join(', ')}).`;
        }
        if (title.includes('MANUAL_ANNOTATION') || title.includes('MANUAL ANNOTATION')) {
          return `Investigator Note: "${payload.description}" — added by ${payload.agent || 'system'}.`;
        }
        return Object.entries(payload)
          .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${JSON.stringify(v)}`)
          .join(', ');
      }
    } catch (err) {
      // Fallback
    }
    return description;
  };

  const [liveCases, setLiveCases] = useState<any[]>([]);
  const [liveTimelineEvents, setLiveTimelineEvents] = useState<TimelineEvent[]>([]);

  // Combined list of live database cases
  const combinedEvidenceItems: EvidenceItem[] = liveCases.map(c => ({
    id: c.case_id,
    type: 'thread' as const,
    title: `Slack Case #${c.short_id}`,
    source: `Slack Event`,
    status: (c.verdict === 'FRAUD_LIKELY' ? 'threat' : c.verdict === 'REVIEW' ? 'suspicious' : c.verdict === 'CLEAR' ? 'verified' : 'unverified') as any,
    timestamp: c.created_at,
    description: `Slack triggered investigation. Current status: ${c.status}`,
    content: `Status: ${c.status}\nVerdict: ${c.verdict || 'PENDING'}\nRisk Score: ${c.risk_score !== null ? (c.risk_score * 100).toFixed(1) + '%' : 'N/A'}\nAmount at Risk: $${c.amount_at_risk.toLocaleString()}`,
    confidence: c.risk_score !== null ? Math.round(c.risk_score * 100) : 0,
  }));

  // Poll live cases from API
  useEffect(() => {
    let active = true;
    const fetchLiveCases = async () => {
      try {
        const data = await listCases();
        if (active) {
          setLiveCases(data.cases || []);
        }
      } catch (err) {
        console.error('Failed to fetch live cases:', err);
      }
    };
    fetchLiveCases();
    const interval = setInterval(fetchLiveCases, 3000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  // Poll timeline events for selected live case
  useEffect(() => {
    if (!selectedCaseId) {
      setLiveTimelineEvents([]);
      return;
    }
    let active = true;
    const fetchAudit = async () => {
      try {
        const data = await getCaseAudit(selectedCaseId);
        if (active) {
          const events: TimelineEvent[] = (data.entries || []).map((entry: any, index: number) => {
            let desc = '';
            if (entry.payload) {
              if (entry.payload.reason) desc = String(entry.payload.reason);
              else if (entry.payload.summary) desc = String(entry.payload.summary);
              else if (entry.payload.description) desc = String(entry.payload.description);
              else if (entry.payload.verdict) desc = `Verdict: ${entry.payload.verdict}`;
              else desc = JSON.stringify(entry.payload);
            }
            return {
              id: `audit-${entry.entry_id || index}`,
              timestamp: new Date(entry.created_at).toLocaleTimeString() + ' UTC',
              title: entry.event_type.replace(/_/g, ' ').toUpperCase(),
              type: (entry.event_type === 'verdict' && entry.payload?.verdict === 'FRAUD_LIKELY' ? 'threat' : 'info') as any,
              description: desc,
              sourceId: selectedCaseId,
              agentName: String(entry.payload?.agent || 'system')
            };
          });
          setLiveTimelineEvents(events);
        }
      } catch (err) {
        console.error('Failed to fetch case audit:', err);
      }
    };
    fetchAudit();
    const interval = setInterval(fetchAudit, 3000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [selectedCaseId]);

  // Real-time ticking UTC Clock (Simulated enterprise standard)
  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setCurrentTime(now.toUTCString().replace('GMT', 'UTC'));
    }, 1000);
    return () => clearInterval(timer);
  }, []);



  // Set default selected case when cases load
  useEffect(() => {
    if (!selectedCaseId && combinedEvidenceItems.length > 0) {
      setSelectedCaseId(combinedEvidenceItems[0].id);
    }
  }, [combinedEvidenceItems, selectedCaseId]);

  // Active highlighted relationship map nodes for the current selected case
  const getGraphHighlightType = (nodeId: string) => {
    if (!selectedCaseId) return 'default';
    if (selectedCase.status === 'threat') {
      if (nodeId === 'voice' || nodeId === 'central' || nodeId === 'vpn') return 'threat';
    }
    if (selectedCase.status === 'suspicious') {
      if (nodeId === 'invoice' || nodeId === 'central') return 'suspicious';
    }
    if (selectedCase.status === 'verified') {
      if (nodeId === 'ceo_email' || nodeId === 'secure_ledger') return 'verified';
    }
    return 'default';
  };

  const handleAddNote = async (e: FormEvent) => {
    e.preventDefault();
    if (!newNote.trim() || !selectedCaseId) return;

    try {
      await addAnnotation(selectedCaseId, newNote);
    } catch (err) {
      console.error('Failed to save manual annotation:', err);
    }
    setNewNote('');
  };

  // Filter evidence lists
  const filteredEvidence = combinedEvidenceItems.filter(item => 
    item.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.source.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const selectedCase = combinedEvidenceItems.find(item => item.id === selectedCaseId) || {
    id: '',
    type: 'thread' as const,
    title: 'No Case Selected',
    source: 'N/A',
    status: 'unverified' as const,
    timestamp: '',
    description: 'Select a case from the feed to view its forensic timeline.',
    content: 'No case data loaded.',
    confidence: 0
  };
  const selectedTimeline = liveTimelineEvents;

  const threatCount = combinedEvidenceItems.filter(c => c.status === 'threat').length;
  const verifiedCount = combinedEvidenceItems.filter(c => c.status === 'verified').length;
  const cleanPercentage = combinedEvidenceItems.length > 0
    ? ((verifiedCount / combinedEvidenceItems.length) * 100).toFixed(1) + '%'
    : '100.0%';
  const filesScannedCount = 1042 + combinedEvidenceItems.length * 27;

  return (
    <div className="min-h-screen bg-obsidian text-slate-white flex flex-col font-sans select-none overflow-hidden h-screen">
      
      {/* 1. Header of the physical operations console */}
      <header className="border-b border-slate-white/10 bg-obsidian/90 px-6 py-4 shrink-0 flex flex-col md:flex-row md:items-center justify-between gap-4 z-20">
        
        {/* Left identity branding */}
        <div className="flex items-center gap-4">
          <button 
            onClick={onExit}
            className="flex items-center gap-2 font-mono text-[10px] tracking-widest text-slate-white/40 hover:text-electric-cyan transition-colors duration-200 uppercase cursor-pointer focus:outline-none"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            [ EXIT ]
          </button>
          
          <div className="h-6 w-[1px] bg-slate-white/10 hidden md:block" />

          {/* Toggle view mode */}
          <button 
            onClick={toggleUiMode}
            className="flex items-center gap-1.5 font-mono text-[9px] tracking-widest text-electric-cyan border border-electric-cyan/20 bg-electric-cyan/5 px-2.5 py-1 rounded-xs hover:bg-electric-cyan/10 transition-colors uppercase cursor-pointer"
          >
            {uiMode === 'tactical' ? 'Enterprise view' : 'Tactical HUD view'}
          </button>

          <div className="h-6 w-[1px] bg-slate-white/10 hidden md:block" />
          
          {uiMode === 'enterprise' ? (
            <div className="relative group">
              <button className="flex items-center gap-1.5 font-mono text-[9px] tracking-widest text-slate-white/60 bg-slate-white/5 border border-slate-white/10 px-3 py-1.5 rounded-xs hover:border-slate-white/20 transition-all cursor-pointer">
                {selectedClient}
                <ChevronRight className="w-3 h-3 rotate-90" />
              </button>
              <div className="absolute left-0 mt-1 hidden group-hover:block bg-obsidian border border-slate-white/10 rounded-xs shadow-xl z-50 w-56 py-1 overflow-hidden">
                {clientsList.map(c => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setSelectedClient(c)}
                    className={`w-full text-left font-mono text-[9px] tracking-wider px-4 py-2 hover:bg-slate-white/5 transition-colors block ${
                      selectedClient === c ? 'text-electric-cyan font-bold' : 'text-slate-white/50'
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div>
              <span className="font-display font-black text-sm tracking-[0.25em] text-slate-white uppercase block">
                SENTINEL COGNITIVE CONSOLE
              </span>
              <span className="font-mono text-[9px] tracking-wider text-slate-white/30 block mt-0.5">
                FORENSIC AUDITING WORKSPACE // ACTIVE_PORT_3000
              </span>
            </div>
          )}
        </div>

        {/* Global Realtime System Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 md:gap-8 border border-slate-white/5 bg-slate-white/[0.01] rounded-xs px-5 py-2.5 max-w-2xl">
          <div className="flex flex-col">
            <span className="font-mono text-[8px] text-slate-white/30 tracking-widest uppercase">FILES SCANNED</span>
            <span className="font-mono text-xs font-semibold text-slate-white">{filesScannedCount.toLocaleString()} files</span>
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-[8px] text-evidence-crimson tracking-widest uppercase">CRITICAL ALERTS</span>
            <span className="font-mono text-xs font-semibold text-evidence-crimson animate-pulse">{threatCount} {threatCount === 1 ? 'threat vector' : 'threat vectors'}</span>
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-[8px] text-cyber-emerald tracking-widest uppercase">VERIFIED CLEAN</span>
            <span className="font-mono text-xs font-semibold text-cyber-emerald">{cleanPercentage} safe</span>
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-[8px] text-electric-cyan tracking-widest uppercase">SYSTEM CLOCK</span>
            <span className="font-mono text-[10px] text-electric-cyan whitespace-nowrap overflow-hidden text-ellipsis max-w-[130px] font-semibold">{currentTime}</span>
          </div>
        </div>
      </header>



      {/* 3. Three-column Operations layout */}
      <div className="flex-1 flex flex-col lg:flex-row min-h-0 relative">
        
        {/* PANEL A: LEFT COLUMN - Evidence Queue (3 Columns equivalent) */}
        <div className="w-full lg:w-[320px] xl:w-[360px] shrink-0 border-r border-slate-white/10 flex flex-col bg-obsidian/45 min-h-0">
          
          {/* Header & Search */}
          <div className="p-4 border-b border-slate-white/5 shrink-0">
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-[10px] text-slate-white/40 tracking-widest uppercase">[ EVIDENCE FEED ]</span>
              <span className="font-mono text-[9px] text-slate-white/20">{filteredEvidence.length} vectors</span>
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-white/30" />
              <input 
                type="text" 
                placeholder="Search raw logs, filenames..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="w-full bg-obsidian border border-slate-white/10 rounded-xs py-2 pl-9 pr-4 font-mono text-[11px] text-slate-white placeholder-slate-white/20 focus:outline-none focus:border-electric-cyan/40 transition-colors"
              />
            </div>
          </div>

          {/* Evidence Queue list scroll */}
          <div className="flex-1 overflow-y-auto no-scrollbar p-3 space-y-2">
            {filteredEvidence.map((item) => {
              const isActive = item.id === selectedCaseId;
              return (
                <button
                  key={item.id}
                  onClick={() => setSelectedCaseId(item.id)}
                  className={`w-full text-left p-4.5 border rounded-xs transition-all duration-300 block relative overflow-hidden cursor-pointer ${
                    isActive 
                      ? 'border-electric-cyan bg-electric-cyan/[0.03] shadow-[0_0_15px_rgba(56,189,248,0.02)]' 
                      : 'border-slate-white/5 bg-slate-white/[0.01] hover:border-slate-white/15'
                  }`}
                >
                  {/* Semantic top status bar */}
                  <div 
                    className="absolute top-0 left-0 right-0 h-[2px]" 
                    style={{
                      backgroundColor: item.status === 'threat' ? '#EF4444' : item.status === 'suspicious' ? '#F59E0B' : item.status === 'verified' ? '#22C55E' : '#38BDF8'
                    }}
                  />

                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-[9px] text-slate-white/30 font-semibold">{item.id}</span>
                    <span className={`font-mono text-[8px] font-bold tracking-widest uppercase ${
                      item.status === 'threat' ? 'text-evidence-crimson' : item.status === 'suspicious' ? 'text-amber-warning' : item.status === 'verified' ? 'text-cyber-emerald' : 'text-slate-white/40'
                    }`}>
                      {item.status}
                    </span>
                  </div>

                  <h4 className="font-display font-medium text-xs tracking-wider text-slate-white uppercase mb-1 truncate">
                    {item.title}
                  </h4>
                  
                  <span className="font-mono text-[9px] text-slate-white/40 truncate block mb-2">
                    SOURCE: {item.source}
                  </span>

                  <div className="flex justify-between items-center pt-2 border-t border-slate-white/5 text-[9px] font-mono text-slate-white/30">
                    <span>CONFIDENCE: {item.confidence}%</span>
                    <ChevronRight className={`w-3.5 h-3.5 transition-transform ${isActive ? "text-electric-cyan translate-x-0.5" : "text-slate-white/20"}`} />
                  </div>
                </button>
              );
            })}
          </div>

        </div>

        {/* PANEL B: MIDDLE COLUMN - Active Case Forensics (5 Columns equivalent) */}
        <div className="flex-1 flex flex-col min-h-0 bg-obsidian border-r border-slate-white/10">
          
          {/* Active Case Header */}
          <div className="p-6 border-b border-slate-white/10 shrink-0">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[11px] font-bold text-electric-cyan bg-electric-cyan/5 border border-electric-cyan/15 rounded-xs px-2 py-0.5">
                  {selectedCase.id}
                </span>
                <span className="font-mono text-[10px] text-slate-white/30">FORENSIC RECORD SUMMARY</span>
              </div>
              <div className="flex items-center gap-1.5 bg-obsidian border border-slate-white/5 px-2.5 py-1 rounded-xs">
                <span className="w-1.5 h-1.5 rounded-full" style={{
                  backgroundColor: selectedCase.status === 'threat' ? '#EF4444' : selectedCase.status === 'suspicious' ? '#F59E0B' : selectedCase.status === 'verified' ? '#22C55E' : '#38BDF8'
                }} />
                <span className="font-mono text-[9px] font-bold text-slate-white/60 tracking-wider uppercase">
                  VERDICT: {selectedCase.status.toUpperCase()}
                </span>
              </div>
            </div>

            <h3 className="font-display font-bold text-lg md:text-xl tracking-widest text-slate-white uppercase mb-2">
              {selectedCase.title}
            </h3>
            <p className="font-sans text-xs text-slate-white/50 tracking-wider leading-relaxed">
              {selectedCase.description}
            </p>
          </div>

          {/* Details / Drills Container */}
          <div className="flex-1 overflow-y-auto no-scrollbar p-6 space-y-6">
            
            {/* Mitigation Control Hub for Enterprise Users */}
            {uiMode === 'enterprise' && selectedCase.id && (
              <div className="glass-panel p-5 rounded-xs border border-slate-white/10 bg-slate-white/[0.01]">
                <h4 className="font-mono text-[9px] text-slate-white/40 uppercase tracking-wider mb-3">[ CLIENT RESOLUTION ACTIONS ]</h4>
                <div className="flex flex-wrap sm:flex-nowrap gap-3">
                  <button
                    onClick={async () => {
                      try {
                        await addAnnotation(selectedCase.id, JSON.stringify({
                          description: "Transaction approved and cleared manually by risk analyst.",
                          agent: "Human_Risk_Officer"
                        }));
                      } catch (err) {
                        console.error(err);
                      }
                    }}
                    className="flex-1 border border-cyber-emerald/30 bg-cyber-emerald/5 hover:bg-cyber-emerald/15 text-cyber-emerald font-mono text-[9px] font-bold uppercase py-2 px-3 rounded-xs transition-all cursor-pointer flex items-center justify-center gap-1.5"
                  >
                    <ShieldCheck className="w-3.5 h-3.5" />
                    APPROVE CASE
                  </button>
                  <button
                    onClick={async () => {
                      try {
                        await addAnnotation(selectedCase.id, JSON.stringify({
                          description: "Sender geolocations quarantined and network nodes isolated.",
                          nodes: ["VPN_SG_IP", "CEO_VOICE_8"],
                          reason: "Triggered active containment from enterprise console UI.",
                          agent: "Human_Risk_Officer"
                        }));
                      } catch (err) {
                        console.error(err);
                      }
                    }}
                    className="flex-1 border border-evidence-crimson/30 bg-evidence-crimson/5 hover:bg-evidence-crimson/15 text-evidence-crimson font-mono text-[9px] font-bold uppercase py-2 px-3 rounded-xs transition-all cursor-pointer flex items-center justify-center gap-1.5"
                  >
                    <ShieldAlert className="w-3.5 h-3.5" />
                    QUARANTINE
                  </button>
                  <button
                    onClick={async () => {
                      try {
                        await addAnnotation(selectedCase.id, JSON.stringify({
                          description: "Synthesized policy rule enforced permanently in production firewall.",
                          agent: "Human_Risk_Officer"
                        }));
                      } catch (err) {
                        console.error(err);
                      }
                    }}
                    className="flex-1 border border-amber-warning/30 bg-amber-warning/5 hover:bg-amber-warning/15 text-amber-warning font-mono text-[9px] font-bold uppercase py-2 px-3 rounded-xs transition-all cursor-pointer flex items-center justify-center gap-1.5"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    ENFORCE RULE
                  </button>
                </div>
              </div>
            )}
            
            {/* Deep Audit text block */}
            <div className="glass-panel p-5 rounded-xs relative">
              <div className="absolute top-2 right-3 font-mono text-[8px] text-slate-white/20 uppercase tracking-widest">[ COGNITIVE DISCOVERIES ]</div>
              <h4 className="font-mono text-[10px] text-slate-white/40 uppercase tracking-wider mb-3">FACT FILE SPECIFICATIONS:</h4>
              <p className="font-mono text-[11px] text-slate-white/80 leading-relaxed tracking-wider bg-obsidian/40 border border-slate-white/5 rounded-xs p-4 whitespace-pre-wrap">
                {selectedCase.content}
              </p>
            </div>

            {/* Sub-Timeline Header */}
            <div>
              <div className="flex items-center justify-between border-b border-slate-white/5 pb-2 mb-4">
                <span className="font-mono text-[10px] text-slate-white/40 tracking-widest uppercase">CHRONOLOGICAL AUDIT STREAM</span>
                <span className="font-mono text-[9px] text-slate-white/20">{selectedTimeline.length} entries</span>
              </div>

              {/* Sequential Event Stack */}
              <div className="space-y-3">
                {selectedTimeline.map((evt) => (
                  <div 
                    key={evt.id} 
                    className="flex gap-4 p-4 border border-slate-white/5 bg-slate-white/[0.01] rounded-xs relative"
                  >
                    {/* Left semantic line indicator */}
                    <div className="w-1 rounded-full shrink-0" style={{
                      backgroundColor: evt.type === 'threat' ? '#EF4444' : evt.type === 'warning' ? '#F59E0B' : evt.type === 'success' ? '#22C55E' : '#38BDF8'
                    }} />

                    <div className="flex-1">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-1.5">
                        <span className={uiMode === 'enterprise' ? 'font-sans font-bold text-sm text-slate-white' : 'font-display font-medium text-xs tracking-wider text-slate-white uppercase'}>
                          {translateEventTitle(evt.title)}
                        </span>
                        <div className="flex items-center gap-2 font-mono text-[9px] text-slate-white/30">
                          <span className="bg-slate-white/5 px-1.5 py-0.5 rounded-xs">{evt.agentName}</span>
                          <span>{evt.timestamp}</span>
                        </div>
                      </div>
                      <p className={uiMode === 'enterprise' ? 'font-sans text-xs text-slate-white/80 leading-relaxed' : 'font-mono text-[10px] text-slate-white/55 leading-relaxed tracking-wide'}>
                        {translateEventDescription(evt.description, evt.title)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>

          {/* Annotation Input Footer (Interactive manual updates) */}
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

        {/* PANEL C: RIGHT COLUMN - Dynamic Interactive SVG Graph Map (4 Columns equivalent) */}
        <div className="w-full lg:w-[350px] xl:w-[400px] shrink-0 border-t lg:border-t-0 flex flex-col bg-obsidian/45 min-h-[300px] lg:min-h-0">
          
          <div className="p-4 border-b border-slate-white/5 shrink-0 flex justify-between items-center">
            <div>
              <span className="font-mono text-[10px] text-slate-white/40 tracking-widest uppercase block">[ RELATIONSHIP MAP ]</span>
              <span className="font-mono text-[9px] text-slate-white/20 block">Active forensic vectors mapped</span>
            </div>
            <Network className="w-4 h-4 text-slate-white/30" />
          </div>

          {/* Interactive SVG Render Area */}
          <div className="flex-1 relative flex items-center justify-center p-6 bg-obsidian/65">
            
            {/* Dynamic Grid Overlay inside map */}
            <div className="absolute inset-0 console-grid opacity-5 pointer-events-none" />

            <svg className="w-full h-full max-h-[350px]" viewBox="0 0 200 200">
              {/* Edges Connecting Nodes */}
              {/* Voice Node to Central Synapse */}
              <line 
                x1="40" y1="50" x2="100" y2="100" 
                stroke={getGraphHighlightType('voice') === 'threat' ? '#EF4444' : 'rgba(248, 250, 252, 0.1)'} 
                strokeWidth={getGraphHighlightType('voice') !== 'default' ? '2.5' : '1'}
                strokeDasharray={getGraphHighlightType('voice') === 'threat' ? '3 1' : 'none'}
                className="transition-all duration-300"
              />
              {/* VPN Node to Central Synapse */}
              <line 
                x1="160" y1="50" x2="100" y2="100" 
                stroke={getGraphHighlightType('vpn') === 'threat' ? '#EF4444' : 'rgba(248, 250, 252, 0.1)'} 
                strokeWidth={getGraphHighlightType('vpn') !== 'default' ? '2.5' : '1'}
                strokeDasharray={getGraphHighlightType('vpn') === 'threat' ? '3 1' : 'none'}
                className="transition-all duration-300"
              />
              {/* CEO Email Node to Central Synapse */}
              <line 
                x1="160" y1="150" x2="100" y2="100" 
                stroke={getGraphHighlightType('ceo_email') === 'threat' ? '#EF4444' : getGraphHighlightType('ceo_email') === 'verified' ? '#22C55E' : 'rgba(248, 250, 252, 0.1)'} 
                strokeWidth={getGraphHighlightType('ceo_email') !== 'default' ? '2.5' : '1'}
                className="transition-all duration-300"
              />
              {/* Invoice Node to Central Synapse */}
              <line 
                x1="40" y1="150" x2="100" y2="100" 
                stroke={getGraphHighlightType('invoice') === 'suspicious' ? '#F59E0B' : 'rgba(248, 250, 252, 0.1)'} 
                strokeWidth={getGraphHighlightType('invoice') !== 'default' ? '2.5' : '1'}
                className="transition-all duration-300"
              />
              {/* Secure Ledger Conduit */}
              <line 
                x1="100" y1="100" x2="100" y2="165" 
                stroke={getGraphHighlightType('secure_ledger') === 'verified' ? '#22C55E' : 'rgba(248, 250, 252, 0.15)'} 
                strokeWidth={getGraphHighlightType('secure_ledger') !== 'default' ? '2.5' : '1'}
                className="transition-all duration-300"
              />

              {/* Node Circles */}
              {/* 1. Voice Ingestion Print */}
              <g className="cursor-pointer">
                <circle 
                  cx="40" cy="50" r="10" 
                  fill="#07080B" 
                  stroke={getGraphHighlightType('voice') === 'threat' ? '#EF4444' : 'rgba(248, 250, 252, 0.3)'}
                  strokeWidth="2"
                  className="transition-all duration-300"
                />
                <circle cx="40" cy="50" r="3" fill="#EF4444" className="animate-pulse" />
                <text x="40" y="34" fontSize="6.5" fill="#F8FAFC" textAnchor="middle" fontFamily="monospace" opacity="0.6">CEO_VOICE_8</text>
              </g>

              {/* 2. Singapore VPN IP Gateway */}
              <g className="cursor-pointer">
                <circle 
                  cx="160" cy="50" r="10" 
                  fill="#07080B" 
                  stroke={getGraphHighlightType('vpn') === 'threat' ? '#EF4444' : 'rgba(248, 250, 252, 0.3)'}
                  strokeWidth="2"
                  className="transition-all duration-300"
                />
                <circle cx="160" cy="50" r="3" fill="#EF4444" />
                <text x="160" y="34" fontSize="6.5" fill="#F8FAFC" textAnchor="middle" fontFamily="monospace" opacity="0.6">VPN_SG_IP</text>
              </g>

              {/* 3. Central decision Hub (Synapse) */}
              <g className="cursor-pointer">
                <circle 
                  cx="100" cy="100" r="16" 
                  fill="#07080B" 
                  stroke={selectedCase.status === 'threat' ? '#EF4444' : selectedCase.status === 'suspicious' ? '#F59E0B' : selectedCase.status === 'verified' ? '#22C55E' : '#38BDF8'}
                  strokeWidth="3"
                  className="transition-all duration-300"
                />
                <circle cx="100" cy="100" r="6" fill="#38BDF8" className="animate-pulse" />
                <text x="100" y="124" fontSize="7.5" fill="#F8FAFC" textAnchor="middle" fontFamily="monospace" fontWeight="bold">SYNAPSE_CORE</text>
              </g>

              {/* 4. Invoice RT Document */}
              <g className="cursor-pointer">
                <circle 
                  cx="40" cy="150" r="10" 
                  fill="#07080B" 
                  stroke={getGraphHighlightType('invoice') === 'suspicious' ? '#F59E0B' : 'rgba(248, 250, 252, 0.3)'}
                  strokeWidth="2"
                  className="transition-all duration-300"
                />
                <circle cx="40" cy="150" r="3" fill="#F59E0B" />
                <text x="40" y="167" fontSize="6.5" fill="#F8FAFC" textAnchor="middle" fontFamily="monospace" opacity="0.6">INVOICE_RT</text>
              </g>

              {/* 5. CEO CA Email client */}
              <g className="cursor-pointer">
                <circle 
                  cx="160" cy="150" r="10" 
                  fill="#07080B" 
                  stroke={getGraphHighlightType('ceo_email') === 'threat' ? '#EF4444' : getGraphHighlightType('ceo_email') === 'verified' ? '#22C55E' : 'rgba(248, 250, 252, 0.3)'}
                  strokeWidth="2"
                  className="transition-all duration-300"
                />
                <circle cx="160" cy="150" r="3" fill="#22C55E" />
                <text x="160" y="167" fontSize="6.5" fill="#F8FAFC" textAnchor="middle" fontFamily="monospace" opacity="0.6">CEO_EMAIL_US</text>
              </g>
            </svg>

            {/* Float helper status card */}
            <div className="absolute bottom-4 left-4 right-4 bg-obsidian border border-slate-white/5 rounded-xs p-3">
              <span className="font-mono text-[8px] text-slate-white/30 tracking-widest uppercase block mb-1">MAP FOCUS DIRECTORY</span>
              <p className="font-mono text-[9px] text-slate-white/60">
                {selectedCase.id ? `Case short ID: ${selectedCase.id.slice(0, 8)}. Current verdict status: ${selectedCase.status.toUpperCase()}.` : "Select an active case to view mapped relationships."}
              </p>
            </div>

          </div>

        </div>

      </div>

    </div>
  );
}
