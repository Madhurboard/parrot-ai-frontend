import React from "react";

interface LogoProps {
  size?: number;
  className?: string;
  showText?: boolean;
  onlyText?: boolean;
}

export function Logo({ size = 32, className = "", showText = true, onlyText = false }: LogoProps) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      {!onlyText && (
        <div 
          style={{ width: size, height: size }} 
          className="relative flex items-center justify-center shrink-0"
        >
          <img 
            src="/logo.png" 
            alt="Parrot Logo" 
            className="w-full h-full object-contain grayscale opacity-80"
          />
        </div>
      )}
      {(showText || onlyText) && (
        <span className={`${size > 24 ? "text-xl" : "text-base"} font-bold tracking-tighter text-[var(--color-text-primary)] uppercase whitespace-nowrap`}>
          Parrot <span className="text-[var(--color-text-tertiary)]">AI</span>
        </span>
      )}
    </div>
  );
}
