import { useState, FormEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, AlertTriangle, Play, Shield, Zap, DollarSign, FileText, Mic } from 'lucide-react';
import { InvestigatePayload } from '../api/sentinel';

interface EvidenceSubmitModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDeploy: (payload: InvestigatePayload) => void;
}

// Pre-loaded flagship demo case
const FLAGSHIP_CASE: InvestigatePayload = {
  description:
    'Cloned CEO voice note requesting urgent wire transfer of $1,450,000 to routing ' +
    'number RT_912000031 at an offshore Belize entity. Invoice total mismatch detected — ' +
    'visual total $145,000 vs structured total $1,450,000. Caller VPN geolocated to ' +
    'Singapore while CEO email client shows simultaneous San Francisco login. ' +
    'White-on-white prompt injection text found in invoice footer.',
  amount_at_risk: 1450000,
  demo_case: true,
  channel: 'C_DEMO',
  reporter: 'U_DEMO',
};

const QUICK_CASES = [
  {
    label: 'Flagship Case',
    icon: Zap,
    color: '#EF4444',
    description: 'CEO voice clone + invoice mismatch + VPN geo anomaly + injection',
    payload: FLAGSHIP_CASE,
  },
  {
    label: 'Invoice Fraud',
    icon: FileText,
    color: '#F59E0B',
    description: 'Routing number discrepancy in vendor invoice',
    payload: {
      description: 'Vendor invoice with routing number RT_912000031 does not match our supplier ledger. Amount $87,500. Domain registered 12 days ago.',
      amount_at_risk: 87500,
      channel: 'C_DEMO',
      reporter: 'U_DEMO',
    } as InvestigatePayload,
  },
  {
    label: 'Account Takeover',
    icon: Shield,
    color: '#38BDF8',
    description: 'Stylometric anomaly — message tone doesn\'t match sender baseline',
    payload: {
      description: 'Finance department head sending unusual payment request. Writing style significantly different from baseline. Requesting $23,000 urgent transfer.',
      amount_at_risk: 23000,
      channel: 'C_DEMO',
      reporter: 'U_DEMO',
    } as InvestigatePayload,
  },
];

