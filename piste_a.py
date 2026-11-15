"""Piste A : les calculs. Expose analyser(portefeuille) -> mesures, le contrat du CLAUDE.md.

Deux couches :
1. PisteACalculations : le moteur de calcul écrit par le collègue de la piste A (covariance de
   Markowitz, contributions au risque, perte maximale), adapté aux rendements simples du contrat.
2. analyser() : lit les données par donnees.py (S3 d'abord, copie locale en secours), convertit
   en dollars canadiens, aligne les calendriers, applique la correspondance classe et secteur
   du CLAUDE.md et renvoie des nombres Python simples, plus la liste des hypothèses.

Lancer `python piste_a.py` : vérifications du CLAUDE.md, portefeuille de démonstration,
trois portefeuilles de référence pour calibrer la piste B.
"""
import functools

import numpy as np
import pandas as pd

import donnees

JOURS_PAR_AN = 252


# ======================================================================
# 1. Le moteur de calcul (classe du collègue, étapes 4 à 7 du CLAUDE.md)
# ======================================================================
class PisteACalculations:
    def __init__(self, prices_df: pd.DataFrame, weights, risk_free_rate: float = 0.035):
        """
        :param prices_df: prix (colonnes = titres, lignes = dates), déjà en CAD et alignés
        :param weights: poids du portefeuille, dans l'ordre des colonnes, somme 1
        :param risk_free_rate: taux sans risque annuel (non utilisé par le contrat, gardé pour plus tard)
        """
        self.prices_df = prices_df
        self.weights = np.array(weights, dtype=float)
        self.rf = risk_free_rate
        self.returns_df = None
        self.cov_matrix = None
        self.portfolio_volatility = 0.0

    def step_1_prices_to_returns(self) -> pd.DataFrame:
        """
        [Étape 1] Rendements simples quotidiens : r_t = P_t / P_(t-1) - 1  (contrat, étape 4).
        Les prix doivent déjà être en CAD et sur un calendrier commun : voir analyser().
        """
        self.returns_df = (self.prices_df / self.prices_df.shift(1) - 1).dropna()
        return self.returns_df

    def step_2_markowitz_volatility(self) -> tuple:
        """
        [Étape 2] Covariance annualisée et volatilité de Markowitz.
        Formule : sigma_p = sqrt(w' * Cov * w), Cov annualisée sur 252 jours.
        """
        if self.returns_df is None:
            raise ValueError("Run step_1_prices_to_returns first!")
        self.cov_matrix = self.returns_df.cov() * JOURS_PAR_AN
        portfolio_variance = np.dot(self.weights.T, np.dot(self.cov_matrix, self.weights))
        self.portfolio_volatility = np.sqrt(portfolio_variance)
        return self.cov_matrix, self.portfolio_volatility

    def step_3_risk_contribution(self) -> pd.DataFrame:
        """
        [Étape 3] Contribution au risque de chaque titre.
        Formule : MRC_i = (Cov * w)_i / sigma_p ; RC_i = w_i * MRC_i ; part_i = RC_i / sigma_p.
        La somme des parts vaut 1.
        """
        if self.cov_matrix is None:
            self.step_2_markowitz_volatility()
        cov_dot_weights = np.dot(self.cov_matrix, self.weights)
        mrc = cov_dot_weights / self.portfolio_volatility
        rc = self.weights * mrc
        pct_rc = rc / self.portfolio_volatility
        return pd.DataFrame(
            {"Weight": self.weights, "Marginal_Risk_Contrib": mrc,
             "Absolute_Risk_Contrib": rc, "Pct_Risk_Contrib": pct_rc},
            index=self.returns_df.columns,
        )

    def step_4_maximum_drawdown(self) -> dict:
        """
        [Étape 4] Perte maximale historique du portefeuille à pondérations constantes.
        Formule : Drawdown_t = (Peak_t - Value_t) / Peak_t ; MDD = max(Drawdown_t).
        Renvoie un nombre négatif (recul) ; analyser() le rend positif pour le contrat.
        """
        if self.returns_df is None:
            raise ValueError("Run step_1_prices_to_returns first!")
        portfolio_daily_returns = np.dot(self.returns_df, self.weights)
        cumulative_wealth = np.cumprod(1 + portfolio_daily_returns)
        running_max = np.maximum.accumulate(cumulative_wealth)
        drawdowns = (cumulative_wealth - running_max) / running_max
        return {
            "max_drawdown": float(np.min(drawdowns)),
            "cumulative_wealth_series": cumulative_wealth,
            "drawdown_series": drawdowns,
        }


