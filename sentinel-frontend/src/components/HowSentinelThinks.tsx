import { motion } from 'motion/react';
import { 
  UploadCloud, BrainCircuit, GitCompare, LayoutList, CheckCircle 
} from 'lucide-react';

interface Stage {
  title: string;
  sub: string;
  desc: string;
  icon: any;
}

export default function HowSentinelThinks() {
  const stages: Stage[] = [
    {
      title: "Upload Evidence",
      sub: "INGEST",
      desc: "Raw transactions, communication transcripts, and internal files are indexed concurrently.",
      icon: UploadCloud
    },
    {
      title: "Specialist Agents",
      sub: "COGNITION",
      desc: "Niche AI models isolate specific elements—voice signatures, metadata, and routing paths.",
      icon: BrainCircuit
    },
    {
      title: "Cross-Verification",
      sub: "DEDUCTIVE HUB",
      desc: "Discrepancies across modalities are pitted against each other to uncover lies.",
      icon: GitCompare
    },
    {
      title: "Verified Timeline",
      sub: "FORENSICS",
      desc: "A singular chronological fact stream with structured confidence score is produced.",
      icon: LayoutList
    },
    {
      title: "Actionable Decision",
      sub: "PREVENTION",
      desc: "Transactions are placed on safety holds with secure alerts pushed to risk desks.",
      icon: CheckCircle
    }
  ];

  return (
    <section id="pipeline" className="relative py-32 bg-obsidian border-t border-slate-white/5 overflow-hidden">
      <div className="absolute inset-0 console-grid opacity-5 pointer-events-none" />

      <div className="max-w-7xl mx-auto px-6 relative z-10">
        
        {/* Section Header */}
        <div className="mb-24">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-1.5 h-1.5 rounded-full bg-electric-cyan animate-pulse" />
            <span className="font-mono text-[10px] tracking-widest text-electric-cyan uppercase">
              COGNITIVE WORKFLOW
            </span>
          </div>
          <h2 className="font-display font-bold text-3xl md:text-5xl tracking-widest text-slate-white uppercase leading-none mb-6">
            HOW SENTINEL THINKS
          </h2>
          <p className="font-sans text-xs md:text-sm text-slate-white/50 tracking-wider max-w-xl">
            A secure horizontal analysis process. We do not guess. We trace facts across isolated data channels to establish verifiable mathematical alignment.
          </p>
        </div>

        {/* Pipeline Container - Horizontal on Desktop, Vertical on Mobile */}
        <div className="relative">
          
          {/* Background Connecting Line - Desktop Only */}
          <div className="absolute top-12 left-[10%] right-[10%] h-[1px] bg-slate-white/10 hidden lg:block z-0">
            <motion.div
              initial={{ scaleX: 0 }}
              whileInView={{ scaleX: 1 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 2, ease: "easeInOut" }}
              className="h-full bg-gradient-to-r from-electric-cyan via-amber-warning to-cyber-emerald origin-left"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-12 lg:gap-6 relative z-10">
            {stages.map((stage, idx) => {
              const Icon = stage.icon;
              return (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 60, scale: 0.95 }}
                  whileInView={{ opacity: 1, y: 0, scale: 1 }}
                  viewport={{ once: false, margin: "-80px" }}
                  whileHover={{ y: -6, transition: { duration: 0.2 } }}
                  transition={{ 
                    type: "spring",
                    stiffness: 60,
                    damping: 14,
                    delay: idx * 0.12
                  }}
                  className="flex flex-col items-center lg:items-start text-center lg:text-left group cursor-pointer"
                >
                  {/* Icon Node */}
                  <div className="relative flex items-center justify-center w-24 h-24 rounded-full bg-obsidian border border-slate-white/10 group-hover:border-electric-cyan/40 group-hover:shadow-[0_0_20px_rgba(56,189,248,0.1)] transition-all duration-500 z-10 mb-6">
                    <div className="absolute inset-1.5 rounded-full bg-slate-white/[0.01]" />
                    <Icon className="w-8 h-8 text-slate-white/60 group-hover:text-electric-cyan transition-colors duration-500" />
                    
                    {/* Badge step index */}
                    <span className="absolute -top-1 -right-1 flex items-center justify-center w-6 h-6 rounded-full bg-obsidian border border-slate-white/15 font-mono text-[9px] text-slate-white/60">
                      0{idx + 1}
                    </span>
                  </div>

                  {/* Text content */}
                  <div>
                    <span className="font-mono text-[9px] tracking-widest text-electric-cyan/60 block mb-1">
                      {stage.sub}
                    </span>
                    <h3 className="font-display font-medium text-sm tracking-widest text-slate-white uppercase mb-3">
                      {stage.title}
                    </h3>
                    <p className="font-sans text-[11px] text-slate-white/40 tracking-wide leading-relaxed max-w-xs mx-auto lg:mx-0">
                      {stage.desc}
                    </p>
                  </div>
                </motion.div>
              );
            })}
          </div>

        </div>

      </div>
    </section>
  );
}
