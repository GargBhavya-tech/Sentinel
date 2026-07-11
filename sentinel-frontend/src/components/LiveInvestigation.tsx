import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  FileText, Phone, Mail, ArrowDownRight, ArrowUpRight, 
  AlertTriangle, ShieldCheck, RefreshCw, Layers, X, Terminal, Fingerprint, Globe, Key, Cpu 
} from 'lucide-react';
import { playClick, playTick, playSweep, playAlert } from '../utils/audio';

export default function LiveInvestigation() {
  const [step, setStep] = useState(0);
  const [confidence, setConfidence] = useState(0);
  const [selectedEvidence, setSelectedEvidence] = useState<'invoice' | 'voice' | 'email' | null>(null);
  const [activeTab, setActiveTab] = useState<'metadata' | 'raw' | 'forensics'>('metadata');

  // React to sequencer step changes to play futuristic cinematic sounds
  useEffect(() => {
    if (step === 1 || step === 2 || step === 3) {
      playTick();
    } else if (step === 4 || step === 5) {
      playSweep();
    } else if (step === 7) {
      playAlert();
    }
  }, [step]);

  // Timed sequencer for progressive reveal
  useEffect(() => {
    let interval: any;
    let confidenceInterval: any;

    const runSequence = () => {
      // Step 1: Invoice reveals (0s)
      setStep(1);
      setConfidence(0);

      // Step 2: Voice Transcript reveals (1.2s)
      setTimeout(() => {
        setStep(2);
      }, 1200);

      // Step 3: Email Thread reveals (2.4s)
      setTimeout(() => {
        setStep(3);
      }, 2400);

      // Step 4: Vectors Converge & Lines Animate (3.6s)
      setTimeout(() => {
        setStep(4);
      }, 3600);

      // Step 5: Crimson Highlight on Discrepancy (4.8s)
      setTimeout(() => {
        setStep(5);
      }, 4800);

      // Step 6: Confidence Climbs (5.6s)
      setTimeout(() => {
        setStep(6);
        let currentConf = 0;
        confidenceInterval = setInterval(() => {
          currentConf += 2;
          if (currentConf >= 98) {
            currentConf = 98;
            clearInterval(confidenceInterval);
          }
          setConfidence(currentConf);
        }, 15); // Faster confidence climb (from 30ms to 15ms)
      }, 5600);

      // Step 7: Verdict (7.0s)
      setTimeout(() => {
        setStep(7);
      }, 7000);

      // Loop reset sequence: stays at final verdict for 5 seconds, then restarts
      setTimeout(() => {
        setStep(0);
        setConfidence(0);
        // Clean restart after 1.2 seconds of darkness
        setTimeout(() => {
          runSequence();
        }, 1200);
      }, 12000);
    };

    runSequence();

    return () => {
      clearInterval(interval);
      clearInterval(confidenceInterval);
    };
  }, []);

  return (
    <section id="demo" className="relative py-32 bg-obsidian border-t border-slate-white/5 overflow-hidden">
      <div className="absolute inset-0 console-grid opacity-10 pointer-events-none" />
      
      {/* Absolute background accent */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-tr from-evidence-crimson/5 via-transparent to-transparent blur-3xl pointer-events-none" />

      <div className="max-w-7xl mx-auto px-6 relative z-10">
        
        {/* Section Title */}
        <div className="text-center max-w-2xl mx-auto mb-20">
          <div className="flex items-center justify-center gap-2 mb-3">
            <span className="w-1.5 h-1.5 rounded-full bg-evidence-crimson animate-ping" />
            <span className="font-mono text-[10px] tracking-widest text-evidence-crimson uppercase">
              LIVE OPERATION SIMULATOR
            </span>
          </div>
          <h2 className="font-display font-bold text-3xl md:text-5xl tracking-widest text-slate-white uppercase mb-6 leading-tight">
            CROSS-EXAMINATION DEMO
          </h2>
          <p className="font-sans text-xs md:text-sm text-slate-white/50 tracking-wider">
            Observe in real time as Sentinel's autonomous agents index, correlate, and verify mismatched facts across three independent vectors.
          </p>

          {/* Interactive Advisory Banner */}
          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.15 }}
            className="mt-6 inline-flex flex-col sm:flex-row items-center gap-3 bg-electric-cyan/5 border border-electric-cyan/20 rounded-xs px-4 py-3 text-left max-w-xl mx-auto"
          >
            <span className="flex h-2.5 w-2.5 shrink-0 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-electric-cyan opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-electric-cyan"></span>
            </span>
            <p className="font-mono text-[9.5px] text-electric-cyan tracking-wider leading-relaxed uppercase">
              <strong className="text-white">COGNITIVE ADVISORY:</strong> Click on any active evidence block below (e.g., PDF Invoice, Voice, or Email) as they initialize to reveal cryptographic headers, IP routing, and forensic deep-dives.
            </p>
          </motion.div>
        </div>

        {/* Demo Interface Wrapper */}
        <div className="relative max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
          
          {/* Left: Input Evidence Panels (5 Columns) */}
          <motion.div
            initial={{ opacity: 0, x: -60 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: false, margin: "-100px" }}
            transition={{ type: "spring", stiffness: 45, damping: 15 }}
            className="lg:col-span-5 flex flex-col gap-6"
          >
            <div className="flex items-center justify-between px-1">
              <span className="font-mono text-[9px] tracking-widest text-slate-white/30 uppercase">CLICK ANY VECTOR FOR DRILLDOWN</span>
              <span className="font-mono text-[8px] px-1.5 py-0.5 bg-electric-cyan/10 text-electric-cyan rounded-full animate-pulse">INTERACTIVE</span>
            </div>
            
            {/* Element 1: Invoice */}
            <motion.div
              onClick={() => {
                if (step >= 1) {
                  playSweep();
                  setSelectedEvidence('invoice');
                  setActiveTab('metadata');
                }
              }}
              whileHover={step >= 1 ? { scale: 1.02, y: -2 } : {}}
              animate={{
                opacity: step >= 1 ? 1 : 0.15,
                y: step >= 1 ? 0 : 20,
                borderColor: selectedEvidence === 'invoice' 
                  ? "#38BDF8" 
                  : step >= 5 
                    ? "rgba(239, 68, 68, 0.4)" 
                    : "rgba(248, 250, 252, 0.08)"
              }}
              transition={{ duration: 0.4 }}
              className={`p-5 glass-panel rounded-xs relative overflow-hidden select-none ${
                step >= 1 ? 'cursor-pointer hover:bg-slate-white/[0.02] hover:shadow-[0_0_15px_rgba(56,189,248,0.06)]' : 'pointer-events-none'
              }`}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-electric-cyan" />
                  <span className="font-mono text-[11px] tracking-wider text-slate-white/80">INVOICE_9108A_US.PDF</span>
                </div>
                <span className="font-mono text-[9px] text-slate-white/30">[ INGESTED ]</span>
              </div>
              
              <div className="space-y-2 font-mono text-[10px] text-slate-white/50">
                <div className="flex justify-between">
                  <span>VENDOR:</span>
                  <span className="text-slate-white/80">Aether Group Logistics</span>
                </div>
                <div className="flex justify-between">
                  <span>DISBURSEMENT:</span>
                  <span className="text-slate-white/80">$1,450,000.00 USD</span>
                </div>
                <div className="flex justify-between">
                  <span>ROUTING TRANSIT:</span>
                  <motion.span
                    animate={{
                      color: step >= 5 ? "#EF4444" : "#F8FAFC"
                    }}
                    className="font-bold"
                  >
                    RT_912000031
                  </motion.span>
                </div>
              </div>

              {step >= 5 && (
                <div className="absolute right-3 bottom-3 flex items-center gap-1.5 bg-evidence-crimson/10 border border-evidence-crimson/30 rounded-xs px-2 py-0.5">
                  <span className="w-1 h-1 rounded-full bg-evidence-crimson animate-pulse" />
                  <span className="font-mono text-[8px] text-evidence-crimson tracking-wider uppercase">ROUTING MISMATCH</span>
                </div>
              )}
            </motion.div>

            {/* Element 2: Voice Transcript */}
            <motion.div
              onClick={() => {
                if (step >= 2) {
                  playSweep();
                  setSelectedEvidence('voice');
                  setActiveTab('metadata');
                }
              }}
              whileHover={step >= 2 ? { scale: 1.02, y: -2 } : {}}
              animate={{
                opacity: step >= 2 ? 1 : 0.15,
                y: step >= 2 ? 0 : 20,
                borderColor: selectedEvidence === 'voice' 
                  ? "#38BDF8" 
                  : step >= 5 
                    ? "rgba(239, 68, 68, 0.4)" 
                    : "rgba(248, 250, 252, 0.08)"
              }}
              transition={{ duration: 0.4 }}
              className={`p-5 glass-panel rounded-xs relative overflow-hidden select-none ${
                step >= 2 ? 'cursor-pointer hover:bg-slate-white/[0.02] hover:shadow-[0_0_15px_rgba(56,189,248,0.06)]' : 'pointer-events-none'
              }`}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Phone className="w-4 h-4 text-amber-warning" />
                  <span className="font-mono text-[11px] tracking-wider text-slate-white/80">CALL_RECORDING_A8.WAV</span>
                </div>
                <span className="font-mono text-[9px] text-slate-white/30">[ AI TRANSCRIBED ]</span>
              </div>
              
              <div className="space-y-3 font-mono text-[10px] text-slate-white/50">
                <div>
                  <span className="text-amber-warning font-semibold">CALLER (SECURE ID):</span>
                  <p className="text-slate-white/70 italic mt-1 leading-relaxed text-[9px]">
                    &quot;Yes, we need this wire processed immediately. Use the updated bank template routing number ending in 00031...&quot;
                  </p>
                </div>
                <div className="flex justify-between border-t border-slate-white/5 pt-2 text-[9px]">
                  <span>VOICE MATCH STATUS:</span>
                  <span className="text-cyber-emerald">VERIFIED IDENTITY (CEO)</span>
                </div>
                <div className="flex justify-between text-[9px]">
                  <span>CALL METADATA LOC:</span>
                  <motion.span 
                    animate={{
                      color: step >= 5 ? "#EF4444" : "#F8FAFC"
                    }}
                    className="font-bold"
                  >
                    VPN_GATEWAY_SG (IP: 103.22.201.2)
                  </motion.span>
                </div>
              </div>

              {step >= 5 && (
                <div className="absolute right-3 bottom-3 flex items-center gap-1.5 bg-evidence-crimson/10 border border-evidence-crimson/30 rounded-xs px-2 py-0.5">
                  <span className="w-1 h-1 rounded-full bg-evidence-crimson animate-pulse" />
                  <span className="font-mono text-[8px] text-evidence-crimson tracking-wider uppercase">GEOGRAPHIC CONTRAST</span>
                </div>
              )}
            </motion.div>

            {/* Element 3: Email Thread */}
            <motion.div
              onClick={() => {
                if (step >= 3) {
                  playSweep();
                  setSelectedEvidence('email');
                  setActiveTab('metadata');
                }
              }}
              whileHover={step >= 3 ? { scale: 1.02, y: -2 } : {}}
              animate={{
                opacity: step >= 3 ? 1 : 0.15,
                y: step >= 3 ? 0 : 20,
                borderColor: selectedEvidence === 'email' 
                  ? "#38BDF8" 
                  : step >= 5 
                    ? "rgba(239, 68, 68, 0.4)" 
                    : "rgba(248, 250, 252, 0.08)"
              }}
              transition={{ duration: 0.4 }}
              className={`p-5 glass-panel rounded-xs relative overflow-hidden select-none ${
                step >= 3 ? 'cursor-pointer hover:bg-slate-white/[0.02] hover:shadow-[0_0_15px_rgba(56,189,248,0.06)]' : 'pointer-events-none'
              }`}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Mail className="w-4 h-4 text-cyber-emerald" />
                  <span className="font-mono text-[11px] tracking-wider text-slate-white/80">INBOX_GATEWAY_TH.EML</span>
                </div>
                <span className="font-mono text-[9px] text-slate-white/30">[ SIGNED & SECURED ]</span>
              </div>
              
              <div className="space-y-2 font-mono text-[10px] text-slate-white/50">
                <div className="flex justify-between">
                  <span>FROM:</span>
                  <span className="text-slate-white/80">finance@aethercorp.com</span>
                </div>
                <div className="flex justify-between">
                  <span>IP LOCATION ORIGIN:</span>
                  <span className="text-cyber-emerald">SAN FRANCISCO, CA (US)</span>
                </div>
                <div className="flex justify-between">
                  <span>CONTENT AUDIT:</span>
                  <span className="text-slate-white/70 italic text-[9px]">&quot;Disregard previous bank revisions. We use template ending 20038.&quot;</span>
                </div>
              </div>
            </motion.div>

          </motion.div>

          {/* Middle: Vector Integration SVG Lines (2 Columns) */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: false, margin: "-100px" }}
            transition={{ type: "spring", stiffness: 40, damping: 12, delay: 0.15 }}
            className="lg:col-span-2 flex items-center justify-center relative min-h-[150px] lg:min-h-0 pointer-events-none"
          >
            <svg className="absolute inset-0 w-full h-full hidden lg:block" viewBox="0 0 100 100" preserveAspectRatio="none">
              {/* Line 1 (Invoice to Center) */}
              <motion.line
                x1="0" y1="18" x2="100" y2="50"
                stroke="rgba(56, 189, 248, 0.3)"
                strokeWidth="1.5"
                strokeDasharray="4 2"
                animate={step >= 4 ? { strokeDashoffset: [0, -20] } : {}}
                transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                className={`${step >= 4 ? "opacity-100" : "opacity-10"}`}
              />
              {/* Line 2 (Transcript to Center) */}
              <motion.line
                x1="0" y1="50" x2="100" y2="50"
                stroke="rgba(245, 158, 11, 0.3)"
                strokeWidth="1.5"
                strokeDasharray="4 2"
                animate={step >= 4 ? { strokeDashoffset: [0, -20] } : {}}
                transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                className={`${step >= 4 ? "opacity-100" : "opacity-10"}`}
              />
              {/* Line 3 (Email to Center) */}
              <motion.line
                x1="0" y1="82" x2="100" y2="50"
                stroke="rgba(34, 197, 94, 0.3)"
                strokeWidth="1.5"
                strokeDasharray="4 2"
                animate={step >= 4 ? { strokeDashoffset: [0, -20] } : {}}
                transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                className={`${step >= 4 ? "opacity-100" : "opacity-10"}`}
              />
            </svg>
            
            <div className="lg:hidden flex flex-col items-center gap-1">
              <Layers className="w-5 h-5 text-slate-white/20 animate-pulse" />
              <span className="font-mono text-[9px] text-slate-white/20">INTEGRATING VECTORS</span>
            </div>
          </motion.div>

          {/* Right: Central Processing Hub (5 Columns) */}
          <motion.div
            initial={{ opacity: 0, x: 60 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: false, margin: "-100px" }}
            transition={{ type: "spring", stiffness: 45, damping: 15, delay: 0.1 }}
            className="lg:col-span-5 flex flex-col justify-center"
          >
            
            <motion.div
              animate={{
                borderColor: step >= 7 ? "rgba(239, 68, 68, 0.5)" : "rgba(248, 250, 252, 0.08)",
                background: step >= 7 ? "rgba(239, 68, 68, 0.02)" : "rgba(15, 23, 42, 0.45)"
              }}
              transition={{ duration: 0.6 }}
              className="glass-panel p-8 rounded-xs relative flex flex-col justify-between h-full min-h-[400px]"
            >
              <div>
                {/* Header info */}
                <div className="flex justify-between items-center border-b border-slate-white/5 pb-4 mb-6">
                  <div>
                    <span className="font-mono text-[10px] tracking-wider text-slate-white/40 block">COGNITIVE HUB</span>
                    <span className="font-display font-medium text-xs tracking-wider text-slate-white uppercase">SYNAPSE CORE ALPHA</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[9px] text-slate-white/40">ENGINE STATUS:</span>
                    <span className={`font-mono text-[9px] font-bold ${step >= 4 ? "text-electric-cyan" : "text-slate-white/20"}`}>
                      {step >= 7 ? "ALERT" : step >= 4 ? "PROCESSING" : "STANDBY"}
                    </span>
                  </div>
                </div>

                {/* Processing Logs */}
                <div className="h-32 font-mono text-[9px] text-slate-white/40 space-y-2 overflow-y-auto no-scrollbar mb-8">
                  <div className="flex items-center justify-between text-slate-white/60">
                    <span>[09:00:01] INITIALIZING SYNC...</span>
                    <span className="text-cyber-emerald">[OK]</span>
                  </div>
                  
                  {step >= 1 && (
                    <div className="flex items-center justify-between text-slate-white/60">
                      <span>[09:00:02] PARSED INVOICE ROUTING...</span>
                      <span className="text-electric-cyan">RT_912000031</span>
                    </div>
                  )}

                  {step >= 2 && (
                    <div className="flex items-center justify-between text-slate-white/60">
                      <span>[09:00:04] ANALYSIS OF VOICE RECPT...</span>
                      <span className="text-amber-warning">IDENT MATCHED (CEO)</span>
                    </div>
                  )}

                  {step >= 3 && (
                    <div className="flex items-center justify-between text-slate-white/60 flex-wrap">
                      <span>[09:00:06] RETRIEVED SECURE EMAILS...</span>
                      <span className="text-cyber-emerald">DKIM VERIFIED</span>
                    </div>
                  )}

                  {step >= 4 && (
                    <div className="flex items-center justify-between text-electric-cyan animate-pulse">
                      <span>[09:00:07] CROSS-REFERENCING VECTORS...</span>
                      <span>[ACTIVE]</span>
                    </div>
                  )}

                  {step >= 5 && (
                    <div className="flex flex-col text-evidence-crimson font-bold gap-0.5 mt-1">
                      <span>⚠️ DISCREPANCY REVEALED:</span>
                      <span className="pl-2">CEO CALLED FROM IP IN SINGAPORE DURING CONCURRENT EMAIL LOG-IN FROM SAN FRANCISCO. ROUTING NUMBER IN CALL CONTRADICTS ENCRYPTED INBOX INSTRUCTION.</span>
                    </div>
                  )}
                </div>

                {/* Confidence Level Circle & Bar */}
                <div className="bg-obsidian/60 border border-slate-white/5 rounded-xs p-4 mb-6">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-mono text-[10px] tracking-widest text-slate-white/40">THREAT PROBABILITY:</span>
                    <span className={`font-mono text-xs font-bold ${step >= 6 ? "text-evidence-crimson" : "text-slate-white/40"}`}>
                      {confidence}%
                    </span>
                  </div>
                  
                  <div className="w-full bg-slate-white/5 h-2 rounded-full overflow-hidden">
                    <motion.div 
                      className={`h-full ${confidence > 80 ? "bg-evidence-crimson" : confidence > 40 ? "bg-amber-warning" : "bg-electric-cyan"}`}
                      style={{ width: `${confidence}%` }}
                      transition={{ ease: "linear" }}
                    />
                  </div>
                </div>
              </div>

              {/* Verdict Indicator */}
              <div className="relative">
                <AnimatePresence mode="wait">
                  {step >= 7 ? (
                    <motion.div
                      key="alert-verdict"
                      initial={{ scale: 0.95, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.95, opacity: 0 }}
                      className="border border-evidence-crimson bg-evidence-crimson/10 rounded-xs p-4 flex items-start gap-3"
                    >
                      <AlertTriangle className="w-5 h-5 text-evidence-crimson shrink-0 mt-0.5 animate-pulse" />
                      <div>
                        <h4 className="font-display font-bold text-xs tracking-widest text-evidence-crimson uppercase">
                          CONTRADICTION DETECTED // THREAT CONFIRMED
                        </h4>
                        <p className="font-mono text-[9px] text-slate-white/60 tracking-wider mt-1 uppercase">
                          CROSS-COMMUNICATION INTEGRITY BREACHED. IMPERSONATION ATTACK DETECTED. PREVENTATIVE HOLD ENFORCED.
                        </p>
                      </div>
                    </motion.div>
                  ) : (
                    <motion.div
                      key="safe-verdict"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="border border-slate-white/5 bg-slate-white/[0.01] rounded-xs p-4 flex items-center gap-3"
                    >
                      <RefreshCw className="w-4 h-4 text-slate-white/20 animate-spin" />
                      <span className="font-mono text-[9px] tracking-widest text-slate-white/30 uppercase">
                        {step === 0 ? "WAITING FOR EVIDENCE FEED..." : "ANALYZING CHANNELS IN REAL TIME..."}
                      </span>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

            </motion.div>

          </motion.div>

        </div>

        {/* Interactive Forensic Detail Drawer */}
        <AnimatePresence>
          {selectedEvidence && (
            <motion.div
              initial={{ opacity: 0, x: 400 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 400 }}
              transition={{ type: 'spring', stiffness: 90, damping: 16 }}
              className="fixed top-20 right-4 bottom-4 w-full max-w-md bg-obsidian/95 border border-slate-white/10 backdrop-blur-md rounded-xs z-50 p-6 flex flex-col justify-between shadow-[0_0_50px_rgba(0,0,0,0.85)]"
            >
              <div>
                {/* Header */}
                <div className="flex items-center justify-between border-b border-slate-white/10 pb-4 mb-6">
                  <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-electric-cyan" />
                    <span className="font-mono text-xs font-bold tracking-widest text-slate-white uppercase">
                      FORENSIC EVIDENCE ANALYSIS
                    </span>
                  </div>
                  <button
                    onClick={() => {
                      playClick();
                      setSelectedEvidence(null);
                    }}
                    className="text-slate-white/40 hover:text-slate-white transition-colors p-1 cursor-pointer focus:outline-none"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Tabs */}
                <div className="grid grid-cols-3 gap-2 mb-6 border-b border-slate-white/5 pb-3">
                  {[
                    { id: 'metadata', label: 'METADATA' },
                    { id: 'raw', label: 'CYBER HEADERS' },
                    { id: 'forensics', label: 'FORENSIC VERDICT' }
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => {
                        playClick();
                        setActiveTab(tab.id as any);
                      }}
                      className={`font-mono text-[9px] py-1 border transition-all duration-200 cursor-pointer text-center focus:outline-none ${
                        activeTab === tab.id
                          ? 'text-electric-cyan border-electric-cyan/30 bg-electric-cyan/5 font-semibold'
                          : 'text-slate-white/40 border-transparent hover:text-slate-white/75'
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Content rendering based on selected evidence and tab */}
                <div className="space-y-4 text-xs font-sans">
                  {selectedEvidence === 'invoice' && (
                    <div>
                      {activeTab === 'metadata' && (
                        <div className="space-y-3 font-mono text-[10px]">
                          <div className="bg-slate-white/[0.02] p-3 border border-slate-white/5 rounded-xs">
                            <span className="text-slate-white/40 block mb-0.5">ENTITY FILE</span>
                            <span className="text-slate-white font-medium">INVOICE_9108A_US.PDF</span>
                          </div>
                          <div className="bg-slate-white/[0.02] p-3 border border-slate-white/5 rounded-xs">
                            <span className="text-slate-white/40 block mb-0.5">SHA-256 SUM</span>
                            <span className="text-electric-cyan text-[8px] break-all select-all font-bold">
                              a93b22fe901c0b31e9c8a91345d901f02cde59312fe29a8dbd2c03c15049b109
                            </span>
                          </div>
                          <div className="bg-slate-white/[0.02] p-3 border border-slate-white/5 rounded-xs">
                            <span className="text-slate-white/40 block mb-0.5">TARGET DISBURSEMENT</span>
                            <span className="text-slate-white font-medium">$1,450,000.00 USD</span>
                          </div>
                        </div>
                      )}
                      {activeTab === 'raw' && (
                        <div className="font-mono text-[8.5px] text-slate-white/60 bg-black/60 p-4 border border-slate-white/5 rounded-xs h-64 overflow-y-auto space-y-1.5 leading-relaxed no-scrollbar select-text">
                          <div>% PDF-1.4</div>
                          <div>%âãÏÓ</div>
                          <div>3 0 obj &lt;&lt; /Type /Page /Parent 2 0 R /Resources 4 0 R /Contents 5 0 R &gt;&gt;</div>
                          <div className="text-amber-warning">/ForensicInfo &lt;&lt;</div>
                          <div className="pl-3">/RoutingTransit (RT_912000031)</div>
                          <div className="pl-3 text-evidence-crimson">/X-RiskRating (HIGH_MISMATCH_TRANSIT_GATE)</div>
                          <div className="pl-3">/DocHash (0xa93b22fe)</div>
                          <div className="pl-3">/ExtractorVersion (SentinelDoc_v2.8)</div>
                          <div className="text-amber-warning">&gt;&gt;</div>
                          <div>stream</div>
                          <div>BT /F1 12 Tf 70 700 Td (INVOICE TO AETHER) Tj ET</div>
                          <div>BT /F1 10 Tf 70 650 Td (VENDOR REF: Aether Group Logistics) Tj ET</div>
                          <div className="text-evidence-crimson">BT /F1 10 Tf 70 620 Td (TRANSIT GATEWAY: RT_912000031) Tj ET</div>
                          <div>endstream</div>
                        </div>
                      )}
                      {activeTab === 'forensics' && (
                        <div className="space-y-4">
                          <div className="flex items-center gap-2 bg-evidence-crimson/10 border border-evidence-crimson/20 p-3 rounded-xs text-[10px]">
                            <Fingerprint className="w-4 h-4 text-evidence-crimson shrink-0" />
                            <span className="font-mono text-evidence-crimson font-bold uppercase tracking-wider">
                              CRITICAL PATHWAY CORRELATION FAILED
                            </span>
                          </div>
                          <p className="text-xs text-slate-white/70 leading-relaxed font-sans">
                            Sentinel Cross-Verification mapped the Routing Transit Number <strong className="text-evidence-crimson font-mono">RT_912000031</strong> against global clearing maps. It is mapped to an unlisted offshore holding vault account in Belize, contradicting the vendor's standard US clearing house credentials (RT_200192080).
                          </p>
                          <div className="border border-slate-white/10 p-3 bg-slate-white/[0.02] rounded-xs">
                            <span className="font-mono text-[9px] text-slate-white/40 block">CONFIDENCE METRIC</span>
                            <span className="text-evidence-crimson font-mono font-bold text-base">99.8% FRAUD INDEX</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {selectedEvidence === 'voice' && (
                    <div>
                      {activeTab === 'metadata' && (
                        <div className="space-y-3 font-mono text-[10px]">
                          <div className="bg-slate-white/[0.02] p-3 border border-slate-white/5 rounded-xs">
                            <span className="text-slate-white/40 block mb-0.5">AUDIO SOURCE</span>
                            <span className="text-slate-white font-medium">CALL_RECORDING_A8.WAV</span>
                          </div>
                          <div className="bg-slate-white/[0.02] p-3 border border-slate-white/5 rounded-xs">
                            <span className="text-slate-white/40 block mb-0.5">IDENT DEVIATION</span>
                            <span className="text-cyber-emerald text-xs font-semibold">14.2% SPECTRAL MISMATCH (CEO BIOM_VAULT)</span>
                          </div>
                          <div className="bg-slate-white/[0.02] p-3 border border-slate-white/5 rounded-xs">
                            <span className="text-slate-white/40 block mb-0.5">INCOMING INGRESS</span>
                            <span className="text-slate-white font-medium">VPN_GATEWAY_SG (IP: 103.22.201.2)</span>
                          </div>
                        </div>
                      )}
                      {activeTab === 'raw' && (
                        <div className="font-mono text-[8.5px] text-slate-white/60 bg-black/60 p-4 border border-slate-white/5 rounded-xs h-64 overflow-y-auto space-y-1.5 leading-relaxed no-scrollbar select-text">
                          <div>RIFF (72402) WAVEfmt </div>
                          <div>[Audio Ingress Track Node 1]</div>
                          <div>Channels: 1 (Mono) // Sample Rate: 16000Hz</div>
                          <div className="text-amber-warning">SIP_HEADERS:</div>
                          <div className="pl-3">From: &quot;Secure Gateway Alpha&quot; &lt;ceo@aethercorp.com&gt;</div>
                          <div className="pl-3">User-Agent: Linphone/3.6.1 (belle-sip/1.2.4)</div>
                          <div className="pl-3 text-evidence-crimson">X-Origin-IP: 103.22.201.2 (VPN_Exit_Singapore)</div>
                          <div className="pl-3">Authorization: digest response=&quot;7f1a3029...&quot;</div>
                          <div className="text-amber-warning">SPECTRAL ANALYSIS MATRIX:</div>
                          <div className="pl-3">f0_fundamental: 124.5 Hz (Consistent)</div>
                          <div className="pl-3 text-evidence-crimson">formant_jitter: 8.9% (Abnormal micro-frequency delay)</div>
                          <div className="pl-3 text-evidence-crimson">neural_render_artifact: Generative model artifact identified</div>
                        </div>
                      )}
                      {activeTab === 'forensics' && (
                        <div className="space-y-4">
                          <div className="flex items-center gap-2 bg-evidence-crimson/10 border border-evidence-crimson/20 p-3 rounded-xs text-[10px]">
                            <Globe className="w-4 h-4 text-evidence-crimson shrink-0" />
                            <span className="font-mono text-evidence-crimson font-bold uppercase tracking-wider">
                              GEOGRAPHIC CO-LOCATION EXCLUSION
                            </span>
                          </div>
                          <p className="text-xs text-slate-white/70 leading-relaxed font-sans">
                            While the caller's acoustic template holds an 84.6% voice print match to the CEO's biometric vault, the network routing originates from a Singapore proxy IP. Concurrently, the CEO's encrypted enterprise account was authenticated from their home terminal in San Francisco, CA. Dual geographic presence is physically impossible.
                          </p>
                          <div className="border border-slate-white/10 p-3 bg-slate-white/[0.02] rounded-xs">
                            <span className="font-mono text-[9px] text-slate-white/40 block">BIOMETRIC INTEGRITY</span>
                            <span className="text-evidence-crimson font-mono font-bold text-base">HIGH-DENSITY CLONING CONFIRMED</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {selectedEvidence === 'email' && (
                    <div>
                      {activeTab === 'metadata' && (
                        <div className="space-y-3 font-mono text-[10px]">
                          <div className="bg-slate-white/[0.02] p-3 border border-slate-white/5 rounded-xs">
                            <span className="text-slate-white/40 block mb-0.5">EMAIL INGRESS</span>
                            <span className="text-slate-white font-medium">INBOX_GATEWAY_TH.EML</span>
                          </div>
                          <div className="bg-slate-white/[0.02] p-3 border border-slate-white/5 rounded-xs">
                            <span className="text-slate-white/40 block mb-0.5">DKIM ALIGNMENT</span>
                            <span className="text-cyber-emerald text-xs font-semibold">VERIFIED & SIGNED BY SECURE CA</span>
                          </div>
                          <div className="bg-slate-white/[0.02] p-3 border border-slate-white/5 rounded-xs">
                            <span className="text-slate-white/40 block mb-0.5">IP ORIGIN</span>
                            <span className="text-slate-white font-medium">198.51.100.24 (San Francisco, CA)</span>
                          </div>
                        </div>
                      )}
                      {activeTab === 'raw' && (
                        <div className="font-mono text-[8.5px] text-slate-white/60 bg-black/60 p-4 border border-slate-white/5 rounded-xs h-64 overflow-y-auto space-y-1.5 leading-relaxed no-scrollbar select-text">
                          <div>Delivered-To: finance@aethercorp.com</div>
                          <div>Received: from mail-issuer.aethercorp.com (198.51.100.24)</div>
                          <div className="text-cyber-emerald">DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed; d=aethercorp.com;</div>
                          <div className="pl-3 text-cyber-emerald">s=2024-enterprise; h=from:to:subject:date:message-id;</div>
                          <div className="pl-3 text-cyber-emerald">bh=vK8f92jX89bA90pXhX=; b=S9bA10F92837f...</div>
                          <div>From: &quot;Secure Finance Office&quot; &lt;finance@aethercorp.com&gt;</div>
                          <div>Subject: Re: Wire Disbursement routing update</div>
                          <div className="text-cyber-emerald">X-SPF-Record: PASS (domain-level authorization confirmed)</div>
                          <div>Message-ID: &lt;A8910F1-0982-Aether@aethercorp.com&gt;</div>
                          <div className="mt-2 text-slate-white/80 font-semibold">Content-Type: text/plain; charset=UTF-8</div>
                          <div className="text-cyber-emerald">BODY TRACE: &quot;Disregard previous bank revisions. We use template ending 20038.&quot;</div>
                        </div>
                      )}
                      {activeTab === 'forensics' && (
                        <div className="space-y-4">
                          <div className="flex items-center gap-2 bg-cyber-emerald/10 border border-cyber-emerald/20 p-3 rounded-xs text-[10px]">
                            <Key className="w-4 h-4 text-cyber-emerald shrink-0" />
                            <span className="font-mono text-cyber-emerald font-bold uppercase tracking-wider">
                              SECURE CHANNEL VERIFIED
                            </span>
                          </div>
                          <p className="text-xs text-slate-white/70 leading-relaxed font-sans">
                            DKIM, SPF, and DMARC alignments are fully authenticated back to Aether Corp's certified corporate identity cluster. The instructions on this channel to use template ending <strong className="text-cyber-emerald font-mono">20038</strong> represent the genuine, cryptographically-authorized state, exposing the phone call's contradicting claim to routing <strong className="text-evidence-crimson font-mono">RT_912000031</strong> as a fraudulent spoof attempt.
                          </p>
                          <div className="border border-slate-white/10 p-3 bg-slate-white/[0.02] rounded-xs">
                            <span className="font-mono text-[9px] text-slate-white/40 block">AUTHENTIC CHANNELS</span>
                            <span className="text-cyber-emerald font-mono font-bold text-base">INTEGRITY PASSED (100%)</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Bottom Note */}
              <div className="border-t border-slate-white/10 pt-4 mt-6">
                <span className="font-mono text-[9px] text-slate-white/30 block tracking-wider uppercase">
                  COGNITIVE DRILLDOWN INTERACTIVE MATRIX
                </span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </section>
  );
}
