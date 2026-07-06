# -*- coding: utf-8 -*-
"""
JANE STREET-DASHBOARD  (allt-i-ett-appen)
=========================================
En lokal webbapp som samlar alla verktyg under ett tak:
  * Innehav       - lagg in vad du ager pa Avanza (varde i kr, som Avanza visar)
  * Rebalansering - exakt vad du ska kopa/salja for att komma till malvikterna
  * Risk          - fulla riskrapporten (5 ar) i kronor
  * Matare        - live-risken, uppdaterar var 5:e minut med pilar
  * Meritlista    - din portfolj mot 100% VWCE och enkel 60/40

Startas via STARTA_APP.bat (skrivbordsikon) - stoppas via STOPPA_APP.bat.
Allt lokalt pa din dator. Ingen inloggning, inga riktiga pengar rors.
"""

import os
import sys
import json
import threading
import time
import webbrowser
from datetime import datetime

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, Response

import risk_engine as re_mod
import risk_monitor as rm_mod
import track_record as tr_mod

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "portfolio.json")
PIDFIL = os.path.join(HERE, "app.pid")
PORT = 8750

app = Flask(__name__)


# =============== Hjalpare ===============

def las_cfg():
    return re_mod.las_config(CFG)


def spara_cfg(cfg):
    """Skriver portfolio.json (med forklarande kommentar hogst upp)."""
    huvud = (
        "{\n"
        "  // Sparad fran dashboarden. 'varde_kr' = vad innehavet ar vart pa\n"
        "  // Avanza just nu (kr). 'vikt' = MALVIKT. Riskmotorn laser 'ticker'.\n"
    )
    rader = [
        f'  "valuta": {json.dumps(cfg.get("valuta", "SEK"))},',
        f'  "kapital": {json.dumps(cfg.get("kapital", 0))},',
        f'  "usd_sek": {json.dumps(cfg.get("usd_sek", 10.5))},',
        f'  "riskfri_ranta": {json.dumps(cfg.get("riskfri_ranta", 0.02))},',
        '  "innehav": [',
    ]
    inne = []
    for h in cfg["innehav"]:
        inne.append(
            "    { "
            f'"ticker": {json.dumps(h["ticker"])}, '
            f'"namn": {json.dumps(h.get("namn", ""), ensure_ascii=False)}, '
            f'"vikt": {round(float(h.get("vikt", 0)), 4)}, '
            f'"varde_kr": {round(float(h.get("varde_kr", 0)), 2)}'
            " }"
        )
    rader.append(",\n".join(inne))
    rader.append("  ]\n}")
    with open(CFG, "w", encoding="utf-8") as f:
        f.write(huvud + "\n".join(rader) + "\n")


def kapital_fran(cfg):
    """Summa av verkliga varden om de finns, annars faltet kapital."""
    s = sum(float(h.get("varde_kr", 0) or 0) for h in cfg["innehav"])
    return s if s > 0 else float(cfg.get("kapital", 0))


# =============== API: portfolj ===============

@app.get("/api/portfolio")
def api_portfolio():
    cfg = las_cfg()
    return jsonify({
        "kapital": kapital_fran(cfg),
        "riskfri_ranta": cfg.get("riskfri_ranta", 0.02),
        "innehav": [{
            "ticker": h["ticker"],
            "namn": h.get("namn", ""),
            "vikt": float(h.get("vikt", 0)),
            "varde_kr": float(h.get("varde_kr", 0) or 0),
        } for h in cfg["innehav"]],
    })


