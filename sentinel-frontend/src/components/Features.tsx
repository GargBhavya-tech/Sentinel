import React, { useState, useRef, MouseEvent } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'motion/react';
import { FileSearch, Users, Network, Scan, ShieldAlert } from 'lucide-react';
import { playTick } from '../utils/audio';

function TiltCard({ 
  children, 
  id, 
  idx, 
  onMouseEnter, 
  onMouseLeave, 
  className 
}: { 
  children: React.ReactNode; 
  id: number; 
  idx: number; 
  onMouseEnter: () => void; 
  onMouseLeave: () => void; 
  className: string; 
  key?: React.Key;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0.5);
  const y = useMotionValue(0.5);

  // Map 0-1 values to range [-12, 12] degrees of tilt
  const rotateX = useSpring(useTransform(y, [0, 1], [10, -10]), { stiffness: 100, damping: 15 });
  const rotateY = useSpring(useTransform(x, [0, 1], [-10, 10]), { stiffness: 100, damping: 15 });

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    
    x.set(mouseX / width);
    y.set(mouseY / height);
  };

  const handleMouseEnter = () => {
    playTick();
    onMouseEnter();
  };

  const handleMouseLeave = () => {
    x.set(0.5);
    y.set(0.5);
    onMouseLeave();
  };

  return (
    <motion.div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      initial={{ opacity: 0, y: 70, rotateX: 6, rotateY: idx === 0 ? -4 : idx === 2 ? 4 : 0 }}
      whileInView={{ opacity: 1, y: 0, rotateX: 0, rotateY: 0 }}
      viewport={{ once: false, margin: '-80px' }}
      whileHover={{ y: -8, scale: 1.01 }}
      transition={{ 
        type: 'spring',
        stiffness: 50,
        damping: 14,
        delay: idx * 0.12
      }}
      style={{
        rotateX,
        rotateY,
        transformStyle: 'preserve-3d',
        perspective: 1000
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export default function Features() {
  const [hoveredCard, setHoveredCard] = useState<number | null>(null);

  const features = [
    {
      id: 0,
      icon: FileSearch,
      title: "Evidence Scanner",
      tag: "DEEP DOCUMENT INGEST",
      description: "Cross-examines invoices, spreadsheets, emails, and phone transcripts in milliseconds to identify inconsistencies.",
      viz: "scanner"
    },
    {
      id: 1,
      icon: Users,
      title: "Multi-Agent Investigation",
      tag: "CONSENSUS SYNAPSE ENGINE",
      description: "Independent specialized AI agents challenge each other's theories and verify facts before proposing a unified final verdict.",
      viz: "agents"
    },
    {
      id: 2,
      icon: Network,
      title: "Propagation Graph",
      tag: "CONTAGION PATHWAY MAP",
      description: "Traces the flow of suspect capital and forged credentials across communication tunnels and external ledgers.",
      viz: "graph"
    }
  ];

  return (
    <section id="features" className="relative py-32 bg-obsidian border-t border-slate-white/5 overflow-hidden">
      {/* Decorative Grid Lines */}
      <div className="absolute inset-0 console-grid opacity-10 pointer-events-none" />

      <div className="max-w-7xl mx-auto px-6 relative z-10">
        {/* Section Header */}
        <div className="mb-20 max-w-2xl">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-1.5 h-1.5 rounded-full bg-electric-cyan animate-pulse" />
            <span className="font-mono text-[10px] tracking-widest text-electric-cyan uppercase">
              DEEP ANALYSIS PROTOCOLS
            </span>
          </div>
          <h2 className="font-display font-bold text-3xl md:text-5xl tracking-widest text-slate-white uppercase mb-6 leading-tight">
            INVESTIGATIVE SUITE
          </h2>
          <p className="font-sans text-xs md:text-sm text-slate-white/50 tracking-wider leading-relaxed">
            Fraud is no longer isolated to ledgers. Sentinel coordinates multiple layers of verification across disconnected media formats, finding structural lies that simple heuristics miss.
          </p>
        </div>

        {/* Interaction Guideline Badge */}
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="mb-8 flex items-center gap-2.5 bg-electric-cyan/5 border border-electric-cyan/10 rounded-xs px-3.5 py-2.5 max-w-max"
        >
          <Scan className="w-4 h-4 text-electric-cyan animate-pulse" />
          <span className="font-mono text-[9px] tracking-widest text-electric-cyan/80 uppercase">
            [ DIRECTIVE: HOVER AND DRAG CURSOR OVER ANY PROTOCOL TILE TO INITIATE 3D HOLOGRAPHIC DEGREE ROTATION ]
          </span>
        </motion.div>

        {/* Feature Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {features.map((feat, idx) => (
            <TiltCard
              key={feat.id}
              id={feat.id}
              idx={idx}
              onMouseEnter={() => setHoveredCard(feat.id)}
              onMouseLeave={() => setHoveredCard(null)}
              className="group relative flex flex-col justify-between h-[450px] p-8 glass-panel rounded-xs glass-panel-hover overflow-hidden cursor-pointer"
            >
              {/* Highlight Sweep Overlay */}
              <div className="absolute inset-0 bg-radial-gradient from-electric-cyan/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />

              <div>
                {/* Header tag */}
                <div className="flex justify-between items-start mb-6">
                  <span className="font-mono text-[9px] tracking-widest text-electric-cyan/60">
                    {feat.tag}
                  </span>
                  <span className="font-mono text-[10px] text-slate-white/20">
                    [ 0{idx + 1} ]
                  </span>
                </div>

                {/* Visualization Window */}
                <div className="w-full h-36 bg-obsidian/60 border border-slate-white/5 rounded-xs relative overflow-hidden flex items-center justify-center mb-8">
                  <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(56,189,248,0.02),transparent)]" />
                  
                  {/* Visualizations based on feature type */}
                  {feat.viz === "scanner" && (
                    <ScannerViz isActive={hoveredCard === feat.id} />
                  )}
                  {feat.viz === "agents" && (
                    <AgentsViz isActive={hoveredCard === feat.id} />
                  )}
                  {feat.viz === "graph" && (
                    <GraphViz isActive={hoveredCard === feat.id} />
                  )}
                </div>

                {/* Title and Description */}
                <h3 className="font-display font-medium text-lg tracking-wider text-slate-white uppercase mb-3">
                  {feat.title}
                </h3>
                <p className="font-sans text-xs text-slate-white/60 tracking-wide leading-relaxed">
                  {feat.description}
                </p>
              </div>

              {/* Action indicators */}
              <div className="flex items-center justify-between border-t border-slate-white/5 pt-4 mt-4">
                <span className="font-mono text-[9px] tracking-widest text-slate-white/30 group-hover:text-slate-white transition-colors duration-300">
                  SYSTEM STATUS // ARMED
                </span>
                <span className="font-mono text-[10px] text-electric-cyan opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                  ENGAGE // REVEAL
                </span>
              </div>
            </TiltCard>
          ))}
        </div>
      </div>
    </section>
  );
}

