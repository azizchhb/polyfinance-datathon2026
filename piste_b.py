"""Piste B : profil et score.

Trois fonctions publiques :
    evaluer(mesures, profil)
    simuler(portefeuille, changement, profil, analyser)
    proposer_scenarios(portefeuille, profil, analyser)

`analyser` est la fonction de la piste A. Elle est passée en argument pour
pouvoir tester la piste B avec une fausse fonction.

Code repris du guide « Piste B · Profil et score », avec deux corrections :
  1. FNB_PAR_CLASSE utilise XIU.TO et XBB.TO (XIC.TO et ZAG.TO ne sont pas dans
     assets_universe.csv : la vraie piste A planterait dessus).
  2. FNB_LARGES contient les FNB larges du jeu de départ (XIU.TO, SPY, ESGV,
     XBB.TO, ZST.TO, AGG). XIC.TO et ZAG.TO y restent seulement parce que les
     fausses mesures du guide les utilisent.

Conventions : pourcentages en décimales (0.164 = 16,4 %), pertes en nombre
positif (0.31 = baisse de 31 %), clés en minuscules sans accent.
"""

import numpy as np

# ---------------------------------------------------------------- hypothèses
NIVEAUX = [1, 2, 3]  # faible, modéré, élevé
CIBLES = {
    "vol_min":       [0.04, 0.08, 0.13],
    "vol_max":       [0.08, 0.13, 0.20],
    "perte_max":     [0.10, 0.20, 0.35],
    "paris_min":     [6, 5, 4],
    "titre_max":     [0.20, 0.25, 0.35],
    "secteur_max":   [0.30, 0.35, 0.45],
    "crypto_max":    [0.00, 0.05, 0.10],
    "rendement_max": [0.04, 0.06, 0.08],
    # Pire baisse tolérée pendant la crise de 2022. Repères (en CAD) : 20/80 et 60/40 ont
    # perdu environ 14 %, 100 % actions 15,6 %, ZST.TO 0,4 % (python piste_a.py).
    "crise_max":     [0.12, 0.20, 0.35],
}
POIDS = {  # (niveau de risque, risque de perte, diversification)
    "preservation": (0.25, 0.45, 0.30),
    "equilibre":    (0.35, 0.30, 0.35),
    "croissance":   (0.35, 0.20, 0.45),
}
# Avec la quatrième note (résistance à la crise de 2022), quand la piste A la fournit.
POIDS_AVEC_CRISE = {  # (niveau de risque, risque de perte, diversification, crise de 2022)
    "preservation": (0.20, 0.30, 0.25, 0.25),
    "equilibre":    (0.30, 0.20, 0.30, 0.20),
    "croissance":   (0.30, 0.15, 0.40, 0.15),
}
# FNB d'indice général (actions ou obligations) : traités comme déjà diversifiés.
# Pas QQQ (concentré techno), pas TLT (pari sur les taux longs), pas GLD (or).
FNB_LARGES = {"XIU.TO", "SPY", "ESGV", "XBB.TO", "ZST.TO", "AGG",
              "XIC.TO", "ZAG.TO"}  # ces deux-là : seulement pour les fausses mesures du guide
FNB_PAR_CLASSE = {"actions": "XIU.TO", "obligations": "XBB.TO", "or": "GLD"}
PARIS_PLAFOND = 20.0
EPS = 1e-9


# ------------------------------------------------------------ étape 1 : cibles
def capacite(horizon_annees):
    """Risque que l'horizon permet : peu d'années = pas le temps de récupérer d'une baisse."""
    if horizon_annees <= 3:
        return 1
    if horizon_annees <= 7:
        return 2
    return 3


def niveau_effectif(profil):
    """On retient le plus prudent entre la tolérance déclarée et la capacité."""
    return min(profil["risque"], capacite(profil["horizon_annees"]))


def cible(nom, niveau):
    """Valeur de la cible pour ce niveau. np.interp gère les demi-niveaux (1.5, 2.5)."""
    return float(np.interp(niveau, NIVEAUX, CIBLES[nom]))


# ------------------------------------------------------------- étape 2 : notes
def note_plage(x, a, b, penaliser_bas=True):
    """100 dans [a, b], baisse en ligne droite de chaque côté. 0 au double de b."""
    if x > b:
        return max(0.0, 100 * (1 - (x - b) / b))
    if x < a and penaliser_bas:
        return 100 * x / a
    return 100.0