@app.post("/api/portfolio")
def api_portfolio_spara():
    data = request.get_json(force=True)
    innehav = [h for h in data.get("innehav", [])
               if h.get("ticker", "").strip()]
    if not innehav:
        return jsonify({"fel": "minst en ETF behovs"}), 400
    cfg = las_cfg()
    cfg["innehav"] = innehav
    cfg["kapital"] = kapital_fran({"innehav": innehav,
                                   "kapital": data.get("kapital", cfg.get("kapital", 0))})
    if data.get("kapital"):
        try:
            manuellt = float(data["kapital"])
            if sum(float(h.get("varde_kr", 0) or 0) for h in innehav) == 0:
                cfg["kapital"] = manuellt
        except (TypeError, ValueError):
            pass
    spara_cfg(cfg)
    return jsonify({"ok": True, "kapital": cfg["kapital"]})


@app.get("/api/sok")
def api_sok():
    """Sok fond/ETF pa namn via Yahoo. Vanliga svenska fonder har kryptiska
    koder (0P0000XXXX.ST) - det har hittar dem at anvandaren."""
    import yfinance as yf
    fraga = request.args.get("namn", "").strip()
    if len(fraga) < 3:
        return jsonify({"traffar": []})
    try:
        with YF_LAS:
            s = yf.Search(fraga, max_results=8)
        traffar = []
        for q in s.quotes:
            sym = q.get("symbol", "")
            if not sym:
                continue
            typ = q.get("quoteType", "")
            typ_sv = {"MUTUALFUND": "fond", "ETF": "ETF",
                      "EQUITY": "aktie"}.get(typ, typ.lower())
            traffar.append({"ticker": sym,
                            "namn": q.get("longname") or q.get("shortname") or sym,
                            "typ": typ_sv, "typ_kod": typ,
                            "bors": q.get("exchDisp", "")})
        return jsonify({"traffar": traffar})
    except Exception as e:
        return jsonify({"traffar": [], "fel": str(e)})


@app.get("/api/testa_ticker")
def api_testa_ticker():
    """Kollar att en ticker har kursdata innan man sparar den."""
    import yfinance as yf
    t = request.args.get("ticker", "").strip()
    if not t:
        return jsonify({"ok": False, "info": "tom ticker"})
    try:
        with YF_LAS:
            d = yf.download(t, period="1mo", progress=False, auto_adjust=True)
        ok = d is not None and len(d.dropna()) > 0
        sista = float(d["Close"].dropna().iloc[-1].iloc[0]) if ok else None
        return jsonify({"ok": bool(ok), "sista_kurs": sista})
    except Exception as e:
        return jsonify({"ok": False, "info": str(e)})


# =============== API: rebalansering ===============

@app.get("/api/rebalans")
def api_rebalans():
    cfg = las_cfg()
    innehav = cfg["innehav"]
    total = sum(float(h.get("varde_kr", 0) or 0) for h in innehav)
    if total <= 0:
        return jsonify({"fel": "Fyll i 'Varde pa Avanza (kr)' under Innehav forst - "
                               "da vet jag vad du ager.",
                        "fel_en": "Fill in 'Value at your broker' under Holdings first - "
                                  "then I know what you own."})
    raw = np.array([float(h.get("vikt", 0)) for h in innehav], dtype=float)
    mal = raw / raw.sum()
    rader, storsta_avvikelse = [], 0.0
    for h, mv in zip(innehav, mal):
        varde = float(h.get("varde_kr", 0) or 0)
        nu_pct = varde / total
        mal_kr = mv * total
        diff = mal_kr - varde
        storsta_avvikelse = max(storsta_avvikelse, abs(nu_pct - mv))
        if diff > 0:
            atgard = "KOP"
        elif diff < 0:
            atgard = "SALJ"
        else:
            atgard = "OK"
        if abs(diff) < max(300, 0.005 * total):   # under ~0.5% / 300 kr: lat vara
            atgard = "OK"
        rader.append({"ticker": h["ticker"], "namn": h.get("namn", ""),
                      "nu_pct": round(nu_pct * 100, 1),
                      "mal_pct": round(mv * 100, 1),
                      "varde_kr": round(varde),
                      "diff_kr": round(diff),
                      "atgard": atgard})
    behov = bool(storsta_avvikelse > 0.05)
    return jsonify({"total": round(total), "rader": rader,
                    "storsta_avvikelse_pp": round(float(storsta_avvikelse) * 100, 1),
                    "behov": behov})


