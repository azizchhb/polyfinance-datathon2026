"""Piste B : profil et score.

Trois fonctions publiques :
    evaluer(mesures, profil)
    simuler(portefeuille, changement, profil, analyser)
    proposer_scenarios(portefeuille, profil, analyser)

`analyser` est la fonction de la piste A. Elle est passée en argument pour
pouvoir tester la piste B avec une fausse fonction.
"""
import numpy as np

# ---------------------------------------------------------------- hypothèses
NIVEAUX = [1, 2, 3]  # faible, modéré, élevé
CIBLES = {
    "vol_min":     [0.04, 0.08, 0.13],
    "vol_max":     [0.08, 0.13, 0.20],
    "perte_max":   [0.10, 0.20, 0.35],
    "paris_min":   [6, 5, 4],
    "titre_max":   [0.20, 0.25, 0.35],
    "secteur_max": [0.30, 0.35, 0.45],
    "crypto_max":  [0.00, 0.05, 0.10],
    "rendement_max": [0.04, 0.06, 0.08],
}
POIDS = {
    "preservation": (0.25, 0.45, 0.30),
    "equilibre":    (0.35, 0.30, 0.35),
    "croissance":   (0.35, 0.20, 0.45),
}
# Aligné sur assets_universe.csv. QQQ, TLT et GLD n'y sont pas : trop concentrés sur un seul pari.
FNB_LARGES = {"XIU.TO", "SPY", "ESGV", "XBB.TO", "ZST.TO", "AGG"}
FNB_PAR_CLASSE = {"actions": "XIU.TO", "obligations": "XBB.TO", "or": "GLD"}
PARIS_PLAFOND = 20.0
EPS = 1e-9


# ------------------------------------------------------------ étape 1 : cibles
def capacite(horizon_annees):
    if horizon_annees <= 3:
        return 1
    if horizon_annees <= 7:
        return 2
    return 3


def niveau_effectif(profil):
    return min(profil["risque"], capacite(profil["horizon_annees"]))


def cible(nom, niveau):
    return float(np.interp(niveau, NIVEAUX, CIBLES[nom]))


# ------------------------------------------------------------- étape 2 : notes
def note_plage(x, a, b, penaliser_bas=True):
    if x > b:
        return max(0.0, 100 * (1 - (x - b) / b))
    if x < a and penaliser_bas:
        return 100 * x / a
    return 100.0


def note_plafond(x, limite):
    if x <= limite:
        return 100.0
    return max(0.0, 100 * (1 - (x - limite) / limite))


def note_plancher(x, minimum):
    if x >= minimum:
        return 100.0
    return max(0.0, 100 * (x - 1) / (minimum - 1))


def paris_ajustes(contributions):
    somme = sum(c ** 2 for s, c in contributions.items() if s not in FNB_LARGES)
    return PARIS_PLAFOND if somme < EPS else min(PARIS_PLAFOND, 1 / somme)


# ------------------------------------------------------------------ affichage
def pct(x, decimales=1):
    texte = f"{100 * x:.{decimales}f}".rstrip("0").rstrip(".")
    return texte.replace(".", ",") + " %"


def nombre(x, decimales=2):
    return f"{x:.{decimales}f}".rstrip("0").rstrip(".").replace(".", ",")


def dollars(x):
    return f"{x:,.0f}".replace(",", " ") + " $"


def verdict(score):
    if score >= 80:
        return "adequat"
    if score >= 60:
        return "a_surveiller"
    return "inadequat"


# ----------------------------------------------------------- étape 4 : alertes
def rendement_requis(capital, cotisation_annuelle, annees, montant_vise):
    """Rendement annuel r tel que la valeur future atteint le montant visé."""
    def valeur_future(r):
        croissance = (1 + r) ** annees
        rente = annees if abs(r) < EPS else (croissance - 1) / r
        return capital * croissance + cotisation_annuelle * rente

    bas, haut = -0.5, 1.0
    if valeur_future(haut) < montant_vise:
        return haut
    if valeur_future(bas) > montant_vise:
        return bas
    for _ in range(100):  # dichotomie
        milieu = (bas + haut) / 2
        if valeur_future(milieu) < montant_vise:
            bas = milieu
        else:
            haut = milieu
    return (bas + haut) / 2


def _alerte(code, gravite, message):
    return {"code": code, "gravite": gravite, "message": message}