# ======================================================================
# 2. Le contrat : analyser(portefeuille)
# ======================================================================
CLASSES = {"equity": "actions", "etf_equity": "actions", "etf_bond": "obligations",
           "etf_commodity": "or", "crypto": "crypto"}
SECTEURS = {
    "Information Technology": "technologie", "Energy": "energie", "Financials": "finance",
    "Health Care": "sante", "Industrials": "industrie", "Utilities": "services_publics",
    "Communication Services": "communication", "Consumer Staples": "consommation_de_base",
    "Consumer Discretionary": "consommation_discretionnaire", "Gold": "or", "Crypto asset": "crypto",
}


def _secteur(ticker, sector):
    if ticker == "QQQ":
        return "technologie"  # hypothèse de l'équipe : FNB très concentré en technologie
    if sector.startswith("Broad market") or sector.startswith("Bonds"):
        return "diversifie"
    return SECTEURS.get(sector, "autre")


@functools.lru_cache(maxsize=1)
def univers():
    """symbole -> (classe, secteur) d'après assets_universe.csv et la table du CLAUDE.md."""
    table = donnees.charger("assets_universe.csv")
    return {str(r.ticker).strip().upper(): (CLASSES[r.asset_class], _secteur(r.ticker, r.sector))
            for r in table.itertuples()}


def symboles_non_couverts(portefeuille):
    """Symboles du portefeuille absents des 31 actifs du jeu de données (étape 9 : les signaler)."""
    connus = univers()
    return sorted({str(s).strip().upper() for s in portefeuille} - set(connus))


@functools.lru_cache(maxsize=1)
def prix_cad():
    """Cours ajustés en dollars canadiens : un tableau dates x symboles, trous laissés vides.

    Étape 1 : adj_close par date et par symbole. Étape 2 : les titres en USD sont multipliés par
    le taux USD/CAD de la Banque du Canada du jour ; le dernier taux connu est reporté les jours
    sans cotation du taux (fins de semaine de la crypto, jours fériés).
    """
    prix = donnees.charger("prices_daily.csv", parse_dates=["date"])
    fx = donnees.charger("fx_usdcad_daily.csv", parse_dates=["date"]).set_index("date")["usdcad"].sort_index()
    large = prix.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    taux = fx.reindex(large.index, method="ffill").bfill()
    devises = prix.groupby("ticker")["currency"].first()
    en_usd = [t for t in large.columns if devises[t] == "USD"]
    large[en_usd] = large[en_usd].mul(taux, axis=0)
    return large


def _provenance_donnees():
    sources = " ".join(donnees.provenance())
    if "s3://" in sources:
        return f"Données lues depuis Amazon S3 (seau {donnees.seau()})."
    if "cache" in sources:
        return "Données lues depuis le cache local du seau S3."
    return "Données lues depuis la copie locale du dépôt (S3 injoignable)."


CRISE = ("2022-01-01", "2022-12-31")  # seule crise couverte : le jeu commence en novembre 2021


def _pire_baisse(valeurs):
    """Pire baisse du sommet au creux d'une série de valeurs, en nombre positif."""
    valeurs = np.asarray(valeurs, dtype=float)
    return float(1 - (valeurs / np.maximum.accumulate(valeurs)).min())


def crise_2022(rendements, poids):
    """Le portefeuille rejoué sur l'année 2022, à pondérations constantes.

    2022 : hausse rapide des taux, actions et obligations en baisse ensemble. Renvoie la pire
    baisse du portefeuille pendant l'année, sa variation du premier au dernier jour, et la pire
    baisse de chaque titre sur la même période. None si le portefeuille n'a pas de prix en 2022.
    """
    r = rendements.loc[CRISE[0]:CRISE[1]]
    if len(r) < 20:
        return None
    valeur = np.cumprod(1 + r.values @ poids)
    par_titre = {s: _pire_baisse(np.cumprod(1 + r[s].values)) for s in r.columns}
    return {"perte": _pire_baisse(np.concatenate([[1.0], valeur])),
            "variation": float(valeur[-1] - 1),
            "par_titre": par_titre,
            "debut": str(r.index[0].date()), "fin": str(r.index[-1].date())}


