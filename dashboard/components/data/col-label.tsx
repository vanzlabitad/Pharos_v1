"use client";

import { useState } from "react";
import { GLOSSARY } from "@/data/glossary";

export function ColLabel({
  children,
  glossary,
}: {
  children: React.ReactNode;
  glossary?: string;
}) {
  const [hover, setHover] = useState(false);
  const definition = glossary ? GLOSSARY[glossary] : null;

  return (
    <span
      className="relative inline-flex items-center cursor-default"
      onMouseEnter={() => setHover(true)}
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
      {hover && definition && (
        <span className="absolute bottom-full left-0 mb-2 z-50 w-56 p-2.5 rounded-sm bg-bg-raised border border-edge text-data-xs text-ink-200 shadow-lg">
          {definition}
        </span>
      )}
    </span>
  );
}
