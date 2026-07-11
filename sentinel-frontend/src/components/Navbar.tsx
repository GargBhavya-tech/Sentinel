import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Shield, Cpu, Activity, ArrowUpRight, Volume2, VolumeX } from 'lucide-react';
import { enableAudio, playClick } from '../utils/audio';

interface NavbarProps {
  onNavClick: (sectionId: string) => void;
  onEnterConsole: () => void;
  isDashboardOpen: boolean;
}

export default function Navbar({ onNavClick, onEnterConsole, isDashboardOpen }: NavbarProps) {
  const [statusIndex, setStatusIndex] = useState(0);
  const [isScrolled, setIsScrolled] = useState(false);

  const statusLines = [
    "Workspace synced...",
    "Scanning documentation signatures...",
    "Voice prints loaded [SHA-256 verified]...",
    "System: Safe // Monitoring Workspace History"
  ];

  useEffect(() => {
    // Cycle through status messages, then hold on the final one.
    if (statusIndex < statusLines.length - 1) {
      const timer = setTimeout(() => {
        setStatusIndex(prev => prev + 1);
      }, 2500);
      return () => clearTimeout(timer);
    }
  }, [statusIndex]);

  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 20) {
        setIsScrolled(true);
      } else {
        setIsScrolled(false);
      }
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleLogoClick = () => {
    playClick();
    onNavClick('hero');
  };

  const handleLinkClick = (id: string) => {
    playClick();
    onNavClick(id);
  };

  const handleConsoleClick = () => {
    playClick();
    onEnterConsole();
  };

  return (
    <motion.header
      initial={{ y: -50, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      className={`fixed top-0 left-0 w-full z-40 transition-all duration-300 border-b ${
        isScrolled 
          ? 'bg-obsidian/85 backdrop-blur-md border-slate-white/10 py-3' 
          : 'bg-transparent border-slate-white/5 py-4'
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
        {/* Logo */}
        <button 
          onClick={handleLogoClick}
          className="flex items-center gap-2.5 text-left group cursor-pointer focus:outline-none"
        >
          <div className="relative flex items-center justify-center w-8 h-8 rounded-xs bg-slate-white/5 border border-slate-white/10 group-hover:border-electric-cyan/40 transition-colors duration-300">
            <Shield className="w-4 h-4 text-slate-white group-hover:text-electric-cyan transition-colors duration-300" />
            <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-cyber-emerald animate-ping" />
          </div>
          <div>
            <span className="font-display font-bold tracking-widest text-slate-white uppercase block leading-none">
              Sentinel
            </span>
            <span className="font-mono text-[9px] tracking-wider text-slate-white/40 block mt-1">
              AI SECURE // V2.8
            </span>
          </div>
        </button>

        {/* Navigation links - hidden if we are inside dashboard already to avoid confusion */}
        {!isDashboardOpen && (
          <nav className="hidden md:flex items-center gap-8">
            <button
              onClick={() => handleLinkClick('features')}
              className="font-mono text-xs tracking-widest text-slate-white/50 hover:text-slate-white transition-colors duration-200 cursor-pointer focus:outline-none animate-pulse-slow"
            >
              [ SYSTEM METRICS ]
            </button>
            <button
              onClick={() => handleLinkClick('demo')}
              className="font-mono text-xs tracking-widest text-slate-white/50 hover:text-slate-white transition-colors duration-200 cursor-pointer focus:outline-none"
            >
              [ ACTIVE RULES ]
            </button>
            <button
              onClick={handleConsoleClick}
              className="font-mono text-xs tracking-widest text-electric-cyan/70 hover:text-electric-cyan transition-colors duration-200 flex items-center gap-1 cursor-pointer focus:outline-none"
            >
              [ CONSOLE INGRESS ]
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </nav>
        )}

        <div className="flex items-center gap-4">
          {/* Audio Synthesizer Status Badge */}
          <div
            className="flex items-center gap-1.5 font-mono text-[9px] tracking-widest px-2.5 py-1.5 border text-electric-cyan border-electric-cyan/20 bg-electric-cyan/5 rounded-xs select-none"
            title="Futuristic synthesized acoustic feedback signals are actively running on this terminal."
          >
            <Volume2 className="w-3.5 h-3.5 text-electric-cyan animate-pulse" />
            <span className="hidden sm:inline">SYNTH AUDIO: ENGAGED</span>
          </div>

          {/* Ambient Status Label */}
          <div className="hidden sm:flex items-center gap-3 bg-slate-white/[0.02] border border-slate-white/5 rounded-xs px-3 py-1.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyber-emerald opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-cyber-emerald"></span>
            </span>
            <div className="font-mono text-[10px] tracking-wider text-slate-white/70 h-4 flex items-center overflow-hidden min-w-[200px] md:min-w-[260px]">
              <AnimatePresence mode="wait">
                <motion.span
                  key={statusIndex}
                  initial={{ y: 10, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: -10, opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="whitespace-nowrap"
                >
                  {statusLines[statusIndex]}
                </motion.span>
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </motion.header>
  );
}