// 1. Evidence Scanner Micro-Viz
function ScannerViz({ isActive }: { isActive: boolean }) {
  return (
    <div className="w-full h-full relative flex flex-col justify-center px-6 gap-2.5">
      {/* Mock Doc Lines */}
      {[
        { text: "INVOICE #9201 // CORP_A", type: "normal" },
        { text: "TRANSFERRED VALUE: $2,490,000", type: "crimson" },
        { text: "AUTHORIZED: CLONED_SIGN_20a9", type: "crimson" },
        { text: "ROUTING GATEWAY: VERIFIED_A091", type: "emerald" }
      ].map((line, idx) => (
        <div key={idx} className="flex justify-between items-center font-mono text-[9px] leading-none">
          <span className={`tracking-widest ${line.type === 'crimson' ? 'text-evidence-crimson/85' : line.type === 'emerald' ? 'text-cyber-emerald/85' : 'text-slate-white/40'}`}>
            {line.text}
          </span>
          <span className="text-slate-white/20">
            {line.type === 'crimson' ? '[⚠️ DETECTED]' : line.type === 'emerald' ? '[✓ SAFE]' : '[OK]'}
          </span>
        </div>
      ))}

      {/* Sweeping scanline */}
      <motion.div
        animate={isActive ? { top: ["0%", "100%", "0%"] } : { top: ["0%", "0%"] }}
        transition={{ repeat: Infinity, duration: 3, ease: "linear" }}
        className="absolute left-0 right-0 h-[2px] bg-electric-cyan shadow-[0_0_10px_rgba(56,189,248,0.5)] pointer-events-none"
      />
    </div>
  );
}

