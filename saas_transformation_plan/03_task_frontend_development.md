# Task 3: Frontend Development (React / Next.js app)

## Objective
Replace the current generic HTML/JS or Gradio UI with a robust Next.js application designed as a SaaS.

## Sub-Tasks

1. **Initialize Project**
   - Run `npx create-next-app@latest frontend` inside the root repo or alongside it.
   - Use Tailwind CSS, App Router.
   - Install dependencies: `@supabase/supabase-js`, `lucide-react`, `zustand`, `axios`.

2. **Supabase Client & Context**
   - Create a singleton Supabase client using environment variables.
   - Build an Authentication Provider context to wrap the application and track the user's session.

3. **Page: Landing & Login**
   - Create `/` -> A beautiful SaaS hero section promoting Voice Cloning.
   - Create `/login` -> Simple centered Google OAuth integration. Once logged in, redirect to `/dashboard`.

4. **Page: Dashboard (`/dashboard`)**
   - Access restriction: Users must be authenticated.
   - View: Fetch the list of voices owned by the user from Supabase. Display them as cards.
   - Action: A button to "Create New Voice", navigating to the creation wizard.

5. **Page: Voice Creation (`/voices/new`)**
   - Implement an audio upload interface with recording capability.
   - Send the file with the user `access_token` to the FastAPI backend at `/api/voices`.
   - Show loading states. Once complete, redirect back to Dashboard.

6. **Page: Studio / Generation (`/studio`)**
   - Fetch available voices.
   - Provide a large text area for the prompt.
   - **SSE Integration**: Since the FastAPI backend streams generation via SSE (Server-Sent Events), the frontend needs to use the `EventSource` API or fetch with a readable stream to capture progress chunks and the final Base64 encoded WAV file to play to the user.

## Definition of Done
- Users can log in/out via Google.
- Users have isolated dashboards.
- Users can create a voice.
- Users can generate text and hear the streamed output.
