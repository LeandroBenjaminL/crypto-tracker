import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  getPrice,
  getPrices,
  getTop,
  getHistory,
  searchCoins,
  fmtPrice,
  fmtChange,
  fmtCap,
} from "./api";

// ──────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────

function mockFetch(data: unknown, ok = true) {
  return vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    json: () => Promise.resolve(data),
  });
}

function mockFetchError() {
  return vi.fn().mockRejectedValue(new Error("network error"));
}

// Fresh import helper — resets module state (_topCache, etc.) for error-path tests
async function importFreshApi(): Promise<typeof import("./api")> {
  vi.resetModules();
  return await import("./api");
}

// ──────────────────────────────────────────────
// Format helpers (pure, no mock needed)
// ──────────────────────────────────────────────

describe("fmtPrice", () => {
  it("formats prices >= $1 with 2 decimals", () => {
    expect(fmtPrice(65432.1)).toBe("$65,432.10");
  });

  it("formats prices between $0.01 and $1 with 4 decimals", () => {
    expect(fmtPrice(0.1234)).toBe("$0.1234");
  });

  it("formats sub-cent prices with 8 decimals", () => {
    expect(fmtPrice(0.00005678)).toBe("$0.00005678");
  });

  it("handles zero (sub-cent formatting)", () => {
    expect(fmtPrice(0)).toBe("$0.00000000");
  });
});

describe("fmtChange", () => {
  it("adds + prefix for positive changes", () => {
    expect(fmtChange(5.3)).toBe("+5.30%");
  });

  it("keeps - prefix for negative changes", () => {
    expect(fmtChange(-2.1)).toBe("-2.10%");
  });

  it("returns 0.00% for zero (no prefix)", () => {
    expect(fmtChange(0)).toBe("0.00%");
  });
});

describe("fmtCap", () => {
  it("formats trillions", () => {
    expect(fmtCap(2_500_000_000_000)).toBe("$2.50T");
  });

  it("formats billions", () => {
    expect(fmtCap(123_456_789_000)).toBe("$123.46B");
  });

  it("formats millions", () => {
    expect(fmtCap(5_600_000)).toBe("$5.60M");
  });

  it("formats regular numbers", () => {
    expect(fmtCap(999_999)).toBe("$999,999");
  });
});

// ──────────────────────────────────────────────
// getTop — depends on _topCache module state
// ──────────────────────────────────────────────

describe("getTop", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", mockFetch([]));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns top coins from CoinGecko markets endpoint", async () => {
    const coins = [
      {
        id: "bitcoin", symbol: "btc", name: "Bitcoin", market_cap_rank: 1,
        current_price: 65432, price_change_percentage_24h: 2.5,
        total_volume: 30_000_000_000, market_cap: 1_200_000_000_000,
      },
      {
        id: "ethereum", symbol: "eth", name: "Ethereum", market_cap_rank: 2,
        current_price: 3456, price_change_percentage_24h: -1.2,
        total_volume: 15_000_000_000, market_cap: 420_000_000_000,
      },
    ];
    vi.stubGlobal("fetch", mockFetch(coins));

    const result = await getTop(2);
    expect(result).toHaveLength(2);
    expect(result[0].symbol).toBe("btc");
    expect(result[0].price).toBe(65432);
    expect(result[0].change_24h).toBe(2.5);
    expect(result[1].change_24h).toBe(-1.2);
  });
});

describe("getTop — error on first call (fresh module)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns empty array when CoinGecko fails on first fetch", async () => {
    vi.stubGlobal("fetch", mockFetchError());
    const api = await importFreshApi();
    const result = await api.getTop(10);
    expect(result).toEqual([]);
  });

  it("returns empty array on HTTP error on first fetch", async () => {
    vi.stubGlobal("fetch", mockFetch({}, false));
    const api = await importFreshApi();
    const result = await api.getTop(10);
    expect(result).toEqual([]);
  });
});

