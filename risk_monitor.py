# -*- coding: utf-8 -*-
"""
RISKMATARE  (live)
==================
Visar portfoljens RISK just nu och uppdaterar var 5:e minut.
Risk = senaste tidens volatilitet (hur stokig marknaden ar) - det som
faktiskt ror sig kort sikt, till skillnad fran 5-ars-drawdown.

Pilar jamfor mot:  forra matningen  ·  igar  ·  manadens start
  rod pil upp = risken har STIGIT (samre)
  gron pil ner = risken har SJUNKIT (battre)

Kor:  python risk_monitor.py   (anvands aven av appen via app.py)
Historik sparas i risk_history.json sa jamforelserna byggs upp over tid.
Avsluta med Ctrl+C.
"""

import os
import sys
import json
import time
from datetime import datetime

import numpy as np

try:
    import yfinance as yf
except ImportError:
    print("Saknar yfinance. Kor: pip install yfinance")
    sys.exit(1)

from risk_engine import las_config  # aterbrukar den kommentarstalande inlasaren

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "portfolio.json")
HIST = os.path.join(HERE, "risk_history.json")
REFRESH_SEK = 300      # 5 minuter
VOL_FONSTER = 30       # dagar for volatilitetsmatningen
HANDELSDAGAR = 252

# ANSI-farger + UTF-8 (sa block/pil-tecken funkar pa Windows-konsolen)
os.system("")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass
ROD, GRON, GRA, GUL, FET, NOLL = (
    "\033[91m", "\033[92m", "\033[90m", "\033[93m", "\033[1m", "\033[0m")


# ---------- Rakna risk ----------

def berakna_risk(cfg):
    """Returnerar (risk_procent, var_kronor) for portfoljen just nu."""
    innehav = cfg["innehav"]
    tickers = [h["ticker"] for h in innehav]
    raw = np.array([float(h["vikt"]) for h in innehav], dtype=float)

    data = yf.download(tickers, period="3mo", interval="1d",
                       auto_adjust=True, progress=False, group_by="column")
    import pandas as pd
    if isinstance(data.columns, pd.MultiIndex):
        priser = data["Close"].copy()
    else:
        priser = data[["Close"]].copy()
        priser.columns = tickers

    finns = [t for t in tickers if t in priser.columns and priser[t].notna().sum() > 5]
    if not finns:
        raise RuntimeError("ingen kursdata")
    idx = [i for i, t in enumerate(tickers) if t in finns]
    vikter = raw[idx] / raw[idx].sum()
    priser = priser[finns].ffill().dropna()

    dagsavk = priser.pct_change().dropna()
    port = (dagsavk * vikter).sum(axis=1)

    senaste = port.tail(VOL_FONSTER)
    risk_pct = float(senaste.std() * np.sqrt(HANDELSDAGAR) * 100)

    kapital = float(cfg["kapital"])
    var_dag = np.percentile(port.tail(60), 5)  # 95% 1-dags VaR (historisk)
    var_kr = float(var_dag * kapital)
    return risk_pct, var_kr


# ---------- Historik ----------

def las_hist():
    if not os.path.exists(HIST):
        return []
    try:
        with open(HIST, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def spara_hist(hist):
    with open(HIST, "w", encoding="utf-8") as f:
        json.dump(hist[-5000:], f, ensure_ascii=False, indent=0)


def hitta_baslinjer(hist, nu):
    """Returnerar (forra, igar, manad) - dict eller None."""
    idag = nu.strftime("%Y-%m-%d")
    denna_manad = nu.strftime("%Y-%m")
    forra = hist[-1] if hist else None
    igar = next((r for r in reversed(hist) if r["ts"][:10] < idag), None)
    manad = next((r for r in hist if r["ts"][:7] == denna_manad), None)
    return forra, igar, manad


# ---------- Visning ----------

def pil(nu_risk, bas):
    """Fargad pil + text jamfort med en baslinje."""
    if bas is None:
        return f"{GRA}—  (ingen tidigare matning an){NOLL}"
    d = nu_risk - bas["risk"]
    if d > 0.05:
        return f"{ROD}{FET}▲ +{d:.2f} pp   RISK UPP{NOLL}"
    if d < -0.05:
        return f"{GRON}{FET}▼ {d:.2f} pp   risk ner{NOLL}"
    return f"{GRA}=  ofoerandrad ({d:+.2f} pp){NOLL}"


def gauge(risk_pct):
    """Horisontell mätare 0-40%."""
    bredd = 30
    fyllt = max(0, min(bredd, int(round(risk_pct / 40 * bredd))))
    if risk_pct < 10:
        farg, niva = GRON, "lugn"
    elif risk_pct < 20:
        farg, niva = GUL, "normal"
    else:
        farg, niva = ROD, "forhojd"
    bar = farg + "█" * fyllt + GRA + "░" * (bredd - fyllt) + NOLL
    return f"[{bar}]  {farg}{FET}{niva}{NOLL}"


def kr(x):
    return f"{x:,.0f} kr".replace(",", " ")


def rita(nu, risk_pct, var_kr, forra, igar, manad):
    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 60)
    print(f"  {FET}RISKMATARE  -  ETF-portfolj{NOLL}"
          f"        {nu.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"  {FET}Risk (30-dagars volatilitet):  {risk_pct:.1f} %{NOLL}")
    print("  " + gauge(risk_pct))
    print(f"  Mojlig forlust en dalig dag (1/20): {ROD}{kr(var_kr)}{NOLL}")
    print("-" * 60)
    print("  Jamfort med:")
    print(f"   Forra matningen (~5 min): {pil(risk_pct, forra)}")
    print(f"   Igar:                     {pil(risk_pct, igar)}")
    print(f"   Manadens start:           {pil(risk_pct, manad)}")
    print("=" * 60)
    print(f"  {GRA}Uppdaterar var 5:e minut. Ctrl+C for att avsluta.{NOLL}")
    print(f"  {GRA}Rod = risk stiger (samre) · Gron = risk sjunker (battre){NOLL}")


# ---------- Loop ----------

def tick():
    cfg = las_config(CFG)
    nu = datetime.now()
    risk_pct, var_kr = berakna_risk(cfg)
    hist = las_hist()
    forra, igar, manad = hitta_baslinjer(hist, nu)
    rita(nu, risk_pct, var_kr, forra, igar, manad)
    hist.append({"ts": nu.strftime("%Y-%m-%d %H:%M:%S"),
                 "risk": round(risk_pct, 3), "var_kr": round(var_kr)})
    spara_hist(hist)


def main():
    print("Startar riskmatare ... (forsta hamtningen tar nagra sekunder)")
    while True:
        try:
            tick()
        except KeyboardInterrupt:
            print("\nAvslutar. Hej da!")
            break
        except Exception as e:  # nataviktel el. dyl. - fortsatt forsoka
            print(f"{GUL}Tillfalligt fel: {e} - forsoker igen om 5 min.{NOLL}")
        try:
            time.sleep(REFRESH_SEK)
        except KeyboardInterrupt:
            print("\nAvslutar. Hej da!")
            break


if __name__ == "__main__":
    main()
