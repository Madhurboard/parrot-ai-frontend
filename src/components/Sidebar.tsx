"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Mic2, 
  PlusCircle, 
  LogOut, 
  Library,
  User,
  ChevronUp
} from "lucide-react";
import { useAuth } from "./AuthProvider";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";

interface SidebarProps {
  isHovered: boolean;
  setIsHovered: (value: boolean) => void;
}

export default function Sidebar({ isHovered, setIsHovered }: SidebarProps) {
  const { user, signOut } = useAuth();
  const pathname = usePathname();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (pathname === "/" || pathname === "/login") return null;

  // New Order: Clone Voice -> Studio -> Voice Library
  const navLinks = [
    { name: "Clone Voice", href: "/voices/new", icon: PlusCircle },
    { name: "Voice Library", href: "/dashboard", icon: Library },
    { name: "Studio", href: "/studio", icon: Mic2 },
  ];

  const renderNavLink = (
    link: (typeof navLinks)[number],
    compact = false,
  ) => {
    const Icon = link.icon;
    const isActive = pathname === link.href;

    return (
      <Link
        key={link.name}
        href={link.href}
        className={`flex items-center ${compact ? "flex-col justify-center gap-1.5 px-1 py-2" : "h-12 w-full"} transition-all group relative ${
          isActive
            ? "text-[var(--color-text-primary)]"
            : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
        }`}
      >
        {isActive && !compact && (
          <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-[var(--color-text-primary)] rounded-r-full" />
        )}

        <div className={compact ? "flex items-center justify-center" : "w-16 flex items-center justify-center shrink-0"}>
          <div className={`rounded-[var(--radius-pro)] transition-colors ${compact ? "p-2.5" : "p-2"} ${isActive ? "bg-[var(--color-text-primary)] text-[var(--color-bg-primary)]" : "group-hover:bg-[var(--color-bg-secondary)]"}`}>
            <Icon className="h-4 w-4" />
          </div>
        </div>

        <div className={`flex-1 whitespace-nowrap transition-all duration-300 overflow-hidden ${compact ? "opacity-100" : isHovered ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-4"}`}>
          <span className={`font-bold uppercase tracking-widest ${compact ? "text-[8px]" : "text-[11px] pl-2"}`}>
            {link.name}
          </span>
        </div>
      </Link>
    );
  };

  return (
    <>
    <aside 
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setShowUserMenu(false);
      }}
      className={`fixed top-0 left-0 h-screen z-50 hidden md:flex flex-col border-r border-[var(--glass-border)] bg-[var(--color-bg-primary)] transition-[width] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] ${
        isHovered ? "w-[var(--sidebar-width)] shadow-2xl shadow-black/10" : "w-16"
      } ${showUserMenu ? "!overflow-visible" : "overflow-hidden"}`}
    >
      {/* Header */}
      <div className="h-24 flex items-center w-full shrink-0">
        <Link href="/" className="w-16 flex items-center justify-center shrink-0">
          <Logo size={32} showText={false} />
        </Link>
        <div className={`flex-1 transition-all duration-300 overflow-hidden ${isHovered ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-4"}`}>
           <Logo size={32} showText={true} onlyText={true} />
        </div>
      </div>

      {/* Nav Section */}
      <nav className="flex-1 space-y-2 pt-4">
        {navLinks.map((link) => renderNavLink(link))}
      </nav>

      {/* Footer Area */}
      <div className="p-0 border-t border-[var(--glass-border)] shrink-0">
        {/* Theme Toggle Slot */}
        <div className="h-16 flex items-center">
          <div className="w-16 flex items-center justify-center shrink-0">
             <ThemeToggle />
          </div>
          <div className={`flex-1 transition-all duration-300 ${isHovered ? "opacity-40" : "opacity-0"}`}>
             <span className="micro-label pl-2">Appearance</span>
          </div>
        </div>
        
        {user && (
          <div className="mb-4 relative" ref={menuRef}>
             {showUserMenu && (
               <div className="absolute bottom-full left-4 w-56 mb-2 bg-[var(--color-bg-primary)] border border-[var(--glass-border)] rounded-[var(--radius-pro)] shadow-2xl p-2 animate-in fade-in slide-in-from-bottom-2 z-[60]">
                 <div className="px-3 py-2 border-b border-[var(--glass-border)] mb-1">
                   <p className="text-[9px] font-bold text-[var(--color-text-tertiary)] uppercase tracking-widest mb-1">Authenticated as</p>
                   <p className="text-[11px] font-bold text-[var(--color-text-primary)] truncate">{user.email}</p>
                 </div>
                 <button 
                  className="flex items-center gap-3 w-full px-3 py-2.5 text-[10px] font-bold uppercase tracking-widest text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-secondary)] rounded-[var(--radius-pro)] transition-all"
                 >
                   <User className="h-3.5 w-3.5" />
                   Account Settings
                 </button>
                 <button 
                  onClick={() => signOut()}
                  className="flex items-center gap-3 w-full px-3 py-2.5 text-[10px] font-bold uppercase tracking-widest text-red-500 hover:bg-red-500/5 rounded-[var(--radius-pro)] transition-all"
                 >
                   <LogOut className="h-3.5 w-3.5" />
                   Sign Out
                 </button>
               </div>
             )}

             <button 
              onClick={() => setShowUserMenu(!showUserMenu)}
              className={`h-16 flex items-center w-full hover:bg-[var(--color-bg-secondary)] transition-all group ${showUserMenu ? "bg-[var(--color-bg-secondary)]" : ""}`}
             >
                <div className="w-16 flex items-center justify-center shrink-0">
                   <div className="h-8 w-8 rounded-[var(--radius-pro)] bg-[var(--color-text-tertiary)] flex items-center justify-center text-[var(--color-bg-primary)] font-bold text-[10px]">
                      {user.email?.charAt(0).toUpperCase()}
                   </div>
                </div>
                <div className={`flex-1 flex items-center justify-between min-w-0 transition-all duration-300 overflow-hidden ${isHovered ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-4"}`}>
                  <p className="text-[9px] font-bold truncate text-[var(--color-text-primary)] uppercase tracking-tight pl-2">
                    {user.email?.split("@")[0]}
                  </p>
                  <ChevronUp className={`h-3 w-3 mr-4 text-[var(--color-text-tertiary)] transition-transform ${showUserMenu ? "rotate-180" : ""}`} />
                </div>
             </button>
          </div>
        )}
      </div>
    </aside>

    {/* Mobile Header */}
    <div className="fixed top-0 inset-x-0 z-[60] md:hidden glass-card !rounded-none border-t-0 border-x-0 h-[var(--header-height)] flex items-center justify-between px-6 shadow-sm">
      <Link href="/" className="flex items-center">
        <Logo size={24} showText={true} />
      </Link>
      
      <div className="flex items-center gap-4">
        <ThemeToggle />
        {user ? (
          <div className="relative" ref={menuRef}>
            {showUserMenu && (
              <div className="absolute right-0 top-full mt-3 w-64 glass-card p-2 shadow-2xl animate-in fade-in slide-in-from-top-2">
                <div className="px-4 py-3 border-b border-[var(--glass-border)] mb-1">
                  <p className="text-[8px] font-black uppercase tracking-[0.2em] text-[var(--color-text-tertiary)] mb-1">Account</p>
                  <p className="text-[11px] font-black text-[var(--color-text-primary)] truncate">{user.email}</p>
                </div>
                <button className="flex w-full items-center gap-3 rounded-[var(--radius-pro)] px-4 py-3 text-[10px] font-black uppercase tracking-[0.1em] text-[var(--color-text-secondary)] transition-all hover:bg-[var(--color-bg-secondary)] hover:text-[var(--color-text-primary)]">
                  <User className="h-3.5 w-3.5" />
                  Settings
                </button>
                <button
                  onClick={() => signOut()}
                  className="flex w-full items-center gap-3 rounded-[var(--radius-pro)] px-4 py-3 text-[10px] font-black uppercase tracking-[0.1em] text-red-500 transition-all hover:bg-red-500/5"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  Sign Out
                </button>
              </div>
            )}

            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-bg-secondary)] border border-[var(--glass-border)] overflow-hidden transition-transform active:scale-95"
            >
               <div className="h-full w-full flex items-center justify-center bg-[var(--color-text-primary)] text-[var(--color-bg-primary)] text-[10px] font-black">
                 {user.email?.charAt(0).toUpperCase()}
               </div>
            </button>
          </div>
        ) : (
          <Link href="/login" className="h-9 w-9 flex items-center justify-center rounded-full bg-[var(--color-bg-secondary)] border border-[var(--glass-border)] text-[var(--color-text-secondary)] transition-all hover:text-[var(--color-text-primary)]">
            <User className="h-4 w-4" />
          </Link>
        )}
      </div>
    </div>

    {/* Mobile Bottom Nav */}
    <nav className="fixed inset-x-6 bottom-6 z-50 md:hidden glass-card !rounded-full shadow-2xl p-1.5 px-3 border border-white/10">
      <div className="flex items-center justify-between gap-1 h-[48px]">
        {navLinks.map((link) => {
          const Icon = link.icon;
          const isActive = pathname === link.href;
          return (
            <Link
              key={link.name}
              href={link.href}
              className={`flex-1 flex flex-col items-center justify-center gap-0.5 transition-all rounded-full h-full ${
                isActive 
                ? "bg-[var(--color-text-primary)] text-[var(--color-bg-primary)] shadow-md scale-105" 
                : "text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
              }`}
            >
              <Icon className={`${isActive ? "h-3.5 w-3.5" : "h-4 w-4"}`} />
              {isActive && (
                <span className="text-[6px] font-black uppercase tracking-[0.1em]">
                  {link.name.split(' ')[0]}
                </span>
              )}
            </Link>
          );
        })}
      </div>
    </nav>
    </>
  );
}
