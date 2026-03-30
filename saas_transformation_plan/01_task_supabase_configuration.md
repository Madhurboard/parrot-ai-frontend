# Task 1: Supabase Configuration & Setup

## Objective
Set up the Supabase project to act as the central source of truth for Authentication, Database, and Object Storage.

## Sub-Tasks
1. **Project Initialization**
   - Create a new project in the Supabase Dashboard.
   - Note the `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`.

2. **Authentication Setup**
   - Navigate to Authentication > Providers.
   - Enable **Google** provider.
   - Configure Google Cloud OAuth credentials (Client ID and Secret) and set the callback URL to the Supabase redirect URI.

3. **Database Schema Creation**
   - Execute the following SQL (via Supabase SQL Editor):
     ```sql
     -- Voices Table
     CREATE TABLE public.voices (
         id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
         user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
         name text NOT NULL,
         transcript text,
         audio_path text,
         embedding_path text,
         created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
     );
     
     -- Enable RLS
     ALTER TABLE public.voices ENABLE ROW LEVEL SECURITY;
     
     -- RLS Policies
     CREATE POLICY "Users can insert their own voices" ON public.voices FOR INSERT WITH CHECK (auth.uid() = user_id);
     CREATE POLICY "Users can view their own voices" ON public.voices FOR SELECT USING (auth.uid() = user_id);
     CREATE POLICY "Users can delete their own voices" ON public.voices FOR DELETE USING (auth.uid() = user_id);
     ```

4. **Storage Buckets Setup**
   - Create two buckets:
     * `voices-audio` (To store the `.wav`/`.mp3` reference files)
     * `voices-embeddings` (To store the generated `.pt` tensor files)
   - Do NOT make them public.
   - Apply Storage RLS policies so users can only upload/download files belonging to their `auth.uid()` folder path (e.g., `voices-audio/{user_id}/{filename}`).

## Definition of Done
- Supabase endpoints and keys are available.
- Google Auth is functional.
- The `voices` table exists with RLS enforced.
- Storage buckets are created and secured.
