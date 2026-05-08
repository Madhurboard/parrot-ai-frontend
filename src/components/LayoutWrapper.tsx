"use client";

import { usePathname } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import { useState } from "react";

export function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [isSidebarHovered, setIsSidebarHovered] = useState(false);
  const isWorkspace = pathname !== "/" && pathname !== "/login";

  return (
    <>
      {/* Global Sidebar (Hover-based) */}
      <Sidebar 
        isHovered={isSidebarHovered} 
        setIsHovered={setIsSidebarHovered} 
      />

      {/* Combined Header/Navigation */}
      <Navbar />
      
      {/* Main Workspace Wrapper */}
      <main className={`
        ${isWorkspace ? (isSidebarHovered ? "md:pl-[var(--sidebar-width)]" : "md:pl-16") : ""} 
        relative z-10 min-h-screen pb-32 md:pb-0 transition-[padding] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]
      `}>
         {children}
      </main>
    </>
  );
}
