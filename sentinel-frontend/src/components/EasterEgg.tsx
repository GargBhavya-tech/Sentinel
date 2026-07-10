import { useState, MouseEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ShieldAlert, Sparkles, Lock, Eye } from 'lucide-react';
import { playTick } from '../utils/audio';

interface RobberCatProps {
  key?: any;
  x: number;
  y: number;
  scale: number;
  type: 'silhouette' | 'highlighted';
}

function RobberCat({ x, y, scale, type }: RobberCatProps) {
  const isSilhouette = type === 'silhouette';
  
  // High contrast palette inspired by the rich indigo & hot pink/red/gold reference
  const bodyColor = isSilhouette ? '#221F4D' : '#E05B35'; // Shadowy deep purple vs. Vivid crimson-orange burglar
  const innerEarColor = isSilhouette ? '#2D1B4E' : '#FECDD3'; // Dim violet vs. Soft pink
  const maskColor = isSilhouette ? '#0F0E26' : '#111827'; // Dim black vs. Deep leather black mask
  const eyeColor = isSilhouette ? '#3B296A' : '#FDE047'; // Dim purple eyes vs. Sharp bright yellow glowing eyes
  const chestColor = isSilhouette ? '#1B143F' : '#FDBA74'; // Dim chest vs. Light peach chest stripe
  const snoutColor = isSilhouette ? '#221F4D' : '#FCA5A5'; // Dim nose vs. Pink nose

  return (
    <g transform={`translate(${x - 40}, ${y - 50}) scale(${scale})`} className="transition-all duration-300">
      {/* Sleek curly tail */}
      <path 
        d="M 46,75 C 60,75 70,65 68,45 C 66,35 56,35 54,45" 
        fill="none" 
        stroke={bodyColor} 
        strokeWidth="6" 
        strokeLinecap="round" 
      />
      
      {/* Sleek cat body */}
      <ellipse cx="40" cy="65" rx="18" ry="24" fill={bodyColor} />
      
      {/* Chest highlights */}
      <ellipse cx="40" cy="60" rx="11" ry="14" fill={chestColor} />

      {/* Pointy triangular ears */}
      <polygon points="22,22 10,0 31,14" fill={bodyColor} />
      <polygon points="22,22 13,6 28,15" fill={innerEarColor} />
      
      <polygon points="58,22 70,0 49,14" fill={bodyColor} />
      <polygon points="58,22 67,6 52,15" fill={innerEarColor} />

      {/* Tilted head */}
      <ellipse cx="40" cy="34" rx="20" ry="16" fill={bodyColor} />

      {/* Bandit eye mask */}
      <rect x="18" y="25" width="44" height="14" rx="4" fill={maskColor} />
      
      {/* Angry slit eyes inside the mask */}
      <polygon points="25,32 33,30 31,35" fill={eyeColor} />
      <polygon points="55,32 47,30 49,35" fill={eyeColor} />

      {/* Sneaky pink nose */}
      <polygon points="38,39 42,39 40,41" fill={snoutColor} />

      {/* Sneaky hands/paws on the floor */}
      <rect x="27" y="82" width="7" height="10" rx="3.5" fill={bodyColor} />
      <rect x="46" y="82" width="7" height="10" rx="3.5" fill={bodyColor} />
    </g>
  );
}

