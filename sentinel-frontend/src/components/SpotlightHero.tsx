import { useState, useEffect, useRef, MouseEvent } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'motion/react';
import { 
  AlertCircle, FileText, Phone, ArrowRight, ShieldCheck, Play, 
  Fingerprint, Lock, Globe, Terminal, Activity, Scan 
} from 'lucide-react';
import { playTick, playClick } from '../utils/audio';

interface SpotlightHeroProps {
  onDeployClick: () => void;
  onExploreClick: () => void;
}

interface Fragment {
  id: string;
  label: string;
  x: number; // percentage width
  y: number; // percentage height
  color: string;
  icon: any;
  detail?: string;
}

// Subscription helper component to render fast-updating coordinates without re-rendering the heavy Hero parent
function ScopeCoordinates({ spotlightX, spotlightY }: { spotlightX: any; spotlightY: any }) {
  const [coords, setCoords] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const unsubX = spotlightX.on("change", (latest: number) => {
      setCoords((prev) => ({ ...prev, x: Math.round(latest) }));
    });
    const unsubY = spotlightY.on("change", (latest: number) => {
      setCoords((prev) => ({ ...prev, y: Math.round(latest) }));
    });
    return () => {
      unsubX();
      unsubY();
    };
  }, [spotlightX, spotlightY]);

  return (
    <div className="absolute top-16 left-8 bg-obsidian/90 border border-electric-cyan/30 backdrop-blur-sm px-2.5 py-1.5 rounded-xs font-mono text-[8px] text-electric-cyan tracking-wider flex flex-col gap-0.5 whitespace-nowrap shadow-[0_0_15px_rgba(56,189,248,0.2)]">
      <span className="font-bold">LENS_INGRESS: ACTIVE</span>
      <span>X: {coords.x}px</span>
      <span>Y: {coords.y}px</span>
      <span>SPECTRUM: 16000Hz</span>
    </div>
  );
}

