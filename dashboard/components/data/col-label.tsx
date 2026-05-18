"use client";

import { useState, useRef, useCallback } from "react";
import { GLOSSARY } from "@/data/glossary";

export function ColLabel({
  children,
  glossary,
}: {
  children: React.ReactNode;
  glossary?: string;
}) {
  const [hover, setHover] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const definition = glossary ? GLOSSARY[glossary] : null;

  const handleEnter = useCallback(() => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setPos({ top: rect.top - 8, left: rect.left });
    }
    setHover(true);
  }, []);

  return (
    <span
      ref={triggerRef}
      className="relative inline-flex items-center cursor-default"
      onMouseEnter={handleEnter}
      onMouseLeave={() => setHover(false)}
    >
      <span className="text-data-xs font-mono font-medium text-ink-400 uppercase tracking-wide">
        {children}
      </span>
      {glossary && (
        <span className="ml-1 inline-flex items-center justify-center w-3 h-3 rounded-xs bg-accent-wash text-accent text-[8px] font-mono font-bold leading-none">
          ?
        </span>
      )}
      {hover && definition && pos && (
        <span
          className="fixed z-50 w-56 p-2.5 rounded-sm bg-bg-raised border border-edge text-data-xs text-ink-200 shadow-lg"
          style={{ top: pos.top, left: pos.left, transform: "translateY(-100%)" }}
        >
          {definition}
        </span>
      )}
    </span>
  );
}
