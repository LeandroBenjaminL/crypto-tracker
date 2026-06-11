# Crypto Tracker — Frontend (Astro 6)

Frontend estático para [Crypto Tracker](https://github.com/LeandroBenjaminL/crypto-tracker). Construido con [Astro 6](https://astro.build/).

**Live:** [leandrobenjaminl.github.io/crypto-tracker](https://leandrobenjaminl.github.io/crypto-tracker/)

---

## ✨ Features

| Página | Ruta | Descripción |
|--------|------|-------------|
| **Inicio** | `/` | Market overview con cards de precios |
| **Precio** | `/price/[slug]` | Precio detalle con tabla |
| **Top** | `/top` | Top monedas por market cap |
| **Búsqueda** | `/search` | Buscar monedas por nombre/símbolo |
| **Favoritos** | `/favorites` | Monedas favoritas |
| **404** | `/*` | Página no encontrada |

## 🧞 Comandos

```bash
cd frontend

npm install          # Instalar dependencias
npm run dev          # Servidor local → localhost:4321
npm run build        # Build producción → dist/
npm run preview      # Preview del build local
```

## 🏗️ Estructura

```
frontend/
├── src/
│   ├── components/
│   │   ├── CoinsTable.astro     # Tabla de precios reutilizable
│   │   ├── PriceCard.astro      # Card de precio individual
│   │   └── ThemeToggle.astro    # Toggle dark/light theme
│   ├── layouts/
│   │   └── BaseLayout.astro     # Layout base (header + footer + theme)
│   ├── lib/
│   │   ├── api.ts              # Cliente HTTP para la API REST
│   │   └── render.ts           # Helpers de renderizado compartidos
│   ├── pages/
│   │   ├── index.astro         # Home
│   │   ├── price/[slug].astro  # Precio detalle (SSG dinámico)
│   │   ├── top.astro           # Top monedas
│   │   ├── search.astro        # Búsqueda
│   │   ├── favorites.astro     # Favoritos
│   │   └── 404.astro           # Página no encontrada
│   └── styles/
│       └── global.css          # Estilos globales + temas claro/oscuro
├── public/                     # Assets estáticos
├── astro.config.mjs
└── package.json
```

## 🌐 API

El frontend consume la API REST del proyecto:

```typescript
// src/lib/api.ts
const API_BASE = import.meta.env.PUBLIC_API_URL || "http://localhost:8000";
```

En producción apunta a `https://crypto-tracker-api-trwx.onrender.com`. En desarrollo se puede configurar via `PUBLIC_API_URL`.

## 🚀 Deploy

El deploy es automático via GitHub Actions (`.github/workflows/frontend.yml`):

1. Push a `main` con cambios en `frontend/`
2. GitHub Actions corre `npm ci && npm run build`
3. Sube `dist/` como Pages artifact
4. GitHub Pages deploya automáticamente

URL: `https://leandrobenjaminl.github.io/crypto-tracker/`

## 🎨 Tema

Soporte dark/light mode via `ThemeToggle` component. Usa CSS custom properties definidas en `global.css`. La preferencia se persiste en `localStorage`.
