import aiohttp
import asyncio
import os
import anthropic
import logging

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


async def fetch_tsetmc(symbol: str) -> dict | None:
    """Fetch stock data from TSETMC"""
    try:
        # Search for the instrument
        search_url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()

            instruments = data.get("instrumentSearch", [])
            if not instruments:
                return None

            # Get the first match
            instrument = instruments[0]
            isin = instrument.get("insCode", "")

            if not isin:
                return None

            # Fetch price data
            price_url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{isin}/0"
            async with session.get(price_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                price_data = await resp.json()

            prices = price_data.get("closingPriceDaily", [])
            if not prices:
                return None

            # Get last 30 days
            recent = prices[:30]

            return {
                "name": instrument.get("lVal18AFC", symbol),
                "symbol": instrument.get("lVal30", symbol),
                "prices": [p.get("pClosing", 0) for p in recent],
                "volumes": [p.get("qTotTran5J", 0) for p in recent],
                "last_price": recent[0].get("pClosing", 0) if recent else 0,
                "yesterday_price": recent[1].get("pClosing", 0) if len(recent) > 1 else 0,
                "high": recent[0].get("priceMax", 0) if recent else 0,
                "low": recent[0].get("priceMin", 0) if recent else 0,
                "volume": recent[0].get("qTotTran5J", 0) if recent else 0,
            }

    except Exception as e:
        logger.error(f"TSETMC fetch error: {e}")
        return None


def calculate_rsi(prices: list, period: int = 14) -> float | None:
    """Calculate RSI indicator"""
    if len(prices) < period + 1:
        return None

    gains, losses = [], []
    for i in range(1, period + 1):
        diff = prices[i - 1] - prices[i]  # newest first
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calculate_ma(prices: list, period: int) -> float | None:
    """Calculate Moving Average"""
    if len(prices) < period:
        return None
    return round(sum(prices[:period]) / period, 0)


def detect_trend(prices: list) -> str:
    """Simple trend detection"""
    if len(prices) < 5:
        return "نامشخص"

    recent_avg = sum(prices[:5]) / 5
    older_avg = sum(prices[5:10]) / 5 if len(prices) >= 10 else prices[-1]

    change_pct = (recent_avg - older_avg) / older_avg * 100

    if change_pct > 3:
        return "صعودی 📈"
    elif change_pct < -3:
        return "نزولی 📉"
    else:
        return "رنج ➖"


def find_support_resistance(prices: list) -> tuple[list, list]:
    """Find basic support and resistance levels"""
    if len(prices) < 5:
        return [], []

    sorted_prices = sorted(prices)
    n = len(sorted_prices)

    supports = sorted_prices[:3]
    resistances = sorted_prices[-3:]

    supports = [int(p) for p in supports]
    resistances = [int(p) for p in resistances]

    return supports, resistances


async def analyze_stock(symbol: str) -> str:
    """Main function to analyze a stock"""
    # Fetch real data
    data = await fetch_tsetmc(symbol)

    if not data:
        # Use AI with disclaimer
        return await ai_analysis_no_data(symbol)

    prices = data["prices"]

    # Calculate indicators
    rsi = calculate_rsi(prices)
    ma20 = calculate_ma(prices, 20)
    ma50 = calculate_ma(prices, 50)
    trend = detect_trend(prices)
    supports, resistances = find_support_resistance(prices)

    last = data["last_price"]
    yesterday = data["yesterday_price"]
    change_pct = ((last - yesterday) / yesterday * 100) if yesterday else 0

    # Build context for AI
    context = f"""
داده‌های واقعی سهم {symbol} ({data['name']}):
- آخرین قیمت: {last:,} ریال
- تغییر روز: {change_pct:.1f}%
- بیشترین: {data['high']:,} | کمترین: {data['low']:,}
- حجم معاملات: {data['volume']:,}
- روند ۵ روزه: {trend}
- RSI (14): {rsi if rsi else 'ناکافی'}
- MA20: {ma20:,.0f} | MA50: {ma50:,.0f}
- حمایت‌ها: {', '.join(f'{s:,}' for s in supports[:2])}
- مقاومت‌ها: {', '.join(f'{r:,}' for r in resistances[-2:])}
"""

    return await ai_format_analysis(symbol, data['name'], context)


async def ai_analysis_no_data(symbol: str) -> str:
    """When no real data available"""
    return (
        f"⚠️ نتونستم داده‌های واقعی {symbol} رو پیدا کنم.\n\n"
        f"لطفاً نماد رو دقیق بنویس (مثل: خودرو، فولاد، شپنا)\n"
        f"یا مستقیم در TSETMC.com چک کن."
    )


async def ai_format_analysis(symbol: str, name: str, market_data: str) -> str:
    """Use Claude to format and enrich the analysis"""
    try:
        prompt = f"""بر اساس داده‌های زیر، یک تحلیل کوتاه و مفید برای سهم {symbol} بنویس.

{market_data}

فرمت پاسخ دقیقاً اینطور باشد:

🧠 *وضعیت کلی {name}:*
(یک جمله درباره روند)

📈 *روند قیمت:*
(توضیح ساده)

🧱 *حمایت‌ها:*
• ...
• ...

🚧 *مقاومت‌ها:*
• ...
• ...

📊 *اندیکاتورها:*
RSI: ...
MA20 vs MA50: ...
حجم: ...

💡 *نتیجه‌گیری:*
(جمع‌بندی + احتمال حرکت بعدی)

⚠️ این تحلیل صرفاً جهت اطلاع است و سیگنال خرید/فروش نیست."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    except Exception as e:
        logger.error(f"AI format error: {e}")
        return f"⚠️ خطا در پردازش تحلیل {symbol}"