def note_plafond(x, limite):
    """100 sous la limite, puis baisse. 0 au double de la limite."""
    if x <= limite:
        return 100.0
    return max(0.0, 100 * (1 - (x - limite) / limite))


def note_plancher(x, minimum):
    """100 au-dessus du minimum. La droite part de 1 (un seul pari = 0)."""
    if x >= minimum:
        return 100.0
    return max(0.0, 100 * (x - 1) / (minimum - 1))


def paris_ajustes(contributions):
    """Nombre effectif de paris = 1 / somme des contributions au carré (Herfindahl),
    en excluant les FNB larges."""
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
    """Rendement annuel r tel que la valeur future atteint le montant visé (dichotomie)."""
    def valeur_future(r):
        croissance = (1 + r) ** annees
        rente = annees if abs(r) < EPS else (croissance - 1) / r
        return capital * croissance + cotisation_annuelle * rente

    bas, haut = -0.5, 1.0
    if valeur_future(haut) < montant_vise:
        return haut
    if valeur_future(bas) > montant_vise:
        return bas
    for _ in range(100):
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
            f"Les cryptoactifs représentent {pct(crypto)} du portefeuille. "
            f"Le plafond retenu pour ce profil est de {pct(plafond)}."))

    hors_fnb = {s: c for s, c in mesures["contributions"].items() if s not in FNB_LARGES}
    if hors_fnb:
        titre = max(hors_fnb, key=hors_fnb.get)
        plafond = cible("titre_max", n)
        if hors_fnb[titre] > plafond + EPS:
            liste.append(_alerte("TITRE_DOMINANT", "avertissement",
                f"{titre} porte {pct(hors_fnb[titre])} du risque du portefeuille. "
                f"Le plafond retenu pour ce profil est de {pct(plafond)}."))

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
            f"{nombre(profil['horizon_annees'])} ans (niveau {capacite(profil['horizon_annees'])}). "
            f"Le niveau {nombre(n)} est utilisé."))

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
    # On arrondit chaque note avant le score pour que le calcul affiché tombe juste.
    n1 = round(note_plage(vol, a, b, penaliser_bas=objectif != "preservation"))
    n2 = round(note_plafond(perte, limite))
    n3 = round(note_plancher(paris, minimum))
    crise = mesures.get("perte_crise_2022")
    if crise is None:  # mesures sans la crise (fausse piste A, anciennes versions) : trois notes
        w1, w2, w3 = POIDS[objectif]
        score = round(w1 * n1 + w2 * n2 + w3 * n3)
        hypotheses.append(f"Poids des notes pour l'objectif {objectif} : {nombre(w1)}, {nombre(w2)}, {nombre(w3)} (choix de l'équipe).")
    else:
        limite_crise = cible("crise_max", n)
        n4 = round(note_plafond(crise, limite_crise))
        w1, w2, w3, w4 = POIDS_AVEC_CRISE[objectif]
        score = round(w1 * n1 + w2 * n2 + w3 * n3 + w4 * n4)
        hypotheses.append(f"Poids des notes pour l'objectif {objectif} : {nombre(w1)}, {nombre(w2)}, {nombre(w3)}, "
                          f"{nombre(w4)} (choix de l'équipe).")
        hypotheses.append(f"Perte tolérée pendant la crise de 2022 pour le niveau {nombre(n)} : {pct(limite_crise)} "
                          "(choix de l'équipe, repère : un portefeuille 60/40 a perdu environ 14 % en 2022).")

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
    if crise is not None:
        position = "au-dessus de" if crise > limite_crise else "dans"
        e4 = f"Pire baisse de {pct(crise)} pendant la crise de 2022, {position} la limite de {pct(limite_crise)}."
        par_titre = mesures.get("perte_crise_2022_par_titre") or {}
        if len(par_titre) > 1:
            pire = max(par_titre, key=par_titre.get)
            e4 += f" Titre le plus touché : {pire} ({pct(par_titre[pire])} de baisse)."
        notes.append({"nom": "resistance_crise", "valeur": crise, "cible": limite_crise, "note": n4,
                      "poids": w4, "explication": e4})
    liste_alertes = alertes(mesures, profil, n)
    # Une contrainte violée (secteur exclu, crypto refusée) n'est pas un compromis de risque :
    # la personne a dit non. Le score ne la voit pas ; le verdict, lui, ne peut pas dire « adéquat ».
    v, raison = verdict(score), None
    violees = [al for al in liste_alertes if al["gravite"] == "contrainte"]
    if violees and v == "adequat":
        v = "a_surveiller"
        raison = ("Verdict plafonné à « à surveiller » malgré le score : le portefeuille ne respecte pas "
                  f"{'une contrainte' if len(violees) == 1 else 'des contraintes'} du profil (voir les alertes).")
        hypotheses.append("Une contrainte du profil non respectée plafonne le verdict à « à surveiller », "
                          "quel que soit le score (choix de l'équipe).")
    return {
        "score": score,
        "verdict": v,
        "raison_verdict": raison,  # None sauf si une contrainte a plafonné le verdict
        "niveau_effectif": n,
        "notes": notes,
        "alertes": liste_alertes,
        "hypotheses": hypotheses,
    }