def analyser(portefeuille):
    """Mesure le portefeuille (symbole -> montant en CAD) et renvoie les mesures du contrat.

    Lève ValueError si un symbole n'est pas couvert par le jeu de données ou si le portefeuille
    est vide : on signale, on n'ignore jamais en silence (étape 9).
    """
    montants = {}
    for s, m in portefeuille.items():
        if float(m) > 0:
            cle = str(s).strip().upper()
            montants[cle] = montants.get(cle, 0.0) + float(m)
    if not montants:
        raise ValueError("Portefeuille vide : aucun montant positif.")
    manquants = symboles_non_couverts(montants)
    if manquants:
        raise ValueError("Symboles non couverts par le jeu de données : " + ", ".join(manquants)
                         + ". Retirer ces lignes ou les remplacer par un des 31 actifs couverts.")

    connus = univers()
    capital = sum(montants.values())
    ordre = list(montants)
    poids = np.array([montants[s] / capital for s in ordre])

    # Étape 3 : garder les dates où tous les titres du portefeuille ont un prix, sans remplir les trous.
    prix = prix_cad()[ordre].dropna()
    if len(prix) < 30:
        raise ValueError(f"Trop peu de dates communes ({len(prix)}) pour mesurer ce portefeuille.")

    moteur = PisteACalculations(prix, poids)
    moteur.step_1_prices_to_returns()
    _, volatilite = moteur.step_2_markowitz_volatility()
    contributions = moteur.step_3_risk_contribution()["Pct_Risk_Contrib"]
    perte_max = -moteur.step_4_maximum_drawdown()["max_drawdown"]  # contrat : perte en nombre positif

    crise = crise_2022(moteur.returns_df, poids)

    # Gain de diversification (Markowitz, sans rendement espéré) : la volatilité qu'aurait le
    # portefeuille si tous les titres bougeaient ensemble, soit la moyenne pondérée de leurs
    # volatilités, face à la volatilité réelle. L'écart est ce que la diversification efface.
    vol_par_titre = moteur.returns_df.std(ddof=1) * np.sqrt(JOURS_PAR_AN)
    vol_sans_diversification = float(np.dot(poids, vol_par_titre.loc[ordre].values))
    gain = vol_sans_diversification - float(volatilite)
    ratio = vol_sans_diversification / float(volatilite) if volatilite > 0 else 1.0

    par_classe, par_secteur = {}, {}
    for s, w in zip(ordre, poids):
        classe, secteur = connus[s]
        par_classe[classe] = par_classe.get(classe, 0.0) + float(w)
        par_secteur[secteur] = par_secteur.get(secteur, 0.0) + float(w)

    debut, fin = prix.index[0].date(), prix.index[-1].date()
    hypotheses = [
        f"Mesures sur les cours ajustés du {debut} au {fin}, soit {len(moteur.returns_df)} rendements "
        "quotidiens, sur les dates où tous les titres du portefeuille cotent (aucun trou rempli).",
        "Titres en dollars américains convertis en dollars canadiens au taux du jour de la Banque du Canada, "
        "dernier taux reporté les jours sans cotation : le risque mesuré est celui d'un investisseur canadien.",
        "Rendements simples quotidiens, covariance annualisée sur 252 jours, volatilité = racine de w'Σw.",
        "Perte maximale : pire baisse du sommet au creux de la valeur du portefeuille, à pondérations constantes.",
        "Gain de diversification : écart entre la moyenne pondérée des volatilités des titres (si tous "
        "bougeaient ensemble) et la volatilité réelle du portefeuille ; aucun rendement espéré n'intervient.",
        "Crise de 2022 : le portefeuille actuel rejoué du premier au dernier jour de cotation de 2022, à "
        "pondérations constantes ; c'est la seule crise couverte (données à partir de novembre 2021), "
        "ni 2008 ni mars 2020. Une crise future peut toucher d'autres actifs.",
        "Univers de 31 actifs choisi en 2026 parmi des titres devenus gros (biais du survivant). "
        "Aucune composition de FNB, aucune cote ESG, aucune donnée fondamentale.",
        _provenance_donnees(),
    ]

    return {
        "volatilite": float(volatilite),
        "perte_max": float(perte_max),
        "poids": {s: float(w) for s, w in zip(ordre, poids)},
        "contributions": {s: float(contributions[s]) for s in ordre},
        "poids_par_classe": par_classe,
        "poids_par_secteur": par_secteur,
        "classe_par_titre": {s: connus[s][0] for s in ordre},
        "secteur_par_titre": {s: connus[s][1] for s in ordre},
        "capital": float(capital),
        # Ajouts du 15 novembre, en plus du contrat : le gain de diversification de Markowitz.
        "volatilite_par_titre": {s: float(vol_par_titre[s]) for s in ordre},
        "volatilite_sans_diversification": vol_sans_diversification,
        "gain_diversification": gain,
        "ratio_diversification": ratio,
        # Ajout du 15 novembre : résistance à la crise de 2022 (None si aucun prix en 2022).
        "perte_crise_2022": crise["perte"] if crise else None,
        "variation_2022": crise["variation"] if crise else None,
        "perte_crise_2022_par_titre": crise["par_titre"] if crise else {},
        "hypotheses": hypotheses,
    }


