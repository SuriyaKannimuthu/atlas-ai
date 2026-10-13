# Atlas AI - frontend

Next.js 16 (App Router, Cache Components) console for the Atlas AI backend.

```bash
npm install
cp .env.example .env.local   # ATLAS_API_URL, ATLAS_API_KEY
npm run dev                  # http://localhost:3000
```

- The API key is read only on the server (`src/lib/atlas.ts` imports `server-only`). The browser talks to Next.js: Server Components for reads, Server Actions (`src/app/actions.ts`) for mutations, and `src/app/api/incidents/[id]/route.ts` for live polling.
- Theme tokens live in `src/app/globals.css`. Chart colors are validated categorical slots for the dark surface.
- Uncached data is always rendered inside `<Suspense>`, as Cache Components requires.

Checks: `npx tsc --noEmit && npm run lint && npm run build`.

See the [root README](../README.md) for the full project.
