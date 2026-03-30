-- ============================================================================
-- Parrot AI — Supabase Database Migration
-- Run this in the Supabase SQL Editor or via `supabase db push`
-- ============================================================================

-- 1. Voices table
CREATE TABLE IF NOT EXISTS public.voices (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name        text NOT NULL,
    transcript  text DEFAULT '',
    audio_path  text DEFAULT '',
    embedding_path text DEFAULT '',
    created_at  timestamptz DEFAULT now() NOT NULL
);

-- 2. Enable Row Level Security
ALTER TABLE public.voices ENABLE ROW LEVEL SECURITY;

-- 3. RLS Policies — users can only touch their own rows
CREATE POLICY "voices_select_own"
    ON public.voices FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "voices_insert_own"
    ON public.voices FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "voices_delete_own"
    ON public.voices FOR DELETE
    USING (auth.uid() = user_id);

CREATE POLICY "voices_update_own"
    ON public.voices FOR UPDATE
    USING (auth.uid() = user_id);

-- 4. Index for fast user-scoped queries
CREATE INDEX IF NOT EXISTS idx_voices_user_id ON public.voices (user_id);

-- 5. (Optional) Generations history table
CREATE TABLE IF NOT EXISTS public.generations (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    voice_id    uuid REFERENCES public.voices(id) ON DELETE SET NULL,
    prompt_text text NOT NULL,
    duration_ms int,
    created_at  timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.generations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "generations_select_own"
    ON public.generations FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "generations_insert_own"
    ON public.generations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ============================================================================
-- 6. Storage Buckets (Backend managed)
-- ============================================================================
INSERT INTO storage.buckets (id, name, public) 
VALUES ('voices-audio', 'voices-audio', false)
ON CONFLICT (id) DO NOTHING;

INSERT INTO storage.buckets (id, name, public) 
VALUES ('voices-embeddings', 'voices-embeddings', false)
ON CONFLICT (id) DO NOTHING;