# ======================================================================
# Vérifications du CLAUDE.md et portefeuilles de référence
# ======================================================================
if __name__ == "__main__":
    import json
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    from piste_b import evaluer, pct

    CLES_CONTRAT = {"volatilite", "perte_max", "poids", "contributions", "poids_par_classe",
                    "poids_par_secteur", "classe_par_titre", "secteur_par_titre", "capital"}
    CLES_AJOUTEES = {"hypotheses", "volatilite_par_titre", "volatilite_sans_diversification",
                     "gain_diversification", "ratio_diversification",
                     "perte_crise_2022", "variation_2022", "perte_crise_2022_par_titre"}

    DEMO = {"NVDA": 10000, "QQQ": 12500, "BTC-USD": 5000, "XIU.TO": 17500, "XBB.TO": 5000}
    PERSONAS = {
        "Amira": {"risque": 3, "horizon_annees": 15, "objectif": "croissance", "crypto": "oui",
                  "exclure_secteurs": [], "secteurs_interet": ["technologie"], "experience": "intermediaire"},
        "Mateo": {"risque": 2, "horizon_annees": 10, "objectif": "equilibre", "crypto": "non",
                  "exclure_secteurs": ["energie"], "secteurs_interet": [], "experience": "intermediaire"},
        "Robert": {"risque": 1.5, "horizon_annees": 4, "objectif": "preservation", "crypto": "non",
                   "exclure_secteurs": [], "secteurs_interet": [], "experience": "avance"},
    }

    print("=== Portefeuille de démonstration ===")
    m = analyser(DEMO)
    print(json.dumps({k: v for k, v in m.items() if k != "hypotheses"}, ensure_ascii=False, indent=1))
    for h in m["hypotheses"]:
        print("-", h)

    print("\n=== Vérifications du CLAUDE.md ===")
    assert abs(sum(m["contributions"].values()) - 1) < 1e-9, "la somme des contributions doit valoir 1"
    seul = analyser({"NVDA": 1000})
    attendu = prix_cad()["NVDA"].dropna().pct_change().dropna().std() * np.sqrt(JOURS_PAR_AN)
    assert abs(seul["volatilite"] - attendu) < 1e-9, "un seul titre doit avoir la volatilité du titre"
    assert set(m) - CLES_AJOUTEES == CLES_CONTRAT, "les clés doivent être celles du contrat"
    assert all(isinstance(v, float) for v in (m["volatilite"], m["perte_max"], m["capital"]))
    assert m["volatilite_sans_diversification"] >= m["volatilite"] - 1e-9, "la diversification ne peut pas ajouter de risque"
    assert abs(seul["gain_diversification"]) < 1e-9, "un seul titre : aucun gain de diversification"
    print(f"Gain de diversification de la démo : {pct(m['volatilite_sans_diversification'])} si tout bougeait "
          f"ensemble, {pct(m['volatilite'])} en réalité, ratio {m['ratio_diversification']:.2f}".replace(".", ","))
    try:
        analyser({"NVDA": 1000, "PLTR": 1000})
    except ValueError as e:
        print("Symbole non couvert bien signalé :", e)
    print("OK : contributions = 1, un seul titre = sa volatilité, clés du contrat, nombres Python simples.")

    print("\n=== Portefeuilles de référence (pour calibrer les cibles de la piste B) ===")
    REFERENCES = {
        "20/80 (prudent)": {"XIU.TO": 10, "SPY": 10, "XBB.TO": 80},
        "60/40 (équilibré)": {"XIU.TO": 30, "SPY": 30, "XBB.TO": 40},
        "100 % actions": {"XIU.TO": 50, "SPY": 50},
    }
    for nom, p in REFERENCES.items():
        r = analyser(p)
        print(f"{nom:<20} volatilité {pct(r['volatilite']):>7}   perte max {pct(r['perte_max']):>7}"
              f"   perte en 2022 {pct(r['perte_crise_2022']):>7}")

    print("\n=== Scores des trois personas sur la démo, avec les vraies mesures ===")
    for nom, profil in PERSONAS.items():
        r = evaluer(m, profil)
        print(f"{nom:<8} score {r['score']:>3}  {r['verdict']:<13} alertes : {[a['code'] for a in r['alertes']]}")
