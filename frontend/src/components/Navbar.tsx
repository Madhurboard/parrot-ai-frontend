"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "./AuthProvider";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";

export default function Navbar() {
  const { user } = useAuth();
  const pathname = usePathname();

  // Only show on the Landing page. 
  // Login and Workspace pages should not have a global navbar.
  if (pathname !== "/") return null;

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 py-10">
      <div className="max-w-7xl mx-auto px-12 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center shrink-0">
          <Logo size={30} />
        </Link>

        {/* Right Section */}
        <div className="flex items-center gap-10">
          <ThemeToggle />
          {user ? (
            <Link 
              href="/voices/new" 
              className="text-[10px] font-black uppercase tracking-[0.3em] px-8 py-3 border border-[var(--color-text-primary)]/10 rounded-[var(--radius-pro)] hover:bg-[var(--color-text-primary)] hover:text-[var(--color-bg-primary)] transition-all"
            >
              Enter Studio
            </Link>
          ) : (
            <Link
              href="/login"
              className="text-[10px] font-black uppercase tracking-[0.3em] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-all"
            >
              Sign In
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
