# Task 4: Deployment & DevOps

## Objective
Take the localized development code and put it onto proper live environments: Render/Railway for the GPU backend and Vercel for the Next.js frontend.

## Sub-Tasks

1. **Backend Deploy (Render / Railway)**
   - Decide on platform: 
     - Render: Create a "Web Service", connect the GitHub repo, select Docker runtime, and choose a GPU instance tier.
     - Railway: Connect GitHub repo, map to the Dockerfile, and attach a Private GPU builder/runner.
   - **Environment Variables**: Apply `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, etc., in the platform's settings.
   - Expose the public URL of the backend service (e.g. `https://parrot-api.onrender.com`).

2. **Frontend Deploy (Vercel)**
   - Sync the `frontend/` directory or root (with root directory adjusted) to Vercel via GitHub integration.
   - Set environment variables: 
     - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
     - `NEXT_PUBLIC_API_URL` -> pointing to the URL obtained in the Backend deploy step.
   - Configure Vercel rewrite rules if you want the API to appear under `/api` strictly, or just use direct cross-origin calls.

3. **CORS Adjustment**
   - The FastAPI backend currently has `allow_origins=["http://localhost:3000", ...]`. Update this list via an Environment Variable `FRONTEND_URL` to point to the live Vercel domain to prevent CORS blocks.

4. **Verification Testing**
   - Test sign in on the live site.
   - Upload a 5s audio clip and create a voice profile.
   - Generate speech using the profile. Monitor Render/Railway instance logs to ensure no OOM (Out Of Memory) exceptions on the GPU.

## Definition of Done
- A publicly accessible frontend URL.
- Full end-to-end functionality working securely over HTTPS.
