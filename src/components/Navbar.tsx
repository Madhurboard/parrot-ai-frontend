"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "./AuthProvider";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";

export default function Navbar() {
  const { user } = useAuth();
  const pathname = usePathname();

  // Only show on the Landing page and Login page.
  // Workspace pages use the Sidebar component for navigation.
  if (pathname !== "/" && pathname !== "/login") return null;

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-[var(--header-height)] md:h-20 glass-card !rounded-none border-t-0 border-x-0 flex items-center px-6 md:px-12 shadow-sm">
      <div className="w-full flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center shrink-0">
          <Logo size={24} />
        </Link>

        {/* Right Section */}
        <div className="flex items-center gap-4 md:gap-10">
          <ThemeToggle />
          {user ? (
            <Link 
              href="/studio" 
              className="text-[9px] font-black uppercase tracking-[0.2em] px-5 py-2.5 bg-[var(--color-text-primary)] text-[var(--color-bg-primary)] rounded-full hover:opacity-90 transition-all shadow-lg"
            >
              Studio
            </Link>
          ) : (
            <Link
              href="/login"
              className="text-[9px] font-black uppercase tracking-[0.2em] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-all"
            >
              Sign In
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
