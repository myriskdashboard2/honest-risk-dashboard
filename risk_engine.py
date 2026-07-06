# -*- coding: utf-8 -*-
"""
RISKMOTOR for ETF-portfolj
==========================
Visar risken i KRONOR innan du koper. Ingen prediktion, inget "kop"-rad -
bara arlig risk: hur mycket portfoljen svanger, hur mycket du realistiskt
kan forlora, och om dina ETF:er faktiskt diversifierar.

Kor:  python risk_engine.py
Config: portfolio.json  (byt till dina egna tickers och kapital)
"""

import json
import re
import sys
import os
import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("Saknar yfinance. Kor: pip install yfinance")
    sys.exit(1)

HANDELSDAGAR = 252  # borsdagar per ar, standard for annualisering
HIST_AR = 5         # hur manga ars historik vi hamtar


# ---------- Config (tal // -kommentarer och slutkommatecken) ----------

def _rensa_json(text):
    """Tar bort //-kommentarer, /* */-block och slutkommatecken sa att du kan
    kommentera fritt i portfolio.json utan att det kraschar. Respekterar
    strangar (ror inte // inuti citattecken)."""
    ut = []
    i, n = 0, len(text)
    i_strang = False
    while i < n:
        c = text[i]
        if i_strang:
            ut.append(c)
            if c == '\\' and i + 1 < n:      # escapad tecken, hoppa over nasta
                ut.append(text[i + 1]); i += 2; continue
            if c == '"':
                i_strang = False
            i += 1; continue
        if c == '"':
            i_strang = True; ut.append(c); i += 1; continue
        if c == '/' and i + 1 < n and text[i + 1] == '/':      # rad-kommentar
            while i < n and text[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '*':      # block-kommentar
            i += 2
            while i + 1 < n and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2; continue
        ut.append(c); i += 1
    utan_komm = "".join(ut)
    utan_komm = re.sub(r',(\s*[}\]])', r'\1', utan_komm)   # slutkommatecken
    return utan_komm


def las_config(path):
    # Forsta korningen: skapa portfolio.json fran exempelfilen
    if not os.path.exists(path):
        exempel = os.path.join(os.path.dirname(path), "portfolio.example.json")
        if os.path.exists(exempel):
            import shutil
            shutil.copyfile(exempel, path)
            print("(skapade portfolio.json fran portfolio.example.json - "
                  "lagg in dina egna innehav i appen)")
        else:
            print(f"\n  !! Hittar varken {os.path.basename(path)} eller "
                  "portfolio.example.json.")
            sys.exit(1)
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    try:
        return json.loads(_rensa_json(raw))
    except json.JSONDecodeError as e:
        print(f"\n  !! portfolio.json gar inte att lasa: {e}")
        print("     Vanliga fel: saknat kommatecken mellan innehav, eller en")
        print("     ticker/namn som inte star inom \"citattecken\".")
        sys.exit(1)


# ---------- Datahamtning ----------

def hamta_priser(tickers, ar=HIST_AR):
    """Hamtar dagliga stangningskurser (justerade for utdelning/split)."""
    data = yf.download(
        tickers,
        period=f"{ar}y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column",
    )
    if isinstance(data.columns, pd.MultiIndex):
        priser = data["Close"].copy()
    else:  # en enda ticker
        priser = data[["Close"]].copy()
        priser.columns = tickers
    priser = priser.dropna(how="all").ffill().dropna()
    return priser


# ---------- Riskmatt ----------

def max_drawdown(kurva):
    """Storsta fall fran topp till botten (t.ex. -0.34 = -34%)."""
    topp = kurva.cummax()
    dd = kurva / topp - 1.0
    return dd.min()


def arlig_avkastning(dagsavk):
    """Historisk genomsnittlig arsavkastning (CAGR-liknande)."""
    return (1 + dagsavk).prod() ** (HANDELSDAGAR / len(dagsavk)) - 1


def arlig_volatilitet(dagsavk):
    return dagsavk.std() * np.sqrt(HANDELSDAGAR)


def sharpe(dagsavk, rf):
    vol = arlig_volatilitet(dagsavk)
    if vol == 0:
        return 0.0
    return (arlig_avkastning(dagsavk) - rf) / vol


def historisk_var(dagsavk, niva=0.95):
    """Value at Risk (historisk metod). Returnerar en NEGATIV daglig avk.
    Tolkning vid 95%: 'en genomsnittlig dalig dag' - varre 1 dag av 20."""
    return np.percentile(dagsavk, (1 - niva) * 100)


# ---------- Rapport ----------

def kr(x, valuta="SEK"):
    return f"{x:,.0f} {valuta}".replace(",", " ")


def procent(x):
    return f"{x*100:+.1f}%"


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(here, "portfolio.json")
    cfg = las_config(cfg_path)

    valuta = cfg.get("valuta", "SEK")
    kapital = float(cfg["kapital"])
    rf = float(cfg.get("riskfri_ranta", 0.02))
    innehav = cfg["innehav"]

    tickers = [h["ticker"] for h in innehav]
    namn = {h["ticker"]: h.get("namn", h["ticker"]) for h in innehav}
    raw_vikter = np.array([float(h["vikt"]) for h in innehav], dtype=float)
    vikter = raw_vikter / raw_vikter.sum()  # normalisera till 1

    print("\n" + "=" * 64)
    print("  RISKMOTOR  -  ETF-portfolj")
    print("=" * 64)
    print(f"  Kapital: {kr(kapital, valuta)}   |   Riskfri ranta: {rf*100:.1f}%")
    print(f"  Historik: {HIST_AR} ar dagsdata   |   (historik = INTE prognos)")
    print("-" * 64)

    print("  Hamtar kurser ...", end="", flush=True)
    priser = hamta_priser(tickers)
    saknas = [t for t in tickers if t not in priser.columns]
    if saknas:
        print(f"\n  !! Hittade INGEN data for: {', '.join(saknas)}")
        print("     Kolla tickern pa finance.yahoo.com (t.ex. .ST for Stockholm).")
        tickers = [t for t in tickers if t in priser.columns]
        if not tickers:
            sys.exit(1)
        idx = [i for i, h in enumerate(innehav) if h["ticker"] in tickers]
        vikter = raw_vikter[idx] / raw_vikter[idx].sum()
    priser = priser[tickers]
    print(f" klart ({len(priser)} handelsdagar, "
          f"{priser.index[0].date()} -> {priser.index[-1].date()})")

    dagsavk = priser.pct_change().dropna()

    # Portfoljserie (daglig ombalansering till malvikter - forenkling)
    port_dagsavk = (dagsavk * vikter).sum(axis=1)
    port_kurva = (1 + port_dagsavk).cumprod()

    # ---- Per ETF ----
    print("\n" + "-" * 64)
    print("  PER ETF (historik)")
    print("-" * 64)
    print(f"  {'ETF':<10}{'Vikt':>6}{'Avk/ar':>9}{'Vol/ar':>9}"
          f"{'MaxFall':>9}{'Sharpe':>8}")
    for t, w in zip(tickers, vikter):
        a = dagsavk[t]
        print(f"  {t:<10}{w*100:>5.0f}%{procent(arlig_avkastning(a)):>9}"
              f"{procent(arlig_volatilitet(a)):>9}"
              f"{procent(max_drawdown((1+a).cumprod())):>9}"
              f"{sharpe(a, rf):>8.2f}")

    # ---- Portfoljnivo ----
    p_avk = arlig_avkastning(port_dagsavk)
    p_vol = arlig_volatilitet(port_dagsavk)
    p_dd = max_drawdown(port_kurva)
    p_sharpe = sharpe(port_dagsavk, rf)

    print("\n" + "-" * 64)
    print("  HELA PORTFOLJEN")
    print("-" * 64)
    print(f"  Historisk avkastning/ar : {procent(p_avk)}   (INTE en prognos)")
    print(f"  Volatilitet/ar          : {procent(p_vol)}   (hur mycket det svanger)")
    print(f"  Sharpe (avk per risk)    : {p_sharpe:.2f}   "
          f"({'bra' if p_sharpe>1 else 'ok' if p_sharpe>0.5 else 'svagt'})")
    print(f"  Varsta historiska fall  : {procent(p_dd)}  = {kr(kapital*p_dd, valuta)}")

    # ---- Diversifiering ----
    print("\n" + "-" * 64)
    print("  DIVERSIFIERING (korrelation - 1.0 = ror sig identiskt)")
    print("-" * 64)
    corr = dagsavk.corr()
    header = "  " + " " * 10 + "".join(f"{t[:8]:>9}" for t in tickers)
    print(header)
    for t in tickers:
        rad = "".join(f"{corr.loc[t, o]:>9.2f}" for o in tickers)
        print(f"  {t:<10}{rad}")
    # Nyckelvarning: ojamn vikt eller allt hogt korrelerat
    ovre = corr.where(~np.eye(len(tickers), dtype=bool))
    max_par = ovre.stack().max() if len(tickers) > 1 else 0
    if max_par > 0.9:
        print("  !! Tva innehav ror sig nastan identiskt (>0.90) - du diversifierar")
        print("     mindre an du tror. Overvag att ersatta ett av dem.")

    # ---- Risk i KRONOR (det du bad om) ----
    var95 = historisk_var(port_dagsavk, 0.95)
    var99 = historisk_var(port_dagsavk, 0.99)
    # 1-manads (21 dagar) parametrisk skalning for perspektiv
    man_forlust = var95 * np.sqrt(21)

    print("\n" + "=" * 64)
    print("  VAD KAN JAG FORLORA?  (i kronor, pa {})".format(kr(kapital, valuta)))
    print("=" * 64)
    print(f"  En dalig dag (1 av 20)   : {kr(kapital*var95, valuta)}  ({procent(var95)})")
    print(f"  En riktigt dalig dag(1/100): {kr(kapital*var99, valuta)}  ({procent(var99)})")
    print(f"  En dalig manad (~grovt)  : {kr(kapital*man_forlust, valuta)}  ({procent(man_forlust)})")
    print(f"  Verklig krasch (som varst): {kr(kapital*p_dd, valuta)}  ({procent(p_dd)})")
    print("-" * 64)
    print("  Sa las det: 'varsta historiska fall' ar det VIKTIGA talet - det")
    print("  har faktiskt hant. Kan du sitta still och inte salja nar portfoljen")
    print(f"  star {procent(p_dd)} back? Kan du inte det - ta mindre risk.")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
