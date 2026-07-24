"use client";

import { useEffect, useRef, useState } from "react";

// Eases a numeric value toward its target with requestAnimationFrame.
// Falls back to an instant set when the user prefers reduced motion.
export function AnimatedNumber({
  value,
  decimals = 0,
  prefix = "",
  reducedMotion = false,
}: {
  value: number;
  decimals?: number;
  prefix?: string;
  reducedMotion?: boolean;
}) {
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (reducedMotion) {
      setDisplay(value);
      fromRef.current = value;
      return;
    }
    const from = fromRef.current;
    const delta = value - from;
    if (delta === 0) return;
    const dur = 480;
    let start: number | null = null;

    const tick = (t: number) => {
      if (start == null) start = t;
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(from + delta * eased);
      if (p < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = value;
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      fromRef.current = value;
    };
  }, [value, reducedMotion]);

  return (
    <>
      {prefix}
      {display.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}
    </>
  );
}