def alertes(mesures, profil, n):
    liste = []
    classes = mesures.get("poids_par_classe", {})
    secteurs = mesures.get("poids_par_secteur", {})
    interet = profil.get("secteurs_interet") or []

    # contraintes : la personne a dit non
    crypto = classes.get("crypto", 0)
    if profil.get("crypto", "oui") == "non" and crypto > EPS:
        liste.append(_alerte("CRYPTO_REFUSEE", "contrainte",
            f"Le portefeuille contient {pct(crypto)} de cryptoactifs alors que le profil les exclut."))
    for s in profil.get("exclure_secteurs") or []:
        if secteurs.get(s, 0) > EPS:
            liste.append(_alerte("SECTEUR_EXCLU", "contrainte",
                f"Le secteur {s} représente {pct(secteurs[s])} du portefeuille alors que le profil l'exclut."))

    # avertissements : un seuil du tableau des cibles est dépassé
    plafond = cible("crypto_max", n)
    if profil.get("crypto", "oui") == "oui" and crypto > plafond + EPS:
        liste.append(_alerte("CRYPTO_PLAFOND", "avertissement",
            f"Les cryptoactifs représentent {pct(crypto)} du portefeuille. Le plafond retenu pour ce profil est de {pct(plafond)}."))

    hors_fnb = {s: c for s, c in mesures["contributions"].items() if s not in FNB_LARGES}
    if hors_fnb:
        titre = max(hors_fnb, key=hors_fnb.get)
        plafond = cible("titre_max", n)
        if hors_fnb[titre] > plafond + EPS:
            liste.append(_alerte("TITRE_DOMINANT", "avertissement",
                f"{titre} porte {pct(hors_fnb[titre])} du risque du portefeuille. Le plafond retenu pour ce profil est de {pct(plafond)}."))

    plafond = cible("secteur_max", n)
    for s, w in secteurs.items():
        if s != "diversifie" and w > plafond + EPS:
            debut = (f"Le secteur {s}, indiqué comme secteur d'intérêt, représente"
                     if s in interet else f"Le secteur {s} représente")
            liste.append(_alerte("SECTEUR_DOMINANT", "avertissement",
                f"{debut} {pct(w)} du portefeuille. Le plafond retenu pour ce profil est de {pct(plafond)}."))

    if profil["risque"] > capacite(profil["horizon_annees"]):
        liste.append(_alerte("PROFIL_CONTRADICTOIRE", "avertissement",
            f"La tolérance déclarée (niveau {nombre(profil['risque'])}) dépasse ce que permet un horizon de "
            f"{nombre(profil['horizon_annees'])} ans (niveau {capacite(profil['horizon_annees'])}). Le niveau {nombre(n)} est utilisé."))

    declaree = profil.get("perte_max_toleree")
    if declaree is not None and declaree < 0.5 * cible("perte_max", profil["risque"]):
        liste.append(_alerte("PERTE_CONTRADICTOIRE", "avertissement",
            f"La perte tolérée déclarée ({pct(declaree)}) est très inférieure à celle associée au niveau de risque "
            f"déclaré ({pct(cible('perte_max', profil['risque']))})."))

    vise, capital = profil.get("montant_vise"), mesures.get("capital")
    if vise and capital:
        r = rendement_requis(capital, 12 * (profil.get("cotisation_mensuelle") or 0),
                             profil["horizon_annees"], vise)
        seuil = cible("rendement_max", n)
        if r > seuil + EPS:
            liste.append(_alerte("RENDEMENT_REQUIS_ELEVE", "avertissement",
                f"Atteindre {dollars(vise)} en {nombre(profil['horizon_annees'])} ans exige environ {pct(r)} par an. "
                f"Le seuil retenu pour ce profil est de {pct(seuil)}."))
    return liste


