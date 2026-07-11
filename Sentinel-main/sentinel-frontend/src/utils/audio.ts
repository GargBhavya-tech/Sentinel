// Web Audio API helper for producing clean, cinematic synthesized forensic sound effects
// Completely asset-free: synthesizes audio real-time in the browser.

let audioCtx: AudioContext | null = null;
let isAudioEnabled = true;

// Initialize on first user gesture automatically to bypass browser autoplay policy
if (typeof window !== 'undefined') {
  const initAudioOnGesture = () => {
    if (!audioCtx) {
      try {
        audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      } catch (e) {
        console.warn('Web Audio API not supported in this environment');
      }
    }
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    // Remove listeners once initialized
    window.removeEventListener('click', initAudioOnGesture);
    window.removeEventListener('touchstart', initAudioOnGesture);
    window.removeEventListener('keydown', initAudioOnGesture);
  };

  window.addEventListener('click', initAudioOnGesture, { once: true });
  window.addEventListener('touchstart', initAudioOnGesture, { once: true });
  window.addEventListener('keydown', initAudioOnGesture, { once: true });
}

export function enableAudio(enable: boolean) {
  isAudioEnabled = enable;
  if (enable && !audioCtx) {
    try {
      audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
    } catch (e) {
      console.warn('Web Audio API not supported in this environment');
    }
  }
}

export function getAudioEnabled() {
  return isAudioEnabled;
}

function getContext(): AudioContext | null {
  if (!isAudioEnabled) return null;
  if (!audioCtx) {
    try {
      audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
    } catch (e) {
      return null;
    }
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

// 1. Sleek digital click / navigation click sound
export function playClick() {
  const ctx = getContext();
  if (!ctx) return;

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = 'sine';
  osc.frequency.setValueAtTime(1200, ctx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(150, ctx.currentTime + 0.08);

  gain.gain.setValueAtTime(0.04, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.08);

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start();
  osc.stop(ctx.currentTime + 0.08);
}

// 2. High-tech forensic "scan/hover" tick
export function playTick() {
  const ctx = getContext();
  if (!ctx) return;

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = 'triangle';
  osc.frequency.setValueAtTime(800, ctx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(3000, ctx.currentTime + 0.03);

  gain.gain.setValueAtTime(0.02, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.03);

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start();
  osc.stop(ctx.currentTime + 0.03);
}

// 3. Low-frequency cinematic data sweep (when panel reveals or transitions)
export function playSweep() {
  const ctx = getContext();
  if (!ctx) return;

  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = 'sine';
  osc.frequency.setValueAtTime(90, ctx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(450, ctx.currentTime + 0.4);

  gain.gain.setValueAtTime(0.08, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start();
  osc.stop(ctx.currentTime + 0.4);
}

// 4. Warning Alert / Cyber Threat Confirmed alarm
export function playAlert() {
  const ctx = getContext();
  if (!ctx) return;

  const t = ctx.currentTime;
  
  // Double sweep pattern
  [0, 0.15, 0.3].forEach((delay) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(650, t + delay);
    osc.frequency.exponentialRampToValueAtTime(350, t + delay + 0.12);

    gain.gain.setValueAtTime(0.03, t + delay);
    gain.gain.exponentialRampToValueAtTime(0.001, t + delay + 0.12);

    // Apply lowpass filter to make it warmer/cinematic instead of harsh
    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(1400, t);

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(ctx.destination);

    osc.start(t + delay);
    osc.stop(t + delay + 0.12);
  });
}