# =============== Cache (sa flikarna svarar snabbt och tal Yahoo-strul) ===============

_cache = {}          # nyckel -> (tidpunkt, svar)
CACHE_TTL = 300      # 5 min

# En kolapp for alla Yahoo-hamtningar: tva samtidiga nedladdningar (t.ex.
# forvarmningen + mataren vid appstart) kan krocka och ge slumpfel.
YF_LAS = threading.Lock()


def cachead(nyckel, berakna):
    """Returnera cachat svar om det ar farskt, annars rakna om."""
    nu = time.time()
    traff = _cache.get(nyckel)
    if traff and nu - traff[0] < CACHE_TTL:
        return traff[1]
    svar = berakna()
    _cache[nyckel] = (nu, svar)
    return svar


def cache_nyckel(cfg):
    """Cachen ogiltigfors sa fort nagot i innehaven andras (fond, vikt eller varde)."""
    return json.dumps([(h["ticker"], h.get("vikt"), h.get("varde_kr"))
                       for h in cfg["innehav"]])


# =============== API: risk (fulla rapporten) ===============

@app.get("/api/risk")
def api_risk():
    cfg = las_cfg()
    return jsonify(cachead("risk:" + cache_nyckel(cfg), lambda: _rakna_risk(cfg)))


def _rakna_risk(cfg):
    kapital = kapital_fran(cfg)
    rf = float(cfg.get("riskfri_ranta", 0.02))
    innehav = cfg["innehav"]
    tickers = [h["ticker"] for h in innehav]
    raw = np.array([float(h["vikt"]) for h in innehav], dtype=float)

    with YF_LAS:
        priser = re_mod.hamta_priser(tickers)
    finns = [t for t in tickers if t in priser.columns]
    idx = [i for i, t in enumerate(tickers) if t in finns]
    vikter = raw[idx] / raw[idx].sum()
    priser = priser[finns]
    dagsavk = priser.pct_change().dropna()
    port = (dagsavk * vikter).sum(axis=1)
    kurva = (1 + port).cumprod()

    per_etf = []
    for t, w in zip(finns, vikter):
        a = dagsavk[t]
        per_etf.append({"ticker": t, "vikt": round(float(w) * 100),
                        "avk": round(re_mod.arlig_avkastning(a) * 100, 1),
                        "vol": round(re_mod.arlig_volatilitet(a) * 100, 1),
                        "maxfall": round(re_mod.max_drawdown((1 + a).cumprod()) * 100, 1),
                        "sharpe": round(re_mod.sharpe(a, rf), 2)})

    var95 = re_mod.historisk_var(port, 0.95)
    var99 = re_mod.historisk_var(port, 0.99)
    dd = re_mod.max_drawdown(kurva)
    corr = dagsavk.corr()
    saknas = [t for t in tickers if t not in finns]
    return {
        "kapital": kapital,
        "period": f"{priser.index[0].date()} till {priser.index[-1].date()}",
        "per_etf": per_etf,
        "portfolj": {"avk": round(re_mod.arlig_avkastning(port) * 100, 1),
                     "vol": round(re_mod.arlig_volatilitet(port) * 100, 1),
                     "sharpe": round(re_mod.sharpe(port, rf), 2),
                     "maxfall": round(dd * 100, 1),
                     "maxfall_kr": round(kapital * dd)},
        "kronor": {"dag95": round(kapital * var95),
                   "dag99": round(kapital * var99),
                   "manad": round(kapital * var95 * np.sqrt(21)),
                   "krasch": round(kapital * dd)},
        "korr": {"tickers": finns,
                 "matris": [[round(float(corr.loc[a, b]), 2) for b in finns]
                            for a in finns]},
        "saknas": saknas,
    }


# =============== API: matare ===============