# ----------------------------------------------------- étape 3 : score global
def evaluer(mesures, profil):
    n = niveau_effectif(profil)
    objectif = profil["objectif"]
    hypotheses = []

    a, b = cible("vol_min", n), cible("vol_max", n)
    hypotheses.append(f"Plage de volatilité cible pour le niveau {nombre(n)} : {pct(a)} à {pct(b)} (choix de l'équipe).")

    limite_tableau = cible("perte_max", n)
    declaree = profil.get("perte_max_toleree")
    limite = limite_tableau if declaree is None else min(declaree, limite_tableau)
    if declaree is None:
        hypotheses.append(f"Perte tolérée non précisée : {pct(limite)} supposés pour le niveau {nombre(n)}.")

    minimum = cible("paris_min", n)
    paris = paris_ajustes(mesures["contributions"])
    hypotheses.append(f"Minimum de {nombre(minimum)} paris effectifs pour le niveau {nombre(n)} (choix de l'équipe).")
    hypotheses.append("Les FNB larges sont traités comme parfaitement diversifiés ; leur contenu n'est pas analysé.")
    if profil.get("exclure_secteurs"):
        hypotheses.append("Exclusions ESG approximées par secteur, sans cote ESG, et sans voir le contenu des FNB larges.")

    vol, perte = mesures["volatilite"], mesures["perte_max"]
    n1 = round(note_plage(vol, a, b, penaliser_bas=objectif != "preservation"))
    n2 = round(note_plafond(perte, limite))
    n3 = round(note_plancher(paris, minimum))
    w1, w2, w3 = POIDS[objectif]
    score = round(w1 * n1 + w2 * n2 + w3 * n3)
    hypotheses.append(f"Poids des notes pour l'objectif {objectif} : {nombre(w1)}, {nombre(w2)}, {nombre(w3)} (choix de l'équipe).")

    if vol > b:
        e1 = f"Volatilité de {pct(vol)}, au-dessus de la plage cible de {pct(a)} à {pct(b)}."
    elif vol < a:
        e1 = f"Volatilité de {pct(vol)}, sous la plage cible de {pct(a)} à {pct(b)}."
    else:
        e1 = f"Volatilité de {pct(vol)}, dans la plage cible de {pct(a)} à {pct(b)}."
    position = "au-dessus de" if perte > limite else "dans"
    e2 = f"Perte maximale historique de {pct(perte)}, {position} la limite tolérée de {pct(limite)}."
    position = "sous le" if paris < minimum else "au niveau ou au-dessus du"
    e3 = f"{nombre(paris)} paris effectifs, {position} minimum de {nombre(minimum)}."

    notes = [
        {"nom": "niveau_de_risque", "valeur": vol, "cible": [a, b], "note": n1, "poids": w1, "explication": e1},
        {"nom": "risque_de_perte", "valeur": perte, "cible": limite, "note": n2, "poids": w2, "explication": e2},
        {"nom": "diversification", "valeur": round(paris, 2), "cible": minimum, "note": n3, "poids": w3, "explication": e3},
    ]
    return {
        "score": score,
        "verdict": verdict(score),
        "niveau_effectif": n,
        "notes": notes,
        "alertes": alertes(mesures, profil, n),
        "hypotheses": hypotheses,
    }


# -------------------------------------------------------- étape 5 : scénarios
def appliquer(portefeuille, changement):
    """Renvoie un nouveau portefeuille (symbole -> montant) sans modifier l'original."""
    nouveau = dict(portefeuille)
    total = sum(nouveau.values())
    symbole = changement["symbole"]
    genre = changement["type"]

    if genre == "ajouter":
        nouveau[symbole] = nouveau.get(symbole, 0) + changement["montant"]
        return nouveau

    if genre == "plafonner":
        garde = min(nouveau[symbole], changement["poids_max"] * total)
    elif genre == "retirer":
        garde = 0.0
    else:
        raise ValueError(f"Type de changement inconnu : {genre}")

    libere = nouveau[symbole] - garde
    autres = total - nouveau[symbole]
    if autres <= 0:
        raise ValueError("Impossible de répartir : le portefeuille n'a qu'une ligne.")
    for s in nouveau:
        if s != symbole:
            nouveau[s] += libere * nouveau[s] / autres  # répartition au prorata
    if garde > 0:
        nouveau[symbole] = garde
    else:
        del nouveau[symbole]
    return nouveau


def _phrase(changement, portefeuille, avant, apres):
    total = sum(portefeuille.values())
    s = changement["symbole"]
    fin = f"le score passerait de {avant['score']} à {apres['score']}."
    if changement["type"] == "plafonner":
        return (f"Scénario fictif : si {s} passait de {pct(portefeuille[s] / total)} à "
                f"{pct(changement['poids_max'])} du portefeuille, {fin}")
    if changement["type"] == "ajouter":
        return f"Scénario fictif : si {dollars(changement['montant'])} de {s} étaient ajoutés au portefeuille, {fin}"
    return f"Scénario fictif : si {s} sortait du portefeuille, {fin}"


