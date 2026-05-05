"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { API_BASE_URL } from "@/lib/api";
import {
  Mic,
  Square,
  Upload,
  Loader2,
  AudioLines,
  AlertCircle,
  Zap,
  X,
  PlusCircle
} from "lucide-react";

export default function NewVoicePage() {
  const { user, session, loading: authLoading } = useAuth();
  const router = useRouter();

  const [name, setName] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/");
  }, [user, authLoading, router]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder.current = new MediaRecorder(stream);
      chunks.current = [];
      mediaRecorder.current.ondataavailable = (e) => chunks.current.push(e.data);
      mediaRecorder.current.onstop = () => {
        const mimeType = mediaRecorder.current?.mimeType || "audio/webm";
        const blob = new Blob(chunks.current, { type: mimeType });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
      };
      mediaRecorder.current.start();
      setIsRecording(true);
      setError("");
    } catch (err) {
      setError("Microphone access denied.");
    }
  };

  const stopRecording = () => {
    mediaRecorder.current?.stop();
    setIsRecording(false);
    mediaRecorder.current?.stream.getTracks().forEach((track) => track.stop());
  };

  const handleSubmit = async () => {
    if (!name || !audioBlob || !session) return;
    setLoading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("name", name);
      const ext = audioBlob.type.includes("webm") ? "webm" : audioBlob.type.includes("ogg") ? "ogg" : "wav";
      formData.append("file", audioBlob, `reference.${ext}`);
      const res = await fetch(`${API_BASE_URL}/api/voices`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
        body: formData,
      });
      if (!res.ok) throw new Error("Could not create voice.");
      setSuccess(true);
      setTimeout(() => router.push("/dashboard"), 1500);
    } catch (err) {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (authLoading) return null;

  return (
    <div className="h-screen bg-[var(--color-bg-primary)] flex flex-col items-center justify-center p-6 md:p-12 overflow-hidden">
      <div className="w-full max-w-xl space-y-12 animate-fade-in py-8">

        {/* Page Header */}
        <div className="space-y-3">
          <div className="flex items-center gap-3 text-[9px] font-black uppercase tracking-[0.4em] text-[var(--color-text-tertiary)]">
            <PlusCircle className="h-3.5 w-3.5" />
            <span>New Voice</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-black tracking-tighter text-[var(--color-text-primary)] uppercase">
            Create a New Voice.
          </h1>
          <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed max-w-sm opacity-60">
            Enter a name and record a sample to start cloning your voice.
          </p>
        </div>

        {/* Form Container */}
        <div className="space-y-10">
          {/* Step 01: Voice Name */}
          <div className="space-y-3">
            <label className="text-[8px] font-black uppercase tracking-[0.3em] text-[var(--color-text-tertiary)]">Voice Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My AI Voice"
              className="w-full bg-[var(--color-bg-secondary)] border border-[var(--glass-border)] rounded-[var(--radius-pro)] px-5 py-4 text-lg font-bold text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-text-primary)] transition-all placeholder:opacity-20"
            />
          </div>

          {/* Step 02: Voice Sample */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-[8px] font-black uppercase tracking-[0.3em] text-[var(--color-text-tertiary)]">Voice Sample</label>
              <span className="text-[8px] font-bold text-[var(--color-text-tertiary)] uppercase tracking-widest italic opacity-40">15 seconds minimum</span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={isRecording ? stopRecording : startRecording}
                className={`h-20 border transition-all flex flex-col items-center justify-center gap-1 rounded-[var(--radius-pro)] ${isRecording
                    ? "bg-red-500 border-red-500 text-white animate-pulse shadow-[0_0_20px_rgba(239,68,68,0.2)]"
                    : "bg-[var(--color-bg-secondary)] border-[var(--glass-border)] hover:border-[var(--color-text-primary)] text-[var(--color-text-primary)]"
                  }`}
              >
                {isRecording ? <Square className="h-3.5 w-3.5 fill-white" /> : <Mic className="h-4 w-4" />}
                <span className="text-[8px] font-black uppercase tracking-widest">{isRecording ? "Stop" : "Record"}</span>
              </button>

              <label className="h-20 border border-[var(--glass-border)] bg-[var(--color-bg-secondary)] hover:border-[var(--color-text-primary)] text-[var(--color-text-primary)] cursor-pointer transition-all flex flex-col items-center justify-center gap-1 rounded-[var(--radius-pro)]">
                <Upload className="h-4 w-4" />
                <span className="text-[8px] font-black uppercase tracking-widest">Upload</span>
                <input type="file" className="hidden" accept="audio/*" onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) { setAudioBlob(f); setAudioUrl(URL.createObjectURL(f)); }
                }} />
              </label>
            </div>

            {audioUrl && (
              <div className="p-4 border border-[var(--color-text-primary)]/10 bg-[var(--color-bg-secondary)] flex items-center justify-between rounded-[var(--radius-pro)] animate-in slide-in-from-top-1">
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 bg-[var(--color-text-primary)] text-[var(--color-bg-primary)] flex items-center justify-center rounded-[var(--radius-pro)]">
                    <AudioLines className="h-4 w-4" />
                  </div>
                  <div className="space-y-0">
                    <p className="text-[9px] font-black uppercase tracking-wider text-[var(--color-text-primary)]">Sample Ready</p>
                    <p className="text-[7px] font-bold text-[var(--color-text-tertiary)] uppercase tracking-widest opacity-40">Ready to save</p>
                  </div>
                </div>
                <button onClick={() => { setAudioBlob(null); setAudioUrl(null); }} className="p-2 hover:text-red-500 transition-all">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Primary Action */}
        <div className="pt-8 border-t border-[var(--glass-border)]">
          {loading ? (
            <div className="flex items-center justify-center gap-4 py-4 bg-[var(--color-bg-secondary)] border border-[var(--glass-border)] rounded-[var(--radius-pro)]">
              <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-primary)]" />
              <span className="text-[9px] font-black uppercase tracking-[0.4em] text-[var(--color-text-tertiary)]">Saving...</span>
            </div>
          ) : success ? (
            <div className="p-6 bg-[var(--color-text-primary)] text-[var(--color-bg-primary)] text-center rounded-[var(--radius-pro)]">
              <p className="text-sm font-black uppercase tracking-[0.4em]">Voice Saved.</p>
            </div>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!name || !audioBlob}
              className="btn-primary w-full !py-6 text-[11px] flex items-center justify-center gap-4 disabled:opacity-10 transition-all active:scale-[0.98]"
            >
              Create Voice
              <Zap className="h-3.5 w-3.5" />
            </button>
          )}

          {error && (
            <div className="mt-4 flex items-center gap-3 text-red-500 text-[8px] font-black uppercase tracking-widest justify-center">
              <AlertCircle className="h-3 w-3" />
              {error}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