@app.get("/api/gauge")
def api_gauge():
    cfg = las_cfg()
    cfg["kapital"] = kapital_fran(cfg)
    nu = datetime.now()
    with YF_LAS:
        risk_pct, var_kr = rm_mod.berakna_risk(cfg)
    hist = rm_mod.las_hist()
    forra, igar, manad = rm_mod.hitta_baslinjer(hist, nu)

    def jfr(bas):
        if bas is None:
            return None
        return round(risk_pct - bas["risk"], 2)

    svar = {"ts": nu.strftime("%Y-%m-%d %H:%M"),
            "risk": round(risk_pct, 1), "var_kr": round(var_kr),
            "vs_forra": jfr(forra), "vs_igar": jfr(igar), "vs_manad": jfr(manad)}
    hist.append({"ts": nu.strftime("%Y-%m-%d %H:%M:%S"),
                 "risk": round(risk_pct, 3), "var_kr": round(var_kr)})
    rm_mod.spara_hist(hist)
    return jsonify(svar)


# =============== API: stresstest ===============

# Varldsmarknaden i SEK som riskfaktor (MSCI World via LF Global Index).
STRESS_FAKTOR = "0P0000YVZ3.ST"

# Scenarier: aktiechock (varldsindex i SEK) + vad korta rantefonder gjorde da.
# Kalibrerade mot vad som faktiskt hande (MSCI World i SEK, svenska rantefonder).
STRESS_SCENARIER = [
    {"id": "fk2008",
     "namn": "Finanskrisen 2008", "namn_en": "2008 Financial Crisis",
     "aktier": -0.40, "rantor": 0.02,
     "beskrivning": "Aktier -40% under ~1,5 ar. Korta rantefonder holl emot (+2%).",
     "beskrivning_en": "Equities -40% over ~1.5 years. Short-term bond funds held up (+2%)."},
    {"id": "it2000",
     "namn": "IT-kraschen 2000-2002", "namn_en": "Dot-com Crash 2000-2002",
     "aktier": -0.45, "rantor": 0.03,
     "beskrivning": "Utdragen tech-krasch, -45% pa ~2,5 ar. Tech/AI foll langt mer - "
                    "det fangas av fondens beta.",
     "beskrivning_en": "Drawn-out tech crash, -45% over ~2.5 years. Tech/AI fell far more - "
                       "captured by each fund's beta."},
    {"id": "covid",
     "namn": "Covid-kraschen mars 2020", "namn_en": "Covid Crash, March 2020",
     "aktier": -0.30, "rantor": -0.03,
     "beskrivning": "-30% pa EN manad. Aven korta rantefonder foll (~-3%) nar alla "
                    "salde allt samtidigt (likviditetsstress).",
     "beskrivning_en": "-30% in ONE month. Even short-term bond funds fell (~-3%) when "
                       "everyone sold everything at once (liquidity stress)."},
    {"id": "ranta22",
     "namn": "Rantechock 2022", "namn_en": "Rate Shock 2022",
     "aktier": -0.20, "rantor": -0.02,
     "beskrivning": "Snabbt stigande rantor: aktier -20%, aven rantefonder backade nagot.",
     "beskrivning_en": "Rapidly rising rates: equities -20%, even bond funds dipped slightly."},
]


@app.get("/api/stress")
def api_stress():
    cfg = las_cfg()
    return jsonify(cachead("stress:" + cache_nyckel(cfg), lambda: _rakna_stress(cfg)))