// 2. Multi-Agent Synapse Micro-Viz
function AgentsViz({ isActive }: { isActive: boolean }) {
  return (
    <div className="w-full h-full relative flex items-center justify-center">
      {/* Visual node network */}
      <svg className="w-full h-full" viewBox="0 0 100 100">
        {/* Connector lines */}
        <motion.line
          x1="20" y1="50" x2="50" y2="50"
          stroke="rgba(248, 250, 252, 0.15)"
          strokeWidth="1"
          strokeDasharray="3 3"
        />
        <motion.line
          x1="80" y1="50" x2="50" y2="50"
          stroke="rgba(248, 250, 252, 0.15)"
          strokeWidth="1"
          strokeDasharray="3 3"
        />
        <motion.line
          x1="50" y1="20" x2="50" y2="50"
          stroke="rgba(248, 250, 252, 0.15)"
          strokeWidth="1"
          strokeDasharray="3 3"
        />

        {/* Outer nodes (Agents) */}
        <motion.circle
          cx="20" cy="50" r="4"
          fill="#38BDF8"
          animate={isActive ? { scale: [1, 1.3, 1], y: [50, 48, 52, 50] } : {}}
          transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
        />
        <motion.circle
          cx="80" cy="50" r="4"
          fill="#EF4444"
          animate={isActive ? { scale: [1, 1.2, 1], x: [80, 81, 79, 80] } : {}}
          transition={{ repeat: Infinity, duration: 1.8, ease: "easeInOut" }}
        />
        <motion.circle
          cx="50" cy="20" r="4"
          fill="#F59E0B"
          animate={isActive ? { scale: [1, 1.4, 1], y: [20, 22, 18, 20] } : {}}
          transition={{ repeat: Infinity, duration: 2.3, ease: "easeInOut" }}
        />

        {/* Central decision node */}
        <motion.circle
          cx="50" cy="50" r="8"
          fill="#07080B"
          stroke="#22C55E"
          strokeWidth="1.5"
          animate={isActive ? { strokeWidth: [1.5, 3, 1.5], fill: ["#07080B", "#22C55E", "#07080B"] } : {}}
          transition={{ repeat: Infinity, duration: 1.5 }}
        />

        {/* Flow particles */}
        {isActive && (
          <>
            <motion.circle
              cx="20" cy="50" r="1.5" fill="#38BDF8"
              animate={{ cx: [20, 50], cy: [50, 50] }}
              transition={{ repeat: Infinity, duration: 1.2, ease: "easeIn" }}
            />
            <motion.circle
              cx="80" cy="50" r="1.5" fill="#EF4444"
              animate={{ cx: [80, 50], cy: [50, 50] }}
              transition={{ repeat: Infinity, duration: 1.2, ease: "easeIn" }}
            />
            <motion.circle
              cx="50" cy="20" r="1.5" fill="#F59E0B"
              animate={{ cx: [50, 50], cy: [20, 50] }}
              transition={{ repeat: Infinity, duration: 1.2, ease: "easeIn" }}
            />
          </>
        )}
      </svg>
      <div className="absolute top-2 left-3 font-mono text-[8px] text-slate-white/30">
        [ COGNITIVE AGENTS ACTIVE: 3 ]
      </div>
    </div>
  );
}

// 3. Propagation Graph Micro-Viz
function GraphViz({ isActive }: { isActive: boolean }) {
  return (
    <div className="w-full h-full relative flex items-center justify-center">
      <svg className="w-full h-full" viewBox="0 0 100 100">
        {/* Source point */}
        <circle cx="20" cy="30" r="3" fill="#EF4444" />
        
        {/* Branch lines */}
        <motion.line
          x1="20" y1="30" x2="45" y2="40"
          stroke="#EF4444"
          strokeWidth="1.5"
          strokeDasharray={isActive ? "2 1" : "none"}
          animate={isActive ? { strokeDashoffset: [0, -10] } : {}}
          transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
        />
        <motion.line
          x1="20" y1="30" x2="40" y2="15"
          stroke="#EF4444"
          strokeWidth="1"
          strokeDasharray="none"
        />

        <motion.line
          x1="45" y1="40" x2="75" y2="35"
          stroke="#22C55E"
          strokeWidth="1.5"
        />
        <motion.line
          x1="45" y1="40" x2="70" y2="65"
          stroke="#EF4444"
          strokeWidth="1.5"
          strokeDasharray={isActive ? "2 1" : "none"}
          animate={isActive ? { strokeDashoffset: [0, -10] } : {}}
          transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
        />

        {/* Secondary Nodes */}
        <circle cx="45" cy="40" r="3.5" fill="#EF4444" className="animate-pulse" />
        <circle cx="40" cy="15" r="2" fill="#EF4444" />
        <circle cx="75" cy="35" r="3" fill="#22C55E" />
        <circle cx="70" cy="65" r="4.5" fill="#EF4444" />
        
        {/* Extra safe branch */}
        <motion.line
          x1="40" y1="15" x2="65" y2="10"
          stroke="#22C55E"
          strokeWidth="1"
        />
        <circle cx="65" cy="10" r="2" fill="#22C55E" />
      </svg>
      <div className="absolute bottom-2 right-3 font-mono text-[8px] text-evidence-crimson/80 flex items-center gap-1">
        <ShieldAlert className="w-2.5 h-2.5" />
        THREAT TRAJECTORY MAPPED
      </div>
    </div>
  );
}
