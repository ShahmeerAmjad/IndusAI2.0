import { useState, useEffect, useRef } from "react";

export function useCountUp(end: number, duration = 1500, start = 0) {
  const [count, setCount] = useState(start);
  const prevEnd = useRef(start);

  useEffect(() => {
    if (end === prevEnd.current) return;
    prevEnd.current = end;

    const startTime = performance.now();
    const startVal = start;

    function animate(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(startVal + (end - startVal) * eased));
      if (progress < 1) requestAnimationFrame(animate);
    }

    requestAnimationFrame(animate);
  }, [end, duration, start]);

  return count;
}
