"""Moteur d'analyse déterministe (aucun LLM ici).

Tous les chiffres que l'agent cite viennent de ce fichier. Le LLM ne calcule rien :
il appelle ces fonctions via des outils et explique les résultats.

Hypothèses (documentées et affichées dans l'app) :
- Rendements calculés sur `adj_close` (ajusté dividendes + fractionnements, source Yahoo Finance).
- Tout est converti en CAD avec le taux USD/CAD quotidien de la Banque du Canada.
- Calendrier commun = jours ouvrables américains (jours où SPY cote). Les prix TSX, le taux de
  change et les cryptos sont pris au dernier cours connu (report sur 5 jours max).
- Portefeuille simulé à poids constants (rééquilibrage quotidien implicite).
- Période : 2021-11-12 au 2026-11-12. Le passé ne prédit pas le futur.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "alphaforge_starter"
TRADING_DAYS = 252

SOURCES = {
    "prix": "prices_daily.csv (Yahoo Finance via yfinance, adj_close, 2021-11-12 → 2026-11-12)",
    "change": "fx_usdcad_daily.csv (Banque du Canada, série FXUSDCAD)",
    "univers": "assets_universe.csv (organisateurs, secteurs GICS simplifiés)",
    "macro": "macro_rates.csv (Banque du Canada + FRED)",
}

# Part « technologie » estimée des FNB (hypothèse explicite, ordre de grandeur des fiches émetteurs).
# Utilisée seulement pour l'exposition techno « par transparence ».
ETF_TECH_SHARE = {"QQQ": 0.60, "SPY": 0.40, "ESGV": 0.45, "XIU.TO": 0.10}
TECH_SECTORS = {"Information Technology", "Communication Services"}
DEFENSIVE_CLASSES = {"etf_bond", "etf_commodity", "cash"}
ENERGY_FOSSIL = {"XOM", "CNQ.TO", "ENB.TO"}


# --------------------------------------------------------------------------- données
@lru_cache(maxsize=1)
def load_universe() -> pd.DataFrame:
    u = pd.read_csv(DATA_DIR / "assets_universe.csv")
    cash = pd.DataFrame([{
        "asset_id": "A00", "ticker": "CASH", "name": "Liquidités (CAD)", "asset_class": "cash",
        "market": "-", "currency": "CAD", "sector": "Cash",
    }])
    return pd.concat([u, cash], ignore_index=True).set_index("ticker")


@lru_cache(maxsize=1)
def load_prices_cad() -> pd.DataFrame:
    """Matrice date × ticker des prix ajustés en CAD, sur le calendrier américain."""
    px = pd.read_csv(DATA_DIR / "prices_daily.csv", parse_dates=["date"])
    wide = px.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    fx = pd.read_csv(DATA_DIR / "fx_usdcad_daily.csv", parse_dates=["date"]).set_index("date")["usdcad"]

    calendar = wide["SPY"].dropna().index
    full = wide.reindex(wide.index.union(fx.index)).sort_index().ffill(limit=5)
    fx_full = fx.reindex(full.index).ffill(limit=5)
    full = full.loc[calendar]
    fx_full = fx_full.loc[calendar]

    ccy = load_universe()["currency"]
    for t in full.columns:
        if ccy.get(t) == "USD":
            full[t] = full[t] * fx_full
    full["CASH"] = 1.0  # liquidités : rendement nul (hypothèse prudente)
    return full.dropna(how="all")


@lru_cache(maxsize=1)
def load_macro_latest() -> dict:
    m = pd.read_csv(DATA_DIR / "macro_rates.csv", parse_dates=["date"])
    out = {}
    for sid, g in m.groupby("series_id"):
        last = g.sort_values("date").iloc[-1]
        out[sid] = {"label": last["label"], "valeur": float(last["value"]), "unite": last["unit"],
                    "date_observation": last["date"].date().isoformat(), "source": last["source"]}
    return out


# --------------------------------------------------------------------------- métriques
def _metrics_from_series(values: pd.Series) -> dict:
    values = values.dropna()
    rets = values.pct_change().dropna()
    years = (values.index[-1] - values.index[0]).days / 365.25
    cagr = (values.iloc[-1] / values.iloc[0]) ** (1 / years) - 1
    vol = rets.std() * np.sqrt(TRADING_DAYS)
    dd = values / values.cummax() - 1
    y22 = values.loc["2022"]
    ret_2022 = y22.iloc[-1] / y22.iloc[0] - 1 if len(y22) > 1 else np.nan
    monthly = values.resample("ME").last().pct_change().dropna()
    return {
        "rendement_annualise_pct": round(float(cagr) * 100, 1),
        "volatilite_annualisee_pct": round(float(vol) * 100, 1),
        "baisse_max_pct": round(float(dd.min()) * 100, 1),
        "date_creux": dd.idxmin().date().isoformat(),
        "rendement_2022_pct": round(float(ret_2022) * 100, 1),
        "pire_mois_pct": round(float(monthly.min()) * 100, 1),
    }


@lru_cache(maxsize=64)
def asset_metrics(ticker: str) -> dict:
    u = load_universe()
    if ticker not in u.index:
        raise KeyError(f"Ticker inconnu : {ticker}. Univers disponible : {', '.join(u.index)}")
    row = u.loc[ticker]
    base = {"ticker": ticker, "nom": row["name"], "classe": row["asset_class"],
            "secteur": row["sector"], "devise_cotation": row["currency"]}
    if ticker == "CASH":
        return {**base, "rendement_annualise_pct": 0.0, "volatilite_annualisee_pct": 0.0,
                "baisse_max_pct": 0.0, "rendement_2022_pct": 0.0, "pire_mois_pct": 0.0,
                "note": "Liquidités : rendement supposé nul (ignore les intérêts)."}
    return {**base, **_metrics_from_series(load_prices_cad()[ticker]), "source": SOURCES["prix"]}


def normalize(holdings: dict[str, float]) -> dict[str, float]:
    """Montants (CAD) → poids qui somment à 1. Ignore les montants nuls."""
    h = {t.upper(): float(v) for t, v in holdings.items() if float(v) > 0}
    total = sum(h.values())
    if total <= 0:
        raise ValueError("Portefeuille vide.")
    return {t: v / total for t, v in h.items()}


def portfolio_value_series(weights: dict[str, float]) -> pd.Series:
    px = load_prices_cad()[list(weights)]
    rets = px.pct_change().fillna(0.0)
    w = pd.Series(weights)
    port = (rets * w).sum(axis=1)
    return (1 + port).cumprod()


def exposures(weights: dict[str, float]) -> dict:
    u = load_universe()
    by_class, by_sector, by_currency = {}, {}, {}
    tech = 0.0
    for t, w in weights.items():
        r = u.loc[t]
        by_class[r["asset_class"]] = by_class.get(r["asset_class"], 0) + w
        by_sector[r["sector"]] = by_sector.get(r["sector"], 0) + w
        by_currency[r["currency"]] = by_currency.get(r["currency"], 0) + w
        if r["sector"] in TECH_SECTORS:
            tech += w
        tech += w * ETF_TECH_SHARE.get(t, 0)
    pct = lambda d: {k: round(v * 100, 1) for k, v in sorted(d.items(), key=lambda kv: -kv[1])}
    singles = {t: w for t, w in weights.items() if u.loc[t, "asset_class"] in {"equity", "crypto"}}
    top_single = max(singles.items(), key=lambda kv: kv[1]) if singles else ("aucun", 0.0)
    defensive = sum(w for t, w in weights.items() if u.loc[t, "asset_class"] in DEFENSIVE_CLASSES)
    return {
        "par_classe_pct": pct(by_class),
        "par_secteur_pct": pct(by_sector),
        "par_devise_pct": pct(by_currency),
        "exposition_techno_transparence_pct": round(tech * 100, 1),
        "crypto_pct": round(by_class.get("crypto", 0) * 100, 1),
        "defensif_pct": round(defensive * 100, 1),
        "plus_grosse_ligne": top_single[0],
        "plus_grosse_ligne_pct": round(top_single[1] * 100, 1),
        "note_concentration": "Seuls les titres individuels (actions, cryptos) comptent pour la concentration : "
                              "un FNB est déjà diversifié.",
        "energie_fossile_pct": round(sum(weights.get(t, 0) for t in ENERGY_FOSSIL) * 100, 1),
        "nombre_lignes": len(weights),
        "hypothese_techno": "Actions des secteurs IT + Communication, plus une part estimée des FNB "
                            f"({', '.join(f'{k} {int(v*100)}%' for k, v in ETF_TECH_SHARE.items())}).",
    }


# --------------------------------------------------------------------------- gouvernance
def check_rules(profile: dict, weights: dict[str, float], metrics: dict, expo: dict) -> list[dict]:
    """Contrôles déterministes portefeuille ↔ profil. Chaque constat cite valeur, seuil et source."""
    L = profile["limites"]
    findings = []

    def add(rule_id, severity, title, observed, threshold, explanation, source):
        findings.append({"id": rule_id, "gravite": severity, "titre": title, "observe": observed,
                         "seuil": threshold, "explication": explanation, "source": source})

    vol = metrics["volatilite_annualisee_pct"]
    if vol > L["volatilite_max_pct"]:
        add("R1", "élevée", "Volatilité supérieure au profil", f"{vol} %", f"≤ {L['volatilite_max_pct']} %",
            "Les variations historiques du portefeuille dépassent ce que le profil de risque peut supporter.",
            SOURCES["prix"])
    if metrics["baisse_max_pct"] < -L["baisse_max_toleree_pct"]:
        add("R2", "élevée", "Baisse maximale historique trop forte", f"{metrics['baisse_max_pct']} %",
            f"≥ -{L['baisse_max_toleree_pct']} %",
            f"Sur la période, le portefeuille aurait perdu jusqu'à {abs(metrics['baisse_max_pct'])} % "
            f"(creux le {metrics['date_creux']}).", SOURCES["prix"])
    if expo["plus_grosse_ligne_pct"] > L["ligne_max_pct"]:
        add("R3", "moyenne", "Concentration sur une seule ligne",
            f"{expo['plus_grosse_ligne']} = {expo['plus_grosse_ligne_pct']} %", f"≤ {L['ligne_max_pct']} %",
            "Une seule position pèse trop lourd : un problème propre à cette entreprise toucherait tout le portefeuille.",
            "Calcul sur les montants saisis")
    if expo["crypto_pct"] > L["crypto_max_pct"]:
        add("R4", "élevée" if L["crypto_max_pct"] == 0 else "moyenne", "Exposition crypto au-dessus de la limite",
            f"{expo['crypto_pct']} %", f"≤ {L['crypto_max_pct']} %",
            "Les cryptoactifs ont eu les plus fortes baisses de l'univers (voir métriques BTC/ETH).",
            SOURCES["univers"])
    if expo["exposition_techno_transparence_pct"] > L["techno_max_pct"]:
        add("R5", "moyenne", "Diversification sectorielle insuffisante (techno)",
            f"{expo['exposition_techno_transparence_pct']} %", f"≤ {L['techno_max_pct']} %",
            "L'exposition techno, FNB inclus par transparence, dépasse la limite fixée pour ce profil.",
            expo["hypothese_techno"])
    if expo["defensif_pct"] < L["defensif_min_pct"]:
        add("R6", "moyenne" if L["defensif_min_pct"] < 30 else "élevée", "Pas assez d'actifs défensifs",
            f"{expo['defensif_pct']} %", f"≥ {L['defensif_min_pct']} %",
            "Obligations, or et liquidités amortissent les baisses ; l'horizon du client en demande davantage.",
            SOURCES["univers"])
    excluded = [t for t in weights if t in set(profile.get("exclusions", []))]
    if excluded:
        add("R7", "élevée", "Titres contraires aux préférences déclarées", ", ".join(excluded),
            "0 %", profile.get("raison_exclusions", "Exclusion demandée par le client."),
            "Préférences du profil client. Aucune cote ESG dans le jeu de données : "
            "classement à valider avec des sources externes (rapports de durabilité, SEDAR+, EDGAR).")
    if metrics["rendement_2022_pct"] < -L["baisse_max_toleree_pct"]:
        add("R8", "info", "Scénario de stress 2022", f"{metrics['rendement_2022_pct']} %",
            f"≥ -{L['baisse_max_toleree_pct']} %",
            "En 2022, actions et obligations ont baissé ensemble : ce portefeuille aurait dépassé la tolérance du client.",
            SOURCES["prix"])
    return findings


def score(findings: list[dict]) -> int:
    penalty = {"élevée": 25, "moyenne": 10, "info": 3}
    return max(0, 100 - sum(penalty.get(f["gravite"], 0) for f in findings))


def analyze(profile: dict, holdings: dict[str, float]) -> dict:
    u = load_universe()
    unknown = [t for t in holdings if t.upper() not in u.index]
    if unknown:
        raise KeyError(f"Tickers inconnus : {unknown}. Univers : {', '.join(u.index)}")
    weights = normalize(holdings)
    series = portfolio_value_series(weights)
    metrics = _metrics_from_series(series)
    expo = exposures(weights)
    findings = check_rules(profile, weights, metrics, expo)
    return {
        "montant_total_cad": round(sum(float(v) for v in holdings.values()), 2),
        "poids_pct": {t: round(w * 100, 1) for t, w in sorted(weights.items(), key=lambda kv: -kv[1])},
        "metriques_historiques": metrics,
        "expositions": expo,
        "constats_gouvernance": findings,
        "score_adequation_sur_100": score(findings),
        "periode": f"{series.index[0].date()} → {series.index[-1].date()}",
        "sources": [SOURCES["prix"], SOURCES["change"], SOURCES["univers"]],
        "hypotheses": ["Poids constants (rééquilibrage quotidien)", "Conversion en CAD",
                       "Calendrier des jours ouvrables américains", "Liquidités à rendement nul",
                       "Rendements passés ≠ rendements futurs"],
    }
