import { useState, useEffect } from 'react';

// Tracks which section id is currently active by checking, on scroll, which
// section's top edge has most recently crossed a reference line near the
// top of the viewport. Simpler and more deterministic than an
// IntersectionObserver-based approach for a small, fixed set of sections.
export function useScrollSpy(sectionIds) {
  const [activeId, setActiveId] = useState(sectionIds[0]);

  useEffect(() => {
    const REFERENCE_LINE = 140; // px from top, below the sticky nav

    const update = () => {
      let current = sectionIds[0];
      for (const id of sectionIds) {
        const el = document.getElementById(id);
        if (!el) continue;
        if (el.getBoundingClientRect().top <= REFERENCE_LINE) {
          current = id;
        }
      }
      setActiveId(current);
    };

    update();
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
    };
  }, [sectionIds]);

  return activeId;
}
