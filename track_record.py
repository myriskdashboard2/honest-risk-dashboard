# -*- coding: utf-8 -*-
"""
MERITLISTA + BENCHMARK
======================
Svarar pa den enda fraga som betyder nagot: skapar min portfolj faktiskt
varde, eller borde jag bara aga VWCE?

Jamfor din portfolj (vikter fran portfolio.json) mot tva benchmarks:
  * 100% VWCE        - att bara aga hela varlden (ren aktie-referens)
  * Enkel 60/40      - 60% VWCE + 40% rantor (den lata standardportfoljen)

Domer bade pa AVKASTNING och RISKJUSTERAT (Sharpe). Slar du inte den
enkla portfoljen riskjusterat -> forenkla, komplexiteten kostar dig pengar.

Loggar du ditt RIKTIGA konto i mitt_konto.json raknas ocksa din faktiska
tidsviktade avkastning mot benchmark over samma period.

Kor:  python track_record.py   (eller dubbelklicka MERITLISTA.bat)
"""

import os
import sys
import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("Saknar yfinance. Kor: pip install yfinance")
    sys.exit(1)

from risk_engine import las_config

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "portfolio.json")
KONTO = os.path.join(HERE, "mitt_konto.json")
HANDELSDAGAR = 252
BENCH_VWCE = "VWCE.DE"
BENCH_BOND = "AGGH.MI"

os.system("")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass
ROD, GRON, GRA, GUL, FET, NOLL = (
    "\033[91m", "\033[92m", "\033[90m", "\033[93m", "\033[1m", "\033[0m")


# ---------- Data ----------

def hamta(tickers, start):
    data = yf.download(list(set(tickers)), start=start, interval="1d",
                       auto_adjust=True, progress=False, group_by="column")
    if isinstance(data.columns, pd.MultiIndex):
        priser = data["Close"].copy()
    else:
        priser = data[["Close"]].copy()
        priser.columns = [tickers[0]]
    return priser.ffill().dropna()


def buy_hold_kurva(priser, vikter_dict, kapital):
    """Vardekurva om man kopt vikterna vid start och HALLIT (utan ombalansering)."""
    delar = []
    for t, w in vikter_dict.items():
        p = priser[t]
        delar.append(kapital * w * (p / p.iloc[0]))
    return pd.concat(delar, axis=1).sum(axis=1)


# ---------- Matt ----------

def max_drawdown(kurva):
    return (kurva / kurva.cummax() - 1.0).min()


def matt(kurva, rf):
    dagsavk = kurva.pct_change().dropna()
    ar = len(dagsavk) / HANDELSDAGAR
    total = kurva.iloc[-1] / kurva.iloc[0] - 1
    cagr = (kurva.iloc[-1] / kurva.iloc[0]) ** (1 / ar) - 1 if ar > 0 else 0
    vol = dagsavk.std() * np.sqrt(HANDELSDAGAR)
    sharpe = (cagr - rf) / vol if vol > 0 else 0
    return {"slut": kurva.iloc[-1], "total": total, "cagr": cagr,
            "vol": vol, "dd": max_drawdown(kurva), "sharpe": sharpe}


# ---------- Visning ----------

def kr(x):
    return f"{x:,.0f} kr".replace(",", " ")


def pct(x):
    return f"{x*100:+.1f}%"


