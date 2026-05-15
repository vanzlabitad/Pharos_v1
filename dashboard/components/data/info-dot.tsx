"use client";

import { useState, useRef, useEffect } from "react";
import { GLOSSARY } from "@/data/glossary";

export function InfoDot({ glossary }: { glossary: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const definition = GLOSSARY[glossary] ?? `No definition for "${glossary}"`;

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <span ref={ref} className="relative inline-flex items-center ml-1">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-sm bg-accent-wash text-accent text-[9px] font-mono font-bold leading-none hover:bg-accent-muted transition-colors"
        aria-label={`Info: ${glossary}`}
      >
        ?
      </button>
      {open && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-64 p-3 rounded-md bg-bg-raised border border-edge text-data-xs text-ink-200 shadow-lg">
          <span className="block font-mono font-semibold text-accent mb-1">
            {glossary}
          </span>
          {definition}
        </span>
      )}
    </span>
  );
}