export default function SpotlightHero({ onDeployClick, onExploreClick }: SpotlightHeroProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Spotlight mouse coordinates
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Easing springs for smooth fluid movement
  const spotlightX = useSpring(mouseX, { stiffness: 60, damping: 25 });
  const spotlightY = useSpring(mouseY, { stiffness: 60, damping: 25 });

  const spotlightXStr = useTransform(spotlightX, (v) => `${v}px`);
  const spotlightYStr = useTransform(spotlightY, (v) => `${v}px`);

  const fragments: Fragment[] = [
    { id: '1', label: 'Account Hijacked [FAIL_SEC]', x: 18, y: 22, color: '#EF4444', icon: AlertCircle, detail: 'IP_GEO: 103.22.201.2 (VPN_SG)' },
    { id: '2', label: 'Cloned Voice Signature', x: 82, y: 18, color: '#F59E0B', icon: Phone, detail: 'Neural Formant Jitter: 8.9%' },
    { id: '3', label: 'Invoice Mismatch [RT_912]', x: 12, y: 62, color: '#EF4444', icon: FileText, detail: 'Offshore Clearing Belize' },
    { id: '4', label: 'Payroll Anomaly detected', x: 86, y: 68, color: '#F59E0B', icon: AlertCircle, detail: 'Auto-Trigger: Fact Mismatch' },
    { id: '5', label: 'Unverified Recipient', x: 26, y: 82, color: '#38BDF8', icon: ShieldCheck, detail: 'Cryptographic SPF/DKIM Passed' },
    { id: '6', label: 'Suspicious Transfer', x: 74, y: 48, color: '#EF4444', icon: AlertCircle, detail: 'RT_912000031 Contradictory Route' },
    { id: '7', label: 'DKIM Signature verified', x: 45, y: 15, color: '#10B981', icon: ShieldCheck, detail: 'Aether Corporate Certificate' },
    { id: '8', label: 'Biometric Hash matched', x: 62, y: 80, color: '#38BDF8', icon: ShieldCheck, detail: 'CEO Biometric Vault OK' },
    { id: '9', label: 'Dual Geo-Presence check', x: 50, y: 60, color: '#EF4444', icon: AlertCircle, detail: 'SF Home vs SG Proxy Gateway' },
  ];

  useEffect(() => {
    setMounted(true);
    // Initialize spotlight to center of container
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      mouseX.set(rect.width / 2);
      mouseY.set(rect.height / 2);
    }

    // Auto breathing loop when mouse is not active - now wider and more cinematic
    let angle = 0;
    const interval = setInterval(() => {
      if (!isHovered && containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const cx = rect.width / 2;
        const cy = rect.height / 2;
        const r = Math.min(rect.width, rect.height) * 0.22;
        angle += 0.012;
        mouseX.set(cx + Math.cos(angle) * r);
        mouseY.set(cy + Math.sin(angle) * r * 0.7); // slightly oval path for visual dynamism
      }
    }, 16);

    return () => clearInterval(interval);
  }, [isHovered, mouseX, mouseY]);

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      mouseX.set(x);
      mouseY.set(y);
      setIsHovered(true);
    }
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
  };

  // Pre-calculated static connections for the faint wireframe graph
  const nodes = [
    { id: 'n1', x: 30, y: 25, label: 'AUTH_GATEWAY' },
    { id: 'n2', x: 70, y: 20, label: 'VOIP_SIP_TRUNK' },
    { id: 'n3', x: 50, y: 45, label: 'SENTINEL_CORE_COGNITIVE' },
    { id: 'n4', x: 22, y: 58, label: 'SECURE_INBOX_SSL' },
    { id: 'n5', x: 78, y: 62, label: 'BELIZE_ROUTING_TARGET' },
    { id: 'n6', x: 48, y: 72, label: 'BIOMETRIC_VAULT' },
    { id: 'n7', x: 12, y: 38, label: 'DKIM_SERVER' },
    { id: 'n8', x: 88, y: 42, label: 'SPF_VERIFIER_CO' },
  ];

  const connections = [
    { from: 'n1', to: 'n3' },
    { from: 'n2', to: 'n3' },
    { from: 'n4', to: 'n3' },
    { from: 'n5', to: 'n3' },
    { from: 'n4', to: 'n1' },
    { from: 'n5', to: 'n2' },
    { from: 'n4', to: 'n6' },
    { from: 'n5', to: 'n6' },
    { from: 'n3', to: 'n6' },
    { from: 'n7', to: 'n1' },
    { from: 'n7', to: 'n4' },
    { from: 'n8', to: 'n2' },
    { from: 'n8', to: 'n5' },
  ];

  const handleCtaClick = () => {
    playClick();
    onDeployClick();
  };

  const handleExploreClick = () => {
    playClick();
    onExploreClick();
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className="relative w-full min-h-screen bg-obsidian flex flex-col justify-center items-center overflow-hidden px-6 pt-24 cursor-default select-none animate-fade-in"
      id="hero"
    >
      {/* 1. Ambient Spotlighting layer */}
      {mounted && (
        <motion.div
          className="absolute inset-0 pointer-events-none transition-opacity duration-1000 z-10"
          style={{
            background: `radial-gradient(circle 280px at var(--spotlight-x, 50%) var(--spotlight-y, 50%), transparent 10%, rgba(7, 8, 11, 0.96) 95%)`,
            // Injecting motion springs as custom properties for CSS variables to ensure perfect 60fps rendering
            '--spotlight-x': spotlightXStr as any,
            '--spotlight-y': spotlightYStr as any,
          }}
        />
      )}

      {/* Grid overlay under the spotlight */}
      <div className="absolute inset-0 console-grid opacity-15 pointer-events-none" />

      {/* 2. Interactive Scope HUD following the cursor spotlight */}
      {mounted && (
        <motion.div
          className="absolute pointer-events-none z-20 hidden lg:flex flex-col items-center justify-center"
          style={{
            x: spotlightX,
            y: spotlightY,
            translateX: '-50%',
            translateY: '-50%',
          }}
        >
          {/* Rotating Outer Scope Ring */}
          <motion.div 
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 16, ease: "linear" }}
            className="w-48 h-48 border border-dashed border-electric-cyan/20 rounded-full flex items-center justify-center relative"
          >
            {/* Compass ticks */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1px] h-3 bg-electric-cyan/40" />
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[1px] h-3 bg-electric-cyan/40" />
            <div className="absolute left-0 top-1/2 -translate-y-1/2 w-3 h-[1px] bg-electric-cyan/40" />
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-[1px] bg-electric-cyan/40" />
          </motion.div>
          
          {/* Inner target focus lines */}
          <div className="absolute w-12 h-12 border border-electric-cyan/30 rounded-full flex items-center justify-center">
            <div className="w-2 h-2 bg-electric-cyan rounded-full animate-ping" />
          </div>

          {/* Real-time coordinates subscript component */}
          <ScopeCoordinates spotlightX={spotlightX} spotlightY={spotlightY} />
        </motion.div>
      )}

      {/* 3. Wireframe network graph sitting behind the text, only revealed clearly by spotlight */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <svg className="w-full h-full opacity-40">
          {connections.map((conn, idx) => {
            const fromNode = nodes.find(n => n.id === conn.from)!;
            const toNode = nodes.find(n => n.id === conn.to)!;
            return (
              <line
                key={idx}
                x1={`${fromNode.x}%`}
                y1={`${fromNode.y}%`}
                x2={`${toNode.x}%`}
                y2={`${toNode.y}%`}
                stroke="rgba(56, 189, 248, 0.12)"
                strokeWidth="1.5"
                className="transition-all duration-300"
              />
            );
          })}
          {nodes.map(node => (
            <g key={node.id} className="opacity-50 hover:opacity-100 transition-opacity">
              <circle
                cx={`${node.x}%`}
                cy={`${node.y}%`}
                r="6"
                fill="#38BDF8"
                className="animate-pulse"
              />
              <circle
                cx={`${node.x}%`}
                cy={`${node.y}%`}
                r="14"
                stroke="#38BDF8"
                strokeWidth="1"
                fill="none"
                className="animate-ping opacity-25"
                style={{ animationDuration: '4s' }}
              />
              <text
                x={`${node.x}%`}
                y={`${node.y + 4.5}%`}
                fill="#38BDF8"
                fontSize="8"
                fontFamily="JetBrains Mono"
                textAnchor="middle"
                className="opacity-70 font-semibold tracking-wider"
              >
                {node.label}
              </text>
            </g>
          ))}
        </svg>
      </div>

      {/* 4. Floating Investigation Fragments with hover sounds & subtext */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        {fragments.map((frag) => {
          const Icon = frag.icon;
          return (
            <motion.div
              key={frag.id}
              className="absolute transform -translate-x-1/2 -translate-y-1/2 flex flex-col gap-1 border border-slate-white/5 bg-obsidian/40 hover:bg-obsidian/85 hover:border-electric-cyan/30 hover:shadow-[0_0_15px_rgba(56,189,248,0.15)] backdrop-blur-md px-3.5 py-2.5 rounded-xs pointer-events-auto transition-all duration-300 cursor-pointer"
              style={{
                left: `${frag.x}%`,
                top: `${frag.y}%`,
              }}
              whileHover={{ scale: 1.05, y: -4 }}
              onMouseEnter={() => playTick()}
            >
              <div className="flex items-center gap-2">
                <div 
                  className="w-2 h-2 rounded-full animate-pulse shrink-0"
                  style={{ backgroundColor: frag.color }}
                />
                <Icon className="w-3.5 h-3.5 text-slate-white/60" />
                <span className="font-display font-semibold text-[10px] tracking-widest uppercase text-slate-white/90">
                  {frag.label}
                </span>
              </div>
              {frag.detail && (
                <span className="font-mono text-[8px] text-slate-white/40 tracking-wider pl-4">
                  {frag.detail}
                </span>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* 5. Center Hero Text */}
      <div className="relative z-20 text-center max-w-4xl mx-auto flex flex-col items-center">
        {/* Technical tag */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.1 }}
          className="inline-flex items-center gap-2 border border-electric-cyan/20 bg-electric-cyan/5 rounded-full px-4 py-1.5 mb-8"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-electric-cyan animate-pulse" />
          <span className="font-mono text-[10px] tracking-widest text-electric-cyan uppercase">
            COGNITIVE FRAUD SHIELD ACTIVE
          </span>
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
          className="font-display font-black text-6xl md:text-8xl tracking-[0.25em] text-slate-white uppercase select-none leading-none mb-6 scanline-text"
        >
          SENTINEL
        </motion.h1>

        {/* Subheadline */}
        <motion.p
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="font-sans text-sm md:text-lg text-slate-white/60 tracking-wide font-light max-w-2xl leading-relaxed mb-12 px-4"
        >
          Multi-agent fraud investigation for the modern enterprise. Cross-examining every document, voice recording, and transaction before fraud becomes loss.
          <br />
          <span className="text-electric-cyan/80 font-mono text-xs tracking-widest block mt-4 animate-pulse uppercase">
            [ SWEEP CURSOR TO ACTIVATE CYBER FORENSICS FLASHLIGHT ]
          </span>
        </motion.p>

        {/* Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-col sm:flex-row items-center gap-5 w-full justify-center max-w-md px-4"
        >
          {/* Primary CTA */}
          <button
            onClick={handleCtaClick}
            className="group relative w-full sm:w-auto min-w-[210px] bg-slate-white text-obsidian font-mono text-xs tracking-widest font-bold uppercase py-4 px-6 rounded-xs transition-all duration-500 hover:shadow-[0_0_30px_rgba(248,250,252,0.3)] hover:scale-[1.02] active:scale-[0.98] overflow-hidden cursor-pointer"
          >
            {/* Liquid Sweep */}
            <span className="absolute inset-0 bg-gradient-to-r from-transparent via-electric-cyan/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000" />
            <span className="relative flex items-center justify-center gap-2">
              DEPLOY INVESTIGATOR
              <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
            </span>
          </button>

          {/* Secondary CTA */}
          <button
            onClick={handleExploreClick}
            className="group relative w-full sm:w-auto min-w-[210px] bg-transparent text-slate-white border border-slate-white/10 font-mono text-xs tracking-widest font-medium uppercase py-4 px-6 rounded-xs transition-all duration-500 hover:border-slate-white/30 hover:bg-slate-white/5 active:scale-[0.98] overflow-hidden cursor-pointer"
          >
            <span className="absolute inset-0 bg-gradient-to-r from-transparent via-slate-white/10 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000" />
            <span className="relative flex items-center justify-center gap-2">
              EXPLORE DEMO
              <Play className="w-3.5 h-3.5 text-slate-white/60 group-hover:text-slate-white transition-colors duration-300" />
            </span>
          </button>
        </motion.div>
      </div>

      {/* Decorative side margins indicators */}
      <div className="absolute left-6 bottom-8 hidden md:flex flex-col gap-2 pointer-events-none">
        <span className="font-mono text-[9px] text-slate-white/20 tracking-widest uppercase">
          SECURE SECTOR // 01
        </span>
        <span className="font-mono text-[9px] text-slate-white/10 tracking-widest">
          LAT: 37.7749 // LON: -122.4194
        </span>
      </div>

      <div className="absolute right-6 bottom-8 hidden md:flex flex-col gap-1 items-end pointer-events-none">
        <div className="flex gap-1">
          <div className="w-1.5 h-1.5 bg-electric-cyan/40" />
          <div className="w-1.5 h-1.5 bg-electric-cyan/40 animate-pulse" />
          <div className="w-1.5 h-1.5 bg-electric-cyan" />
        </div>
        <span className="font-mono text-[9px] text-slate-white/20 tracking-widest uppercase">
          GRID SYNCHRONIZATION: COMPLETE
        </span>
      </div>
    </div>
  );
}
