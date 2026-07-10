import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { 
  UploadCloud, BrainCircuit, GitCompare, LayoutList, CheckCircle 
} from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

interface Stage {
  title: string;
  sub: string;
  desc: string;
  icon: any;
  meta: string;
  rate: string;
  state: string;
}

function holdAtMiddle(progress: number, hold = 0.25): number {
  const half = hold * 0.5;
  if (progress < 0.5 - half) {
    return gsap.utils.mapRange(0, 0.5 - half, 0, 0.5, progress);
  }
  if (progress > 0.5 + half) {
    return gsap.utils.mapRange(0.5 + half, 1, 0.5, 1, progress);
  }
  return 0.5;
}

export default function HowSentinelThinks() {
  const stages: Stage[] = [
    {
      title: "Upload Evidence",
      sub: "INGEST",
      desc: "Raw transactions, communication transcripts, and internal files are indexed concurrently.",
      icon: UploadCloud,
      meta: "#F-001 INDEXED",
      rate: "4.8 GB/S CONCURRENT",
      state: "STABLE"
    },
    {
      title: "Specialist Agents",
      sub: "COGNITION",
      desc: "Niche AI models isolate specific elements—voice signatures, metadata, and routing paths.",
      icon: BrainCircuit,
      meta: "32 AI AGENTS",
      rate: "CONCURRENT COGNITION",
      state: "ACTIVE"
    },
    {
      title: "Cross-Verification",
      sub: "DEDUCTIVE HUB",
      desc: "Discrepancies across modalities are pitted against each other to uncover lies.",
      icon: GitCompare,
      meta: "1,024 ITERATIONS",
      rate: "DEDUCTION PATH ACTIVE",
      state: "COMPARING"
    },
    {
      title: "Verified Timeline",
      sub: "FORENSICS",
      desc: "A singular chronological fact stream with structured confidence score is produced.",
      icon: LayoutList,
      meta: "99.98% CONFIDENCE",
      rate: "CHRONOLOGY ENGINE",
      state: "VERIFIED"
    },
    {
      title: "Actionable Decision",
      sub: "PREVENTION",
      desc: "Transactions are placed on safety holds with secure alerts pushed to risk desks.",
      icon: CheckCircle,
      meta: "SAFETY PROTOCOL",
      rate: "<12MS RESPONSE HOLD",
      state: "SECURE"
    }
  ];

  const cardsRef = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const ctx = gsap.context(() => {
      cardsRef.current.forEach((card, idx) => {
        if (!card) return;

        // Give each index a beautiful, dynamic, natural 3D tilt as standard setting
        // idx % 2 === 0 tilts slightly one way, idx % 2 !== 0 tilts the other way for beautiful visual variety
        const rotationX = 22; 
        const rotationY = idx % 2 === 0 ? 15 : -15;
        const rotationZ = idx % 2 === 0 ? 5 : -5;

        ScrollTrigger.create({
          trigger: card,
          start: "top bottom-=8%",
          end: "bottom top+=8%",
          scrub: true, // Directly links the animation with scrollbar for instant real-time reversal
          invalidateOnRefresh: true,
          onUpdate: (self) => {
            const t = holdAtMiddle(self.progress, 0.25);

            // Interpolate starting rotated position to opposite rotated position
            const rX = gsap.utils.interpolate(-rotationX, rotationX, t);
            const rY = gsap.utils.interpolate(-rotationY, rotationY, t);
            const rZ = gsap.utils.interpolate(-rotationZ, rotationZ, t);

            // 3D Depth (Z-axis offset): closest (0px) at the middle, far away (-250px) at the edges
            const z = (1 - Math.sin(t * Math.PI)) * -250;
            
            // factor is 1 at edges (unfocused), and 0 at the center (fully focused)
            const factor = 1 - Math.sin(t * Math.PI);

            // Swoop in from left/right angle depending on index for high-end choreography
            const xOffset = (idx % 2 === 0 ? 140 : -120) * factor;

            // Smooth continuous vertical slide from bottom to top
            const yOffset = 90 * (t < 0.5 ? factor : -factor);
            
            // Premium scale effect: 100% in middle, 88% at the top/bottom edges
            const scale = 0.88 + Math.sin(t * Math.PI) * 0.12;

            // Blur transition: perfectly crisp (0px) in the middle, blurred (8px) at edges
            const blur = (1 - Math.sin(t * Math.PI)) * 8;

            // Dim / brightness: bright & luminous (1.0) in the middle, dark & mysterious (0.4) at edges
            const brightness = 0.4 + Math.sin(t * Math.PI) * 0.6;

            gsap.set(card, {
              scale,
              rotationX: rX,
              rotationY: rY,
              rotationZ: rZ,
              x: xOffset,
              y: yOffset,
              z,
              filter: `blur(${blur}px) brightness(${brightness})`
            });
          }
        });
      });
    });

    return () => ctx.revert();
  }, []);

  return (
    <section id="pipeline" className="relative py-32 bg-obsidian border-t border-slate-white/5 overflow-hidden">
      {/* Background grids */}
      <div className="absolute inset-0 console-grid opacity-5 pointer-events-none" />
      <div className="absolute top-1/4 left-1/4 w-[400px] h-[400px] rounded-full bg-electric-cyan/2 filter blur-[150px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] rounded-full bg-cyber-emerald/1 filter blur-[150px] pointer-events-none" />

      <div className="max-w-7xl mx-auto px-6 relative z-10">
        
        {/* Section Header */}
        <div className="mb-28 text-center md:text-left">
          <div className="flex items-center justify-center md:justify-start gap-2 mb-3">
            <span className="w-1.5 h-1.5 rounded-full bg-electric-cyan animate-pulse" />
            <span className="font-mono text-[10px] tracking-widest text-electric-cyan uppercase">
              COGNITIVE WORKFLOW // PERSPECTIVE MATRIX
            </span>
          </div>
          <h2 className="font-display font-bold text-3xl md:text-5xl tracking-widest text-slate-white uppercase leading-none mb-6">
            HOW SENTINEL THINKS
          </h2>
          <p className="font-sans text-xs md:text-sm text-slate-white/50 tracking-wider max-w-xl leading-relaxed">
            A secure horizontal analysis process. We do not guess. We trace facts across isolated data channels to establish verifiable mathematical alignment.
          </p>
        </div>

        {/* 3D Scroll Container */}
        <div 
          className="relative flex flex-col gap-24 md:gap-32 pb-16"
          style={{ perspective: '1200px', transformStyle: 'preserve-3d' }}
        >
          {/* Central vertical track */}
          <div className="absolute top-8 bottom-8 left-1/2 -translate-x-1/2 w-[1px] bg-slate-white/5 hidden md:block z-0">
            <div className="absolute inset-0 bg-gradient-to-b from-electric-cyan via-amber-warning to-cyber-emerald opacity-20" />
          </div>

          {stages.map((stage, idx) => {
            const Icon = stage.icon;
            const isEven = idx % 2 === 0;

            return (
              <div 
                key={idx}
                className={`flex flex-col md:flex-row items-center justify-between gap-8 md:gap-12 relative z-10 w-full ${
                  isEven ? 'md:flex-row-reverse' : ''
                }`}
                style={{ transformStyle: 'preserve-3d' }}
              >
                {/* 1. The rotating 3D Stage Card */}
                <div 
                  className="w-full md:w-1/2 flex justify-center"
                  style={{ transformStyle: 'preserve-3d' }}
                >
                  <div
                    ref={(el) => { cardsRef.current[idx] = el; }}
                    className="w-full max-w-md p-8 rounded-2xl glass-panel glass-panel-hover group relative"
                    style={{ transformStyle: 'preserve-3d' }}
                  >
                    {/* Corner accent decorations */}
                    <div className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2 border-slate-white/10 group-hover:border-electric-cyan/40 transition-colors duration-500" />
                    <div className="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2 border-slate-white/10 group-hover:border-electric-cyan/40 transition-colors duration-500" />
                    <div className="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2 border-slate-white/10 group-hover:border-electric-cyan/40 transition-colors duration-500" />
                    <div className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 border-slate-white/10 group-hover:border-electric-cyan/40 transition-colors duration-500" />

                    {/* Node Header Info */}
                    <div className="flex items-center justify-between border-b border-slate-white/5 pb-4 mb-6 font-mono text-[9px] text-slate-white/35">
                      <span className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-electric-cyan/40 animate-pulse" />
                        NODE_0{idx + 1} // {stage.state}
                      </span>
                      <span>{stage.meta}</span>
                    </div>

                    <div className="flex items-start gap-5">
                      {/* Icon Block */}
                      <div className="flex-shrink-0 relative flex items-center justify-center w-16 h-16 rounded-xl bg-obsidian border border-slate-white/10 group-hover:border-electric-cyan/40 group-hover:shadow-[0_0_20px_rgba(56,189,248,0.15)] transition-all duration-500">
                        <Icon className="w-6 h-6 text-slate-white/60 group-hover:text-electric-cyan transition-colors duration-500" />
                      </div>

                      {/* Content Block */}
                      <div>
                        <span className="font-mono text-[9px] tracking-widest text-electric-cyan block mb-1 uppercase">
                          {stage.sub}
                        </span>
                        <h3 className="font-display font-bold text-base tracking-widest text-slate-white uppercase mb-3">
                          {stage.title}
                        </h3>
                        <p className="font-sans text-[11px] text-slate-white/45 tracking-wide leading-relaxed">
                          {stage.desc}
                        </p>
                      </div>
                    </div>

                    {/* Card Footer Readouts */}
                    <div className="mt-6 pt-4 border-t border-slate-white/5 flex items-center justify-between font-mono text-[8px] text-slate-white/20 tracking-wider">
                      <span>RATE: {stage.rate}</span>
                      <span className="text-electric-cyan/40">SECURE_NODE</span>
                    </div>
                  </div>
                </div>

                {/* 2. Timeline Connection Node (Desktop Only) */}
                <div className="absolute left-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-obsidian border border-slate-white/10 hidden md:flex items-center justify-center z-20">
                  <div className="w-2.5 h-2.5 rounded-full bg-electric-cyan animate-pulse shadow-[0_0_8px_#38bdf8]" />
                </div>

                {/* 3. Staggered technical side information block (Desktop Only) */}
                <div className="w-full md:w-1/2 hidden md:block px-12">
                  <div className={`flex flex-col ${isEven ? 'items-start text-left' : 'items-end text-right'}`}>
                    <span className="font-mono text-[9px] text-slate-white/15 uppercase tracking-widest block mb-1">
                      Fact Channel Validation Track
                    </span>
                    <span className="font-mono text-[10px] text-electric-cyan/40 uppercase tracking-widest font-bold mb-2">
                      [ SECURE DATA PATH 0{idx + 1} ]
                    </span>
                    <p className="font-sans text-[10px] text-slate-white/25 max-w-xs leading-relaxed">
                      Continuous active telemetry streams through our secure pipeline to reinforce total alignment with zero speculative heuristics.
                    </p>
                  </div>
                </div>

              </div>
            );
          })}
        </div>

      </div>
    </section>
  );
}
