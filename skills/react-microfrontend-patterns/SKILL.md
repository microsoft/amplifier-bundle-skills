---
name: react-microfrontend-patterns
description: >
  Use when building a React frontend that dynamically loads independent
  bundles sharing a single React instance via import maps, needs frecency-based
  autocomplete, dynamic schema-driven forms, or Zustand state with localStorage.
---

# React Micro-Frontend Patterns

## The Pattern

**Problem:** You have multiple independently-built UI bundles that must share React at runtime, a form system driven by server-side schemas that change dynamically, and state that needs to persist in the browser and sync across tabs.

**Approach:** Import maps with Vite's `rollupOptions.external` for shared React, a useFrecency hook with exponential decay scoring, schema-to-React rendering with action-triggered schema refinement, and Zustand stores with localStorage sync.

Pattern proven in production across multiple React frontends and web services.

## Key Design Decisions

### 1. Import map + `rollupOptions.external` for shared React

When multiple independently-built bundles run on the same page, each gets its own copy of React. This causes the "dual React instance" bug: hooks break because the React instance that rendered the component is different from the one providing `useState`.

The fix: externalize React in every bundle's Vite config and provide it via an import map in the HTML:

```html
<!-- index.html -->
<script type="importmap">
{
  "imports": {
    "react": "https://esm.sh/react@19.2.4",
    "react-dom": "https://esm.sh/react-dom@19.2.4",
    "react-dom/client": "https://esm.sh/react-dom@19.2.4/client",
    "react/jsx-runtime": "https://esm.sh/react@19.2.4/jsx-runtime"
  }
}
</script>
```

```typescript
// vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      external: ['react', 'react-dom', 'react-dom/client', 'react/jsx-runtime'],
    },
  },
})
```

### 2. The Vite dev-mode problem

Vite's dev server ignores browser import maps — it pre-bundles CJS modules and serves them from `/.vite/deps/`. This means dynamically-loaded bundles that use bare `import React from 'react'` will resolve via the import map to a *different* React instance than the host app.

**Solutions:** Use `@vitejs/plugin-react` with careful configuration, or write a custom Vite plugin that serves shim modules redirecting bare specifiers to Vite's pre-bundled paths during dev. This is inherently complex — consult your Vite config documentation for the specifics of your setup.

### 3. useFrecency hook: group-by-suffix, exponential decay scoring

Frecency (frequency + recency) ranks autocomplete results by how often AND how recently a user selected them:

```typescript
// hooks/useFrecency.ts
const DECAY_HALF_LIFE_MS = 7 * 24 * 60 * 60 * 1000  // 1-week half-life
const STORAGE_KEY = 'frecency-data'
const _suggestionCache = new Map<string, string[]>()  // module-level perf cache

interface FrecencyEntry {
  score: number
  lastUsed: number  // timestamp ms
}

function computeScore(entry: FrecencyEntry, now: number): number {
  const ageFraction = (now - entry.lastUsed) / DECAY_HALF_LIFE_MS
  return entry.score * Math.pow(0.5, ageFraction)
}

function useFrecency(namespace: string) {
  const [entries, setEntries] = useState<Record<string, FrecencyEntry>>(() => {
    const stored = localStorage.getItem(`${STORAGE_KEY}:${namespace}`)
    return stored ? JSON.parse(stored) : {}
  })

  const getSuggestions = useCallback((fieldKey: string, allValues: string[]) => {
    const cacheKey = `${namespace}:${fieldKey}`
    if (_suggestionCache.has(cacheKey)) return _suggestionCache.get(cacheKey)!
    const now = Date.now()
    const sorted = [...allValues].sort((a, b) => {
      const sa = entries[a] ? computeScore(entries[a], now) : 0
      const sb = entries[b] ? computeScore(entries[b], now) : 0
      return sb - sa
    })
    _suggestionCache.set(cacheKey, sorted)
    return sorted
  }, [namespace, entries])

  const recordValue = useCallback((fieldKey: string, value: string) => {
    _suggestionCache.clear()
    setEntries(prev => {
      const now = Date.now()
      const existing = prev[value] ?? { score: 0, lastUsed: now }
      const updated = { ...prev, [value]: { score: existing.score + 1, lastUsed: now } }
      localStorage.setItem(`${STORAGE_KEY}:${namespace}`, JSON.stringify(updated))
      return updated
    })
  }, [namespace])

  const recordAll = useCallback((formData: Record<string, string>) => {
    _suggestionCache.clear()
    setEntries(prev => {
      const now = Date.now()
      const updated = { ...prev }
      for (const value of Object.values(formData)) {
        if (value) {
          const existing = updated[value] ?? { score: 0, lastUsed: now }
          updated[value] = { score: existing.score + 1, lastUsed: now }
        }
      }
      localStorage.setItem(`${STORAGE_KEY}:${namespace}`, JSON.stringify(updated))
      return updated
    })
  }, [namespace])

  return { getSuggestions, recordValue, recordAll }
}
```

