"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase";
import { useAuth } from "@/components/AuthProvider";
import { ShieldCheck, Sparkles, ArrowLeft } from "lucide-react";
import { Logo } from "@/components/Logo";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const supabase = createClient();

  useEffect(() => {
    if (!loading && user) {
      router.replace("/voices/new");
    }
  }, [user, loading, router]);

  const signInWithGoogle = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/voices/new`,
      },
    });
    if (error) console.error("OAuth error:", error.message);
  };

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center px-6 overflow-hidden transition-colors duration-500">
      {/* Premium Grain Overlay */}
      <div className="grainy-overlay" />

      {/* Moving Background (Aurora) - Matched with Landing */}
      <div className="aurora-container">
        <div className="aurora-blob top-[-20%] left-[-20%]" />
        <div className="aurora-blob bottom-[-20%] right-[-20%] [animation-delay:-10s]" />
        <div className="aurora-blob top-[10%] right-[-10%] [animation-delay:-20s]" />
      </div>

      {/* Back to Landing Link */}
      <Link 
        href="/" 
        className="absolute top-10 left-10 flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.4em] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] transition-all group z-50"
      >
        <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
        <span>Return</span>
      </Link>

      <div className="glass-card w-full max-w-sm p-12 text-center animate-fade-in-up border-[var(--glass-border)] relative z-10 shadow-2xl backdrop-blur-xl">
        {/* Logo */}
        <div className="mx-auto mb-10 flex justify-center">
            <Logo size={48} className="flex-col !gap-4" />
        </div>

        <div className="space-y-2 mb-10">
          <h1 className="text-2xl font-black tracking-tighter text-[var(--color-text-primary)]">
            Studio <span className="text-[var(--color-text-tertiary)] uppercase">Access</span>
          </h1>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--color-text-tertiary)]">
            Identity Gate
          </p>
        </div>

        <div className="space-y-4">
          <button
            onClick={signInWithGoogle}
            className="group flex w-full items-center justify-center gap-4 rounded-[var(--radius-pro)] border border-[var(--glass-border)] bg-[var(--color-bg-secondary)]/50 py-4 text-base font-bold text-[var(--color-text-primary)] transition-all hover:bg-[var(--color-text-primary)] hover:text-[var(--color-bg-primary)] hover:scale-[1.02] active:scale-[0.98] backdrop-blur-md"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Continue with Google
          </button>
        </div>

        <div className="mt-12 pt-8 border-t border-[var(--glass-border)] space-y-6">
           <div className="flex items-center justify-center gap-6">
              <div className="flex flex-col items-center gap-1">
                 <ShieldCheck className="h-4 w-4 text-[var(--color-text-tertiary)] opacity-30" />
                 <span className="text-[10px] font-bold text-[var(--color-text-tertiary)] uppercase tracking-widest">Secure</span>
              </div>
              <div className="flex flex-col items-center gap-1">
                 <Sparkles className="h-4 w-4 text-[var(--color-text-tertiary)] opacity-30" />
                 <span className="text-[10px] font-bold text-[var(--color-text-tertiary)] uppercase tracking-widest">Advanced</span>
              </div>
           </div>
           
           <p className="max-w-[240px] mx-auto text-[9px] font-bold text-[var(--color-text-tertiary)] uppercase tracking-widest leading-relaxed">
             Identity verification managed via <span className="text-[var(--color-text-secondary)]">OpenID Protocols</span>
           </p>
        </div>
      </div>
    </div>
  );
}