def sparkline(serie, punkter=48):
    tecken = "▁▂▃▄▅▆▇█"
    s = serie.dropna()
    if len(s) > punkter:
        s = s.iloc[:: max(1, len(s) // punkter)]
    lo, hi = s.min(), s.max()
    if hi == lo:
        return tecken[0] * len(s)
    return "".join(tecken[min(7, int((v - lo) / (hi - lo) * 7.999))] for v in s)


def domslut(namn, min_m, bench_m):
    """Jamfor min portfolj mot ett benchmark, riskjusterat."""
    ravk = min_m["cagr"] - bench_m["cagr"]
    dsharpe = min_m["sharpe"] - bench_m["sharpe"]
    avk_txt = (f"{GRON}+{ravk*100:.1f}pp battre{NOLL}" if ravk > 0
               else f"{ROD}{ravk*100:.1f}pp samre{NOLL}")
    if dsharpe > 0.03:
        dom = f"{GRON}{FET}Du SLAR {namn} riskjusterat (+{dsharpe:.2f} Sharpe).{NOLL}"
    elif dsharpe < -0.03:
        dom = f"{ROD}{FET}{namn} ar battre riskjusterat ({dsharpe:.2f} Sharpe) - forenkla.{NOLL}"
    else:
        dom = f"{GUL}Likvardigt med {namn} riskjusterat - komplexiteten tillfor lite.{NOLL}"
    return avk_txt, dom


def rad(namn, m):
    print(f"  {namn:<16}{kr(m['slut']):>14}{pct(m['total']):>9}"
          f"{pct(m['cagr']):>8}/ar{pct(m['dd']):>9}{m['sharpe']:>8.2f}")


# ---------- Riktigt konto (tidsviktad avkastning) ----------

def riktigt_konto(rf):
    if not os.path.exists(KONTO):
        return
    try:
        with open(KONTO, encoding="utf-8") as f:
            k = las_config_text(f.read())
    except Exception:
        return
    matn = sorted(k.get("matningar", []), key=lambda r: r["datum"])
    if len(matn) < 2:
        print(f"\n  {GRA}(mitt_konto.json: logga minst 2 matningar sa raknar jag "
              f"din riktiga avkastning har){NOLL}")
        return

    # Tidsviktad avkastning (TWR): kedja delperioders avkastning, rensat for insattningar
    faktor = 1.0
    for i in range(1, len(matn)):
        forra, nu = matn[i - 1], matn[i]
        insatt = float(nu.get("insatt_sedan_forra", 0))
        start_v = float(forra["varde"])
        slut_v = float(nu["varde"])
        if start_v > 0:
            faktor *= (slut_v - insatt) / start_v
    twr = faktor - 1
    d0 = datetime.strptime(matn[0]["datum"], "%Y-%m-%d")
    d1 = datetime.strptime(matn[-1]["datum"], "%Y-%m-%d")
    ar = max((d1 - d0).days / 365.25, 1e-9)

    bench = hamta([BENCH_VWCE, BENCH_BOND], matn[0]["datum"])
    b6040 = buy_hold_kurva(bench, {BENCH_VWCE: 0.6, BENCH_BOND: 0.4}, 1.0)
    bench_ret = b6040.iloc[-1] / b6040.iloc[0] - 1

    print("\n" + "=" * 64)
    print(f"  {FET}DITT RIKTIGA KONTO{NOLL}  ({matn[0]['datum']} -> {matn[-1]['datum']})")
    print("=" * 64)
    print(f"  Din tidsviktade avkastning : {pct(twr)}   (rensat for insattningar)")
    print(f"  Enkel 60/40 samma period   : {pct(bench_ret)}")
    diff = twr - bench_ret
    if diff > 0:
        print(f"  {GRON}{FET}Du slog benchmark med {diff*100:+.1f} procentenheter.{NOLL}")
    else:
        print(f"  {ROD}{FET}Du lag {diff*100:.1f} pp EFTER benchmark. Fragan: varfor?{NOLL}")


def las_config_text(raw):
    # aterbruka kommentars-rensningen fran risk_engine
    from risk_engine import _rensa_json
    return json.loads(_rensa_json(raw))


# ---------- Main ----------

def main():
    cfg = las_config(CFG)
    rf = float(cfg.get("riskfri_ranta", 0.02))
    kapital = float(cfg["kapital"])
    innehav = cfg["innehav"]

    start = cfg.get("startdatum") or (
        datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")

    tickers = [h["ticker"] for h in innehav]
    raw = np.array([float(h["vikt"]) for h in innehav], dtype=float)

    print("  Hamtar historik ...", end="", flush=True)
    alla = list(set(tickers + [BENCH_VWCE, BENCH_BOND]))
    priser = hamta(alla, start)
    finns = [t for t in tickers if t in priser.columns]
    idx = [i for i, t in enumerate(tickers) if t in finns]
    vikter = {t: raw[i] / raw[idx].sum() for i, t in zip(idx, finns)}
    print(f" klart ({priser.index[0].date()} -> {priser.index[-1].date()})")

    # Kurvor
    min_kurva = buy_hold_kurva(priser, vikter, kapital)
    vwce_kurva = buy_hold_kurva(priser, {BENCH_VWCE: 1.0}, kapital)
    b6040_kurva = buy_hold_kurva(priser, {BENCH_VWCE: 0.6, BENCH_BOND: 0.4}, kapital)

    min_m = matt(min_kurva, rf)
    vwce_m = matt(vwce_kurva, rf)
    b6040_m = matt(b6040_kurva, rf)

    print("\n" + "=" * 64)
    print(f"  {FET}MERITLISTA{NOLL}  -  kopt for {kr(kapital)} vid start, hallit")
    print("=" * 64)
    print(f"  {'':<16}{'Vart nu':>14}{'Totalt':>9}{'Snitt':>11}{'MaxFall':>9}{'Sharpe':>8}")
    rad(f"{FET}Min portfolj{NOLL}", min_m)
    rad("100% VWCE", vwce_m)
    rad("Enkel 60/40", b6040_m)

    print("\n  Utveckling (min portfolj):  " + GRON + sparkline(min_kurva) + NOLL)
    print("  Utveckling (enkel 60/40):   " + GRA + sparkline(b6040_kurva) + NOLL)

    print("\n" + "-" * 64)
    print(f"  {FET}DOMSLUT{NOLL}")
    print("-" * 64)
    for namn, bm in [("100% VWCE", vwce_m), ("enkla 60/40", b6040_m)]:
        avk_txt, dom = domslut(namn, min_m, bm)
        print(f"  vs {namn:<12} avkastning: {avk_txt}")
        print(f"     {dom}")

    print("\n  " + GRA + "OBS: historik, inte prognos. 100% VWCE tar mer aktierisk -")
    print("  darfor ar Sharpe (riskjusterat) den arligaste jamforelsen." + NOLL)

    riktigt_konto(rf)
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
