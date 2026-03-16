# Kalshi

Kalshi is the first CFTC-regulated prediction market exchange in the United States.

## Overview

| Feature | Details |
|---------|---------|
| Type | Regulated prediction market |
| Regulation | CFTC (US) |
| Settlement | USD |
| Access | US residents (with restrictions) |
| Contract type | Event contracts |

## Setup

### 1. Create a Kalshi Account

1. Visit [kalshi.com](https://kalshi.com)
2. Complete identity verification (KYC)
3. Fund your account

### 2. Get API Credentials

1. Log into Kalshi
2. Go to Settings > API
3. Generate API key and secret

### 3. Configure PolyBot

```bash
KALSHI_API_KEY=your_api_key
KALSHI_API_SECRET=your_api_secret
KALSHI_ENVIRONMENT=demo  # or "prod"
KALSHI_COMPLIANCE_APPROVED=false  # Set true only after review
```

## Configuration

```bash
# Enable Kalshi venue
VENUES_KALSHI_ENABLED=true

# Environment (demo for testing, prod for live)
KALSHI_ENVIRONMENT=demo

# Must be explicitly approved for production
KALSHI_COMPLIANCE_APPROVED=false
```

!!! warning "Compliance"
    Before enabling `KALSHI_COMPLIANCE_APPROVED=true`, ensure you understand Kalshi's terms of service and any applicable regulations.

## Market Types

Kalshi offers event contracts on:

- Politics and elections
- Economics (Fed rates, GDP, etc.)
- Weather events
- Financial markets
- Current events

## Differences from Polymarket

| Aspect | Kalshi | Polymarket |
|--------|--------|------------|
| Regulation | CFTC regulated | Offshore |
| Currency | USD | USDC (crypto) |
| KYC | Required | Optional |
| Access | US (mostly) | Non-US |
| Fees | ~1-2% | ~1% |
| Settlement | USD bank | Crypto wallet |

## API Rate Limits

Kalshi has more conservative rate limits than Polymarket. PolyBot handles this automatically.

## Risk Considerations

- **Regulatory risk**: Rules may change
- **Access restrictions**: Some markets restricted by state
- **Lower liquidity**: Generally less volume than Polymarket
- **USD settlement**: Different from crypto markets

## CLI Commands

```bash
# Check Kalshi connection
polybot venues status kalshi

# List Kalshi markets
polybot markets --venue kalshi
```

## Best Practices

1. **Use demo first** - Test thoroughly before live trading
2. **Understand regulations** - Know what's allowed in your state
3. **Monitor compliance** - Keep up with regulatory changes
4. **Consider fees** - Factor into strategy profitability
5. **Manage settlement** - Understand USD withdrawal process
