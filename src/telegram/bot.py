"""
Telegram Bot para crypto-tracker.

Comandos:
  /start       — mensaje de bienvenida
  /price COIN  — precio actual (ej: /price btc)
  /top [N]     — top N monedas (default 10)
  /alert COIN above|below PRECIO — crear alerta de precio

Requiere:
  - TELEGRAM_BOT_TOKEN en el environment
  - DATABASE_URL para alertas
"""

from __future__ import annotations

import logging
import os

from telegram.ext import Application, CommandHandler, ContextTypes

from src.adapters.api_client import CoinGeckoClient
from src.config import settings
from src.core.price_service import PriceService
from telegram import Update

_logger = logging.getLogger("crypto-tracker.telegram")

# Token desde variable de entorno
_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_ALLOWED_USERS: list[int] = []

# Parsear lista de usuarios permitidos (opcional)
_users_raw = os.getenv("TELEGRAM_ALLOWED_USERS", "")
if _users_raw:
    _ALLOWED_USERS = [int(u.strip()) for u in _users_raw.split(",") if u.strip()]


def _is_allowed(user_id: int) -> bool:
    """Solo responde a usuarios permitidos (si la lista está configurada)."""
    return not _ALLOWED_USERS or user_id in _ALLOWED_USERS


# ------------------------------------------------------------------
# Handlers
# ------------------------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bienvenida."""
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ No autorizado")
        return
    await update.message.reply_text(
        "🤖 *Crypto Tracker Bot*\n\n"
        "Comandos:\n"
        "• `/price btc` — precio de una moneda\n"
        "• `/top 10` — top monedas\n"
        "• `/alert btc above 100000` — alerta de precio\n"
        "• `/help` — esta ayuda",
        parse_mode="Markdown",
    )


async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el precio de una moneda. Uso: /price btc"""
    if not _is_allowed(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Usá: /price <moneda>\nEj: /price btc")
        return

    query = context.args[0]
    client = CoinGeckoClient(
        base_url=settings.coingecko_base_url,
        api_key=settings.coingecko_api_key,
    )
    service = PriceService(api_client=client)

    try:
        result = service.get_price(query)
        if result.has_price() and result.price_data:
            pd = result.price_data
            indicator = "📈" if pd.change_24h > 0 else "📉" if pd.change_24h < 0 else "➖"
            msg = (
                f"*{result.coin.name} ({result.coin.symbol.upper()})*\n"
                f"💰 Precio: `${pd.price:,.2f}`\n"
                f"{indicator} 24h: `{pd.change_24h:+.2f}%`\n"
                f"💼 Market Cap: `${pd.market_cap:,.0f}`"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ No hay datos para '{query}'")
    except Exception as exc:
        _logger.warning("Error en /price %s: %s", query, exc)
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra las top monedas. Uso: /top 10"""
    if not _is_allowed(update.effective_user.id):
        return

    limit = 10
    if context.args:
        try:
            limit = min(int(context.args[0]), 50)
        except ValueError:
            pass

    client = CoinGeckoClient(
        base_url=settings.coingecko_base_url,
        api_key=settings.coingecko_api_key,
    )
    service = PriceService(api_client=client)

    try:
        results = service.list_top(limit=limit)
        lines = [f"🏆 *Top {limit}*"]
        for i, r in enumerate(results, 1):
            pd = r.price_data
            if pd:
                indicator = "🟢" if pd.change_24h > 0 else "🔴" if pd.change_24h < 0 else "⚪"
                lines.append(
                    f"{i}. *{r.coin.name}* ({r.coin.symbol.upper()})\n"
                    f"   ${pd.price:,.2f} {indicator} {pd.change_24h:+.2f}%"
                )
            if i >= 10:  # Telegram tiene límite de mensajes
                break

        await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")
    except Exception as exc:
        _logger.warning("Error en /top: %s", exc)
        await update.message.reply_text(f"❌ Error: {exc}")


async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Crea una alerta de precio. Uso: /alert btc above 100000"""
    if not _is_allowed(update.effective_user.id):
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "Usá: /alert <moneda> <above|below> <precio>\n"
            "Ej: /alert btc above 100000"
        )
        return

    coin, condition, price_str = context.args[0], context.args[1], context.args[2]

    if condition not in ("above", "below"):
        await update.message.reply_text("❌ Condición: 'above' o 'below'")
        return

    try:
        target_price = float(price_str)
    except ValueError:
        await update.message.reply_text("❌ Precio inválido")
        return

    if not settings.database_url:
        await update.message.reply_text("❌ No hay DB configurada para alertas")
        return

    from datetime import datetime, timezone

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from src.adapters.database import PriceAlertRow
    from src.core.price_service import SYMBOL_TO_ID

    coin_id = SYMBOL_TO_ID.get(coin.strip().lower(), coin.strip().lower())

    engine = create_engine(settings.database_url)
    row = PriceAlertRow(
        coin_id=coin_id,
        symbol=coin,
        target_price=target_price,
        condition=condition,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    with Session(engine) as session:
        session.add(row)
        session.commit()
        session.refresh(row)

    dir_str = "📈 supere" if condition == "above" else "📉 baje de"
    await update.message.reply_text(
        f"✅ Alerta #{row.id} creada:\n"
        f"   {coin} {dir_str} `${target_price:,.2f}`"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra la ayuda."""
    await start(update, context)


# ------------------------------------------------------------------
# Polling de alertas disparadas (para future uso)
# ------------------------------------------------------------------

_LAST_CHECKED: dict[int, int] = {}


def get_triggered_since_last(chat_id: int) -> list[dict]:
    """
    Devuelve alertas que se dispararon desde la última vez que
    se checkearon para este chat. (Para implementar notificaciones push)
    """
    from src.core.pipeline import get_pipeline_stats

    stats = get_pipeline_stats()
    if not stats or not stats.get("last_run"):
        return []

    # TODO: implementar seguimiento de alertas por chat_id
    return []


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> None:
    """Arranca el bot de Telegram."""
    if not _TOKEN:
        _logger.error("TELEGRAM_BOT_TOKEN no configurado")
        print("[!] TELEGRAM_BOT_TOKEN no está configurado")
        return

    app = Application.builder().token(_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("alert", cmd_alert))
    app.add_handler(CommandHandler("help", cmd_help))

    _logger.info("Bot de Telegram arrancando...")
    print("🤖 Bot de Crypto Tracker corriendo...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
