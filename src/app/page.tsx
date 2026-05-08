"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { useEffect, useState } from "react";

export default function LandingPage() {
  const { user } = useAuth();
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const heights = [60, 85, 40, 92, 65, 75, 50, 90, 45, 80, 55, 70, 35, 95, 60, 85];

  return (
    <div className="relative flex flex-col items-center min-h-screen">
      {/* Premium Grain Overlay */}
      <div className="grainy-overlay" />

      {/* Moving Background (Aurora) - High visibility z-index */}
      <div className="aurora-container">
        <div className="aurora-blob top-[-20%] left-[-20%]" />
        <div className="aurora-blob bottom-[-20%] right-[-20%] [animation-delay:-10s]" />
        <div className="aurora-blob top-[10%] right-[-10%] [animation-delay:-20s]" />
      </div>

      {/* ── Hero Section ── */}
      <section className="relative w-full flex-1 flex flex-col items-center justify-center pt-32 pb-24 px-6 z-10">
        <div className="max-w-6xl mx-auto flex flex-col items-center text-center space-y-12">
          <div className="space-y-6 animate-fade-in">
            <h1 className="hero-title">
              Voice <br />
              <span className="text-[var(--color-text-tertiary)]">Intelligence.</span>
            </h1>
          </div>
          
          <p className="text-lg md:text-2xl text-[var(--color-text-secondary)] max-w-xl leading-snug font-medium">
            Professional cloning and synthesis. <br />
            Built for the future of audio.
          </p>

          <div className="flex items-center gap-4 pt-4">
            <Link
              href={user ? "/studio" : "/login"}
              className="btn-primary flex items-center gap-3 group"
            >
              Get Started
              <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
            </Link>
          </div>

          <div className="flex items-center gap-1.5 h-12 pt-8 opacity-20">
             {[...Array(16)].map((_, i) => (
               <div 
                 key={i} 
                 className="wave-bar" 
                 style={{ 
                   animationDelay: `${i * 0.1}s`,
                   height: isMounted ? `${heights[i % heights.length]}%` : "20%"
                 }} 
               />
             ))}
          </div>
        </div>
      </section>

      {/* ── Ultra Minimal Footer ── */}
      <footer className="relative w-full px-6 md:px-12 py-12 flex flex-col md:flex-row items-center justify-between gap-6 opacity-30 z-10">
        <div className="text-[9px] font-bold uppercase tracking-[0.3em]">
          Parrot AI © 2026
        </div>
        <div className="hidden md:block h-px flex-1 mx-12 bg-[var(--color-text-primary)]/10" />
        <div className="text-[9px] font-bold uppercase tracking-[0.3em]">
          Studio Engine v3
        </div>
      </footer>
    </div>
  );
}
