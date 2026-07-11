import { useState, useEffect } from 'react';
import { motion, AnimatePresence, useScroll, useTransform } from 'motion/react';
import { RefreshCw } from 'lucide-react';
import Navbar from './components/Navbar';
import SpotlightHero from './components/SpotlightHero';
import Features from './components/Features';
import LiveInvestigation from './components/LiveInvestigation';
import HowSentinelThinks from './components/HowSentinelThinks';
import EasterEgg from './components/EasterEgg';
import PlatformTransition from './components/PlatformTransition';
import DashboardConsole from './components/DashboardConsole';
import { useInvestigation } from './hooks/useInvestigation';
import CustomCursor from './components/CustomCursor';

type ViewState = 'landing' | 'transitioning' | 'dashboard';

export default function App() {
  const [viewState, setViewState] = useState<ViewState>('landing');
  // Single shared investigation instance — DashboardConsole requires it as a prop.
  const investigation = useInvestigation();
  const { scrollY } = useScroll();

  // Create subtle parallax translation and fading for background layers
  const backgroundY = useTransform(scrollY, [0, 4000], [0, 400]);
  const glowOpacity = useTransform(scrollY, [0, 1500], [0.4, 0.12]);

  // Handle navbar link click smooth scrolling
  const handleNavClick = (sectionId: string) => {
    if (viewState !== 'landing') {
      setViewState('landing');
      // Give state a brief moment to render before scrolling
      setTimeout(() => {
        const element = document.getElementById(sectionId);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth' });
        }
      }, 100);
    } else {
      const element = document.getElementById(sectionId);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  const handleEnterConsole = () => {
    setViewState('transitioning');
  };

  // Complete the "syncing console" flash from ANY entry point. PlatformTransition
  // (which normally fires onTransitionComplete) only exists inside the landing
  // view and unmounts the instant we leave it, so without this effect the
  // spinner would hang forever. Watching viewState also self-heals a state that
  // was left in 'transitioning' (e.g. across a hot reload).
  useEffect(() => {
    if (viewState !== 'transitioning') return;
    const t = setTimeout(() => {
      setViewState('dashboard');
      window.scrollTo(0, 0);
    }, 1300);
    return () => clearTimeout(t);
  }, [viewState]);

  const handleTransitionComplete = () => {
    setViewState('dashboard');
    window.scrollTo(0, 0);
  };

  return (
    <div className="bg-obsidian min-h-screen relative font-sans text-slate-white overflow-x-hidden selection:bg-electric-cyan selection:text-obsidian">
      
      {/* Global premium custom cursor */}
      <CustomCursor />
      
      {/* Scroll-Linked Parallax Technical Grid & Glowing Ambient Depth */}
      <motion.div 
        className="fixed inset-0 pointer-events-none z-0"
        style={{ y: backgroundY }}
      >
        <div className="absolute inset-0 console-grid opacity-[0.06]" />
        <motion.div 
          className="absolute inset-0"
          style={{ 
            background: 'radial-gradient(circle at 50% 35%, rgba(56, 189, 248, 0.08) 0%, transparent 60%)',
            opacity: glowOpacity
          }}
        />
        <div className="absolute top-[900px] left-[15%] w-[450px] h-[450px] rounded-full bg-electric-cyan/2 filter blur-[140px]" />
        <div className="absolute top-[2000px] right-[10%] w-[550px] h-[550px] rounded-full bg-evidence-crimson/1.5 filter blur-[160px]" />
      </motion.div>

      {/* Dynamic scanline aesthetic layer to reinforce the forensic theme */}
      <div className="fixed inset-0 bg-radial-gradient(circle_at_center,rgba(56,189,248,0.015),transparent) pointer-events-none z-30" />

      <AnimatePresence mode="wait">
        {viewState === 'landing' && (
          <motion.div
            key="landing-view"
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
          >
            {/* Header */}
            <Navbar 
              onNavClick={handleNavClick} 
              onEnterConsole={handleEnterConsole}
              isDashboardOpen={false}
            />

            {/* Hero Spotlight Section */}
            <SpotlightHero 
              onDeployClick={handleEnterConsole}
              onExploreClick={() => handleNavClick('demo')}
            />

            {/* Features (Scanned illuminated cards) */}
            <Features />

            {/* Easter Egg Section - Illustrated proudly ginger cat sitting on phone */}
            <section className="relative py-24 bg-obsidian border-t border-slate-white/5 overflow-hidden flex flex-col items-center">
              <div className="absolute inset-0 console-grid opacity-5 pointer-events-none" />
              <div className="max-w-7xl mx-auto px-6 relative z-10 w-full">
                <div className="text-center mb-12">
                  <span className="font-mono text-[9px] text-slate-white/25 uppercase tracking-widest">[ SECURITY ASSURANCE PROTOCOLS ]</span>
                </div>
                <EasterEgg />
              </div>
            </section>

            {/* Live Investigation Demo Section */}
            <LiveInvestigation />

            {/* Cognitive Pipeline Workflow */}
            <HowSentinelThinks />

            {/* Physical Operations Console Transition Launcher */}
            <PlatformTransition 
              onTransitionStart={() => setViewState('transitioning')}
              onTransitionComplete={handleTransitionComplete}
            />

            {/* Simple Minimalist Footer */}
            <footer className="border-t border-slate-white/5 py-12 bg-obsidian relative z-10">
              <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6">
                <div>
                  <span className="font-display font-black text-xs tracking-widest text-slate-white uppercase">SENTINEL</span>
                  <p className="font-mono text-[9px] text-slate-white/30 mt-1 uppercase">ALL SYSTEM ASSETS SECURED // OPERATIONAL VERSION 2.8</p>
                </div>
                <div className="flex gap-8 font-mono text-[9px] text-slate-white/30 tracking-wider">
                  <span>SYSTEM STATUS: SAFE</span>
                  <span>© 2026 SENTINEL TECHNOLOGIES INC.</span>
                </div>
              </div>
            </footer>
          </motion.div>
        )}

        {viewState === 'transitioning' && (
          <motion.div
            key="transition-flash"
            initial={{ opacity: 1 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
            className="fixed inset-0 bg-obsidian z-50 flex flex-col items-center justify-center cursor-wait"
          >
            {/* Cinematic intermediate progress scanner to bridge transition */}
            <div className="flex flex-col items-center gap-4">
              <RefreshCw className="w-8 h-8 text-electric-cyan animate-spin" />
              <span className="font-mono text-[10px] tracking-widest text-electric-cyan uppercase animate-pulse">
                SYNCING SECURE CONSOLE ENVIRONMENTS...
              </span>
            </div>
          </motion.div>
        )}

        {viewState === 'dashboard' && (
          <motion.div
            key="dashboard-view"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.8 }}
            className="h-screen w-screen"
          >
            <DashboardConsole onExit={() => setViewState('landing')} investigation={investigation} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
