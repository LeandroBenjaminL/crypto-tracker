# Frontend Skill — Crypto Tracker (Astro)

## Stack

- **Framework**: Astro 6 (static output, `output: "static"`)
- **Charts**: Chart.js 4.x (client-side, import dinámico)
- **API Client**: `src/lib/api.ts` — fetch nativo con timeouts y fallbacks
- **Hosting**: GitHub Pages (`base: "/crypto-tracker"`)

## 🔴 REGLAS

### 1. CoinGecko es la fuente primaria, no Render

El frontend estático en GitHub Pages **no puede depender** de la API de Render
(cold start ~5-15s, sin garantía de disponibilidad). Siempre:

```
CoinGecko (directo, CORS ✓, rápido) → fallback → Render API
```

No al revés. La API de Render se usa para features que requieren DB
(favoritos, portfolio, histórico cacheado). Para precios en vivo, CoinGecko directo.

### 2. Tiempos de timeout generosos

Render puede tardar en cold start. Timeouts:

| Llamada | Timeout |
|---|---|
| CoinGecko directo | 5s |
| Render API | 8s (si es fallback, 15s si es primaria) |

### 3. getStaticPaths debe cubrir todas las monedas comunes

Para páginas de detalle (`/price/{slug}`), generar páginas estáticas para
al menos las top 100 monedas. Para cualquier otra, redirigir o mostrar 404
con carga dinámica.

### 4. Todas las URLs con prefijo `/crypto-tracker/`

En GitHub Pages con `base: "/crypto-tracker"`, TODAS las rutas absolutas
deben llevar ese prefijo. Usar `const BASE = "/crypto-tracker"` en scripts.

### 5. No dependencias pesadas en client-side

Astro corre en el server y el browser. Chart.js va con import dinámico.
Evitar librerías UI pesadas — el CSS inline es suficiente para el dark theme.

### 6. Favoritos en localStorage

Los favoritos se guardan en `localStorage` con key `crypto_favorites`.
No hay backend de favoritos para el frontend estático.

---

## Estructura

```
frontend/
  src/
    lib/api.ts         → API client (CoinGecko primario, Render fallback)
    layouts/           → BaseLayout.astro (nav, footer, CSS global)
    components/        → PriceCard.astro, CoinsTable.astro
    pages/
      index.astro      → Landing + hero + top 10
      price/[slug].astro → Detalle con chart.js
      top.astro        → Top 50/100
      search.astro     → Búsqueda client-side
      favorites.astro  → localStorage favorites
      404.astro        → Página 404 con detección de precio
```

## API Client (`src/lib/api.ts`)

```typescript
// Prioridad: CoinGecko directo → Render API
export async function getTop(limit = 10): Promise<CoinResult[]>
export async function getPrice(query: string): Promise<CoinResult | null>
export async function getPrices(queries: string[]): Promise<CoinResult[]>
export async function getHistory(query: string, days = 7): Promise<HistoryPoint[]>
export async function searchCoins(query: string): Promise<CoinResult[]>
```

Todas tienen fallback interno. Si CoinGecko falla, intentan Render.
Si Render también falla, devuelven array vacío o null — nunca crashean.
