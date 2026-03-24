# Platform API Reference

## Polymarket

**Type**: Crypto-native, built on Polygon (Ethereum L2)
**Settlement**: On-chain via smart contracts
**API Docs**: https://docs.polymarket.com
**Status**: Available globally (some geo-restrictions apply — check your jurisdiction)

### Key endpoints
- Markets: `GET https://gamma-api.polymarket.com/markets`
- Orderbook: `GET https://clob.polymarket.com/book?token_id={condition_id}`
- Place order: `POST https://clob.polymarket.com/order`
- Balance: `GET https://clob.polymarket.com/balance`
- WebSocket (live orderbook): `wss://clob.polymarket.com/ws`

### Auth
- Uses EIP-712 signing with your Polygon wallet private key
- Get API key from polymarket.com/settings → API Keys
- Required env vars: `POLYMARKET_API_KEY`, `POLYGON_PRIVATE_KEY`, `POLYGON_ADDRESS`

### Notes
- USDC on Polygon (bridge from Ethereum or buy directly on Polygon network)
- Uses CLOB (Central Limit Order Book) with off-chain matching, on-chain settlement
- Minimum order: ~$1 USDC
- Use LIMIT orders — market orders have high slippage on thin books

---

## Kalshi

**Type**: US-regulated exchange (CFTC-designated contract market)
**Settlement**: Cash settlement in USD
**API Docs**: https://trading-api.readme.io
**Demo env**: https://demo-api.kalshi.co (mock funds, safe for testing)
**Status**: US users only (check regulatory status in your state)

### Key endpoints
- Markets: `GET https://trading-api.kalshi.com/trade-api/v2/markets`
- Orderbook: `GET https://trading-api.kalshi.com/trade-api/v2/markets/{ticker}/orderbook`
- Place order: `POST https://trading-api.kalshi.com/trade-api/v2/portfolio/orders`
- Balance: `GET https://trading-api.kalshi.com/trade-api/v2/portfolio/balance`

### Auth
- API key + secret, passed as Authorization header: `Token {api_key}`
- Required env vars: `KALSHI_API_KEY`
- Sign up at kalshi.com → Settings → API

### Notes
- Prices in cents (0–100 scale, not 0–1 like Polymarket)
- Uses contract count (not dollar amounts directly) for order sizing
- Has a well-documented demo environment — use this first
- Kalshi recently overtook Polymarket in weekly volume
- US-regulated = more legal certainty for US traders

---

## pmxt (Unified Wrapper)

If you want a single interface for both platforms:
- GitHub: search "pmxt prediction market" — inspired by CCXT (crypto exchange library)
- Normalizes API differences between Polymarket and Kalshi
- Optional — the bot works fine calling each API directly

---

## Which exchange to use for which markets

| Market Type | Recommended Platform | Why |
|---|---|---|
| Crypto price markets | Polymarket | Higher liquidity, faster |
| Macro/Fed/CPI markets | Kalshi | More regulated, US-focused |
| Political markets | Either | Check which has more volume |
| Testing/paper trading | Kalshi demo | Free mock funds, safe |
