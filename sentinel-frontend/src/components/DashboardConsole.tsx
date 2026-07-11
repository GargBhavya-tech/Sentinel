import { useState, useEffect, FormEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  ShieldAlert, ShieldCheck, HelpCircle, Activity, 
  Clock, Plus, Search, FileText, Phone, Mail, 
  TrendingUp, RefreshCw, ChevronRight, Terminal, Network, ArrowLeft, Send
} from 'lucide-react';
import { EvidenceItem, TimelineEvent, AgentStatus } from '../types';
import { listCases, getCaseAudit } from '../api/sentinel';

interface DashboardConsoleProps {
  onExit: () => void;
  // The shared investigation instance from useInvestigation(). Optional: this
  // console currently runs a self-contained simulation, but App passes the live
  // instance so a future wiring can drive it from real SSE state.
  investigation?: ReturnType<typeof import('../hooks/useInvestigation')['useInvestigation']>;
}

export default function DashboardConsole({ onExit }: DashboardConsoleProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCaseId, setSelectedCaseId] = useState('SENT-109A');
  const [newNote, setNewNote] = useState('');
  const [currentTime, setCurrentTime] = useState('10:24:02 UTC');

  const [liveCases, setLiveCases] = useState<any[]>([]);
  const [liveTimelineEvents, setLiveTimelineEvents] = useState<TimelineEvent[]>([]);

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
    if (!selectedCaseId || selectedCaseId.startsWith('SENT-')) {
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

  // Live Agent simulation state
  const [agents, setAgents] = useState<AgentStatus[]>([
    { id: 'ag-1', name: 'Speech_Synapse_Agent', role: 'Acoustic Forensics', status: 'analyzing', currentTask: 'Comparing acoustic resonances with CEO voiceprint', progress: 42 },
    { id: 'ag-2', name: 'Document_Structure_Agent', role: 'Metadata & Integrity', status: 'idle', currentTask: 'Awaiting ledger feeds', progress: 100 },
    { id: 'ag-3', name: 'Geo_Tunnel_Agent', role: 'Geographic Cross-Ex', status: 'analyzing', currentTask: 'Mapping IP routing nodes against verified geo-profiles', progress: 78 },
    { id: 'ag-4', name: 'Ledger_Integrity_Agent', role: 'Transaction Audit', status: 'alert', currentTask: 'Routing RT_912000031 mismatch identified', progress: 100 },
  ]);

  // Simulate agent progress and status shifting in real time
  useEffect(() => {
    const interval = setInterval(() => {
      setAgents(prev => prev.map(agent => {
        if (agent.status === 'analyzing') {
          const nextProgress = agent.progress + Math.floor(Math.random() * 8) + 2;
          if (nextProgress >= 100) {
            return {
              ...agent,
              status: 'complete',
              progress: 100,
              currentTask: 'Analysis verified. Verdict logged to Central Synapse.'
            };
          }
          return { ...agent, progress: nextProgress };
        } else if (agent.status === 'complete') {
          // Restart after some time
          if (Math.random() > 0.7) {
            return {
              ...agent,
              status: 'analyzing',
              progress: 0,
              currentTask: agent.id === 'ag-1' ? 'Ingesting CALL_RECORD_B2.wav print' : 'Tracing geo coordinates on network packet #091'
            };
          }
        }
        return agent;
      }));
    }, 1200);

    return () => clearInterval(interval);
  }, []);

  // Pre-loaded evidence queue cases
  const [evidenceItems, setEvidenceItems] = useState<EvidenceItem[]>([
    {
      id: 'SENT-109A',
      type: 'voice',
      title: 'Cloned CEO Voice Print',
      source: 'call_recording_a8.wav',
      status: 'threat',
      timestamp: '2026-07-09T10:14:02Z',
      description: 'Audio print of voice instructing wire disbursement matches AI voice cloner patterns.',
      content: 'CEO voice replication detected. Mismatch in breath-to-speech ratio (98.2% synthetic rating). Frequency overlay matches PrimeCloner-v4 neural model.',
      confidence: 98,
    },
    {
      id: 'SENT-109B',
      type: 'spreadsheet',
      title: 'Aether Ledger Routing Discrepancy',
      source: 'invoice_9108A_US.pdf',
      status: 'suspicious',
      timestamp: '2026-07-09T10:16:15Z',
      description: 'Disbursement routing number RT_912000031 differs from primary payroll ledger.',
      content: 'The provided transit routing matches external shell entity registered in offshore jurisdiction. Discrepancy marked against primary supplier account records.',
      confidence: 64,
    },
    {
      id: 'SENT-109C',
      type: 'document',
      title: 'Singapore IP Tunnel Activity',
      source: 'network_stream_node.log',
      status: 'threat',
      timestamp: '2026-07-09T10:18:40Z',
      description: 'VPN gateway node route matches high-risk fraud center fingerprints.',
      content: 'Caller geolocation traced to Singapore VPN node. Concurrent login from CEO primary email client registered in San Francisco, CA. Simultaneous presence physically impossible.',
      confidence: 91,
    },
    {
      id: 'SENT-109D',
      type: 'thread',
      title: 'DKIM Verified Inbox Protocol',
      source: 'inbox_gateway_th.eml',
      status: 'verified',
      timestamp: '2026-07-09T10:20:10Z',
      description: 'Encrypted email thread confirming correct ledger routing ending in 20038.',
      content: 'Cryptographic handshake and DKIM signatures verified intact. Content matches trusted parameters. Source address validated.',
      confidence: 99,
    },
    {
      id: 'SENT-110A',
      type: 'payment',
      title: 'Pending Payroll Transfer Hold',
      source: 'transfer_instruction_A9.json',
      status: 'unverified',
      timestamp: '2026-07-09T10:22:15Z',
      description: 'Drafted transfer of $1,450,000.00 suspended awaiting final agent decision.',
      content: 'Value matches standard monthly payroll threshold. Transaction queued on hold pending resolving current critical threats.',
      confidence: 15,
    }
  ]);

  // Forensic chronological logs for the selected case
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([
    { id: 'e1', timestamp: '10:14:02 UTC', title: 'File Ingestion Sync', type: 'info', description: 'Raw call_recording_a8.wav print ingested.', sourceId: 'SENT-109A', agentName: 'Document_Structure_Agent' },
    { id: 'e2', timestamp: '10:14:08 UTC', title: 'Voiceprint Overlay Analysis', type: 'warning', description: 'Speech_Synapse_Agent completed spectrograph mapping.', sourceId: 'SENT-109A', agentName: 'Speech_Synapse_Agent' },
    { id: 'e3', timestamp: '10:14:15 UTC', title: 'Synthetic Signature Flags', type: 'threat', description: '98% synthetic match with prime-cloner voice models.', sourceId: 'SENT-109A', agentName: 'Speech_Synapse_Agent' },
    { id: 'e4', timestamp: '10:14:22 UTC', title: 'System Preventative Hold', type: 'threat', description: 'Transaction routing held. Cross-examination queue compiled.', sourceId: 'SENT-109A', agentName: 'Ledger_Integrity_Agent' },

    { id: 'e5', timestamp: '10:16:15 UTC', title: 'Invoice Parsing Completed', type: 'info', description: 'Extracted routing data from invoice_9108A_US.pdf.', sourceId: 'SENT-109B', agentName: 'Document_Structure_Agent' },
    { id: 'e6', timestamp: '10:16:20 UTC', title: 'Transit Code Check', type: 'warning', description: 'Discrepancy identified between transit codes RT_912000031 and secure ledger template.', sourceId: 'SENT-109B', agentName: 'Ledger_Integrity_Agent' },

    { id: 'e7', timestamp: '10:18:40 UTC', title: 'IP Geo-Mapping', type: 'info', description: 'Network stream traced to SG gateway node.', sourceId: 'SENT-109C', agentName: 'Geo_Tunnel_Agent' },
    { id: 'e8', timestamp: '10:19:02 UTC', title: 'Concurrency Contrast Fail', type: 'threat', description: 'CEO CA mail log-in overlaps call origin coordinates.', sourceId: 'SENT-109C', agentName: 'Geo_Tunnel_Agent' },

    { id: 'e9', timestamp: '10:20:10 UTC', title: 'Cryptographic Audit', type: 'success', description: 'DKIM and secure signatures parsed. Integrity fully intact.', sourceId: 'SENT-109D', agentName: 'Document_Structure_Agent' },

    { id: 'e10', timestamp: '10:22:15 UTC', title: 'Transaction Queued', type: 'info', description: 'Draft transfer payload placed on temporary hold pending threat review.', sourceId: 'SENT-110A', agentName: 'Ledger_Integrity_Agent' },
  ]);

  // Active highlighted relationship map nodes for the current selected case
  const getGraphHighlightType = (nodeId: string) => {
    if (selectedCaseId === 'SENT-109A') {
      if (nodeId === 'voice' || nodeId === 'central') return 'threat';
    }
    if (selectedCaseId === 'SENT-109B') {
      if (nodeId === 'ledger' || nodeId === 'central' || nodeId === 'invoice') return 'suspicious';
    }
    if (selectedCaseId === 'SENT-109C') {
      if (nodeId === 'vpn' || nodeId === 'central' || nodeId === 'ceo_email') return 'threat';
    }
    if (selectedCaseId === 'SENT-109D') {
      if (nodeId === 'ceo_email' || nodeId === 'secure_ledger') return 'verified';
    }
    return 'default';
  };

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
      sourceId: selectedCaseId,
      agentName: 'Secure_Human_Desk'
    };

    setTimelineEvents(prev => [newEvent, ...prev]);
    setNewNote('');
  };

  // Combined list of live database cases and pre-loaded mock cases
  const combinedEvidenceItems: EvidenceItem[] = [
    ...liveCases.map(c => ({
      id: c.case_id,
      type: 'thread' as const,
      title: `Slack Case #${c.short_id}`,
      source: `Slack Event`,
      status: (c.verdict === 'FRAUD_LIKELY' ? 'threat' : c.verdict === 'REVIEW' ? 'suspicious' : c.verdict === 'CLEAR' ? 'verified' : 'unverified') as any,
      timestamp: c.created_at,
      description: `Slack triggered investigation. Current status: ${c.status}`,
      content: `Status: ${c.status}\nVerdict: ${c.verdict || 'PENDING'}\nRisk Score: ${c.risk_score !== null ? (c.risk_score * 100).toFixed(1) + '%' : 'N/A'}\nAmount at Risk: $${c.amount_at_risk.toLocaleString()}`,
      confidence: c.risk_score !== null ? Math.round(c.risk_score * 100) : 0,
    })),
    ...evidenceItems
  ];

  // Filter evidence lists
  const filteredEvidence = combinedEvidenceItems.filter(item => 
    item.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.source.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const selectedCase = combinedEvidenceItems.find(item => item.id === selectedCaseId) || combinedEvidenceItems[0];
  const selectedTimeline = selectedCaseId.startsWith('SENT-') 
    ? timelineEvents.filter(e => e.sourceId === selectedCaseId)
    : liveTimelineEvents;

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
            [ EXIT CONSOLE ]
          </button>
          
          <div className="h-6 w-[1px] bg-slate-white/10 hidden md:block" />
          
          <div>
            <span className="font-display font-black text-sm tracking-[0.25em] text-slate-white uppercase block">
              SENTINEL COGNITIVE CONSOLE
            </span>
            <span className="font-mono text-[9px] tracking-wider text-slate-white/30 block mt-0.5">
              FORENSIC AUDITING WORKSPACE // ACTIVE_PORT_3000
            </span>
          </div>
        </div>

        {/* Global Realtime System Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 md:gap-8 border border-slate-white/5 bg-slate-white/[0.01] rounded-xs px-5 py-2.5 max-w-2xl">
          <div className="flex flex-col">
            <span className="font-mono text-[8px] text-slate-white/30 tracking-widest uppercase">FILES SCANNED</span>
            <span className="font-mono text-xs font-semibold text-slate-white">204,912 files</span>
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-[8px] text-evidence-crimson tracking-widest uppercase">CRITICAL ALERTS</span>
            <span className="font-mono text-xs font-semibold text-evidence-crimson animate-pulse">2 threat vectors</span>
          </div>
          <div className="flex flex-col">
            <span className="font-mono text-[8px] text-cyber-emerald tracking-widest uppercase">VERIFIED CLEAN</span>
            <span className="font-mono text-xs font-semibold text-cyber-emerald">99.8% safe</span>
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
                <span className={`font-mono text-[8px] tracking-widest ${agent.status === 'alert' ? 'text-evidence-crimson' : agent.status === 'analyzing' ? 'text-electric-cyan animate-pulse' : 'text-slate-white/30'}`}>
                  {agent.status.toUpperCase()}
                </span>
              </div>
              <div className="w-full bg-slate-white/5 h-1 rounded-full overflow-hidden mb-0.5">
                <div 
                  className={`h-full ${agent.status === 'alert' ? 'bg-evidence-crimson' : agent.status === 'complete' ? 'bg-cyber-emerald' : 'bg-electric-cyan'}`} 
                  style={{ width: `${agent.progress}%`, transition: 'width 0.8s ease-out' }} 
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
                {selectedCaseId === 'SENT-109A' && "Active spectrograph discrepancy identified between CEO_VOICE_8 and central verified parameters."}
                {selectedCaseId === 'SENT-109B' && "Routing code mismatch detected between ledger supplier records and external invoice."}
                {selectedCaseId === 'SENT-109C' && "Incompatible logins mapped between US email client and SG voicecall VPN IP."}
                {selectedCaseId === 'SENT-109D' && "DKIM signature integrity matches approved CA standards."}
                {selectedCaseId === 'SENT-110A' && "Transaction draft paused, holding for central synapse consensus."}
              </p>
            </div>

          </div>

        </div>

      </div>

    </div>
  );
}