// ──────────────────────────────────────────────
// getPrice
// ──────────────────────────────────────────────

describe("getPrice", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns coin data from CoinGecko detail endpoint", async () => {
    const cgResponse = {
      id: "bitcoin", symbol: "bitcoin", name: "Bitcoin", market_cap_rank: 1,
      market_data: {
        current_price: { usd: 65000 },
        price_change_percentage_24h: 3.2,
        total_volume: { usd: 30_000_000_000 },
        market_cap: { usd: 1_200_000_000_000 },
      },
    };
    vi.stubGlobal("fetch", mockFetch(cgResponse));

    const result = await getPrice("btc");
    expect(result).not.toBeNull();
    expect(result!.symbol).toBe("btc");
    expect(result!.price).toBe(65000);
    expect(result!.change_24h).toBe(3.2);
  });

  it("returns null when coin is not found (network error)", async () => {
    vi.stubGlobal("fetch", mockFetchError());

    const result = await getPrice("nonexistent");
    expect(result).toBeNull();
  });
});

// ──────────────────────────────────────────────
// getPrices
// ──────────────────────────────────────────────

describe("getPrices", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns prices for multiple coins from simple/price", async () => {
    const simplePrice = {
      bitcoin: { usd: 65432, usd_24h_change: 1.5 },
      ethereum: { usd: 3456, usd_24h_change: -0.8 },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true, status: 200,
          json: () => Promise.resolve(simplePrice),
        })
        .mockResolvedValue({
          ok: true, status: 200,
          json: () => Promise.resolve([]),
        }),
    );

    const result = await getPrices(["btc", "eth"]);
    expect(result).toHaveLength(2);
    expect(result[0].symbol).toBe("btc");
    expect(result[0].price).toBe(65432);
    expect(result[1].symbol).toBe("eth");
    expect(result[1].price).toBe(3456);
  });

  it("returns empty array on network failure", async () => {
    vi.stubGlobal("fetch", mockFetchError());

    const result = await getPrices(["btc", "eth"]);
    expect(result).toEqual([]);
  });
});

// ──────────────────────────────────────────────
// getHistory
// ──────────────────────────────────────────────

describe("getHistory", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns history points from CoinGecko", async () => {
    const historyData = {
      prices: [
        [1700000000000, 42000],
        [1700086400000, 42500],
        [1700172800000, 41800],
      ],
    };
    vi.stubGlobal("fetch", mockFetch(historyData));

    const result = await getHistory("btc", 7);
    expect(result).toHaveLength(3);
    expect(result[0].price).toBe(42000);
    expect(result[0].timestamp).toBe(1700000000000);
  });

  it("returns empty array when CoinGecko fails", async () => {
    vi.stubGlobal("fetch", mockFetchError());

    const result = await getHistory("btc", 7);
    expect(result).toEqual([]);
  });
});

// ──────────────────────────────────────────────
// searchCoins
// ──────────────────────────────────────────────

describe("searchCoins", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("finds coins by symbol locally (no fetch needed)", async () => {
    const result = await searchCoins("btc");
    expect(result.length).toBeGreaterThan(0);
    expect(result[0].symbol).toBe("btc");
  });

  it("finds coins by partial name locally", async () => {
    const result = await searchCoins("bitcoin");
    expect(result.length).toBeGreaterThan(0);
    const btc = result.find((c) => c.symbol === "btc");
    expect(btc).toBeDefined();
    expect(btc!.name).toBe("Bitcoin");
  });

  it("returns empty from API when search query is too short (no local match)", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true, status: 200,
          json: () => Promise.resolve({ coins: [] }),
        })
        .mockResolvedValueOnce({
          ok: true, status: 200,
          json: () => Promise.resolve([]),
        }),
    );
    const result = await searchCoins("x");
    expect(Array.isArray(result)).toBe(true);
    expect(result.length).toBe(0);
  });
});