def simuler(portefeuille, changement, profil, analyser):
    mesures_avant = analyser(portefeuille)
    avant = evaluer(mesures_avant, profil)
    mesures_apres = analyser(appliquer(portefeuille, changement))
    apres = evaluer(mesures_apres, profil)

    ameliore, degrade = [], []
    for x, y in zip(avant["notes"], apres["notes"]):
        if y["note"] != x["note"]:
            ligne = f"{x['nom']} : {x['note']} → {y['note']}"
            (ameliore if y["note"] > x["note"] else degrade).append(ligne)

    codes_avant = {al["code"] for al in avant["alertes"]}
    codes_apres = {al["code"] for al in apres["alertes"]}
    ameliore += [f"alerte levée : {c}" for c in sorted(codes_avant - codes_apres)]
    degrade += [f"nouvelle alerte : {c}" for c in sorted(codes_apres - codes_avant)]

    for s in profil.get("secteurs_interet") or []:
        w0 = mesures_avant.get("poids_par_secteur", {}).get(s, 0)
        w1 = mesures_apres.get("poids_par_secteur", {}).get(s, 0)
        if w1 < w0 - 0.005:
            degrade.append(f"poids du secteur d'intérêt {s} : {pct(w0)} → {pct(w1)}")

    hypotheses = list(apres["hypotheses"])
    if changement["type"] in ("plafonner", "retirer"):
        hypotheses.append("Le montant libéré est réparti sur les autres lignes au prorata de leur poids.")
    else:
        hypotheses.append("Le montant ajouté est de l'argent nouveau : le total du portefeuille augmente.")

    return {
        "changement": changement,
        "avant": avant,
        "apres": apres,
        "ameliore": ameliore,
        "degrade": degrade,
        "phrase": _phrase(changement, portefeuille, avant, apres),
        "hypotheses": hypotheses,
    }


def _candidats(portefeuille, mesures, profil):
    total = sum(portefeuille.values())
    liste = []

    # 1. réduire de moitié les trois plus gros contributeurs au risque, hors FNB larges
    hors_fnb = {s: c for s, c in mesures["contributions"].items()
                if s not in FNB_LARGES and s in portefeuille}
    for s in sorted(hors_fnb, key=hors_fnb.get, reverse=True)[:3]:
        liste.append({"type": "plafonner", "symbole": s,
                      "poids_max": round(portefeuille[s] / total / 2, 4)})

    # 2. ajouter un FNB large pour chaque classe absente ou sous les 10 %
    classes = mesures.get("poids_par_classe", {})
    for classe, fnb in FNB_PAR_CLASSE.items():
        if classes.get(classe, 0) < 0.10:
            liste.append({"type": "ajouter", "symbole": fnb, "montant": round(0.10 * total)})

    # 3. retirer les lignes qui violent une contrainte
    classe_de = mesures.get("classe_par_titre", {})
    secteur_de = mesures.get("secteur_par_titre", {})
    exclus = set(profil.get("exclure_secteurs") or [])
    for s in portefeuille:
        crypto_refusee = profil.get("crypto", "oui") == "non" and classe_de.get(s) == "crypto"
        if (crypto_refusee or secteur_de.get(s) in exclus) and len(portefeuille) > 1:
            liste.append({"type": "retirer", "symbole": s})
    return liste


def proposer_scenarios(portefeuille, profil, analyser, maximum=3):
    mesures = analyser(portefeuille)
    retenus = []
    for changement in _candidats(portefeuille, mesures, profil):
        resultat = simuler(portefeuille, changement, profil, analyser)
        avant, apres = resultat["avant"], resultat["apres"]

        contraintes_avant = {al["code"] for al in avant["alertes"] if al["gravite"] == "contrainte"}
        contraintes_apres = {al["code"] for al in apres["alertes"] if al["gravite"] == "contrainte"}
        if contraintes_apres - contraintes_avant:
            continue  # crée une nouvelle contrainte violée

        secteurs_apres = analyser(appliquer(portefeuille, changement)).get("poids_par_secteur", {})
        if any(mesures.get("poids_par_secteur", {}).get(s, 0) > EPS and secteurs_apres.get(s, 0) < EPS
               for s in profil.get("secteurs_interet") or []):
            continue  # ramène à zéro un secteur d'intérêt

        levees = len(contraintes_avant - contraintes_apres)
        if apres["score"] > avant["score"] or levees > 0:
            retenus.append((levees, apres["score"], resultat))

    retenus.sort(key=lambda t: (t[0], t[1]), reverse=True)
    scenarios, symboles = [], set()
    for _, _, resultat in retenus:
        s = resultat["changement"]["symbole"]
        if s not in symboles:
            scenarios.append(resultat)
            symboles.add(s)
        if len(scenarios) == maximum:
            break
    return scenarios