export default function EasterEgg() {
  const [isHovered, setIsHovered] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 500, y: 150 });

  // 10 thief cats spread beautifully across the panoramic stage
  const thiefCats = [
    { id: 1, x: 70, y: 110, scale: 0.8 },
    { id: 2, x: 150, y: 105, scale: 0.85 },
    { id: 3, x: 230, y: 110, scale: 0.8 },
    { id: 4, x: 310, y: 100, scale: 0.9 },
    { id: 5, x: 390, y: 105, scale: 0.85 },
    // Ginger cat is at x=500 in foreground
    { id: 6, x: 610, y: 105, scale: 0.85 },
    { id: 7, x: 690, y: 100, scale: 0.9 },
    { id: 8, x: 770, y: 110, scale: 0.8 },
    { id: 9, x: 850, y: 105, scale: 0.85 },
    { id: 10, x: 930, y: 110, scale: 0.8 },
  ];

  const handleMouseEnter = () => {
    setIsHovered(true);
    playTick();
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
  };

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 1000;
    const y = ((e.clientY - rect.top) / rect.height) * 300;
    setMousePosition({ x, y });
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 50, scale: 0.97 }}
      whileInView={{ opacity: 1, y: 0, scale: 1 }}
      viewport={{ once: false, margin: "-60px" }}
      transition={{ type: "spring", stiffness: 50, damping: 14 }}
      whileHover={{ y: -6, transition: { duration: 0.2 } }}
      className="relative max-w-5xl mx-auto p-6 rounded-xs bg-obsidian/40 border border-slate-white/5 backdrop-blur-sm overflow-hidden select-none w-full cursor-crosshair"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onMouseMove={handleMouseMove}
    >
      {/* Laser sweep animation when hovered */}
      {isHovered && (
        <motion.div 
          initial={{ x: "-100%" }}
          animate={{ x: "100%" }}
          transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
          className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-electric-cyan/5 to-transparent pointer-events-none z-10"
        />
      )}

      <div className="absolute top-2 left-3 font-mono text-[8px] text-slate-white/20 tracking-widest flex items-center gap-1">
        <Sparkles className="w-2.5 h-2.5 text-amber-warning/50" />
        SECURE NODE METRICS // PANORAMIC COGNITIVE EASTER EGG
      </div>

      <div className="absolute top-2 right-3 font-mono text-[8px] text-electric-cyan/40 tracking-widest flex items-center gap-1">
        <span className="w-1.5 h-1.5 bg-electric-cyan/80 rounded-full animate-ping" />
        SYSTEM STATUS: ONLINE
      </div>

      <div className="flex flex-col items-center mt-4">
        {/* SVG Vector Illustration */}
        <div className="relative w-full aspect-[16/6] md:aspect-[24/7] flex items-center justify-center">
          <svg 
            viewBox="0 0 1000 300" 
            className="w-full h-full filter drop-shadow-[0_0_25px_rgba(56,189,248,0.12)]"
          >
            {/* Definitions for gradients and masks */}
            <defs>
              {/* Ultra-luminous, bright yellow-golden-white spotlight beam gradient */}
              <linearGradient id="yellow-beam-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#FFFBEB" stopOpacity="0.75" /> {/* Whitish bright yellow top */}
                <stop offset="30%" stopColor="#FDE047" stopOpacity="0.55" /> {/* Vibrant yellow */}
                <stop offset="70%" stopColor="#EAB308" stopOpacity="0.3" /> {/* Warm gold */}
                <stop offset="100%" stopColor="#D97706" stopOpacity="0.0" /> {/* Smooth fadeout */}
              </linearGradient>

              {/* Cyan glow for smartphone base */}
              <linearGradient id="laser-glow" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#38BDF8" stopOpacity="0" />
              </linearGradient>

              {/* Dynamic spotlight mask mapping to synchronize the mask revealing high-contrast cats */}
              <mask id="spotlight-mask">
                {/* Black background masks out the high contrast cats */}
                <rect width="1000" height="300" fill="#000000" />
                
                {/* Sweeping spotlight wedge in white to reveal them */}
                <motion.polygon 
                  points="-60,0 60,0 300,300 -60,300" 
                  fill="#FFFFFF"
                  animate={isHovered ? { x: mousePosition.x } : { x: [-150, 950, -150] }}
                  transition={isHovered ? { type: "spring", stiffness: 120, damping: 20 } : { repeat: Infinity, duration: 8, ease: "easeInOut" }}
                />
              </mask>
            </defs>

            {/* Dark background container */}
            <rect width="1000" height="300" rx="4" fill="#07080B" opacity="0.3" />

            {/* Background grid lines for tech blueprint vibe */}
            <g stroke="rgba(56, 189, 248, 0.03)" strokeWidth="0.5">
              <line x1="100" y1="0" x2="100" y2="300" />
              <line x1="200" y1="0" x2="200" y2="300" />
              <line x1="300" y1="0" x2="300" y2="300" />
              <line x1="400" y1="0" x2="400" y2="300" />
              <line x1="500" y1="0" x2="500" y2="300" />
              <line x1="600" y1="0" x2="600" y2="300" />
              <line x1="700" y1="0" x2="700" y2="300" />
              <line x1="800" y1="0" x2="800" y2="300" />
              <line x1="900" y1="0" x2="900" y2="300" />
              
              <line x1="0" y1="75" x2="1000" y2="75" />
              <line x1="0" y1="150" x2="1000" y2="150" />
              <line x1="0" y1="225" x2="1000" y2="225" />
            </g>

            {/* LAYER 1: Silhouette Robber Cats (Background / Dim Outside Spotlight) */}
            <g id="dim-silhouettes" opacity="0.45">
              {thiefCats.map((cat) => (
                <RobberCat 
                  key={`sil-${cat.id}`} 
                  x={cat.x} 
                  y={cat.y} 
                  scale={cat.scale} 
                  type="silhouette" 
                />
              ))}
            </g>

            {/* LAYER 2: Highly dramatic sweeping spotlight beam */}
            <g>
              {/* Floor puddle of bright yellow light */}
              <motion.ellipse 
                cx="120" 
                cy="285" 
                rx="180" 
                ry="14" 
                fill="#FDE047" 
                opacity="0.45"
                animate={isHovered ? { x: mousePosition.x } : { x: [-150, 950, -150] }}
                transition={isHovered ? { type: "spring", stiffness: 120, damping: 20 } : { repeat: Infinity, duration: 8, ease: "easeInOut" }}
                className="blur-[1px]"
              />

              {/* Diagonal overhead searchlight beam */}
              <motion.polygon 
                points="-60,0 60,0 300,300 -60,300" 
                fill="url(#yellow-beam-grad)"
                animate={isHovered ? { x: mousePosition.x } : { x: [-150, 950, -150] }}
                transition={isHovered ? { type: "spring", stiffness: 120, damping: 20 } : { repeat: Infinity, duration: 8, ease: "easeInOut" }}
                style={{ mixBlendMode: 'screen' }}
              />
            </g>

            {/* LAYER 3: Illuminated High-Contrast Robber Cats (Revealed only inside the spotlight) */}
            <g id="illuminated-high-contrast" mask="url(#spotlight-mask)">
              {thiefCats.map((cat) => (
                <RobberCat 
                  key={`high-${cat.id}`} 
                  x={cat.x} 
                  y={cat.y} 
                  scale={cat.scale} 
                  type="highlighted" 
                />
              ))}
            </g>

            {/* LAYER 4: Glowing smartphone & stack of highly detailed dollar bank notes in center */}
            <g transform="translate(410, 180)">
              {/* Radial glow below phone */}
              <ellipse cx="90" cy="50" rx="100" ry="14" fill="#38BDF8" opacity="0.3" className="animate-pulse" />
              
              {/* Phone base body (Perspective tilted) */}
              <polygon points="20,45 160,15 180,60 40,90" fill="#0F172A" stroke="#38BDF8" strokeWidth="2.5" />
              
              {/* Screen content (Glowing deep blue-cyan) */}
              <polygon points="24,45 156,17 173,57 41,85" fill="#0A0F1D" stroke="#38BDF8" strokeWidth="0.5" />
              
              {/* Overlapping, highly detailed green dollar notes (Not an envelope!) */}
              {/* Bill 1 (Bottom) */}
              <g transform="translate(10, 12)">
                <polygon points="10,50 110,25 125,48 25,73" fill="#166534" stroke="#4ADE80" strokeWidth="0.5" />
                <ellipse cx="67" cy="49" rx="12" ry="6" fill="#86EFAC" opacity="0.6" />
                <text x="18" y="55" fill="#FFFFFF" fontSize="6" fontFamily="monospace" fontWeight="bold">$</text>
                <text x="111" y="32" fill="#FFFFFF" fontSize="6" fontFamily="monospace" fontWeight="bold">$</text>
              </g>

              {/* Bill 2 (Middle) */}
              <g transform="translate(5, 6)">
                <polygon points="20,53 120,28 135,51 35,76" fill="#15803D" stroke="#22C55E" strokeWidth="0.5" />
                <ellipse cx="77" cy="52" rx="12" ry="6" fill="#BBF7D0" opacity="0.8" />
                <text x="28" y="58" fill="#FFFFFF" fontSize="6" fontFamily="monospace" fontWeight="bold">$</text>
                <text x="121" y="35" fill="#FFFFFF" fontSize="6" fontFamily="monospace" fontWeight="bold">$</text>
              </g>

              {/* Bill 3 (Top bill with security seal, dollar sign corners and engravings) */}
              <g>
                <polygon points="30,48 130,23 145,46 45,71" fill="#22C55E" stroke="#86EFAC" strokeWidth="1" />
                <polygon points="33,48 127,25 140,46 46,69" fill="none" stroke="#14532D" strokeWidth="0.5" strokeDasharray="1,1" />
                
                {/* Center portrait shield */}
                <ellipse cx="87" cy="47" rx="14" ry="7" fill="#DCFCE7" stroke="#166534" strokeWidth="0.5" />
                <circle cx="87" cy="47" r="4.5" fill="#166534" />
                <circle cx="87" cy="47" r="2" fill="#86EFAC" />

                {/* Corners "$" symbols */}
                <text x="36" y="53" fill="#14532D" fontSize="6" fontFamily="monospace" fontWeight="bold">$</text>
                <text x="123" y="31" fill="#14532D" fontSize="6" fontFamily="monospace" fontWeight="bold">$</text>
                <text x="135" y="41" fill="#14532D" fontSize="5" fontFamily="monospace">$</text>
                <text x="46" y="63" fill="#14532D" fontSize="5" fontFamily="monospace">$</text>

                {/* Engraving lines */}
                <line x1="43" y1="41" x2="123" y2="21" stroke="#14532D" strokeWidth="0.5" opacity="0.3" />
                <line x1="39" y1="51" x2="135" y2="27" stroke="#14532D" strokeWidth="0.5" opacity="0.3" />
                <line x1="49" y1="61" x2="141" y2="38" stroke="#14532D" strokeWidth="0.5" opacity="0.3" />
              </g>

              {/* Floating security lock hologram over money stack */}
              <g transform="translate(145, 20)" className="animate-bounce" style={{ animationDuration: '2s' }}>
                <circle cx="8" cy="8" r="7" fill="#07080B" stroke="#38BDF8" strokeWidth="1" />
                <rect x="5" y="8" width="6" height="5" rx="1" fill="#38BDF8" />
                <path d="M 6,8 L 6,6 C 6,5 7,4 8,4 C 9,4 10,5 10,6 L 10,8" fill="none" stroke="#38BDF8" strokeWidth="1" />
              </g>
            </g>

            {/* LAYER 5: Confident Orange/Ginger Cat sitting proudly on the money notes (Always fully visible in foreground) */}
            <g transform="translate(460, 115)">
              {/* Tail */}
              <path d="M 60,65 C 75,65 85,50 82,35 C 80,25 70,25 68,35" fill="none" stroke="#F97316" strokeWidth="8" strokeLinecap="round" />
              <path d="M 60,65 C 75,65 85,50 82,35 C 80,25 70,25 68,35" fill="none" stroke="#FB923C" strokeWidth="6" strokeLinecap="round" />

              {/* Body */}
              <ellipse cx="40" cy="55" rx="22" ry="26" fill="#F97316" />
              {/* Tummy highlight */}
              <ellipse cx="40" cy="58" rx="14" ry="16" fill="#FED7AA" />

              {/* Head */}
              <ellipse cx="40" cy="25" rx="22" ry="20" fill="#F97316" />

              {/* Ears */}
              <polygon points="20,15 12,-4 32,8" fill="#F97316" />
              <polygon points="20,15 15,0 28,8" fill="#FED7AA" />

              <polygon points="60,15 68,-4 48,8" fill="#F97316" />
              <polygon points="60,15 65,0 52,8" fill="#FED7AA" />

              {/* Big, Confident Eyes */}
              <circle cx="30" cy="22" r="6" fill="#FFFFFF" />
              <circle cx="30" cy="22" r="2.5" fill="#07080B" />
              
              <circle cx="50" cy="22" r="6" fill="#FFFFFF" />
              <circle cx="50" cy="22" r="2.5" fill="#07080B" />

              {/* Snout and nose */}
              <circle cx="37" cy="29" r="2.5" fill="#FED7AA" />
              <circle cx="43" cy="29" r="2.5" fill="#FED7AA" />
              <polygon points="38,27 42,27 40,29" fill="#F43F5E" />
              
              {/* Whiskers */}
              <line x1="18" y1="28" x2="5" y2="28" stroke="#FED7AA" strokeWidth="1" />
              <line x1="18" y1="31" x2="6" y2="33" stroke="#FED7AA" strokeWidth="1" />
              <line x1="62" y1="28" x2="75" y2="28" stroke="#FED7AA" strokeWidth="1" />
              <line x1="62" y1="31" x2="74" y2="33" stroke="#FED7AA" strokeWidth="1" />

              {/* Sitting Front Paws */}
              <rect x="28" y="70" width="8" height="15" rx="4" fill="#F97316" />
              <rect x="28" y="80" width="8" height="5" rx="2.5" fill="#FED7AA" />
              
              <rect x="44" y="70" width="8" height="15" rx="4" fill="#F97316" />
              <rect x="44" y="80" width="8" height="5" rx="2.5" fill="#FED7AA" />
            </g>
          </svg>
        </div>

        {/* Captions & User Instructions */}
        <div className="h-10 mt-2 text-center flex items-center justify-center">
          <AnimatePresence>
            {isHovered ? (
              <motion.div
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-1.5 text-[10px] font-mono tracking-widest text-amber-warning uppercase font-semibold"
              >
                <ShieldAlert className="w-3.5 h-3.5 text-amber-warning animate-pulse" />
                &quot;The original asset remains locked. Copycats are exposed, but cryptographic consensus never lies.&quot;
              </motion.div>
            ) : (
              <span className="font-mono text-[9px] text-slate-white/25 uppercase tracking-widest flex items-center gap-2">
                <Eye className="w-3.5 h-3.5 text-slate-white/25 animate-pulse" />
                [ SWEEP CURSOR OVER PANORAMA TO SHINE THE LENS SCANNER & EXPOSE THE THIEVES ]
              </span>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
