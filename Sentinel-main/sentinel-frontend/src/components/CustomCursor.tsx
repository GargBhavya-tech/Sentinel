import { useEffect, useState } from 'react';
import { motion, useMotionValue, useSpring, AnimatePresence } from 'motion/react';

export default function CustomCursor() {
  const [isHovered, setIsHovered] = useState(false);
  const [isPressed, setIsPressed] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const [hoverType, setHoverType] = useState<'default' | 'link' | 'danger' | 'warning'>('default');
  const [isTouchDevice, setIsTouchDevice] = useState(false);

  // Motion values for direct mouse tracking (used for the fast inner dot)
  const mouseX = useMotionValue(-100);
  const mouseY = useMotionValue(-100);

  // Spring values for trailing organic lag (used for the outer ring)
  // Perfectly balanced stiffness and damping for that beautiful smooth lag
  const springConfig = { stiffness: 220, damping: 24, mass: 0.6 };
  const ringX = useSpring(mouseX, springConfig);
  const ringY = useSpring(mouseY, springConfig);

  useEffect(() => {
    // Check if device supports hover / is a touch device
    const checkTouch = () => {
      const touchSupport = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
      setIsTouchDevice(touchSupport);
    };
    checkTouch();

    if (isTouchDevice) return;

    const handleMouseMove = (e: MouseEvent) => {
      mouseX.set(e.clientX);
      mouseY.set(e.clientY);
      if (!isVisible) setIsVisible(true);
    };

    const handleMouseOver = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target) return;

      // Check if target or any ancestor is an interactive element
      const interactiveEl = target.closest('a, button, [role="button"], input, select, textarea, .interactive, .cursor-pointer');

      if (interactiveEl) {
        setIsHovered(true);
        
        // Context-aware color-coding for the tactical reticle
        if (
          interactiveEl.classList.contains('border-evidence-crimson') || 
          interactiveEl.closest('.border-evidence-crimson') ||
          interactiveEl.classList.contains('bg-evidence-crimson') ||
          interactiveEl.closest('.bg-evidence-crimson')
        ) {
          setHoverType('danger');
        } else if (
          interactiveEl.classList.contains('text-amber-warning') || 
          interactiveEl.closest('.text-amber-warning')
        ) {
          setHoverType('warning');
        } else {
          setHoverType('link');
        }
      } else {
        setIsHovered(false);
        setHoverType('default');
      }
    };

    const handleMouseDown = () => setIsPressed(true);
    const handleMouseUp = () => setIsPressed(false);

    // Hide custom cursor when cursor exits the viewport
    const handleMouseLeaveWindow = () => setIsVisible(false);
    const handleMouseEnterWindow = () => setIsVisible(true);

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseover', handleMouseOver);
    window.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mouseup', handleMouseUp);
    
    document.addEventListener('mouseleave', handleMouseLeaveWindow);
    document.addEventListener('mouseenter', handleMouseEnterWindow);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseover', handleMouseOver);
      window.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mouseup', handleMouseUp);
      
      document.removeEventListener('mouseleave', handleMouseLeaveWindow);
      document.removeEventListener('mouseenter', handleMouseEnterWindow);
    };
  }, [isVisible, isTouchDevice, mouseX, mouseY]);

  // Don't render custom cursor on mobile touch screens
  if (isTouchDevice) return null;

  // Determine colors based on interactive hover types
  const getColors = () => {
    switch (hoverType) {
      case 'danger':
        return {
          dot: 'bg-evidence-crimson shadow-[0_0_8px_#ef4444]',
          ring: 'border-evidence-crimson bg-evidence-crimson/10',
          tick: 'bg-evidence-crimson',
        };
      case 'warning':
        return {
          dot: 'bg-amber-warning shadow-[0_0_8px_#f59e0b]',
          ring: 'border-amber-warning bg-amber-warning/10',
          tick: 'bg-amber-warning',
        };
      case 'link':
      default:
        return {
          dot: 'bg-electric-cyan shadow-[0_0_8px_#38bdf8]',
          ring: 'border-electric-cyan bg-electric-cyan/8',
          tick: 'bg-electric-cyan',
        };
    }
  };

  const colors = getColors();

  return (
    <div className="fixed inset-0 pointer-events-none z-[9999] overflow-hidden">
      <AnimatePresence>
        {isVisible && (
          <>
            {/* 1. Tactical Outer Ring with dynamic sizing & spring delay */}
            <motion.div
              style={{
                x: ringX,
                y: ringY,
                translateX: '-50%',
                translateY: '-50%',
              }}
              animate={{
                width: isPressed ? 20 : isHovered ? 44 : 26,
                height: isPressed ? 20 : isHovered ? 44 : 26,
                borderWidth: isHovered ? '2px' : '1px',
              }}
              transition={{
                type: 'spring',
                stiffness: 300,
                damping: 20,
              }}
              className={`absolute rounded-full border transition-colors duration-200 flex items-center justify-center ${colors.ring}`}
            >
              {/* Tactical scope corner ticks that rotate and reveal during hover lock-on */}
              {isHovered && (
                <motion.div
                  initial={{ opacity: 0, rotate: -45, scale: 0.6 }}
                  animate={{ opacity: 1, rotate: 45, scale: 1 }}
                  exit={{ opacity: 0, rotate: -45, scale: 0.6 }}
                  transition={{ duration: 0.25, ease: 'easeOut' }}
                  className="absolute inset-0 flex items-center justify-center"
                >
                  {/* Scope lines */}
                  <div className={`absolute top-[-3px] w-[2px] h-[6px] ${colors.tick}`} />
                  <div className={`absolute bottom-[-3px] w-[2px] h-[6px] ${colors.tick}`} />
                  <div className={`absolute left-[-3px] h-[2px] w-[6px] ${colors.tick}`} />
                  <div className={`absolute right-[-3px] h-[2px] w-[6px] ${colors.tick}`} />
                </motion.div>
              )}
            </motion.div>

            {/* 2. Snappy Inner Precision Dot (Directly tracking mouse for zero-latency feel) */}
            <motion.div
              style={{
                x: mouseX,
                y: mouseY,
                translateX: '-50%',
                translateY: '-50%',
              }}
              animate={{
                scale: isPressed ? 0.6 : isHovered ? 1.4 : 1,
              }}
              transition={{
                type: 'spring',
                stiffness: 400,
                damping: 15,
              }}
              className={`absolute w-1.5 h-1.5 rounded-full transition-colors duration-200 ${colors.dot}`}
            />
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
