import { InfoDot } from "./info-dot";

export function Stat({
  label,
  value,
  glossary,
  accent: useAccent,
  size = "md",
}: {
  label: string;
  value: string | number;
  glossary?: string;
  accent?: boolean;
  size?: "sm" | "md" | "lg";
}) {
  const sizeClasses = {
    sm: "text-data-sm",
    md: "text-data-md",
    lg: "text-data-lg",
  };

  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-data-xs text-ink-400 font-mono uppercase tracking-wide flex items-center">
        {label}
        {glossary && <InfoDot glossary={glossary} />}
      </span>
      <span
        className={`font-mono font-semibold ${sizeClasses[size]} ${
          useAccent ? "text-accent" : "text-ink-100"
        }`}
      >
        {value}
      </span>
    </div>
  );
}
