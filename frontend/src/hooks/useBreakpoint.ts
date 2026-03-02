/**
 * Хук для определения текущего breakpoint (адаптивность).
 * Пункт плана: 1.17.7
 */
import { useState, useEffect } from 'react';

interface BreakpointState {
  isMobile: boolean;   // < 768px
  isTablet: boolean;   // 768–1024px
  isDesktop: boolean;  // > 1024px
  width: number;
}

export default function useBreakpoint(): BreakpointState {
  const [state, setState] = useState<BreakpointState>(() => {
    const w = typeof window !== 'undefined' ? window.innerWidth : 1200;
    return {
      width: w,
      isMobile: w < 768,
      isTablet: w >= 768 && w <= 1024,
      isDesktop: w > 1024,
    };
  });

  useEffect(() => {
    let rafId: number;

    const handleResize = () => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        const w = window.innerWidth;
        setState({
          width: w,
          isMobile: w < 768,
          isTablet: w >= 768 && w <= 1024,
          isDesktop: w > 1024,
        });
      });
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(rafId);
    };
  }, []);

  return state;
}