/**
 * API client for the Crypto Tracker frontend.
 *
 * Prioiridad: CoinGecko directo (siempre CORS, sin cold start) → Render API.
 *
 * CoinGecko tiene CORS abierto (*), no requiere API key para reads básicos,
 * y responde rapido. Render tiene cold start (~5-15s) que puede hacer
 * timeout en el frontend estatico de GitHub Pages.
 */

const CG_BASE = "https://api.coingecko.com/api/v3";
const RENDER_BASE = "https://crypto-tracker-api-trwx.onrender.com";

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

// ──────────────────────────────────────────────
// Fetch helper con timeout
// ──────────────────────────────────────────────

async function _fetch<T>(url: string, timeoutMs = 8000): Promise<T> {
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), timeoutMs);
	try {
		const res = await fetch(url, { signal: controller.signal });
		clearTimeout(timer);
		if (!res.ok) throw new Error(`HTTP ${res.status}`);
		return (await res.json()) as T;
	} catch (err) {
		clearTimeout(timer);
		throw err;
	}
}

// ──────────────────────────────────────────────
// CoinGecko directo (fuente primaria)
// ──────────────────────────────────────────────

const SYMBOL_TO_ID: Record<string, string> = {
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
	uni: "uniswap",
	atom: "cosmos",
	ltc: "litecoin",
	bch: "bitcoin-cash",
	trx: "tron",
	xlm: "stellar",
	etc: "ethereum-classic",
	fil: "filecoin",
	apt: "aptos",
	sui: "sui",
	near: "near",
	icp: "internet-computer",
	vet: "vechain",
	aave: "aave",
	grt: "the-graph",
	sand: "the-sandbox",
	mana: "decentraland",
	axs: "axie-infinity",
	shib: "shiba-inu",
	pepe: "pepe",
	bonk: "bonk",
	wif: "dogwifhat",
	floki: "floki",
	dai: "dai",
	usdc: "usd-coin",
	usdt: "tether",
	cro: "crypto-com-chain",
	ton: "the-open-network",
	hbar: "hedera-hashgraph",
	algo: "algorand",
	inj: "injective-protocol",
	rune: "thorchain",
	pendle: "pendle",
	fet: "fetch-ai",
	tao: "bittensor",
	render: "render-token",
	strk: "starknet",
	sei: "sei-network",
	dydx: "dydx-chain",
	ena: "ethena",
	ondo: "ondo-finance",
	jup: "jupiter-exchange-solana",
	jto: "jito-governance-token",
};

// Reverse map: CoinGecko ID → symbol
const ID_TO_SYMBOL: Record<string, string> = {};
for (const [sym, id] of Object.entries(SYMBOL_TO_ID)) {
	ID_TO_SYMBOL[id] = sym;
}

// Cache de top coins: se fetchea 100 una vez, se reusa para todos los limites
let _topCache: CoinResult[] | null = null;
let _topCachePromise: Promise<CoinResult[]> | null = null;

function _resolveId(query: string): string {
	return SYMBOL_TO_ID[query.toLowerCase()] || query.toLowerCase();
}

