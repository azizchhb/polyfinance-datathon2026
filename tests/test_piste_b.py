"""Tests de la piste B, repris du tableau « Tests à écrire » du guide.

Lancer, depuis la racine du dépôt : python tests/test_piste_b.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # la racine : piste_b.py

from piste_b import (evaluer, simuler, proposer_scenarios, note_plage, note_plancher,
                     paris_ajustes, niveau_effectif, appliquer)

# Fausses mesures du guide (page 2)
MESURES = {
    "volatilite": 0.164,
    "perte_max": 0.31,
    "poids": {"NVDA": 0.20, "QQQ": 0.25, "BTC-USD": 0.10, "XIC.TO": 0.35, "ZAG.TO": 0.10},
    "contributions": {"NVDA": 0.40, "QQQ": 0.20, "BTC-USD": 0.25, "XIC.TO": 0.14, "ZAG.TO": 0.01},
    "poids_par_classe": {"actions": 0.80, "obligations": 0.10, "crypto": 0.10, "or": 0.0},
    "poids_par_secteur": {"technologie": 0.45, "diversifie": 0.45, "crypto": 0.10},
    "classe_par_titre": {"NVDA": "actions", "QQQ": "actions", "BTC-USD": "crypto",
                         "XIC.TO": "actions", "ZAG.TO": "obligations"},
    "secteur_par_titre": {"NVDA": "technologie", "QQQ": "technologie", "BTC-USD": "crypto",
                          "XIC.TO": "diversifie", "ZAG.TO": "diversifie"},
    "capital": 50000,
}

AMIRA = {"risque": 3, "horizon_annees": 15, "objectif": "croissance", "crypto": "oui",
         "secteurs_interet": ["technologie"]}
MATEO = {"risque": 2, "horizon_annees": 10, "objectif": "equilibre", "perte_max_toleree": 0.20,
         "crypto": "non", "exclure_secteurs": ["energie"], "secteurs_interet": ["technologie"]}
ROBERT = {"risque": 1.5, "horizon_annees": 4, "objectif": "preservation", "crypto": "non"}


def codes(resultat):
    return {a["code"] for a in resultat["alertes"]}


def test_trois_personas():
    a, m, r = evaluer(MESURES, AMIRA), evaluer(MESURES, MATEO), evaluer(MESURES, ROBERT)
    assert [n["note"] for n in a["notes"]] == [100, 100, 94], a["notes"]
    assert [n["note"] for n in m["notes"]] == [74, 45, 70], m["notes"]
    assert [n["note"] for n in r["notes"]] == [44, 0, 62], r["notes"]
    assert (a["score"], m["score"], r["score"]) == (97, 64, 30)
    assert (a["verdict"], m["verdict"], r["verdict"]) == ("adequat", "a_surveiller", "inadequat")
    assert "TITRE_DOMINANT" in codes(a)
    assert codes(m) == {"CRYPTO_REFUSEE", "TITRE_DOMINANT", "SECTEUR_DOMINANT"}


def test_bornes_des_notes():
    assert note_plage(0.08, 0.08, 0.13) == 100
    assert note_plage(0.13, 0.08, 0.13) == 100
    assert note_plage(0.26, 0.08, 0.13) == 0
    assert paris_ajustes({"SPY": 0.6, "XBB.TO": 0.4}) == 20  # que des FNB larges
    assert note_plancher(paris_ajustes({"NVDA": 1.0}), 5) == 0  # un seul titre


def test_tout_obligations():
    obligations = {**MESURES, "volatilite": 0.05}
    assert evaluer(obligations, {**AMIRA, "objectif": "croissance"})["notes"][0]["note"] < 100
    assert evaluer(obligations, {**ROBERT, "objectif": "preservation"})["notes"][0]["note"] == 100


def test_profil_contradictoire():
    profil = {"risque": 3, "horizon_annees": 2, "objectif": "croissance"}
    assert niveau_effectif(profil) == 1
    assert "PROFIL_CONTRADICTOIRE" in codes(evaluer(MESURES, profil))


def test_champ_optionnel_absent():
    res = evaluer(MESURES, {"risque": 2, "horizon_annees": 10, "objectif": "equilibre"})
    assert any("Perte tolérée non précisée" in h for h in res["hypotheses"])


def test_appliquer():
    p = {"A": 50, "B": 30, "C": 20}
    assert appliquer(p, {"type": "retirer", "symbole": "A"}) == {"B": 60, "C": 40}
    assert appliquer(p, {"type": "ajouter", "symbole": "D", "montant": 10})["D"] == 10
    assert p == {"A": 50, "B": 30, "C": 20}  # l'original n'est pas modifié


def fausse_analyser(portefeuille):
    """Fausse piste A : volatilité et contributions proportionnelles aux montants."""
    total = sum(portefeuille.values())
    poids = {s: v / total for s, v in portefeuille.items()}
    crypto = poids.get("BTC-USD", 0)
    return {**MESURES, "poids": poids, "contributions": poids,
            "volatilite": 0.08 + 0.4 * crypto, "perte_max": 0.12 + 0.6 * crypto,
            "poids_par_classe": {"actions": 1 - crypto, "crypto": crypto},
            "poids_par_secteur": {"diversifie": 1 - crypto, "crypto": crypto},
            "capital": total}


def test_simuler_et_scenarios():
    portefeuille = {"SPY": 30000, "NVDA": 10000, "BTC-USD": 10000}
    res = simuler(portefeuille, {"type": "retirer", "symbole": "BTC-USD"}, MATEO, fausse_analyser)
    assert "alerte levée : CRYPTO_REFUSEE" in res["ameliore"]
    assert isinstance(res["degrade"], list)
    assert res["phrase"].startswith("Scénario fictif")
    scenarios = proposer_scenarios(portefeuille, MATEO, fausse_analyser)
    assert scenarios and scenarios[0]["changement"] == {"type": "retirer", "symbole": "BTC-USD"}
    assert len({s["changement"]["symbole"] for s in scenarios}) == len(scenarios)


if __name__ == "__main__":
    tests = [f for nom, f in list(globals().items()) if nom.startswith("test_")]
    for t in tests:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(tests)} tests réussis.")
    for nom, profil in [("Amira", AMIRA), ("Mateo", MATEO), ("Robert", ROBERT)]:
        r = evaluer(MESURES, profil)
        print(f"{nom:7} score {r['score']:3} ({r['verdict']}) · notes {[n['note'] for n in r['notes']]} · alertes {sorted(codes(r))}")