# -------------------------------------------------------- étape 5 : scénarios
def appliquer(portefeuille, changement):
    """Renvoie un nouveau portefeuille (symbole -> montant) sans modifier l'original.

    Types : ajouter, plafonner, retirer, combiner (une liste `etapes` appliquées dans
    l'ordre) et reallouer (`poids_cibles` : symbole -> poids final, total inchangé). Pour plafonner et retirer, `vers` (facultatif) désigne le titre qui
    reçoit le montant libéré ; sans `vers`, il est réparti au prorata des autres lignes.
    """
    if changement["type"] == "reallouer":
        cibles = {s: w for s, w in changement["poids_cibles"].items() if w > EPS}
        somme, total = sum(cibles.values()), sum(portefeuille.values())
        return {s: total * w / somme for s, w in cibles.items()}
    if changement["type"] == "combiner":
        nouveau = dict(portefeuille)
        for etape in changement["etapes"]:
            nouveau = appliquer(nouveau, etape)
        return nouveau

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
    vers = changement.get("vers")
    if vers:
        if vers == symbole:
            raise ValueError("Le titre réduit et le titre qui reçoit le montant doivent différer.")
        nouveau[vers] = nouveau.get(vers, 0) + libere
    else:
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


def _decrire(changement, portefeuille):
    """Une proposition en « si ... », décrite sur le portefeuille d'avant ce changement."""
    total = sum(portefeuille.values())
    s = changement["symbole"]
    vers = changement.get("vers")
    if changement["type"] == "ajouter":
        return f"{dollars(changement['montant'])} de {s} étaient ajoutés au portefeuille"
    if changement["type"] == "plafonner":
        texte = f"{s} passait de {pct(portefeuille[s] / total)} à {pct(changement['poids_max'])} du portefeuille"
        return texte + (f", la différence allant dans {vers}" if vers else "")
    texte = f"{s} ({pct(portefeuille[s] / total)}) sortait du portefeuille"
    return texte + (f", le montant allant dans {vers}" if vers else "")


def _decrire_reallocation(portefeuille, apres):
    """« NVDA passait de 38,5 % à 0 %, SPY de 0 % à 40 % » : baisses d'abord, puis hausses."""
    t0, t1 = sum(portefeuille.values()), sum(apres.values())
    lignes = []
    for s in list(portefeuille) + [s for s in apres if s not in portefeuille]:
        w0, w1 = portefeuille.get(s, 0) / t0, apres.get(s, 0) / t1
        if abs(w1 - w0) >= 0.005:
            lignes.append((w1 > w0, s, w0, w1))
    lignes.sort(key=lambda l: l[0])
    morceaux = [f"{s} passait de {pct(w0)} à {pct(w1)}" if i == 0 else f"{s} de {pct(w0)} à {pct(w1)}"
                for i, (_, s, w0, w1) in enumerate(lignes)]
    if len(morceaux) > 1:
        return ", ".join(morceaux[:-1]) + " et " + morceaux[-1]
    return morceaux[0] if morceaux else "rien ne changeait"


def _phrase(changement, portefeuille, avant, apres):
    fin = f"le score passerait de {avant['score']} à {apres['score']}."
    if changement["type"] == "reallouer":
        texte = _decrire_reallocation(portefeuille, appliquer(portefeuille, changement))
        return f"Scénario fictif, total du portefeuille inchangé : si {texte}, {fin}"
    if changement["type"] != "combiner":
        return f"Scénario fictif : si {_decrire(changement, portefeuille)}, {fin}"
    morceaux, courant = [], dict(portefeuille)
    for i, etape in enumerate(changement["etapes"], start=1):
        morceaux.append(f"({i}) {_decrire(etape, courant)}")
        courant = appliquer(courant, etape)
    return (f"Scénario fictif en {len(morceaux)} étape(s) : si " + " ; puis ".join(morceaux) + f", {fin}")