def _rakna_stress(cfg):
    import yfinance as yf
    innehav = [h for h in cfg["innehav"] if float(h.get("varde_kr", 0) or 0) > 0]
    if not innehav:
        return {"fel": "Fyll i 'Varde pa Avanza (kr)' under Innehav forst.",
                "fel_en": "Fill in 'Value at your broker' under Holdings first."}
    total = sum(float(h["varde_kr"]) for h in innehav)
    tickers = [h["ticker"] for h in innehav]
    alla = list(set(tickers + [STRESS_FAKTOR]))

    with YF_LAS:
        data = yf.download(alla, period="3y", interval="1d",
                           auto_adjust=True, progress=False, group_by="column")
    priser = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data[["Close"]]
    priser = priser.ffill()

    # VECKOdata: fonders NAV slapar olika dagar - dagsdata underskattar beta,
    # veckodata tvattar bort efterslapningen.
    vecka = priser.resample("W-FRI").last().pct_change().dropna(how="all")
    if STRESS_FAKTOR not in vecka.columns or vecka[STRESS_FAKTOR].dropna().empty:
        return {"fel": "Kunde inte hamta varldsindex-fonden som riskfaktor.",
                "fel_en": "Could not fetch the world-index fund used as risk factor."}
    f = vecka[STRESS_FAKTOR]

    rader_bas = []
    for h in innehav:
        t = h["ticker"]
        varde = float(h["varde_kr"])
        if t == STRESS_FAKTOR:
            beta, vol, veckor = 1.0, float(f.std() * np.sqrt(52)), int(f.notna().sum())
        elif t in vecka.columns:
            par = pd.concat([vecka[t], f], axis=1).dropna()
            veckor = len(par)
            if veckor < 20:
                beta, vol = None, None
            else:
                a, b = par.iloc[:, 0], par.iloc[:, 1]
                beta = float(np.cov(a, b)[0, 1] / np.var(b)) if np.var(b) > 0 else 0.0
                vol = float(a.std() * np.sqrt(52))
        else:
            beta, vol, veckor = None, None, 0
        ar_ranta = vol is not None and vol < 0.04   # <4%/ar = rantefond
        rader_bas.append({"ticker": t, "namn": h.get("namn", t), "varde": varde,
                          "beta": None if beta is None else round(beta, 2),
                          "ranta": ar_ranta, "veckor": veckor})

    scenarier_ut = []
    for sc in STRESS_SCENARIER:
        per_fond, summa = [], 0.0
        for r in rader_bas:
            if r["beta"] is None:
                shock = sc["aktier"]          # okand fond: anta full aktiechock (forsiktigt)
                antagande = {"typ": "okand"}
            elif r["ranta"]:
                shock = sc["rantor"]
                antagande = {"typ": "ranta"}
            else:
                shock = max(-0.95, r["beta"] * sc["aktier"])
                antagande = {"typ": "beta", "beta": r["beta"]}
            kr = shock * r["varde"]
            summa += kr
            per_fond.append({"namn": r["namn"], "ticker": r["ticker"],
                             "varde": round(r["varde"]),
                             "shock_pct": round(shock * 100, 1),
                             "kr": round(kr), "antagande": antagande})
        per_fond.sort(key=lambda x: x["kr"])
        scenarier_ut.append({"namn": sc["namn"], "namn_en": sc["namn_en"],
                             "beskrivning": sc["beskrivning"],
                             "beskrivning_en": sc["beskrivning_en"],
                             "total_kr": round(summa),
                             "total_pct": round(summa / total * 100, 1),
                             "per_fond": per_fond})

    return {"total": round(total), "scenarier": scenarier_ut,
            "metod": ("Beta mot varldsindex i SEK (LF Global Index) pa VECKOdata "
                      "senaste ~3 aren. Rantefonder (volatilitet under 4%/ar) far "
                      "historiskt kalibrerade antaganden per scenario."),
            "metod_en": ("Beta vs a world index in SEK (LF Global Index) on WEEKLY data, "
                         "~3 years. Bond funds (volatility below 4%/yr) get historically "
                         "calibrated assumptions per scenario.")}


# =============== API: meritlista ===============

@app.get("/api/meritlista")
def api_meritlista():
    cfg = las_cfg()
    return jsonify(cachead("merit:" + cache_nyckel(cfg),
                           lambda: _rakna_meritlista(cfg)))


