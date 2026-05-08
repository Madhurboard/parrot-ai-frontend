"use client";

import { Suspense, useEffect, useState, useRef, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { API_BASE_URL } from "@/lib/api";
import {
  Play,
  Download,
  Loader2,
  Mic,
  Plus,
  Trash2,
  Layers,
  Search,
  Cpu,
  AlertCircle,
  Waves,
  ChevronDown
} from "lucide-react";

interface Voice {
  id: string;
  name: string;
}

interface ProgressEvent {
  stage: string;
  percent: number;
  message: string;
}

interface DialogueLine {
  speaker: string;
  voiceId: string;
  text: string;
  type: "cloned" | "preset";
}

type StudioMode = "clone" | "design" | "dialogue";

interface HistoryItem {
  id: string;
  url: string;
  timestamp: Date;
  mode: string;
  name: string;
}

function StudioInner() {
  const { user, session, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [mode, setMode] = useState<StudioMode>("clone");
  const [activeSpeakerMenu, setActiveSpeakerMenu] = useState<number | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<string>("");
  const [prompt, setPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const [designInstruct, setDesignInstruct] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(true);

  const [dialogueLines, setDialogueLines] = useState<DialogueLine[]>([
    { speaker: "", voiceId: "", text: "", type: "cloned" },
  ]);

  const activeAudioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/");
  }, [user, authLoading, router]);

  useEffect(() => {
    const v = searchParams.get("voice");
    const m = searchParams.get("mode");
    if (v) setSelectedVoice(v);
    if (m && (m === "clone" || m === "design" || m === "dialogue")) setMode(m);
  }, [searchParams]);

  useEffect(() => {
    if (!session) return;
    fetch(`${API_BASE_URL}/api/voices`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then((r) => r.json())
      .then((data) => setVoices(Array.isArray(data) ? data : []))
      .catch(console.error);
  }, [session]);

  const handleModeChange = useCallback(async (newMode: StudioMode) => {
    setMode(newMode);
    setError("");

    if (!session) return;
    const targetModel = newMode === "design" ? "design" : "base";
    try {
      const formData = new FormData();
      formData.append("target_model", targetModel);
      await fetch(`${API_BASE_URL}/api/model/switch`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
        body: formData,
      });
    } catch (err) {
      console.error("Model switch failed:", err);
    }
  }, [session]);

  const addHistory = (url: string, itemMode: string) => {
    const newItem: HistoryItem = {
      id: Math.random().toString(36).substr(2, 9),
      url,
      timestamp: new Date(),
      mode: itemMode,
      name: `Clip #${history.length + 1}`
    };
    setHistory(prev => [newItem, ...prev]);
  };

  const generateVoice = async () => {
    if (!session) return;
    if (mode === "clone" && !selectedVoice) {
      setError("Please select a voice first.");
      return;
    }
    if (!prompt.trim() && mode !== "dialogue") {
      setError("Please enter text.");
      return;
    }

    setGenerating(true);
    setError("");
    setProgress({ stage: "Preparing", percent: 0, message: "Connecting..." });

    try {
      if (mode === "design") {
        const formData = new FormData();
        formData.append("text", prompt);
        formData.append("instruct", designInstruct);

        const response = await fetch(`${API_BASE_URL}/api/generate-design`, {
          method: "POST",
          headers: { Authorization: `Bearer ${session.access_token}` },
          body: formData,
        });

        if (!response.ok) throw new Error("Design failed.");
        const blob = await response.blob();
        addHistory(URL.createObjectURL(blob), "design");
        setProgress({ stage: "Done", percent: 100, message: "Created." });
      } else {
        const formData = new FormData();
        formData.append("prompt", prompt);
        if (selectedVoice) formData.append("voice_id", selectedVoice);

        const response = await fetch(`${API_BASE_URL}/api/generate-stream`, {
          method: "POST",
          headers: { Authorization: `Bearer ${session.access_token}` },
          body: formData,
        });

        if (!response.ok) throw new Error("Synthesis failed.");

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        if (!reader) throw new Error("No stream.");

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          
          // Split by double newline to separate complete events
          const events = buffer.split("\n\n");
          // Keep the last incomplete event in buffer
          buffer = events.pop() || "";

          for (const eventBlock of events) {
            if (!eventBlock.trim()) continue; // Skip empty blocks
            
            const lines = eventBlock.split("\n");
            let eventType = "";
            let eventData = "";
            
            for (const line of lines) {
              if (line.startsWith("event: ")) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith("data: ")) {
                eventData = line.slice(6);
              }
            }
            
            if (eventType && eventData) {
              try {
                const data = JSON.parse(eventData);
                if (eventType === "progress") {
                  setProgress({
                    stage: data.stage || "Processing",
                    percent: data.percent || 0,
                    message: data.message || "",
                  });
                } else if (eventType === "complete" && data.audio) {
                  const binaryString = atob(data.audio);
                  const bytes = new Uint8Array(binaryString.length);
                  for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                  }
                  const audioBlob = new Blob([bytes], { type: "audio/wav" });
                  addHistory(URL.createObjectURL(audioBlob), "clone");
                  setProgress({ stage: "Done", percent: 100, message: "Audio ready!" });
                } else if (eventType === "error") {
                  throw new Error(data.message || "Failed.");
                }
              } catch (parseErr) {
                console.error(`[SSE] Parse error for event ${eventType}:`, parseErr);
              }
            }
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error occurred.");
    } finally {
      setGenerating(false);
    }
  };

  const generateDialogue = async () => {
    if (!session) return;
    setGenerating(true);
    setError("");
    setProgress({ stage: "Stitching", percent: 0, message: "Processing..." });

    try {
      const response = await fetch(`${API_BASE_URL}/api/generate-dialogue`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          lines: dialogueLines.map(l => ({
            speaker: l.type === "cloned" ? l.voiceId : l.speaker,
            text: l.text,
            type: l.type
          }))
        }),
      });

      if (!response.ok) throw new Error("Synthesis failed.");
      const blob = await response.blob();
      addHistory(URL.createObjectURL(blob), "dialogue");
      setProgress({ stage: "Complete", percent: 100, message: "Done." });
    } catch (err) {
      setError("Synthesis failed.");
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    const handleClickOutside = () => setActiveSpeakerMenu(null);
    if (activeSpeakerMenu !== null) {
      window.addEventListener('click', handleClickOutside);
    }
    return () => window.removeEventListener('click', handleClickOutside);
  }, [activeSpeakerMenu]);

  if (authLoading) return <div className="flex h-screen items-center justify-center bg-[var(--color-bg-primary)]"><Loader2 className="h-6 w-6 animate-spin text-[var(--color-text-primary)]" /></div>;

  return (
    <div className="flex flex-col min-h-[100dvh] overflow-hidden bg-[var(--color-bg-primary)] text-[var(--color-text-primary)] pb-20 md:pb-0">

      {/* ── Header ── */}
      <header className="h-14 flex items-center justify-between px-4 sm:px-6 border-b border-[var(--glass-border)] bg-[var(--color-bg-primary)] shrink-0 z-40 gap-3">
        <div className="flex items-center gap-3 sm:gap-6 min-w-0">
          <button
            onClick={() => setIsLeftSidebarOpen(!isLeftSidebarOpen)}
            className="p-1.5 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] transition-colors border border-transparent hover:border-[var(--glass-border)] rounded-[var(--radius-pro)]"
          >
            <Layers className="h-4 w-4" />
          </button>
          <div className="flex flex-col">
            <span className="text-[8px] font-black uppercase tracking-[0.4em] text-[var(--color-text-tertiary)] opacity-40">Active</span>
            <span className="text-[10px] font-black uppercase tracking-[0.2em]">Studio</span>
          </div>
        </div>

        <div className="flex items-center gap-1 bg-[var(--color-bg-secondary)] p-1 rounded-[var(--radius-pro)] border border-[var(--glass-border)] overflow-x-auto max-w-[calc(100vw-12rem)] sm:max-w-none">
          {(["clone", "design", "dialogue"] as StudioMode[]).map((m) => (
            <button
              key={m}
              onClick={() => handleModeChange(m)}
              className={`px-2 sm:px-6 py-1 rounded-[var(--radius-pro)] text-[8px] sm:text-[9px] font-black uppercase tracking-[0.2em] sm:tracking-[0.3em] transition-all whitespace-nowrap ${mode === m
                ? "bg-[var(--color-text-primary)] text-[var(--color-bg-primary)] shadow-sm"
                : "text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
                }`}
            >
              {m}
            </button>
          ))}
        </div>

        <div className="hidden sm:flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 px-3 py-1 border border-[var(--glass-border)] rounded-[var(--radius-pro)]">
            <div className="h-1 w-1 bg-emerald-500 rounded-full animate-pulse" />
            <span className="text-[8px] font-black uppercase tracking-widest text-[var(--color-text-tertiary)]">Engine Online</span>
          </div>
        </div>
      </header>

      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">

        {/* ── Sidebar (Left) ── */}
        <aside className={`flex flex-col bg-[var(--color-bg-primary)] border-r border-[var(--glass-border)] transition-all duration-300 ${isLeftSidebarOpen && mode === "clone" ? "w-full md:w-64 h-52 md:h-auto" : "w-full md:w-0 h-0 overflow-hidden border-none"}`}>
          <div className="p-4 sm:p-6 space-y-4 sm:space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-[9px] font-black uppercase tracking-[0.3em] text-[var(--color-text-tertiary)]">Library</h2>
              <span className="text-[8px] font-black opacity-30">[{voices.length}]</span>
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--color-text-tertiary)]" />
              <input
                type="text"
                placeholder="SEARCH..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-[var(--color-bg-secondary)] border border-[var(--glass-border)] rounded-[var(--radius-pro)] py-2 pl-9 pr-3 text-[9px] font-black uppercase tracking-widest focus:outline-none focus:border-[var(--color-text-primary)] transition-all placeholder:opacity-20"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-4 pb-4 md:pb-6 space-y-1 custom-scrollbar">
            {voices.filter(v => v.name.toLowerCase().includes(searchTerm.toLowerCase())).map(v => (
              <button
                key={v.id}
                onClick={() => setSelectedVoice(v.id)}
                className={`w-full flex items-center gap-3 p-2.5 rounded-[var(--radius-pro)] transition-all border ${selectedVoice === v.id
                  ? "bg-[var(--color-text-primary)] border-[var(--color-text-primary)] text-[var(--color-bg-primary)]"
                  : "border-transparent hover:bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"}`}
              >
                <Mic className={`h-3 w-3 ${selectedVoice === v.id ? "opacity-100" : "opacity-30"}`} />
                <span className="truncate flex-1 text-left text-[9px] font-black uppercase tracking-widest">{v.name}</span>
              </button>
            ))}
          </div>
        </aside>

        {/* ── Main Canvas ── */}
        <main className="flex-1 flex flex-col overflow-hidden bg-[var(--color-bg-primary)] relative min-h-0">

          <div className="absolute inset-0 pointer-events-none opacity-[0.02] grayscale">
            <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-[var(--color-text-primary)] rounded-full blur-[150px] animate-pulse" />
          </div>

          <div className="flex-1 flex flex-col p-4 sm:p-6 md:p-12 z-10 overflow-y-auto custom-scrollbar">
            <div className="max-w-4xl mx-auto w-full flex-1 flex flex-col gap-8 animate-fade-in">

              <div className="space-y-1.5 shrink-0">
                <h2 className="text-[10px] font-black uppercase tracking-[0.5em] text-[var(--color-text-tertiary)]">
                  {mode === "clone" ? "Cloning" : mode === "design" ? "Design" : "Dialogue"}
                </h2>
                <div className="h-0.5 w-8 bg-[var(--color-text-primary)]" />
              </div>

              {/* Input Area - Scrollable */}
              <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar space-y-8">
                {mode === "design" && (
                  <div className="space-y-3">
                    <label className="text-[9px] font-black uppercase tracking-[0.3em] opacity-40">Voice Characteristics</label>
                    <input
                      type="text"
                      value={designInstruct}
                      onChange={(e) => setDesignInstruct(e.target.value)}
                      placeholder='E.G. "DEEP, PROFESSIONAL, COMMANDING"'
                      className="w-full p-4 rounded-[var(--radius-pro)] bg-[var(--color-bg-secondary)] border border-[var(--glass-border)] text-[9px] font-black uppercase tracking-widest focus:outline-none focus:border-[var(--color-text-primary)] transition-all"
                    />
                  </div>
                )}

                {mode === "dialogue" ? (
                  <div className="space-y-6">
                    <div className="flex items-center justify-between px-1">
                      <label className="text-[9px] font-bold uppercase tracking-[0.2em] opacity-30 text-[var(--color-text-primary)]">Script Segments</label>
                      <button 
                        onClick={() => setDialogueLines([...dialogueLines, { speaker: "", voiceId: "", text: "", type: "cloned" }])}
                        className="text-[9px] font-bold uppercase tracking-widest text-[var(--color-text-primary)] hover:opacity-50 transition-opacity flex items-center gap-2"
                      >
                        <Plus className="h-3 w-3" /> Add
                      </button>
                    </div>
                    
                    <div className="space-y-1 pr-2">
                      {dialogueLines.map((line, i) => (
                        <div key={i} className="group flex items-center gap-0 py-4 border-b border-[var(--color-text-primary)]/10 last:border-none transition-all hover:bg-[var(--color-bg-secondary)]/30 rounded-sm relative" onClick={(e) => e.stopPropagation()}>
                          <div className="w-32 shrink-0 pr-4 flex justify-end items-center gap-2 group/speaker cursor-pointer">
                            <div 
                              onClick={() => setActiveSpeakerMenu(activeSpeakerMenu === i ? null : i)}
                              className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.1em] text-[var(--color-text-primary)] hover:text-[var(--color-text-secondary)] transition-colors pr-2"
                            >
                              {line.speaker || "SPEAKER"}
                              <ChevronDown className={`h-2.5 w-2.5 transition-transform ${activeSpeakerMenu === i ? 'rotate-180' : ''} opacity-40`} />
                            </div>
                          </div>

                          {/* Precise Vertical Separator */}
                          <div className="w-[1px] h-4 bg-[var(--color-text-primary)] opacity-30 shrink-0 group-focus-within:opacity-100 transition-opacity relative">
                            {activeSpeakerMenu === i && (
                              <div className="absolute top-full left-0 mt-2 w-64 bg-[var(--color-bg-primary)] border border-[var(--glass-border)] rounded-[var(--radius-pro)] shadow-[0_30px_60px_rgba(0,0,0,0.6)] z-[999] py-1.5 overflow-hidden backdrop-blur-3xl animate-in fade-in slide-in-from-top-2 duration-200">
                                <div className="px-4 py-2.5 text-[8px] font-black opacity-30 uppercase tracking-[0.3em] border-b border-[var(--glass-border)] mb-1.5">Select Voice</div>
                                <div className="max-h-[280px] overflow-y-auto custom-scrollbar">
                                  {voices.map(v => (
                                    <button
                                      key={v.id}
                                      onClick={() => {
                                        const newList = [...dialogueLines];
                                        newList[i].speaker = v.name;
                                        newList[i].voiceId = v.id;
                                        newList[i].type = "cloned";
                                        setDialogueLines(newList);
                                        setActiveSpeakerMenu(null);
                                      }}
                                      className="w-full text-left px-4 py-3 text-[11px] font-black uppercase tracking-[0.15em] hover:bg-[var(--color-text-primary)] hover:text-[var(--color-bg-primary)] transition-all flex items-center justify-between group/item"
                                    >
                                      <span>{v.name}</span>
                                      <Mic className="h-3 w-3 opacity-0 group-hover/item:opacity-100 transition-opacity" />
                                    </button>
                                  ))}
                                  <div className="px-4 py-2 text-[7px] font-black opacity-20 uppercase tracking-[0.4em] mt-2 mb-1">System Presets</div>
                                  {["Nova", "Atlas"].map(p => (
                                    <button
                                      key={p}
                                      onClick={() => {
                                        const newList = [...dialogueLines];
                                        newList[i].speaker = p;
                                        newList[i].voiceId = p;
                                        newList[i].type = "preset";
                                        setDialogueLines(newList);
                                        setActiveSpeakerMenu(null);
                                      }}
                                      className="w-full text-left px-4 py-3 text-[11px] font-black uppercase tracking-[0.15em] hover:bg-[var(--color-text-primary)] hover:text-[var(--color-bg-primary)] transition-all opacity-60 hover:opacity-100"
                                    >
                                      {p}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                          
                          <div className="flex-1 pl-6 flex items-center">
                            <textarea
                              value={line.text}
                              rows={1}
                              onChange={(e) => {
                                const newList = [...dialogueLines];
                                newList[i].text = e.target.value;
                                setDialogueLines(newList);
                              }}
                              placeholder="Begin dialogue..."
                              className="w-full bg-transparent text-[14px] font-medium focus:outline-none placeholder:opacity-10 resize-none min-h-[1.5em] leading-[1.5] py-0"
                            />
                          </div>
                          
                          <button 
                            onClick={() => setDialogueLines(dl => dl.filter((_, idx) => idx !== i))} 
                            className="p-1 text-[var(--color-text-tertiary)] hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all ml-4"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>

                    {dialogueLines.length === 0 && (
                      <div className="py-12 border border-dashed border-[var(--glass-border)] rounded-[var(--radius-pro)] flex flex-col items-center justify-center opacity-10 cursor-pointer hover:opacity-20 transition-all" onClick={() => setDialogueLines([{ speaker: "", voiceId: "", text: "", type: "cloned" }])}>
                        <Plus className="h-5 w-5 mb-2" />
                        <span className="text-[8px] font-bold uppercase tracking-[0.2em]">Add first segment</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="h-full flex flex-col space-y-3">
                    <div className="flex items-center justify-between">
                      <label className="text-[9px] font-bold uppercase tracking-[0.1em] opacity-30 text-[var(--color-text-primary)]">Script</label>
                      <span className="text-[8px] font-medium tracking-widest opacity-20">{prompt.length} / 2000</span>
                    </div>
                    <textarea
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="Begin typing..."
                      className="flex-1 min-h-[90px] p-4 rounded-[var(--radius-pro)] bg-[var(--color-bg-secondary)] border border-[var(--glass-border)] text-lg font-medium tracking-tight focus:outline-none focus:border-[var(--color-text-primary)] focus:bg-[var(--color-bg-primary)] shadow-[inset_0_1px_3px_rgba(0,0,0,0.02)] resize-none leading-relaxed transition-all placeholder:opacity-10"
                    />
                  </div>
                )}
              </div>

              {/* Execution Dock - Fixed at Bottom of Main */}
              <div className="shrink-0 pt-6 border-t border-[var(--glass-border)] space-y-6">

                {/* Results Reel (Vertical Master Stack) */}
                <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4">
                  <div className="flex items-center justify-between">
                    <label className="text-[8px] font-bold uppercase tracking-[0.1em] opacity-30 text-[var(--color-text-primary)]">Recent Clips</label>
                    {history.length > 0 && (
                      <button onClick={() => setHistory([])} className="text-[8px] font-bold uppercase tracking-widest opacity-20 hover:opacity-100 transition-opacity">Clear</button>
                    )}
                  </div>

                  {history.length > 0 ? (
                    <div className="space-y-2 max-h-[280px] overflow-y-auto pr-2 custom-scrollbar">
                      {history.map((item) => (
                        <div key={item.id} className={`w-full p-4 rounded-[var(--radius-pro)] bg-[var(--color-bg-secondary)] border ${playingId === item.id ? "border-[var(--color-text-primary)]" : "border-[var(--glass-border)]"} flex items-center gap-6 group transition-all relative overflow-hidden`}>
                          {/* Background Accent */}
                          <div className={`absolute inset-0 bg-[var(--color-text-primary)] transition-opacity ${playingId === item.id ? "opacity-[0.03]" : "opacity-0 group-hover:opacity-[0.01]"}`} />

                          <div className="flex flex-col shrink-0 w-24 relative z-10">
                            <span className="text-[9px] font-black tracking-widest truncate">{item.name}</span>
                            <span className="text-[7px] font-medium opacity-30">{item.timestamp.toLocaleTimeString()}</span>
                          </div>

                          <div className="shrink-0 relative z-10">
                            <button
                              onClick={() => {
                                if (activeAudioRef.current) {
                                  if (playingId === item.id) {
                                    activeAudioRef.current.pause();
                                    setPlayingId(null);
                                  } else {
                                    activeAudioRef.current.src = item.url;
                                    activeAudioRef.current.play();
                                    setPlayingId(item.id);
                                  }
                                }
                              }}
                              className={`h-10 w-10 rounded-[var(--radius-pro)] flex items-center justify-center transition-all ${playingId === item.id ? "bg-[var(--color-text-primary)] text-[var(--color-bg-primary)]" : "bg-[var(--color-bg-primary)] text-[var(--color-text-primary)] border border-[var(--glass-border)] hover:border-[var(--color-text-primary)]"}`}
                            >
                              {playingId === item.id ? <div className="flex gap-0.5 items-end h-3"><div className="w-0.5 h-full bg-current animate-wave-sm" /><div className="w-0.5 h-1/2 bg-current animate-wave-sm delay-75" /><div className="w-0.5 h-3/4 bg-current animate-wave-sm delay-150" /></div> : <Play className="h-4 w-4 fill-current ml-0.5" />}
                            </button>
                          </div>

                          {/* Full Width Animated Waveform */}
                          <div className="flex-1 h-12 flex items-center justify-center gap-[2px] relative z-10 overflow-hidden">
                            {[...Array(80)].map((_, i) => (
                              <div
                                key={i}
                                className={`w-[1px] bg-[var(--color-text-primary)] rounded-full transition-all duration-700`}
                                style={{
                                  height: `${10 + Math.abs(Math.sin(i * 0.2)) * 80}%`,
                                  opacity: playingId === item.id ? (0.2 + Math.random() * 0.5) : (0.05 + Math.random() * 0.1),
                                  animation: playingId === item.id ? `wave 1.5s ease-in-out infinite ${i * 0.02}s` : 'none'
                                }}
                              />
                            ))}
                          </div>

                          <div className="flex items-center gap-2 shrink-0 relative z-10">
                            <span className="text-[7px] font-black uppercase tracking-[0.2em] px-2 py-1 bg-[var(--color-bg-primary)] border border-[var(--glass-border)] rounded-full opacity-40">{item.mode}</span>
                            <a
                              href={item.url}
                              download={`${item.name}.wav`}
                              className="h-10 w-10 flex items-center justify-center border border-[var(--glass-border)] rounded-[var(--radius-pro)] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:border-[var(--color-text-primary)] transition-all bg-[var(--color-bg-primary)]"
                              title="Download"
                            >
                              <Download className="h-4 w-4" />
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="w-full py-8 border border-dashed border-[var(--glass-border)] rounded-[var(--radius-pro)] flex flex-col items-center justify-center opacity-10">
                      <Waves className="h-4 w-4 mb-2" />
                      <span className="text-[8px] font-bold uppercase tracking-[0.2em]">Workspace Ready</span>
                    </div>
                  )}
                </div>

                <div className="flex gap-4 items-end">
                  <div className="flex-1">
                    {generating ? (
                      <div className="space-y-3 animate-pulse">
                        <div className="flex items-center justify-between text-[8px] font-black uppercase tracking-[0.4em]">
                          <span>{progress?.stage}</span>
                          <span className="text-sm italic">{progress?.percent}%</span>
                        </div>
                        <div className="w-full h-1 bg-[var(--color-bg-secondary)] rounded-full overflow-hidden">
                          <div className="h-full bg-[var(--color-text-primary)] transition-all duration-300" style={{ width: `${progress?.percent}%` }} />
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={mode === "dialogue" ? generateDialogue : generateVoice}
                        className="w-full py-4 bg-[var(--color-text-primary)] text-[var(--color-bg-primary)] rounded-[var(--radius-pro)] text-[10px] font-bold uppercase tracking-[0.4em] flex items-center justify-center gap-3 hover:opacity-90 active:scale-[0.99] transition-all shadow-lg"
                      >
                        <Cpu className="h-4 w-4" />
                        Create
                      </button>
                    )}
                  </div>
                </div>

                {error && <div className="p-3 border border-red-500/20 bg-red-500/5 text-red-500 text-[8px] font-black uppercase tracking-widest flex items-center gap-3 rounded-[var(--radius-pro)]">
                  <AlertCircle className="h-3 w-3" /> {error}
                </div>}
              </div>
            </div>
          </div>

          <audio
            ref={activeAudioRef}
            className="hidden"
            onPlay={() => { }}
            onPause={() => setPlayingId(null)}
            onEnded={() => setPlayingId(null)}
          />
        </main>
      </div>
    </div>
  );
}

export default function StudioPage() {
  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center bg-[var(--color-bg-primary)]"><Loader2 className="h-6 w-6 animate-spin text-[var(--color-text-primary)]" /></div>}>
      <StudioInner />
    </Suspense>
  );
}
