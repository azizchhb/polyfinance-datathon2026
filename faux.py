"""Fausses pistes A et C, pour construire l'interface sans attendre.

Tous les chiffres de ce fichier sont inventés. Il respecte seulement le
format du contrat. À supprimer quand les vraies pistes sont branchées.
"""
import numpy as np

from piste_b import evaluer

# Les 31 actifs de assets_universe.csv : symbole -> (classe, secteur, volatilité annuelle inventée).
# Classes et secteurs suivent la table de correspondance du contrat. Seules les volatilités sont inventées.
TITRES = {
    "RY.TO":   ("actions", "finance", 0.17),
    "TD.TO":   ("actions", "finance", 0.18),
    "MFC.TO":  ("actions", "finance", 0.22),
    "ENB.TO":  ("actions", "energie", 0.17),
    "CNQ.TO":  ("actions", "energie", 0.30),
    "CNR.TO":  ("actions", "industrie", 0.19),
    "FTS.TO":  ("actions", "services_publics", 0.15),
    "ATD.TO":  ("actions", "consommation_de_base", 0.20),
    "SHOP.TO": ("actions", "technologie", 0.55),
    "CSU.TO":  ("actions", "technologie", 0.25),
    "AAPL":    ("actions", "technologie", 0.27),
    "MSFT":    ("actions", "technologie", 0.25),
    "NVDA":    ("actions", "technologie", 0.50),
    "GOOGL":   ("actions", "communication", 0.30),
    "AMZN":    ("actions", "consommation_discretionnaire", 0.33),
    "TSLA":    ("actions", "consommation_discretionnaire", 0.60),
    "JPM":     ("actions", "finance", 0.24),
    "JNJ":     ("actions", "sante", 0.17),
    "PG":      ("actions", "consommation_de_base", 0.16),
    "XOM":     ("actions", "energie", 0.26),
    "XIU.TO":  ("actions", "diversifie", 0.14),
    "SPY":     ("actions", "diversifie", 0.16),
    "QQQ":     ("actions", "technologie", 0.22),
    "ESGV":    ("actions", "diversifie", 0.17),
    "XBB.TO":  ("obligations", "diversifie", 0.06),
    "ZST.TO":  ("obligations", "diversifie", 0.01),
    "AGG":     ("obligations", "diversifie", 0.06),
    "TLT":     ("obligations", "diversifie", 0.15),
    "GLD":     ("or", "or", 0.15),
    "BTC-USD": ("crypto", "crypto", 0.65),
    "ETH-USD": ("crypto", "crypto", 0.80),
}
DEFAUT = ("actions", "autre", 0.25)


def _correlation(a, b):
    if a == b:
        return 1.0
    classe_a, classe_b = TITRES.get(a, DEFAUT)[0], TITRES.get(b, DEFAUT)[0]
    if classe_a == classe_b == "actions":
        return 0.7
    if "obligations" in (classe_a, classe_b):
        return 0.1
    return 0.3


def analyser(portefeuille):
    """Fausse piste A : même format que la vraie, chiffres inventés."""
    symboles = list(portefeuille)
    capital = float(sum(portefeuille.values()))
    poids = np.array([portefeuille[s] / capital for s in symboles])
    vols = np.array([TITRES.get(s, DEFAUT)[2] for s in symboles])
    covariance = np.array([[vols[i] * vols[j] * _correlation(a, b)
                            for j, b in enumerate(symboles)]
                           for i, a in enumerate(symboles)])
    variance = float(poids @ covariance @ poids)
    contributions = poids * (covariance @ poids) / variance

    par_classe, par_secteur = {}, {}
    for s, w in zip(symboles, poids):
        classe, secteur, _ = TITRES.get(s, DEFAUT)
        par_classe[classe] = par_classe.get(classe, 0.0) + float(w)
        par_secteur[secteur] = par_secteur.get(secteur, 0.0) + float(w)

    volatilite = variance ** 0.5
    return {
        "volatilite": volatilite,
        "perte_max": min(0.95, 1.9 * volatilite),  # inventé
        "poids": {s: float(w) for s, w in zip(symboles, poids)},
        "contributions": {s: float(c) for s, c in zip(symboles, contributions)},
        "poids_par_classe": par_classe,
        "poids_par_secteur": par_secteur,
        "classe_par_titre": {s: TITRES.get(s, DEFAUT)[0] for s in symboles},
        "secteur_par_titre": {s: TITRES.get(s, DEFAUT)[1] for s in symboles},
        "capital": capital,
    }


def demander(texte, portefeuille, profil):
    """Fausse piste C : renvoie une réponse au bon format, sans modèle de langage."""
    resultat = evaluer(analyser(portefeuille), profil)
    phrases = [f"Réponse factice à « {texte} ». Le score du portefeuille est de {resultat['score']} sur 100."]
    phrases += [note["explication"] for note in resultat["notes"]]
    if resultat["alertes"]:
        phrases.append(resultat["alertes"][0]["message"])
    return {
        "reponse": " ".join(phrases),
        "outils_appeles": [
            {"outil": "analyser", "resume": f"{len(portefeuille)} titres analysés"},
            {"outil": "evaluer", "resume": f"score de {resultat['score']} sur 100"},
        ],
        "limites": ["Réponse factice : l'agent de la piste C n'est pas encore branché."],
    }
