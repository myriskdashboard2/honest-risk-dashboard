# Honest Risk Dashboard

**See the risk of your fund/ETF portfolio in real money — before you buy.**

A local, private portfolio risk tool for retail investors. You enter what you
own (or what you're thinking of buying); it shows you — honestly — how much it
shakes, what a bad day/month costs in money, whether your funds actually
diversify each other, and what historical catastrophes would do to your
portfolio today.

No login. No account. No cloud. **It never touches real money and it never
tells you to buy anything.**

> 🇸🇪/🇬🇧 The app is bilingual — switch between Swedish and English with the 🌐
> button in the header.

## What it does

| Tab | What you get |
|-----|--------------|
| 🏦 **Holdings** | Enter your funds/ETFs by value (as your broker shows them). Built-in name search finds the cryptic Yahoo codes for regular mutual funds. |
| ⚖️ **Rebalancing** | Exact buy/sell amounts in SEK to get back to your target weights. Mechanical "buy low, sell high" — no feelings. |
| 🌡️ **Gauge** | Live risk meter (30-day volatility, annualized), refreshed every 5 minutes, with red/green arrows vs the previous reading, yesterday and start of month. |
| 🛡️ **Risk** | 5-year analysis: per-fund and portfolio volatility, Sharpe, worst historical fall, Value-at-Risk in money, and a correlation matrix that exposes false diversification. |
| 🌪️ **Stress Test** | Four historical crises (2008, dot-com, Covid, 2022 rate shock) replayed against your portfolio as it looks now, using per-fund betas measured on weekly data. |
| 🏆 **Track Record** | Your portfolio vs "own the world, do nothing" (100% VWCE) and a simple 60/40 — judged on risk-adjusted return (Sharpe). The most honest tab. |
| ❓ **Help** | Plain-language explanations of every measure, the formulas, and the people who invented them (Bachelier, Markowitz, Sharpe, …). |

## Philosophy

Most portfolio tools flatter you. This one is built on one rule: **show the
risk, never make promises.**

- Buys are measured at real historical prices; nothing is smoothed to look good.
- The benchmark tab will happily tell you a boring index fund beats your
  clever portfolio — if that is what the data says.
- Every number that is history is labeled as history. The app contains no
  predictions, no signals, no "buy now".

## Install (Windows)

1. Install [Python 3](https://www.python.org/downloads/) — check
   **"Add Python to PATH"** during installation.
2. Download this repository (green **Code** button → *Download ZIP*) and unzip.
3. Double-click **`INSTALLERA.bat`** (installs the Python libraries — one time).
4. Double-click **`skapa_genvagar.bat`** (creates desktop start/stop icons).
5. Click the **"Jane Street - STARTA"** icon — the dashboard opens in your
   browser at `http://127.0.0.1:8750`.

> The `.bat` files have Swedish names (the tool was born in Sweden):
> `INSTALLERA` = install, `STARTA_APP`/`STOPPA_APP` = start/stop the app,
> `skapa_genvagar` = create desktop shortcuts.

### Any platform (manual)

```bash
pip install -r requirements.txt
python app.py            # opens http://127.0.0.1:8750
```

## Privacy & data

- **Your portfolio never leaves your computer.** There is no server, no
  telemetry, no account. `portfolio.json` (your holdings) is created locally
  from `portfolio.example.json` on first run and is listed in `.gitignore`.
- Price data is fetched by *your* machine directly from Yahoo Finance via the
  open-source [yfinance](https://github.com/ranaroussi/yfinance) library.
  Data can be delayed or wrong; nothing is redistributed.

## Disclaimer

This app is **not financial advice** and never gives buy or sell
recommendations. All figures are based on **historical data** — history is not
a forecast, and future losses can exceed every "worst fall" and stress
scenario shown. Investments can rise and fall in value; you can lose all
invested capital. The software is provided **"as is"**, without warranty of
any kind — see [LICENSE](LICENSE). All investment decisions are your own.

## Support

The app is free and always will be. If it saved you from a bad decision (or a
flattering simulation), you can buy me a coffee:

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-yellow?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/YOUR_USERNAME)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue?logo=paypal)](https://paypal.me/myriskdashboard)

Supporting is entirely optional and gives no extra features, no premium
signals and no advice — the app stays identical for everyone.

## License

[MIT](LICENSE) © 2026 Michael Johnlin