The group-by-suffix pattern extracts a group name from the field key using a regex suffix match — not from URL path splits:

```typescript
// Group extraction uses /_([a-z]+)$/ on field keys:
function getGroupFromFieldKey(fieldKey: string): string | null {
  const match = fieldKey.match(/_([a-z]+)$/)
  return match ? match[1] : null  // e.g. "repo_name" → "name", "target_branch" → "branch"
}
```

> **Note:** The `/_([a-z]+)$/` regex extracts groups from field keys like `workspace_repo` → `repo`. Adapt this regex to your own field naming convention.

### 4. Zustand store with localStorage sync and Map-based collections

```typescript
// stores/appStore.ts
import { create } from 'zustand'

interface AppState {
  items: Map<string, Item>
  activeId: string | null
  events: Map<string, AppEvent[]>
  addEvent: (id: string, event: AppEvent) => void
  setItem: (item: Item) => void
}

const MAX_EVENTS_PER_ITEM = 1000  // event capping

const useAppStore = create<AppState>((set) => ({
  items: new Map(),
  activeId: null,
  events: new Map(),

  setItem: (item) => set((state) => {
    const next = new Map(state.items)
    next.set(item.id, item)
    // Persist to localStorage
    localStorage.setItem('items', JSON.stringify([...next.entries()]))
    return { items: next }
  }),

  addEvent: (id, event) => set((state) => {
    const next = new Map(state.events)
    const existing = next.get(id) || []
    // Event capping — keep most recent N events
    const updated = [...existing, event].slice(-MAX_EVENTS_PER_ITEM)
    next.set(id, updated)
    return { events: next }
  }),
}))
```

The localStorage sync pattern on init:

```typescript
// Hydrate from localStorage on store creation
const stored = localStorage.getItem('items')
if (stored) {
  try {
    const entries = JSON.parse(stored) as [string, Item][]
    initialItems = new Map(entries)
  } catch {
    // Corrupt localStorage — start fresh
  }
}
```

## Template / Starter Code

```typescript
// Minimal Zustand store with localStorage persistence
import { create } from 'zustand'

interface AppState {
  items: Record<string, Item>
  setItem: (id: string, item: Item) => void
}

const STORAGE_KEY = 'app-state'

function loadPersistedState(): Record<string, Item> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

const useStore = create<AppState>((set) => ({
  items: loadPersistedState(),
  setItem: (id, item) => set((state) => {
    const next = { ...state.items, [id]: item }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    return { items: next }
  }),
}))
```

## Gotchas & Lessons Learned

1. **The dual-React-instance problem is silent until hooks break.** Everything renders fine — components appear, props flow. But `useState` throws "Invalid hook call" because the component was rendered by React instance A but the hook tries to register with React instance B. The error message doesn't mention "two copies of React" — you have to know to look for it.

2. **Import maps don't work in Vite dev mode.** Vite's dev server pre-bundles dependencies using esbuild, which ignores the browser's import map. A dev shim is required. This is the most common source of "works in production, breaks in dev" issues with shared React.

3. **Event capping prevents memory exhaustion.** Without the `MAX_EVENTS_PER_ITEM` cap, a long-running instance would accumulate thousands of events in the Zustand store. The `.slice(-N)` pattern keeps only the most recent events. Choose N based on what the UI actually renders — if you only show the last 50 events, capping at 1000 is generous.

4. **localStorage has a ~5MB limit per origin.** Large Map serializations can exceed this. The Zustand persistence should either cap the total size or use IndexedDB for larger datasets. A common symptom: the app works until the localStorage quota is exceeded, then silently stops persisting.
