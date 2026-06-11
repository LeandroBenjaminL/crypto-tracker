/**
 * Client-side render helpers for the Crypto Tracker frontend.
 *
 * These functions generate HTML strings for dynamic table rendering,
 * avoiding duplication across pages that render coin data client-side.
 */

import { fmtPrice, fmtChange, fmtCap } from "./api";
import type { CoinResult } from "./api";

export interface CoinsTableOptions {
	/** Table caption / heading (optional) */
	caption?: string;
	/** Link target for "View all" action (optional) */
	viewAllLink?: string;
	/** Show rank column (default: true) */
	showRank?: boolean;
	/** Show market cap column (default: true) */
	showMarketCap?: boolean;
	/** Show volume column (default: true) */
	showVolume?: boolean;
}

const BASE = "/crypto-tracker";

/**
 * Render a complete coins table as an HTML string.
 *
 * @param coins - Array of coin data to render
 * @param opts - Rendering options
 * @returns HTML string safe for innerHTML assignment
 */
export function renderCoinsTable(
	coins: CoinResult[],
	opts: CoinsTableOptions = {},
): string {
	const {
		caption,
		viewAllLink,
		showRank = true,
		showMarketCap = true,
		showVolume = true,
	} = opts;

	if (!coins || coins.length === 0) {
		return `<p class="text-muted">No se pudieron cargar los datos.</p>`;
	}

	const rows = coins
		.map(
			(c) => `
		<tr>
			${showRank ? `<td class="text-muted">${c.rank}</td>` : ""}
			<td>
				<a href="${BASE}/price/${c.symbol}" style="color: inherit; font-weight: 500">
					${c.name}
				</a>
				<span class="text-muted" style="margin-left: 0.3rem; font-size: 0.8rem">
					${c.symbol?.toUpperCase() ?? ""}
				</span>
			</td>
			<td>${c.price != null ? fmtPrice(c.price) : "—"}</td>
			<td class="${(c.change_24h ?? 0) >= 0 ? "green" : "red"}">
				${c.change_24h != null ? fmtChange(c.change_24h) : "—"}
			</td>
			${showMarketCap ? `<td style="text-align: right">${c.market_cap != null ? fmtCap(c.market_cap) : "—"}</td>` : ""}
			${showVolume ? `<td style="text-align: right">${c.volume_24h != null ? fmtCap(c.volume_24h) : "—"}</td>` : ""}
		</tr>`,
		)
		.join("");

	const headerCells = `
		${showRank ? "<th>#</th>" : ""}
		<th>Nombre</th>
		<th>Precio</th>
		<th>24h</th>
		${showMarketCap ? '<th style="text-align: right">Market Cap</th>' : ""}
		${showVolume ? '<th style="text-align: right">Volumen</th>' : ""}
	`;

	const headerExtra =
		viewAllLink || caption
			? `
		<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem">
			${caption ? `<h3 style="font-size: 0.9rem; opacity: 0.7">${caption}</h3>` : "<span></span>"}
			${
				viewAllLink
					? `<a href="${viewAllLink}" class="btn" style="font-size: 0.8rem">Ver todas →</a>`
					: ""
			}
		</div>`
			: "";

	return `
	<div class="card" style="overflow-x: auto">
		${headerExtra}
		<table>
			<thead><tr>${headerCells}</tr></thead>
			<tbody>${rows}</tbody>
		</table>
	</div>`;
}

/**
 * Render a grid of coin cards (for hero section, etc.).
 *
 * @param coins - Array of coin data to render
 * @returns HTML string with card grid
 */
export function renderCoinCards(coins: CoinResult[]): string {
	if (!coins || coins.length === 0) return "";

	return coins
		.map((c) => {
			const isUp = (c.change_24h ?? 0) >= 0;
			const color = isUp ? "var(--green)" : "var(--red)";
			const arrow = isUp ? "▲" : "▼";
			return `
		<div class="card" style="padding: 1.25rem">
			<div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1.5px; opacity: 0.5; margin-bottom: 0.25rem">
				${c.name}
			</div>
			<div style="font-size: 1.5rem; font-weight: 700; color: ${color}">
				${c.price != null ? fmtPrice(c.price) : "—"}
			</div>
			<div style="font-size: 0.85rem; color: ${color}">
				${arrow} ${fmtChange(c.change_24h ?? 0)}
			</div>
		</div>`;
		})
		.join("");
}