def _rakna_meritlista(cfg):
    rf = float(cfg.get("riskfri_ranta", 0.02))
    kapital = kapital_fran(cfg)
    innehav = cfg["innehav"]
    from datetime import timedelta
    start = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")

    tickers = [h["ticker"] for h in innehav]
    raw = np.array([float(h["vikt"]) for h in innehav], dtype=float)
    alla = list(set(tickers + [tr_mod.BENCH_VWCE, tr_mod.BENCH_BOND]))
    with YF_LAS:
        priser = tr_mod.hamta(alla, start)
    finns = [t for t in tickers if t in priser.columns]
    idx = [i for i, t in enumerate(tickers) if t in finns]
    vikter = {t: raw[i] / raw[idx].sum() for i, t in zip(idx, finns)}

    min_k = tr_mod.buy_hold_kurva(priser, vikter, kapital)
    vwce_k = tr_mod.buy_hold_kurva(priser, {tr_mod.BENCH_VWCE: 1.0}, kapital)
    b64_k = tr_mod.buy_hold_kurva(priser, {tr_mod.BENCH_VWCE: 0.6,
                                           tr_mod.BENCH_BOND: 0.4}, kapital)

    def rad(key, m):
        return {"key": key, "slut": round(m["slut"]),
                "total": round(m["total"] * 100, 1),
                "cagr": round(m["cagr"] * 100, 1),
                "dd": round(m["dd"] * 100, 1), "sharpe": round(m["sharpe"], 2)}

    min_m = tr_mod.matt(min_k, rf)
    vwce_m = tr_mod.matt(vwce_k, rf)
    b64_m = tr_mod.matt(b64_k, rf)

    # kurvpunkter for graf (glesa ut till ~120 punkter)
    def punkter(k):
        steg = max(1, len(k) // 120)
        return [round(float(v)) for v in k.iloc[::steg]]

    return {
        "period": f"{priser.index[0].date()} - {priser.index[-1].date()}",
        "rader": [rad("min", min_m), rad("vwce", vwce_m), rad("b6040", b64_m)],
        # strukturerade domslut - gränssnittet formulerar texten pa valt sprak
        "domslut": [
            {"mot": "vwce", "diff_sharpe": round(min_m["sharpe"] - vwce_m["sharpe"], 2)},
            {"mot": "b6040", "diff_sharpe": round(min_m["sharpe"] - b64_m["sharpe"], 2)},
        ],
        "graf": {"min": punkter(min_k), "vwce": punkter(vwce_k),
                 "b6040": punkter(b64_k)},
    }


# =============== Sidan ===============

@app.get("/")
def index():
    with open(os.path.join(HERE, "dashboard.html"), encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/html")


# =============== Start ===============

def oppna_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{PORT}")


def forvarm():
    """Borja rakna Risk + Meritlista direkt vid start, sa flikarna ar
    fardiga (cachade) nar anvandaren klickar. Fel har ar ofarliga -
    fliken raknar da om sjalv vid klick."""
    try:
        cfg = las_cfg()
        cachead("risk:" + cache_nyckel(cfg), lambda: _rakna_risk(cfg))
        cachead("merit:" + cache_nyckel(cfg), lambda: _rakna_meritlista(cfg))
        cachead("stress:" + cache_nyckel(cfg), lambda: _rakna_stress(cfg))
    except Exception as e:
        print(f"(forvarmning misslyckades - flikarna raknar sjalva: {e})")


def main():
    with open(PIDFIL, "w") as f:
        f.write(str(os.getpid()))
    threading.Thread(target=oppna_browser, daemon=True).start()
    threading.Thread(target=forvarm, daemon=True).start()
    print(f"Dashboard: http://127.0.0.1:{PORT}   (stang med STOPPA_APP)")
    app.run(host="127.0.0.1", port=PORT, debug=False)


if __name__ == "__main__":
    main()
