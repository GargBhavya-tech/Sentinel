import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Terminal, Shield, ArrowUpRight } from 'lucide-react';

interface PlatformTransitionProps {
  onTransitionStart: () => void;
  onTransitionComplete: () => void;
}

export default function PlatformTransition({ onTransitionStart, onTransitionComplete }: PlatformTransitionProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [isClicked, setIsClicked] = useState(false);

  const handleLaunch = () => {
    if (isClicked) return;
    setIsClicked(true);
    onTransitionStart();

    // Trigger completion after the cinematic expand animation
    setTimeout(() => {
      onTransitionComplete();
    }, 1800);
  };

  return (
    <section className="relative py-36 bg-obsidian border-t border-slate-white/5 overflow-hidden flex flex-col items-center justify-center">
      {/* Console Grid Lines */}
      <div className="absolute inset-0 console-grid opacity-15 pointer-events-none" />

      {/* Contracting Wrapper when clicked */}
      <motion.div
        animate={isClicked ? { scale: 0.94, opacity: 0 } : { scale: 1, opacity: 1 }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-10 text-center max-w-xl mx-auto px-6 flex flex-col items-center"
      >
        <div className="flex items-center gap-2.5 mb-6">
          <Terminal className="w-4 h-4 text-slate-white/30" />
          <span className="font-mono text-[9px] tracking-widest text-slate-white/30 uppercase">
            OPERATIONS TERMINAL // INGRESS ALPHA
          </span>
        </div>

        <h2 className="font-display font-bold text-3xl md:text-5xl tracking-[0.2em] text-slate-white uppercase leading-none mb-6">
          LAUNCH SYSTEM
        </h2>

        <p className="font-sans text-xs md:text-sm text-slate-white/40 tracking-wider max-w-md leading-relaxed mb-12">
          Verify signatures, transactions, and live communications in real-time. Stand inside the forensic stream.
        </p>

        {/* Liquid-fill custom Button */}
        <button
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          onClick={handleLaunch}
          className="group relative w-full max-w-sm py-5 px-10 border border-slate-white/30 rounded-xs overflow-hidden cursor-pointer"
        >
          {/* Liquid Fill Element */}
          <div 
            className="absolute bottom-0 left-0 right-0 bg-electric-cyan z-0 origin-bottom transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)]"
            style={{
              height: isHovered ? '100%' : '0%',
              opacity: isHovered ? 1 : 0
            }}
          />

          {/* Label Content */}
          <span 
            className="relative z-10 font-mono text-xs tracking-[0.25em] uppercase font-bold flex items-center justify-center gap-2 transition-colors duration-500"
            style={{
              color: isHovered ? '#07080B' : '#F8FAFC'
            }}
          >
            LAUNCH INVESTIGATION
            <ArrowUpRight className="w-4 h-4" />
          </span>
        </button>

        <div className="mt-8 flex gap-8 items-center justify-center font-mono text-[9px] text-slate-white/20 tracking-wider">
          <span>PORT ACCESS // 3000</span>
          <span>SESSION_TOKEN // ACTIVE</span>
        </div>
      </motion.div>

      {/* Circular expanding mask fixed-overlay */}
      {isClicked && (
        <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
          {/* Collapsing core dot */}
          <motion.div
            initial={{ scale: 1, opacity: 1 }}
            animate={{ scale: [1, 0, 1], opacity: [1, 1, 1] }}
            transition={{
              times: [0, 0.4, 0.5],
              duration: 0.8,
              ease: "easeInOut"
            }}
            className="w-4 h-4 rounded-full bg-electric-cyan shadow-[0_0_20px_rgba(56,189,248,0.8)] absolute"
          >
            {/* The actual expanding matte cover */}
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 380 }}
              transition={{
                delay: 0.5,
                duration: 1.1,
                ease: [0.34, 1.56, 0.64, 1] // overshoot bounce for expanding feeling
              }}
              className="w-10 h-10 rounded-full bg-obsidian border border-electric-cyan/20 origin-center absolute -top-3 -left-3"
            />
          </motion.div>
        </div>
      )}
    </section>
  );
}