async function _cgPrice(symbol: string): Promise<CoinResult | null> {
	const id = _resolveId(symbol);
	try {
		const data = await _fetch<
			Record<string, { usd: number; usd_24h_change?: number }>
		>(
			`${CG_BASE}/simple/price?ids=${id}&vs_currencies=usd&include_24hr_change=true`,
			5000,
		);
		const coin = data[id];
		if (!coin) return null;
		return {
			id,
			symbol,
			name: id.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
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

async function _cgPrices(ids: string[]): Promise<Map<string, CoinResult>> {
	const cgIds = ids.map((s) => _resolveId(s));
	try {
		const data = await _fetch<
			Record<string, { usd: number; usd_24h_change?: number }>
		>(
			`${CG_BASE}/simple/price?ids=${cgIds.join(",")}&vs_currencies=usd&include_24hr_change=true`,
			5000,
		);
		const map = new Map<string, CoinResult>();
		for (let i = 0; i < ids.length; i++) {
			const symbol = ids[i];
			const id = cgIds[i];
			const coin = data[id];
			if (coin) {
				map.set(symbol, {
					id,
					symbol,
					name: id.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
					rank: 0,
					price: coin.usd,
					change_24h: coin.usd_24h_change ?? null,
					volume_24h: null,
					market_cap: null,
					price_formatted: fmtPrice(coin.usd),
				});
			}
		}
		return map;
	} catch {
		return new Map();
	}
}

async function _cgTop(): Promise<CoinResult[]> {
	try {
		const list = await _fetch<any[]>(
			`${CG_BASE}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false`,
			8000,
		);
		return (list || []).map((c: any) => ({
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

async function _cgHistory(symbol: string, days = 7): Promise<HistoryPoint[]> {
	const id = _resolveId(symbol);
	try {
		const data = await _fetch<{ prices: [number, number][] }>(
			`${CG_BASE}/coins/${id}/market_chart?vs_currency=usd&days=${days}`,
			5000,
		);
		return (data.prices || []).map(([ts, price]) => ({ timestamp: ts, price }));
	} catch {
		return [];
	}
}

async function _cgSearch(query: string): Promise<CoinResult[]> {
	try {
		const data = await _fetch<{ coins: any[] }>(
			`${CG_BASE}/search?query=${encodeURIComponent(query)}`,
			5000,
		);
		return (data.coins || []).slice(0, 20).map((c: any) => ({
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
// Helpers
// ──────────────────────────────────────────────

/** Completar market_cap, volume, rank desde cache de top coins */
function _enrichFromCache(coin: CoinResult): CoinResult {
	if (!_topCache) return coin;
	const cached = _topCache.find(
		(c) =>
			c.symbol === coin.symbol ||
			c.id === coin.id ||
			c.name.toLowerCase() === coin.name.toLowerCase(),
	);
	if (!cached) return coin;
	return {
		...coin,
		market_cap: coin.market_cap ?? cached.market_cap,
		volume_24h: coin.volume_24h ?? cached.volume_24h,
		rank: coin.rank || cached.rank,
	};
}

// ──────────────────────────────────────────────
// Public API — CoinGecko primario, Render fallback
// ──────────────────────────────────────────────

export async function getPrice(query: string): Promise<CoinResult | null> {
	// 1) CoinGecko directo
	const cg = await _cgPrice(query);
	if (cg) {
		// Completar market_cap, volume, rank desde cache de top coins
		const enriched = _enrichFromCache(cg);
		return enriched;
	}
	// 2) Render API (fallback — trae datos de DB con mas campos)
	try {
		return await _fetch<CoinResult>(
			`${RENDER_BASE}/api/price/${encodeURIComponent(query)}`,
			8000,
		);
	} catch {
		return null;
	}
}

export async function getPrices(queries: string[]): Promise<CoinResult[]> {
	// 1) CoinGecko batch
	const cgMap = await _cgPrices(queries);
	const results: CoinResult[] = [];
	const missing: string[] = [];
	for (const q of queries) {
		if (cgMap.has(q)) {
			results.push(cgMap.get(q)!);
		} else {
			missing.push(q);
		}
	}
	// 2) Render para las que CoinGecko no tenia
	if (missing.length > 0) {
		try {
			const q = missing.map((s) => encodeURIComponent(s)).join(",");
			const renderResults = await _fetch<CoinResult[]>(
				`${RENDER_BASE}/api/prices?q=${q}`,
				8000,
			);
			// Merge manteniendo el orden original
			for (const rr of renderResults) {
				const idx = queries.findIndex(
					(q) => q.toLowerCase() === (rr.symbol?.toLowerCase() ?? ""),
				);
				if (idx >= 0 && !cgMap.has(queries[idx])) {
					results.push(rr);
				}
			}
		} catch {
			// Si Render falla, intentamos individual
			for (const m of missing) {
				const ind = await _cgPrice(m);
				if (ind) results.push(ind);
			}
		}
	}
	return results;
}

export async function getTop(limit = 10): Promise<CoinResult[]> {
	// Cache: si ya tenemos datos, filtrar por limite
	if (_topCache) {
		return _topCache.slice(0, limit);
	}
	// Evitar fetches paralelos duplicados
	if (_topCachePromise) {
		const all = await _topCachePromise;
		return all.slice(0, limit);
	}
	// 1) CoinGecko (fetchea 100 y cachea)
	_topCachePromise = _cgTop().then((coins) => {
		_topCache = coins;
		_topCachePromise = null;
		return coins;
	});
	const cg = await _topCachePromise;
	if (cg.length > 0) return cg.slice(0, limit);
	// 2) Render API (fallback — sin cache)
	try {
		return await _fetch<CoinResult[]>(
			`${RENDER_BASE}/api/top?limit=${limit}`,
			8000,
		);
	} catch {
		return [];
	}
}

export async function getHistory(
	query: string,
	days = 7,
): Promise<HistoryPoint[]> {
	// 1) CoinGecko directo
	const cg = await _cgHistory(query, days);
	if (cg.length > 0) return cg;
	// 2) Render API (fallback — historico cacheado)
	try {
		return await _fetch<HistoryPoint[]>(
			`${RENDER_BASE}/api/history/${encodeURIComponent(query)}?days=${days}`,
			8000,
		);
	} catch {
		return [];
	}
}

export async function searchCoins(query: string): Promise<CoinResult[]> {
	const q = query.toLowerCase().trim();
	// 1) Local search contra SYMBOL_TO_ID
	if (q.length >= 2) {
		const local: CoinResult[] = [];
		for (const [sym, id] of Object.entries(SYMBOL_TO_ID)) {
			if (
				sym.includes(q) ||
				id.includes(q) ||
				id.replace(/-/g, " ").includes(q)
			) {
				local.push({
					id,
					symbol: sym,
					name: id.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
					rank: 0,
					price: null,
					change_24h: null,
					volume_24h: null,
					market_cap: null,
					price_formatted: null,
				});
			}
		}
		if (local.length > 0) return local;
	}
	// 2) CoinGecko search
	const cg = await _cgSearch(q);
	if (cg.length > 0) return cg;
	// 3) Render API (fallback)
	try {
		return await _fetch<CoinResult[]>(
			`${RENDER_BASE}/api/search/${encodeURIComponent(q)}`,
			8000,
		);
	} catch {
		return [];
	}
}

// ──────────────────────────────────────────────
// Formatters
// ──────────────────────────────────────────────

export function fmtPrice(price: number): string {
	if (price >= 1)
		return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
	if (price >= 0.01) return `$${price.toFixed(4)}`;
	return `$${price.toFixed(8)}`;
}

export function fmtChange(change: number): string {
	const sign = change > 0 ? "+" : "";
	return `${sign}${change.toFixed(2)}%`;
}

export function fmtCap(value: number): string {
	if (value >= 1_000_000_000_000)
		return `$${(value / 1_000_000_000_000).toFixed(2)}T`;
	if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
	if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
	return `$${value.toLocaleString()}`;
}