export default function EvidenceSubmitModal({ isOpen, onClose, onDeploy }: EvidenceSubmitModalProps) {
  const [description, setDescription] = useState('');
  const [amountAtRisk, setAmountAtRisk] = useState('');
  const [isDeploying, setIsDeploying] = useState(false);
  const [selectedQuick, setSelectedQuick] = useState<number | null>(null);

  const handleQuickSelect = (idx: number) => {
    setSelectedQuick(idx);
    setDescription(QUICK_CASES[idx].payload.description);
    setAmountAtRisk(String(QUICK_CASES[idx].payload.amount_at_risk || ''));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!description.trim() && selectedQuick === null) return;

    setIsDeploying(true);

    const payload: InvestigatePayload =
      selectedQuick !== null
        ? QUICK_CASES[selectedQuick].payload
        : {
            description: description.trim(),
            amount_at_risk: parseFloat(amountAtRisk) || 0,
            channel: 'C_DEMO',
            reporter: 'U_DEMO',
          };

    onDeploy(payload);
    // Modal closes immediately — transition takes over
  };

  const handleClose = () => {
    if (isDeploying) return;
    setDescription('');
    setAmountAtRisk('');
    setSelectedQuick(null);
    setIsDeploying(false);
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-obsidian/80 backdrop-blur-sm"
            onClick={handleClose}
          />

          {/* Modal */}
          <motion.div
            key="modal-panel"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
          >
            <div
              className="w-full max-w-2xl bg-obsidian border border-slate-white/10 rounded-xs shadow-2xl pointer-events-auto"
              onClick={e => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between p-6 border-b border-slate-white/10">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="w-2 h-2 rounded-full bg-evidence-crimson animate-pulse" />
                    <span className="font-mono text-[9px] tracking-widest text-electric-cyan uppercase">
                      [ SENTINEL DEPLOYMENT GATEWAY ]
                    </span>
                  </div>
                  <h2 className="font-display font-bold text-xl tracking-widest text-slate-white uppercase">
                    Deploy Investigator
                  </h2>
                  <p className="font-mono text-[10px] text-slate-white/40 mt-1">
                    Submit evidence for multi-agent cross-examination
                  </p>
                </div>
                <button
                  onClick={handleClose}
                  disabled={isDeploying}
                  className="text-slate-white/30 hover:text-slate-white transition-colors disabled:opacity-30 cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleSubmit}>
                <div className="p-6 space-y-6">

                  {/* Quick case selector */}
                  <div>
                    <span className="font-mono text-[9px] text-slate-white/40 tracking-widest uppercase block mb-3">
                      [ QUICK CASE TEMPLATES ]
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      {QUICK_CASES.map((qc, idx) => {
                        const Icon = qc.icon;
                        const isSelected = selectedQuick === idx;
                        return (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => handleQuickSelect(idx)}
                            className={`text-left p-3 border rounded-xs transition-all duration-200 cursor-pointer ${
                              isSelected
                                ? 'border-electric-cyan bg-electric-cyan/5'
                                : 'border-slate-white/10 bg-slate-white/[0.01] hover:border-slate-white/20'
                            }`}
                          >
                            <div className="flex items-center gap-2 mb-1.5">
                              <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: qc.color }} />
                              <Icon className="w-3.5 h-3.5 text-slate-white/50" />
                              <span className="font-mono text-[10px] font-bold text-slate-white tracking-wider">
                                {qc.label}
                              </span>
                            </div>
                            <p className="font-mono text-[9px] text-slate-white/40 leading-relaxed">
                              {qc.description}
                            </p>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Divider */}
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-px bg-slate-white/10" />
                    <span className="font-mono text-[9px] text-slate-white/25 uppercase tracking-widest">or describe manually</span>
                    <div className="flex-1 h-px bg-slate-white/10" />
                  </div>

                  {/* Description textarea */}
                  <div>
                    <label className="font-mono text-[9px] text-slate-white/40 tracking-widest uppercase block mb-2">
                      [ DESCRIBE THE SUSPICIOUS ACTIVITY ]
                    </label>
                    <textarea
                      value={description}
                      onChange={e => {
                        setDescription(e.target.value);
                        if (selectedQuick !== null) setSelectedQuick(null);
                      }}
                      placeholder="e.g. Unusual wire transfer request received via voice note from CFO account. Invoice routing number differs from our records. Request is unusually urgent..."
                      rows={4}
                      className="w-full bg-obsidian border border-slate-white/10 rounded-xs px-4 py-3 font-mono text-[11px] text-slate-white placeholder-slate-white/20 focus:outline-none focus:border-electric-cyan/40 transition-colors resize-none"
                    />
                  </div>

                  {/* Amount at risk */}
                  <div>
                    <label className="font-mono text-[9px] text-slate-white/40 tracking-widest uppercase block mb-2">
                      [ AMOUNT AT RISK (USD) — optional, enables expected-loss triage ]
                    </label>
                    <div className="relative">
                      <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-white/30" />
                      <input
                        type="number"
                        value={amountAtRisk}
                        onChange={e => setAmountAtRisk(e.target.value)}
                        placeholder="1450000"
                        className="w-full bg-obsidian border border-slate-white/10 rounded-xs pl-9 pr-4 py-2.5 font-mono text-[11px] text-slate-white placeholder-slate-white/20 focus:outline-none focus:border-electric-cyan/40 transition-colors"
                      />
                    </div>
                  </div>

                  {/* Warning banner */}
                  <div className="flex items-start gap-3 bg-evidence-crimson/5 border border-evidence-crimson/15 rounded-xs p-3">
                    <AlertTriangle className="w-4 h-4 text-evidence-crimson shrink-0 mt-0.5" />
                    <p className="font-mono text-[9px] text-slate-white/50 leading-relaxed">
                      All evidence is processed through the PII redaction gateway before reaching any AI agent.
                      Sentinel's contradiction engine cross-examines agents against each other —
                      the disagreement is the signal.
                    </p>
                  </div>
                </div>

                {/* Footer */}
                <div className="p-6 pt-0 flex items-center justify-between gap-4">
                  <button
                    type="button"
                    onClick={handleClose}
                    disabled={isDeploying}
                    className="font-mono text-[10px] text-slate-white/40 hover:text-slate-white/70 tracking-wider uppercase transition-colors disabled:opacity-30 cursor-pointer"
                  >
                    CANCEL
                  </button>

                  <button
                    type="submit"
                    disabled={isDeploying || (!description.trim() && selectedQuick === null)}
                    className="group relative flex items-center gap-2 bg-slate-white text-obsidian font-mono text-xs font-bold tracking-widest uppercase py-3 px-8 rounded-xs hover:bg-electric-cyan hover:shadow-[0_0_25px_rgba(56,189,248,0.4)] transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer overflow-hidden"
                  >
                    <span className="absolute inset-0 bg-gradient-to-r from-transparent via-electric-cyan/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />
                    <span className="relative flex items-center gap-2">
                      {isDeploying ? (
                        <>
                          <span className="w-3 h-3 rounded-full border-2 border-obsidian border-t-transparent animate-spin" />
                          DEPLOYING…
                        </>
                      ) : (
                        <>
                          <Play className="w-3.5 h-3.5" />
                          DEPLOY INVESTIGATOR
                        </>
                      )}
                    </span>
                  </button>
                </div>
              </form>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
