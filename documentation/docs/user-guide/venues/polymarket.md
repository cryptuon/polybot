# Polymarket

Polymarket is the primary venue supported by PolyBot. It's the largest crypto-native prediction market, built on the Polygon blockchain.

## Overview

| Feature | Details |
|---------|---------|
| Type | Crypto prediction market |
| Blockchain | Polygon (MATIC) |
| Settlement | USDC |
| Regulation | Offshore (not US-regulated) |
| Volume | $3+ billion monthly |

## Setup

### 1. Create a Polymarket Account

1. Visit [polymarket.com](https://polymarket.com)
2. Connect your Ethereum wallet
3. Deposit USDC to your Polymarket proxy wallet

### 2. Get Your Credentials

```bash
# Your wallet private key (keep secret!)
POLYMARKET_PRIVATE_KEY=your_private_key_without_0x

# Your proxy address (shown in Polymarket profile)
POLYMARKET_PROXY_ADDRESS=0x...
```

### 3. Generate API Credentials

```bash
# Auto-generate L2 API credentials
polybot auth --derive
```

This will output:
```
API Key: ...
Secret: ...
Passphrase: ...
```

Add these to your `.env`:
```bash
POLYMARKET_API_KEY=...
POLYMARKET_API_SECRET=...
POLYMARKET_API_PASSPHRASE=...
```

## Configuration

```bash
# Signature type (most users use 2)
# 0=EOA, 1=POLY_PROXY, 2=GNOSIS_SAFE
POLYMARKET_SIGNATURE_TYPE=2
```

## API Endpoints

PolyBot uses these Polymarket APIs:

| API | Purpose |
|-----|---------|
| CLOB | Order placement, positions |
| Gamma | Market data, events |
| Data | Historical data, trades |
| WebSocket | Real-time price updates |

## Rate Limits

Polymarket has rate limits per 10-second window:

| Endpoint | Limit |
|----------|-------|
| CLOB General | 9,000 |
| CLOB Order POST | 3,500 |
| CLOB Order DELETE | 3,000 |
| Gamma General | 4,000 |
| Data API | 1,000 |

PolyBot automatically manages rate limiting.

## Market Types

Polymarket offers:

- **Binary markets** - YES/NO outcomes
- **Multi-outcome** - Multiple possible outcomes
- **Scalar markets** - Numeric ranges

Most strategies focus on binary markets.

## Order Types

Supported order types:

- **Limit orders** - Specify price
- **Market orders** - Fill at best available
- **GTC** - Good till cancelled
- **FOK** - Fill or kill

## Fees

- **Maker fee**: 0% (provide liquidity)
- **Taker fee**: ~1% (take liquidity)
- **Gas fees**: Minimal on Polygon

## Best Practices

1. **Start with testnet** - Practice before using real funds
2. **Use shadow mode** - Test strategies without real trades
3. **Monitor positions** - Check the dashboard regularly
4. **Understand settlement** - Know how markets resolve
5. **Check liquidity** - Ensure sufficient volume before trading

## Troubleshooting

### "Invalid signature" errors

- Verify `POLYMARKET_SIGNATURE_TYPE` matches your wallet type
- Regenerate API credentials with `polybot auth --derive`

### "Insufficient balance" errors

- Check your USDC balance on Polymarket
- Ensure funds are in your proxy wallet, not main wallet

### Orders not filling

- Check if market has sufficient liquidity
- Verify your price is competitive
- Review order book depth