def simuler(portefeuille, changement, profil, analyser):
    mesures_avant = analyser(portefeuille)
    avant = evaluer(mesures_avant, profil)
    portefeuille_apres = appliquer(portefeuille, changement)
    mesures_apres = analyser(portefeuille_apres)
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
    etapes = changement.get("etapes", [changement])
    if any(e["type"] in ("plafonner", "retirer") and not e.get("vers") for e in etapes):
        hypotheses.append("Le montant libéré est réparti sur les autres lignes au prorata de leur poids.")
    if any(e.get("vers") for e in etapes):
        hypotheses.append("Le montant libéré va entièrement dans le titre indiqué ; le total du portefeuille ne change pas.")
    if any(e["type"] == "ajouter" for e in etapes):
        hypotheses.append("Le montant ajouté est de l'argent nouveau : le total du portefeuille augmente.")
    if changement["type"] == "reallouer":
        hypotheses.append("Réallocation : les montants sont déplacés entre les titres, sans argent nouveau ; "
                          "frais de transaction et impôts ignorés.")
    if len(etapes) > 1 or changement.get("etapes_recherche"):
        hypotheses.append("Les étapes sont trouvées une à une, en gardant chaque fois celle qui rapproche le plus "
                          "le portefeuille des cibles du profil ; d'autres combinaisons existent.")

    total_apres = sum(portefeuille_apres.values())
    return {
        "changement": changement,
        "avant": avant,
        "apres": apres,
        "ameliore": ameliore,
        "degrade": degrade,  # obligatoire, même vide : on montre le compromis
        "phrase": _phrase(changement, portefeuille, avant, apres),
        "hypotheses": hypotheses,
        # poids de chaque titre avant et après, pour le tableau de l'interface
        "poids_avant": {s: m / sum(portefeuille.values()) for s, m in portefeuille.items()},
        "poids_apres": {s: m / total_apres for s, m in portefeuille_apres.items()},
    }


# Titres qui peuvent recevoir un montant libéré : FNB larges et or, jamais un titre
# isolé ni la crypto (on ne veut pas remplacer une concentration par une autre).
DESTINATIONS = ["XBB.TO", "ZST.TO", "AGG", "XIU.TO", "SPY", "ESGV", "GLD"]
MAX_ETAPES = 6
ETAPES_LEGER = 2
SCORE_SUFFISANT = 90  # on arrête d'ajouter des étapes une fois ce score atteint


def _contraintes(resultat):
    return {al["code"] for al in resultat["alertes"] if al["gravite"] == "contrainte"}


def _poids_contraint(mesures, profil):
    """Part du portefeuille qui viole une contrainte (crypto refusée, secteur exclu)."""
    poids = 0.0
    if profil.get("crypto", "oui") == "non":
        poids += mesures.get("poids_par_classe", {}).get("crypto", 0)
    for s in profil.get("exclure_secteurs") or []:
        poids += mesures.get("poids_par_secteur", {}).get(s, 0)
    return poids


def _ecart(evaluation):
    """Distance continue aux cibles. Le score sature à 0 loin des cibles : cet écart
    départage alors les étapes qui rapprochent quand même le portefeuille."""
    total = 0.0
    for n in evaluation["notes"]:
        v, c = n["valeur"], n["cible"]
        if n["nom"] == "niveau_de_risque":
            total += max(0.0, v - c[1]) / c[1]
        elif n["nom"] in ("risque_de_perte", "resistance_crise"):
            total += max(0.0, v - c) / c
        else:
            total += max(0.0, c - v) / c
    return total


def _candidats(portefeuille, destinations):
    """Tous les changements d'une étape : réduire de moitié ou retirer chaque ligne,
    le montant libéré allant au prorata ou dans une destination."""
    total = sum(portefeuille.values())
    liste = []
    for s, montant in portefeuille.items():
        w = montant / total
        for vers in [None] + [d for d in destinations if d != s]:
            if vers is None and len(portefeuille) == 1:
                continue
            base = {"symbole": s, **({"vers": vers} if vers else {})}
            if w > 0.04:
                liste.append({"type": "plafonner", "poids_max": round(w / 2, 4), **base})
            liste.append({"type": "retirer", **base})
    return liste


