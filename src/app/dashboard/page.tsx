"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import {
  Plus,
  Search,
  Mic2,
  Database,
  Clock,
  MoreVertical,
  Play,
  Trash2,
  Edit2,
  X,
  Check,
  PlusCircle,
  RefreshCcw,
  Loader2
} from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { API_BASE_URL } from "@/lib/api";

interface Voice {
  id: string;
  name: string;
  created_at: string;
}

export default function Dashboard() {
  const { user, session, loading: authLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && !user) router.replace("/");
  }, [user, authLoading, router]);

  const [voices, setVoices] = useState<Voice[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // State for Rename & Delete
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [activeMenu, setActiveMenu] = useState<string | null>(null);

  const fetchVoices = async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE_URL}/api/voices`, {
        headers: {
          "Authorization": `Bearer ${session.access_token}`,
          "Accept": "application/json"
        },
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setVoices(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.error("Dashboard fetch error:", err);
      setError(err.message || "Failed to connect to backend");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (session) {
      fetchVoices();
    }
  }, [session]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this voice permanently?")) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/voices/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${session?.access_token}` },
      });
      if (res.ok) fetchVoices();
    } catch (err) {
      console.error(err);
    }
  };

  const handleRename = async (id: string) => {
    if (!editName.trim()) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/voices/${id}/rename`, {
        method: "PATCH",
        headers: {
          "Authorization": `Bearer ${session?.access_token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ name: editName }),
      });
      if (res.ok) {
        setEditingId(null);
        fetchVoices();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const filteredVoices = voices.filter(v =>
    v.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="h-screen flex flex-col animate-fade-in max-w-[1600px] mx-auto overflow-hidden">
      
      {/* ── Page Header ── */}
      <header className="px-8 md:px-14 py-10 flex flex-col md:flex-row md:items-end justify-between gap-8 border-b border-[var(--glass-border)] shrink-0">
        <div className="space-y-3">
          <div className="flex items-center gap-2.5 text-[9px] font-black uppercase tracking-[0.4em] text-[var(--color-text-tertiary)]">
            <span>Voices: {voices.length}</span>
          </div>
          <h1 className="text-4xl font-black tracking-tighter uppercase text-[var(--color-text-primary)]">Voice Library.</h1>
          <p className="text-xs text-[var(--color-text-secondary)] font-medium opacity-60">Voice profile management.</p>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={fetchVoices}
            disabled={loading}
            className="p-4 border border-[var(--glass-border)] rounded-[var(--radius-pro)] hover:bg-[var(--color-bg-secondary)] transition-all active:scale-95 disabled:opacity-50"
          >
            <RefreshCcw className={`h-4 w-4 text-[var(--color-text-primary)] ${loading ? "animate-spin" : ""}`} />
          </button>
          <Link
            href="/voices/new"
            className="btn-primary !px-10 !py-5 text-[10px] font-black uppercase tracking-[0.4em] flex items-center gap-3 active:scale-[0.98] transition-all"
          >
            <PlusCircle className="h-4 w-4" />
            Create New
          </Link>
        </div>
      </header>

      {/* ── Error State ── */}
      {error && (
        <div className="p-6 border border-red-500/20 bg-red-500/5 rounded-[var(--radius-pro)] flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="h-2 w-2 bg-red-500 rounded-full animate-pulse" />
            <p className="text-[10px] font-black uppercase tracking-widest text-red-500/80">Connection Error: {error}</p>
          </div>
          <button onClick={fetchVoices} className="text-[9px] font-black uppercase tracking-widest text-[var(--color-text-primary)] hover:underline">Retry Connection</button>
        </div>
      )}

      {/* ── Scrollable Content ── */}
      <section className="flex-1 overflow-y-auto px-8 md:px-14 py-10 space-y-10 custom-scrollbar">
        <div className="flex items-center justify-between gap-6">
          <div className="relative flex-1 max-w-xl group">
            <Search className="absolute left-5 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-tertiary)]" />
            <input
              type="text"
              placeholder="SEARCH BY NAME..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-[var(--color-bg-secondary)] border border-[var(--glass-border)] rounded-[var(--radius-pro)] py-4 pl-14 pr-6 text-[10px] font-black uppercase tracking-widest text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-text-primary)] transition-all placeholder:opacity-20"
            />
          </div>
        </div>

        {/* ── Voice Grid ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-8">
          {loading && voices.length === 0 ? (
            [...Array(4)].map((_, i) => (
              <div key={i} className="h-56 rounded-[var(--radius-pro)] border border-[var(--glass-border)] bg-[var(--color-bg-secondary)]/10 animate-pulse" />
            ))
          ) : filteredVoices.length > 0 ? (
            filteredVoices.map((voice) => (
              <div
                key={voice.id}
                className="group relative flex flex-col justify-between p-8 border border-[var(--glass-border)] bg-[var(--color-bg-secondary)]/5 hover:bg-[var(--color-bg-secondary)]/10 hover:border-[var(--color-text-primary)] transition-all duration-300 rounded-[var(--radius-pro)]"
              >
                {/* Menu Toggle */}
                <div className="absolute top-4 right-4 z-10">
                  <button
                    onClick={() => setActiveMenu(activeMenu === voice.id ? null : voice.id)}
                    className="p-2 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] transition-colors rounded-[var(--radius-pro)] hover:bg-[var(--color-bg-secondary)]"
                  >
                    <MoreVertical className="h-4 w-4" />
                  </button>

                  {activeMenu === voice.id && (
                    <div className="absolute right-0 mt-2 w-40 bg-[var(--color-bg-primary)] border border-[var(--glass-border)] shadow-2xl rounded-[var(--radius-pro)] py-2 animate-in fade-in zoom-in-95 z-20">
                      <button
                        onClick={() => { setEditingId(voice.id); setEditName(voice.name); setActiveMenu(null); }}
                        className="w-full text-left px-4 py-2.5 text-[9px] font-black uppercase tracking-widest hover:bg-[var(--color-bg-secondary)] flex items-center gap-3"
                      >
                        <Edit2 className="h-3 w-3" />
                        Rename
                      </button>
                      <button
                        onClick={() => { handleDelete(voice.id); setActiveMenu(null); }}
                        className="w-full text-left px-4 py-2.5 text-[9px] font-black uppercase tracking-widest hover:bg-red-500/10 text-red-500 flex items-center gap-3"
                      >
                        <Trash2 className="h-3 w-3" />
                        Delete
                      </button>
                    </div>
                  )}
                </div>

                <div className="space-y-6">
                  <div className="h-10 w-10 bg-[var(--color-text-primary)]/5 border border-[var(--glass-border)] text-[var(--color-text-primary)] flex items-center justify-center rounded-[var(--radius-pro)] group-hover:bg-[var(--color-text-primary)] group-hover:text-[var(--color-bg-primary)] transition-all">
                    <Mic2 className="h-5 w-5" />
                  </div>

                  <div className="space-y-2">
                    {editingId === voice.id ? (
                      <div className="flex items-center gap-2">
                        <input
                          autoFocus
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleRename(voice.id)}
                          className="bg-transparent border-b border-[var(--color-text-primary)] text-lg font-black uppercase tracking-tighter focus:outline-none w-full"
                        />
                        <button onClick={() => handleRename(voice.id)} className="p-1 hover:text-emerald-500"><Check className="h-4 w-4" /></button>
                        <button onClick={() => setEditingId(null)} className="p-1 hover:text-red-500"><X className="h-4 w-4" /></button>
                      </div>
                    ) : (
                      <h3 className="font-black text-xl tracking-tighter uppercase text-[var(--color-text-primary)] truncate">{voice.name}</h3>
                    )}
                    <div className="flex items-center gap-2 text-[8px] font-black uppercase tracking-widest text-[var(--color-text-tertiary)] opacity-60">
                      <Clock className="h-3 w-3" />
                      {new Date(voice.created_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>

                <div className="mt-10 pt-6 border-t border-[var(--glass-border)]">
                  <Link
                    href={`/studio?voice=${voice.id}`}
                    className="w-full h-12 flex items-center justify-center gap-3 border border-[var(--color-text-primary)] text-[var(--color-text-primary)] hover:bg-[var(--color-text-primary)] hover:text-[var(--color-bg-primary)] text-[9px] font-black uppercase tracking-[0.3em] transition-all rounded-[var(--radius-pro)]"
                  >
                    <Play className="h-3 w-3 fill-current" />
                    Use in Studio
                  </Link>
                </div>
              </div>
            ))
          ) : !loading && (
            <div className="col-span-full py-24 flex flex-col items-center justify-center text-center space-y-8 border border-dashed border-[var(--glass-border)] rounded-[var(--radius-pro)] animate-fade-in">
              <Database className="h-12 w-12 text-[var(--color-text-tertiary)] opacity-20" />
              <div className="space-y-3">
                <h2 className="text-2xl font-black uppercase tracking-tight text-[var(--color-text-primary)]">Library Empty.</h2>
                <p className="text-xs text-[var(--color-text-secondary)] font-medium max-w-xs mx-auto">You haven't cloned any voices yet. Start your first project now.</p>
              </div>
              <Link
                href="/voices/new"
                className="btn-primary !px-12 !py-5 text-[10px] font-black uppercase tracking-[0.4em]"
              >
                Create First Voice
              </Link>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
