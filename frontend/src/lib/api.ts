/**
 * API client for the Crypto Tracker backend (deployed on Render).
 * Falls back to CoinGecko directly when the API is unreachable.
 */

// Base URL for the deployed Crypto Tracker API
const API_BASE = "https://crypto-tracker-api-trwx.onrender.com";

// CoinGecko direct fallback (pro API-free endpoints)
const CG_BASE = "https://api.coingecko.com/api/v3";

export interface CoinResult {
  id: string;
  symbol: string;
  name: string;
  rank: number;
  price: number | null;
  change_24h: number | null;
  volume_24h: number | null;
  market_cap: number | null;
  price_formatted: string | null;
}

export interface HistoryPoint {
  timestamp: number;
  price: number;
}

export interface FavoriteItem {
  symbol: string;
  added_at: string;
}

// ──────────────────────────────────────────────
// Internal fetch with timeout & error handling
// ──────────────────────────────────────────────

async function _fetch<T>(
  url: string,
  timeoutMs = 8000,
  fallback?: () => T | Promise<T>,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
  } catch (err) {
    clearTimeout(timer);
    if (fallback) return fallback();
    throw err;
  }
}

// ──────────────────────────────────────────────
// CoinGecko direct fallback (no API key needed)
// ──────────────────────────────────────────────

async function _cgPrice(symbol: string): Promise<CoinResult | null> {
  // Local symbol → id map (subset)
  const map: Record<string, string> = {
    btc: "bitcoin",
    eth: "ethereum",
    sol: "solana",
    xrp: "ripple",
    ada: "cardano",
    doge: "dogecoin",
    dot: "polkadot",
    avax: "avalanche-2",
    matic: "matic-network",
    link: "chainlink",
  };
  const id = map[symbol.toLowerCase()] || symbol.toLowerCase();
  try {
    const data: Record<string, { usd: number; usd_24h_change?: number }> =
      await _fetch(
        `${CG_BASE}/simple/price?ids=${id}&vs_currencies=usd&include_24hr_change=true`,
        5000,
      );
    const coin = data[id];
    if (!coin) return null;
    return {
      id,
      symbol,
      name: id.charAt(0).toUpperCase() + id.slice(1),
      rank: 0,
      price: coin.usd,
      change_24h: coin.usd_24h_change ?? null,
      volume_24h: null,
      market_cap: null,
      price_formatted: fmtPrice(coin.usd),
    };
  } catch {
    return null;
  }
}

async function _cgTop(limit = 10): Promise<CoinResult[]> {
  try {
    const list: any[] = await _fetch(
      `${CG_BASE}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=${limit}&page=1&sparkline=false`,
      8000,
    );
    return list.map((c) => ({
      id: c.id,
      symbol: c.symbol,
      name: c.name,
      rank: c.market_cap_rank ?? 0,
      price: c.current_price,
      change_24h: c.price_change_percentage_24h,
      volume_24h: c.total_volume,
      market_cap: c.market_cap,
      price_formatted: fmtPrice(c.current_price),
    }));
  } catch {
    return [];
  }
}

async function _cgHistory(
  symbol: string,
  days = 7,
): Promise<HistoryPoint[]> {
  const map: Record<string, string> = {
    btc: "bitcoin",
    eth: "ethereum",
    sol: "solana",
  };
  const id = map[symbol.toLowerCase()] || symbol.toLowerCase();
  try {
    const data: { prices: [number, number][] } = await _fetch(
      `${CG_BASE}/coins/${id}/market_chart?vs_currency=usd&days=${days}`,
      8000,
    );
    return (data.prices || []).map(([ts, price]) => ({
      timestamp: ts,
      price,
    }));
  } catch {
    return [];
  }
}

async function _cgSearch(query: string): Promise<CoinResult[]> {
  try {
    const data: { coins: any[] } = await _fetch(
      `${CG_BASE}/search?query=${encodeURIComponent(query)}`,
      5000,
    );
    return (data.coins || []).slice(0, 20).map((c) => ({
      id: c.id,
      symbol: c.symbol,
      name: c.name,
      rank: c.market_cap_rank ?? 0,
      price: null,
      change_24h: null,
      volume_24h: null,
      market_cap: null,
      price_formatted: null,
    }));
  } catch {
    return [];
  }
}

// ──────────────────────────────────────────────
// Public API
// ──────────────────────────────────────────────

export async function getPrice(
  query: string,
): Promise<CoinResult | null> {
  return _fetch<CoinResult>(
    `${API_BASE}/api/price/${encodeURIComponent(query)}`,
    6000,
    () => _cgPrice(query),
  );
}

export async function getPrices(
  queries: string[],
): Promise<CoinResult[]> {
  const q = queries.map((s) => encodeURIComponent(s)).join(",");
  try {
    return await _fetch<CoinResult[]>(
      `${API_BASE}/api/prices?q=${q}`,
      6000,
    );
  } catch {
    // Fallback individual
    const results = await Promise.allSettled(
      queries.map((s) => getPrice(s)),
    );
    return results
      .filter((r) => r.status === "fulfilled" && r.value)
      .map((r) => (r as PromiseFulfilledResult<CoinResult>).value);
  }
}

export async function getTop(limit = 10): Promise<CoinResult[]> {
  return _fetch<CoinResult[]>(
    `${API_BASE}/api/top?limit=${limit}`,
    8000,
    () => _cgTop(limit),
  );
}

export async function getHistory(
  query: string,
  days = 7,
): Promise<HistoryPoint[]> {
  return _fetch<HistoryPoint[]>(
    `${API_BASE}/api/history/${encodeURIComponent(query)}?days=${days}`,
    8000,
    () => _cgHistory(query, days),
  );
}

export async function searchCoins(query: string): Promise<CoinResult[]> {
  return _fetch<CoinResult[]>(
    `${API_BASE}/api/search/${encodeURIComponent(query)}`,
    6000,
    () => _cgSearch(query),
  );
}

export async function getHealth(): Promise<{ status: string }> {
  return _fetch(`${API_BASE}/api/health`, 4000);
}

// ──────────────────────────────────────────────
// Formatters
// ──────────────────────────────────────────────

export function fmtPrice(price: number): string {
  if (price >= 1) return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (price >= 0.01) return `$${price.toFixed(4)}`;
  return `$${price.toFixed(8)}`;
}

export function fmtChange(change: number): string {
  const sign = change > 0 ? "+" : "";
  return `${sign}${change.toFixed(2)}%`;
}

export function fmtCap(value: number): string {
  if (value >= 1_000_000_000_000) return `$${(value / 1_000_000_000_000).toFixed(2)}T`;
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  return `$${value.toLocaleString()}`;
}