def _admissible(mesures_avant, mesures_apres, eval_avant, eval_apres, profil):
    """Refuse un changement qui crée une contrainte violée ou vide un secteur d'intérêt."""
    if _contraintes(eval_apres) - _contraintes(eval_avant):
        return False
    secteurs_avant = mesures_avant.get("poids_par_secteur", {})
    secteurs_apres = mesures_apres.get("poids_par_secteur", {})
    return not any(secteurs_avant.get(s, 0) > EPS and secteurs_apres.get(s, 0) < EPS
                   for s in profil.get("secteurs_interet") or [])


def _chemin(portefeuille, profil, analyser, max_etapes, destinations=DESTINATIONS):
    """Recherche gloutonne. À chaque étape, on garde le changement qui réduit le plus la part
    en contrainte, puis qui monte le plus le score, puis qui réduit le plus l'écart aux cibles.
    Les étapes qui retirent une contrainte ne comptent pas dans max_etapes."""
    courant = dict(portefeuille)
    mesures = analyser(courant)
    evaluation = evaluer(mesures, profil)
    etapes, comptees = [], 0
    while len(etapes) < max_etapes + 4:
        contraint = _poids_contraint(mesures, profil)
        if not contraint and (comptees >= max_etapes or evaluation["score"] >= SCORE_SUFFISANT):
            break
        meilleur = None
        for c in _candidats(courant, destinations):
            essai = appliquer(courant, c)
            m = analyser(essai)
            e = evaluer(m, profil)
            if not _admissible(mesures, m, evaluation, e, profil):
                continue
            cle = (-round(_poids_contraint(m, profil), 4), e["score"], -_ecart(e))
            if meilleur is None or cle > meilleur[0]:
                meilleur = (cle, c, essai, m, e)
        if meilleur is None:
            break
        _, c, essai, m, e = meilleur
        retire_contrainte = _poids_contraint(m, profil) < contraint - EPS
        utile = e["score"] >= evaluation["score"] + 2 or _ecart(e) < 0.9 * _ecart(evaluation)
        if not (retire_contrainte or utile):
            break
        etapes.append(c)
        comptees += 0 if retire_contrainte else 1
        courant, mesures, evaluation = essai, m, e
    return etapes


def _scenario(portefeuille, etapes, profil, analyser):
    """Un seul changement : décrit tel quel. Plusieurs : résumés par la réallocation finale,
    plus lisible que la suite d'étapes de la recherche (qui peut toucher un titre deux fois)."""
    if len(etapes) == 1:
        changement = etapes[0]
    else:
        final = appliquer(portefeuille, {"type": "combiner", "etapes": etapes})
        total = sum(final.values())
        changement = {"type": "reallouer", "etapes_recherche": len(etapes),
                      "poids_cibles": {s: round(m / total, 4) for s, m in final.items() if m / total >= 0.0005}}
    resultat = simuler(portefeuille, changement, profil, analyser)
    levees = _contraintes(resultat["avant"]) - _contraintes(resultat["apres"])
    return resultat if resultat["apres"]["score"] > resultat["avant"]["score"] or levees else None


def proposer_scenarios(portefeuille, profil, analyser, maximum=3):
    """Jusqu'à trois scénarios contrastés :
      1. le plus complet (jusqu'à six étapes de recherche, toutes destinations) ;
      2. une variante qui n'utilise pas les destinations du premier ;
      3. une version légère (deux étapes, hors retrait des contraintes)."""
    essais = []
    premier = _chemin(portefeuille, profil, analyser, MAX_ETAPES)
    essais.append(premier)
    utilisees = {e.get("vers") for e in premier}
    autres = [d for d in DESTINATIONS if d not in utilisees]
    if autres:
        essais.append(_chemin(portefeuille, profil, analyser, MAX_ETAPES, autres))
    essais.append(_chemin(portefeuille, profil, analyser, ETAPES_LEGER))

    scenarios, vus = [], []
    for etapes in essais:
        if not etapes or etapes in vus:
            continue
        vus.append(etapes)
        resultat = _scenario(portefeuille, etapes, profil, analyser)
        if resultat:
            scenarios.append(resultat)
    scenarios.sort(key=lambda r: r["apres"]["score"], reverse=True)
    return scenarios[:maximum]
