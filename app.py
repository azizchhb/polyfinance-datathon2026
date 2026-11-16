"""Interface Streamlit de la piste D. Lancer avec : python -m streamlit run app.py

Deux écrans dans une seule application :
1. le questionnaire, plein écran : le profil, puis le portefeuille ;
2. les résultats, une longue page où rien n'est caché : verdict, notes, graphique, alertes,
   scénarios, hypothèses, et la discussion avec l'agent en bas.
L'interface ne calcule rien : elle appelle analyser (piste A), evaluer et proposer_scenarios
(piste B), demander (piste C), et affiche ce qu'elles renvoient.
"""
import base64
import functools
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from piste_a import analyser, symboles_non_couverts, trajectoire_crise_2022, trajectoire_periode, univers
from piste_b import (MARGE_CONFORT, NOTE_LIMITE, appliquer, evaluer, nombre, nombre_de_scenarios, pct,
                     proposer_scenarios)
from piste_c import demander

AVERTISSEMENT = ("Simulation à but éducatif, à partir de données historiques. "
                 "Aucune transaction réelle, aucun conseil financier personnalisé.")

RISQUES = {"Faible": 1, "Faible à modéré": 1.5, "Modéré": 2, "Modéré à élevé": 2.5, "Élevé": 3}
OBJECTIFS = {"Préserver le capital": "preservation", "Équilibre": "equilibre", "Croissance": "croissance"}
EXPERIENCES = {"Débutant": "debutant", "Intermédiaire": "intermediaire", "Avancé": "avance"}
# Secteurs de assets_universe.csv, traduits (voir la table de correspondance du contrat)
SECTEURS = ["technologie", "energie", "finance", "sante", "industrie", "services_publics",
            "communication", "consommation_de_base", "consommation_discretionnaire"]
VERDICTS = {"adequat": "Adéquat", "a_surveiller": "À surveiller", "inadequat": "Inadéquat"}
NOMS_NOTES = {"niveau_de_risque": "Niveau de risque",
              "risque_de_perte": "Risque de perte",
              "diversification": "Diversification",
              "resistance_crise": "Résistance à la crise de 2022"}
# Deux premières couleurs de la palette catégorielle validée (paire sûre pour le daltonisme),
# avec leurs pas pour fond sombre. Les textes ne portent jamais la couleur des séries.
COULEURS = {"clair": ["#2a78d6", "#eb6834"], "sombre": ["#3987e5", "#d95926"]}
ENCRE = {"clair": "#31333f", "sombre": "#fafafa"}
SERIES = ["Poids dans le capital", "Part du risque"]
# Les six premiers créneaux de la même palette, pour l'anneau. L'ordre est fixe et jamais
# recyclé : c'est pourquoi l'anneau se limite à six parts (voir parts_portefeuille).
CATEGORIELLES = {"clair": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"],
                 "sombre": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c"]}
ENCRE_DOUCE = {"clair": "#52514e", "sombre": "#c3c2b7"}
FOND = {"clair": "#ffffff", "sombre": "#0e1117"}

PERSONAS = {
    "Amira": {"risque": 3, "horizon_annees": 15, "objectif": "croissance", "perte_max_toleree": None,
              "crypto": "oui", "exclure_secteurs": [], "secteurs_interet": ["technologie"],
              "montant_vise": None, "cotisation_mensuelle": None, "experience": "intermediaire"},
    "Mateo": {"risque": 2, "horizon_annees": 10, "objectif": "equilibre", "perte_max_toleree": None,
              "crypto": "non", "exclure_secteurs": ["energie"], "secteurs_interet": [],
              "montant_vise": None, "cotisation_mensuelle": None, "experience": "intermediaire"},
    "Robert": {"risque": 1.5, "horizon_annees": 4, "objectif": "preservation", "perte_max_toleree": None,
               "crypto": "non", "exclure_secteurs": [], "secteurs_interet": [],
               "montant_vise": None, "cotisation_mensuelle": None, "experience": "avance"},
}
PORTRAITS = {
    "Amira": "26 ans · risque élevé · 15 ans et plus · croissance, technologies, crypto",
    "Mateo": "41 ans · risque modéré · 8 à 12 ans · équilibre, préférences ESG",
    "Robert": "59 ans · risque faible à modéré · 3 à 5 ans · préservation du capital",
}
QUESTIONS = {
    "Amira": ["Suis-je trop concentrée sur la techno ?",
              "Et si je plafonnais NVDA à 10 % du portefeuille ?",
              "D'où vient le chiffre de perte maximale ?"],
    "Mateo": ["Mon portefeuille respecte-t-il mes exclusions ESG ?",
              "Je veux avoir 250 000 $ dans 10 ans, qu'est-ce que ça exige ?",
              "Quels changements rapprocheraient ce portefeuille de mon profil ?"],
    "Robert": ["J'ai lu plein d'articles sur NVIDIA. Je veux y mettre 60 000 $.",
               "Ce portefeuille me convient-il ?",
               "D'où vient le chiffre de perte maximale ?"],
    "Personnalisé": ["Ce portefeuille me convient-il ?",
                   "Quels changements rapprocheraient ce portefeuille de mon profil ?",
                   "D'où vient le chiffre de perte maximale ?"],
}
PORTEFEUILLE_DEMO = {"NVDA": 10000, "QQQ": 12500, "BTC-USD": 5000, "XIU.TO": 17500, "XBB.TO": 5000}
DOSSIER_PORTEFEUILLES = Path(__file__).resolve().parent / "data" / "portefeuilles"


# ------------------------------------------------------------------ fonctions
def lire_csv(fichier):
    """Renvoie (portefeuille, messages). portefeuille : dictionnaire symbole -> montant."""
    try:
        df = pd.read_csv(fichier)
    except Exception:
        return {}, ["Le fichier n'est pas un CSV lisible."]
    df.columns = [str(c).strip().lower() for c in df.columns]
    if not {"symbole", "montant_cad"} <= set(df.columns):
        return {}, ["Le CSV doit contenir les colonnes symbole et montant_cad."]

    messages = []
    df["symbole"] = df["symbole"].astype(str).str.strip().str.upper()
    df["montant_cad"] = pd.to_numeric(df["montant_cad"], errors="coerce")
    if df["montant_cad"].isna().any():
        messages.append("Des montants ne sont pas des nombres : ces lignes sont ignorées.")
    if (df["montant_cad"] <= 0).any():
        messages.append("Les montants nuls ou négatifs sont ignorés.")
    df = df[df["montant_cad"] > 0]
    if df.empty:
        return {}, messages + ["Aucune ligne valide dans le fichier."]
    if df["symbole"].duplicated().any():
        messages.append("Des symboles en double ont été additionnés.")
    totaux = df.groupby("symbole")["montant_cad"].sum()
    return {s: float(m) for s, m in totaux.items()}, messages


def portefeuille_type(persona):
    """Le portefeuille d'exemple du persona (data/portefeuilles), sinon la démonstration."""
    chemin = DOSSIER_PORTEFEUILLES / f"{persona.lower()}.csv"
    if chemin.exists():
        p, _ = lire_csv(chemin)
        if p:
            return p
    return dict(PORTEFEUILLE_DEMO)


def style(largeur):
    """La feuille de style de la page : largeur bornée, échelle typographique, cartes.

    Streamlit sert des polices de 16 px dans une page sans limite de largeur : sur un grand écran
    les colonnes s'étirent, tout paraît petit et la page tient en un écran et demi. On borne la
    largeur du contenu, on monte l'échelle d'un cran (tout Streamlit est en rem, il suffit de
    changer la taille de base) et les sections s'empilent au lieu de se serrer côte à côte : la
    page devient longue, chaque élément est lisible et le vide sur les côtés disparaît.
    """
    return f"""<style>
/* largeur du contenu et respiration verticale */
.block-container, [data-testid="stMainBlockContainer"] {{
    max-width: {largeur}px;
    padding: 3.5rem 2rem 7rem 2rem;
}}

/* échelle typographique */
html {{ font-size: 17.5px !important; }}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {{ font-size: 1.02rem; line-height: 1.7; }}
[data-testid="stCaptionContainer"] p {{ font-size: 0.92rem; line-height: 1.6; }}
h1 {{ font-size: 2.9rem !important; letter-spacing: -0.025em; }}
h2 {{ font-size: 1.85rem !important; letter-spacing: -0.015em; padding-top: 2.6rem !important; }}
h3 {{ font-size: 1.3rem !important; letter-spacing: -0.01em; }}

/* cartes : on arrondit la bordure, sans toucher aux marges (ce conteneur enveloppe aussi
   les colonnes : une marge ici décalerait toute la page) */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 14px; }}

/* chiffres : la valeur est l'élément le plus gros de la carte */
[data-testid="stMetricValue"] {{ font-size: 2.4rem; font-weight: 600; line-height: 1.15; }}
[data-testid="stMetricLabel"] p {{ font-size: 0.92rem; }}

/* barres de progression épaissies, sinon invisibles à cette échelle */
[data-testid="stProgress"] > div > div,
[data-testid="stProgress"] > div > div > div {{ height: 12px; border-radius: 99px; }}

/* la liste des titres à côté de l'anneau : la pastille reprend la couleur de sa part */
.ligne-titre {{
    display: flex; align-items: center; gap: 0.7rem;
    padding: 0.62rem 0.1rem; font-size: 1rem;
    border-bottom: 1px solid rgba(128, 128, 128, 0.2);
}}
.ligne-titre .pastille {{ width: 11px; height: 11px; border-radius: 50%; flex: 0 0 auto; }}
.ligne-titre .nom {{ font-weight: 600; }}
.ligne-titre .montant {{ margin-left: auto; opacity: 0.72; }}
.ligne-titre .poids {{ width: 4.4rem; text-align: right; font-variant-numeric: tabular-nums; }}
.drapeau {{ width: 20px; height: 13px; object-fit: cover; border-radius: 2px; flex: 0 0 auto;
            box-shadow: 0 0 0 1px rgba(128,128,128,.35); vertical-align: -2px; }}
.globe {{ width: 20px; text-align: center; flex: 0 0 auto; font-size: 14px; line-height: 13px; }}
.barre-pays {{ display: flex; gap: 2px; height: 18px; margin: .4rem 0 .6rem; }}
.barre-pays span {{ display: block; height: 100%; }}
.barre-pays span:first-child {{ border-radius: 4px 0 0 4px; }}
.barre-pays span:last-child {{ border-radius: 0 4px 4px 0; }}
.barre-pays span:only-child {{ border-radius: 4px; }}
.legende-pays {{ display: flex; flex-wrap: wrap; gap: .4rem 1.6rem; font-size: 1rem; }}
.legende-pays > span {{ display: inline-flex; align-items: center; gap: .45rem; }}
.legende-pays .carre {{ width: 11px; height: 11px; border-radius: 3px; }}

/* onglets : les libellés gardent leur taille par défaut, trop petite à cette échelle */
[data-testid="stTabs"] button p {{ font-size: 1rem; }}

/* alertes, boutons et saisie à la taille du reste */
[data-testid="stAlert"] {{ border-radius: 12px; padding: 1rem 1.1rem; }}
[data-testid="stAlert"] p {{ font-size: 1rem; }}
.stButton button {{ border-radius: 10px; padding: 0.55rem 1.1rem; font-size: 1rem; }}
[data-testid="stChatInput"] textarea {{ font-size: 1.02rem; }}
/* point de départ : « Personnalisé » seul sur la première ligne, les trois personas en dessous */
.st-key-choix_persona div[role="radiogroup"] > div:first-child {{ flex-basis: 100%; }}
.st-key-choix_persona div[role="radiogroup"] > div:not(:first-child) {{ flex: 1 1 0; min-width: 0; }}
@media (max-width: 640px) {{
  .st-key-choix_persona div[role="radiogroup"] > div:not(:first-child) {{ flex: 1 1 100%; }}
}}
</style>"""


def md(texte):
    """Texte sûr pour le Markdown de Streamlit : un « $ » non échappé ouvre une formule mathématique."""
    return str(texte).replace("$", "\\$")


def dollars(x):
    return f"{x:,.0f}".replace(",", " ") + " $"


def pourcent(x, decimales=1):
    return f"{100 * x:.{decimales}f} %".replace(".", ",")


def liste_titres(mesures):
    """Les lignes du portefeuille en HTML, de la plus grosse à la plus petite.

    La pastille reprend la couleur de l'anneau, ce qui relie les deux sans légende ; les lignes
    regroupées sous « Autres » portent la couleur de cette part. Le « $ » est écrit en entité
    HTML : tel quel, deux dollars sur la même page ouvrent une formule mathématique.
    """
    couleurs = dict(zip([titre for titre, _ in parts_portefeuille(mesures)],
                        CATEGORIELLES[mode_theme()]))
    lignes = []
    for titre, part in sorted(mesures["poids"].items(), key=lambda couple: couple[1], reverse=True):
        pastille = couleurs.get(titre) or couleurs.get("Autres", "#9a9a95")
        montant = dollars(mesures["capital"] * part).replace("$", "&#36;")
        pourcentage = f"{100 * part:.1f}".replace(".", ",")
        lignes.append(f'<div class="ligne-titre">'
                      f'<span class="pastille" style="background:{pastille}"></span>'
                      f'{icone_pays(mesures.get("pays_par_titre", {}).get(titre))}'
                      f'<span class="nom">{titre}</span>'
                      f'<span class="montant">{montant}</span>'
                      f'<span class="poids">{pourcentage} %</span></div>')
    return "".join(lignes)


# Drapeaux en petites images PNG embarquées (domaine public, flagcdn.com) : Windows n'affiche pas
# les émojis de drapeaux, il écrirait « CA » et « US » en lettres.
DOSSIER_DRAPEAUX = Path(__file__).parent / "assets" / "drapeaux"
PAYS = {"canada": ("Canada", "ca"), "etats_unis": ("États-Unis", "us"), "mondial": ("Mondial (or, crypto)", None)}
COULEURS_PAYS = {"clair": {"canada": "#d52b1e", "etats_unis": "#3c3b6e", "mondial": "#9a9a95"},
                 "sombre": {"canada": "#e5544a", "etats_unis": "#8a8fd8", "mondial": "#898781"}}


@functools.lru_cache(maxsize=None)
def icone_pays(pays):
    """Petit drapeau en HTML (image embarquée), un globe pour « mondial », rien si inconnu."""
    if pays not in PAYS:
        return ""
    nom, code = PAYS[pays]
    if code is None:
        return f'<span class="globe" title="{nom}">🌐</span>'
    donnees = base64.b64encode((DOSSIER_DRAPEAUX / f"{code}.png").read_bytes()).decode()
    return f'<img class="drapeau" alt="{nom}" title="{nom}" src="data:image/png;base64,{donnees}">'


def repartition_pays(mesures):
    """Barre segmentée par pays, puis la légende avec drapeaux et pourcentages (jamais la couleur seule)."""
    couleurs = COULEURS_PAYS[mode_theme()]
    parts = [(p, mesures["poids_par_pays"].get(p, 0.0)) for p in PAYS if mesures["poids_par_pays"].get(p, 0) > 0]
    barre = "".join(f'<span style="width:{100 * w:.2f}%;background:{couleurs[p]}" title="{PAYS[p][0]}"></span>'
                    for p, w in parts)
    legende = "".join(f'<span><span class="carre" style="background:{couleurs[p]}"></span>{icone_pays(p)}'
                      f'{PAYS[p][0]} <b>{pct(w)}</b></span>' for p, w in parts)
    return f'<div class="barre-pays">{barre}</div><div class="legende-pays">{legende}</div>'


def etiquette(dico, valeur):
    """Le libellé affiché pour une valeur du contrat (1.5 -> « Faible à modéré »)."""
    return next((e for e, v in dico.items() if v == valeur), next(iter(dico)))


def aide_score(resultat, profil):
    """Texte du « ? » à côté du score : comment il est construit et ce qu'il ne dit pas."""
    poids = ", ".join(f"{NOMS_NOTES[n['nom']].lower()} {pct(n['poids'])}" for n in resultat["notes"])
    return (f"**Moyenne pondérée des {len(resultat['notes'])} notes ci-dessous.** Poids pour l'objectif "
            f"{etiquette(OBJECTIFS, profil['objectif']).lower()} : {poids}.\n\n"
            "**Verdict** : adéquat à 80 et plus, à surveiller de 60 à 79, inadéquat sous 60. Une contrainte "
            "non respectée (secteur exclu, crypto refusée) plafonne le verdict à « à surveiller », quel que soit "
            "le score.\n\n"
            f"**Repère** : chaque note vaut {nombre(NOTE_LIMITE)} pile à la limite de votre profil. Un portefeuille "
            "au bord de toutes ses cibles obtient donc environ 70 (à surveiller) ; 100 demande une marge.\n\n"
            "Le score mesure l'adéquation du risque à votre profil, pas un rendement attendu. Les cibles et les "
            "poids sont des choix de l'équipe, pas une norme.")


def aide_note(note):
    """Texte du « ? » de chaque note : la mesure, votre cible, la règle de notation, le poids."""
    nom, cible_note, poids = note["nom"], note["cible"], pct(note["poids"])
    confort = 1 - MARGE_CONFORT
    if nom == "niveau_de_risque":
        a, b = cible_note
        texte = ("**Mesure** : volatilité annuelle du portefeuille, l'écart-type des rendements quotidiens "
                 "de 2021 à 2026 en dollars canadiens, multiplié par la racine de 252. Elle tient compte des "
                 "corrélations entre les titres (Markowitz).\n\n"
                 f"**Votre cible** : de {pct(a)} à {pct(b)}.\n\n"
                 f"**Note** : 100 jusqu'au milieu de la plage ({pct((a + b) / 2)}), 70 pile à {pct(b)}, "
                 f"0 à {pct(2 * b)}. Sous {pct(a)}, la note baisse aussi, sauf pour un objectif de "
                 "préservation : le portefeuille n'utilise pas le risque accepté.")
    elif nom == "risque_de_perte":
        texte = ("**Mesure** : pire baisse du sommet au creux entre 2021 et 2026, en gardant les pondérations "
                 "actuelles constantes.\n\n"
                 f"**Votre cible** : au plus {pct(cible_note)}, la plus prudente entre la perte que vous tolérez "
                 "et celle de votre niveau de risque.\n\n"
                 f"**Note** : 100 jusqu'à {pct(confort * cible_note)}, 70 pile à {pct(cible_note)}, "
                 f"0 à {pct(2 * cible_note)}.")
    elif nom == "diversification":
        texte = ("**Mesure** : nombre effectif de paris, soit 1 divisé par la somme des carrés des parts du "
                 "risque. Quatre titres qui portent chacun un quart du risque font 4 paris ; un titre qui en "
                 "porte la moitié pèse comme deux. Les FNB larges (XIU.TO, SPY, ESGV, XBB.TO, ZST.TO, AGG) "
                 "comptent comme déjà diversifiés ; plafond à 20.\n\n"
                 f"**Votre cible** : au moins {nombre(cible_note)} paris.\n\n"
                 f"**Note** : 0 pour un seul pari, 70 pile à {nombre(cible_note)}, 100 dès "
                 f"{nombre((1 + 2 * MARGE_CONFORT) * cible_note)}.")
    else:  # resistance_crise
        texte = ("**Mesure** : le portefeuille actuel rejoué sur l'année 2022, quand actions et obligations "
                 "ont baissé ensemble ; on garde la pire baisse du sommet au creux.\n\n"
                 f"**Votre cible** : au plus {pct(cible_note)}. Repère : un portefeuille 60/40 a perdu environ "
                 "14 % en 2022.\n\n"
                 f"**Note** : 100 jusqu'à {pct(confort * cible_note)}, 70 pile à {pct(cible_note)}, "
                 f"0 à {pct(2 * cible_note)}.")
    return texte + f"\n\n**Poids dans le score** : {poids}."


def bandeau_verdict(verdict):
    """Le verdict en mots, dans une couleur : la couleur ne porte jamais l'information seule."""
    {"adequat": st.success, "a_surveiller": st.warning, "inadequat": st.error}[verdict](VERDICTS[verdict])


def mode_theme():
    """« sombre » ou « clair » selon le thème actif de Streamlit (clair si l'information manque)."""
    try:
        return "sombre" if st.context.theme.type == "dark" else "clair"
    except Exception:
        return "clair"


def graphique(mesures):
    """Barres horizontales groupées : poids dans le capital et part du risque, par titre.

    Graphique vectoriel natif : il prend la largeur disponible sans grossir les barres ni les
    polices, et suit le thème. Les étiquettes ne sont posées que sur la part du risque, qui est
    l'histoire du graphique ; l'axe, la légende et l'infobulle portent le reste.
    """
    theme = mode_theme()
    symboles = sorted(mesures["poids"], key=mesures["contributions"].get, reverse=True)
    df = pd.DataFrame(
        [{"Titre": s, "Mesure": SERIES[0], "Valeur": 100 * mesures["poids"][s]} for s in symboles]
        + [{"Titre": s, "Mesure": SERIES[1], "Valeur": 100 * mesures["contributions"][s]} for s in symboles])

    base = alt.Chart(df).transform_calculate(
        affichage="replace(format(datum.Valeur, '.1f'), '.', ',') + ' %'",
        etiquette="format(datum.Valeur, '.0f') + ' %'",
    ).encode(
        y=alt.Y("Titre:N", sort=symboles, title=None,
                axis=alt.Axis(labelFontSize=15, ticks=False, domain=False, labelPadding=14)),
        yOffset=alt.YOffset("Mesure:N", sort=SERIES),
        x=alt.X("Valeur:Q", title="% du total",
                scale=alt.Scale(domain=[0, float(df["Valeur"].max()) * 1.2], nice=False),
                axis=alt.Axis(tickCount=5, format=".0f", domain=False, gridOpacity=0.35,
                              labelFontSize=13, titleFontSize=13, titlePadding=12)),
        color=alt.Color("Mesure:N", sort=SERIES, scale=alt.Scale(domain=SERIES, range=COULEURS[theme]),
                        legend=alt.Legend(title=None, orient="top", direction="horizontal",
                                          symbolType="square", labelFontSize=14, symbolSize=180,
                                          offset=14)),
        tooltip=[alt.Tooltip("Titre:N", title="Titre"), alt.Tooltip("Mesure:N", title="Mesure"),
                 alt.Tooltip("affichage:N", title="% du total")],
    )
    barres = base.mark_bar(size=26, cornerRadiusTopRight=5, cornerRadiusBottomRight=5)
    etiquettes = (base.transform_filter(alt.datum.Mesure == SERIES[1])
                  .mark_text(align="left", baseline="middle", dx=8, fontSize=14)
                  .encode(text="etiquette:N", color=alt.value(ENCRE[theme])))
    return (barres + etiquettes).properties(height=max(280, 72 * len(symboles)))


def parts_portefeuille(mesures):
    """Les parts à dessiner dans l'anneau : les cinq plus grosses lignes, puis « Autres ».

    Au-delà de six parts, les tranches deviennent trop fines pour être comparées d'un coup
    d'œil et les étiquettes se chevauchent. Le tableau plus bas garde le détail complet, ligne
    par ligne : rien n'est caché, seulement regroupé pour le dessin.
    """
    poids = sorted(mesures["poids"].items(), key=lambda couple: couple[1], reverse=True)
    if len(poids) > 6:
        poids = poids[:5] + [("Autres", sum(part for _, part in poids[5:]))]
    return poids


def beignet(mesures):
    """Le portefeuille en anneau : la part de chaque titre, le capital au centre.

    Chaque part porte son nom et son pourcentage à l'extérieur de l'anneau : trois des six
    teintes passent sous le rapport de contraste de 3:1 sur fond clair, donc la couleur ne
    distingue jamais une part à elle seule. Un trait de la couleur du fond sépare les parts,
    sinon deux teintes voisines se touchent et se lisent comme une seule.
    """
    theme = mode_theme()
    parts = parts_portefeuille(mesures)
    df = pd.DataFrame([{"Titre": titre, "Part": 100 * part, "Rang": rang}
                       for rang, (titre, part) in enumerate(parts)])

    base = alt.Chart(df).transform_calculate(
        etiquette="datum.Titre + '  ' + replace(format(datum.Part, '.1f'), '.', ',') + ' %'",
        affichage="replace(format(datum.Part, '.1f'), '.', ',') + ' %'",
    ).encode(
        theta=alt.Theta("Part:Q", stack=True),
        # L'ordre vient du rang, pas de la taille : « Autres » reste la dernière part même
        # quand son total dépasse celui de la cinquième ligne.
        order=alt.Order("Rang:Q", sort="ascending"),
        color=alt.Color("Titre:N", sort=None, legend=None,
                        scale=alt.Scale(domain=list(df["Titre"]),
                                        range=CATEGORIELLES[theme][:len(df)])),
        tooltip=[alt.Tooltip("Titre:N", title="Titre"),
                 alt.Tooltip("affichage:N", title="Part du capital")],
    )
    anneau = base.mark_arc(innerRadius=118, outerRadius=170, cornerRadius=2,
                           stroke=FOND[theme], strokeWidth=2)
    etiquettes = base.mark_text(radius=196, fontSize=14).encode(
        text=alt.Text("etiquette:N"), color=alt.value(ENCRE[theme]))
    capital = (alt.Chart(pd.DataFrame([{"texte": dollars(mesures["capital"])}]))
               .mark_text(fontSize=38, fontWeight=700, dy=-14)
               .encode(text="texte:N", color=alt.value(ENCRE[theme])))
    detail = (alt.Chart(pd.DataFrame([{"texte": f"{len(mesures['poids'])} titres"}]))
              .mark_text(fontSize=15, dy=22)
              .encode(text="texte:N", color=alt.value(ENCRE_DOUCE[theme])))
    return alt.layer(anneau, etiquettes, capital, detail).properties(height=490)


def tableau_poids(mesures):
    """Les mêmes chiffres que le graphique, en tableau : lisibles sans couleur ni survol."""
    symboles = sorted(mesures["poids"], key=mesures["contributions"].get, reverse=True)
    return pd.DataFrame({
        "Titre": symboles,
        "Classe": [mesures["classe_par_titre"].get(s, "") for s in symboles],
        "Secteur": [mesures["secteur_par_titre"].get(s, "") for s in symboles],
        "Montant (CAD)": [round(mesures["capital"] * mesures["poids"][s]) for s in symboles],
        "Poids (%)": [round(100 * mesures["poids"][s], 1) for s in symboles],
        "Part du risque (%)": [round(100 * mesures["contributions"][s], 1) for s in symboles],
    })


MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def graphique_crise(trajet, limite):
    """La valeur du portefeuille pendant 2022, en dollars, avec la limite de perte du profil.

    Une seule série (le portefeuille), donc pas de légende : le titre de la section la nomme.
    La ligne pointillée part du sommet : c'est la valeur sous laquelle la baisse aurait dépassé
    la perte tolérée par ce profil. Sommet et creux sont étiquetés ; le reste se lit au survol.
    """
    theme = mode_theme()
    bleu, encre, douce = COULEURS[theme][0], ENCRE[theme], ENCRE_DOUCE[theme]
    df = pd.DataFrame({"date": pd.to_datetime(trajet["dates"]), "valeur": trajet["valeurs"]})
    df["texte"] = [dollars(v) for v in df["valeur"]]
    df["jour"] = [f"{d.day} {MOIS[d.month - 1]} {d.year}" for d in df["date"]]
    bas = min(trajet["creux"]["valeur"], trajet["sommet"]["valeur"] * (1 - limite) if limite else 1e18)
    echelle = alt.Scale(domain=[bas * 0.92, max(trajet["valeurs"]) * 1.04], nice=False)
    mois = "[" + ", ".join(f"'{m}'" for m in MOIS) + "][month(datum.value)]"
    x = alt.X("date:T", title=None, axis=alt.Axis(labelExpr=mois, tickCount="month", labelFontSize=13,
                                                     domain=False, ticks=False, grid=False, labelColor=douce))
    y = alt.Y("valeur:Q", title="Valeur du portefeuille (CAD)", scale=echelle,
              axis=alt.Axis(tickCount=5, labelExpr="replace(format(datum.value, ',.0f'), ',', ' ') + ' $'",
                            domain=False, ticks=False, gridOpacity=0.35,
                            labelFontSize=13, titleFontSize=13, titlePadding=12, labelColor=douce,
                            titleColor=douce))
    survol = alt.selection_point(fields=["date"], nearest=True, on="pointerover", empty=False, clear="pointerout")
    ligne = alt.Chart(df).mark_line(strokeWidth=2, color=bleu).encode(x=x, y=y)
    cible = alt.Chart(df).mark_point(opacity=0, size=400).encode(
        x=x, y=y, tooltip=[alt.Tooltip("jour:N", title="Date"),
                           alt.Tooltip("texte:N", title="Valeur")]).add_params(survol)
    repere = alt.Chart(df).mark_rule(color=douce, strokeWidth=1).encode(x=x).transform_filter(survol)
    point = (alt.Chart(df).mark_point(filled=True, size=90, color=bleu, stroke=FOND[theme], strokeWidth=2)
             .encode(x=x, y=y).transform_filter(survol))

    extremes = pd.DataFrame([
        {"date": pd.to_datetime(trajet["sommet"]["date"]), "valeur": trajet["sommet"]["valeur"],
         "texte": f"Sommet : {dollars(trajet['sommet']['valeur'])}", "dy": -16, "aligne": "left"},
        {"date": pd.to_datetime(trajet["creux"]["date"]), "valeur": trajet["creux"]["valeur"],
         "texte": f"Creux : {dollars(trajet['creux']['valeur'])}", "dy": 20, "aligne": "center"}])
    marques = alt.Chart(extremes).mark_point(filled=True, size=110, color=bleu, stroke=FOND[theme],
                                             strokeWidth=2).encode(x=x, y=y)
    textes = [alt.Chart(extremes.iloc[[k]]).mark_text(fontSize=13, fontWeight=600, dy=int(extremes.dy[k]),
                                                       align=extremes.aligne[k], dx=4 if k == 0 else 0,
                                                       color=encre).encode(x=x, y=y, text="texte:N")
              for k in range(2)]
    couches = [ligne, repere, point, cible, marques] + textes
    if limite:
        seuil = trajet["sommet"]["valeur"] * (1 - limite)
        regle = pd.DataFrame({"date": [df["date"].iloc[-1]], "valeur": [seuil], "texte": [f"Votre limite : baisse de {pourcent(limite, 0)} "
                                                           f"depuis le sommet ({dollars(seuil)})"]})
        couches.insert(0, alt.Chart(regle).mark_rule(color=douce, strokeDash=[6, 4], strokeWidth=1.5)
                       .encode(y=alt.Y("valeur:Q", scale=echelle)))
        couches.append(alt.Chart(regle).mark_text(align="right", dy=-8, fontSize=13, color=douce)
                       .encode(x=x, y=alt.Y("valeur:Q", scale=echelle), text="texte:N"))
    return alt.layer(*couches).properties(height=380)


def graphique_crise_comparee(actuel, scenario, limite, periode=False):
    """Le portefeuille actuel et le scénario sur le même axe en dollars : pendant 2022 (par défaut),
    ou sur toute la période du jeu (periode=True : axe en années, 2022 surlignée en gris).

    Deux séries : légende en haut et nom au bout de chaque ligne (l'identité ne repose jamais sur
    la seule couleur). Le portefeuille actuel est le contexte, en gris ; le scénario, en bleu.
    La limite du profil part de la valeur de départ, commune aux deux (même total).
    """
    theme = mode_theme()
    bleu, douce, gris = COULEURS[theme][0], ENCRE_DOUCE[theme], "#898781"
    noms = ["Portefeuille actuel", "Scénario"]
    # Les deux portefeuilles n'ont pas forcément le même calendrier (jours fériés de Toronto et de
    # New York, crypto) : on garde les dates communes, sans remplir de trou.
    large = pd.merge(pd.DataFrame({"date": pd.to_datetime(actuel["dates"]), noms[0]: actuel["valeurs"]}),
                     pd.DataFrame({"date": pd.to_datetime(scenario["dates"]), noms[1]: scenario["valeurs"]}),
                     on="date", how="inner")
    dates = large["date"]
    large["jour"] = [f"{d.day} {MOIS[d.month - 1]} {d.year}" for d in dates]
    large["texte_actuel"] = [dollars(v) for v in large[noms[0]]]
    large["texte_scenario"] = [dollars(v) for v in large[noms[1]]]
    long = large.melt(id_vars=["date"], value_vars=noms, var_name="Série", value_name="valeur")
    seuil = actuel["valeurs"][0] * (1 - limite) if limite else None
    plus_bas = min(min(actuel["valeurs"]), min(scenario["valeurs"]), seuil or 1e18)
    plus_haut = max(max(actuel["valeurs"]), max(scenario["valeurs"]))
    echelle = alt.Scale(domain=[plus_bas * 0.92, plus_haut * 1.04], nice=False)
    mois = "[" + ", ".join(f"'{m}'" for m in MOIS) + "][month(datum.value)]"
    etiquettes = "timeFormat(datum.value, '%Y')" if periode else mois
    x = alt.X("date:T", title=None, axis=alt.Axis(labelExpr=etiquettes, tickCount="year" if periode else "month",
                                                     labelFontSize=12, domain=False, ticks=False, grid=False,
                                                     labelColor=douce))
    y = alt.Y("valeur:Q", title="Valeur (CAD)", scale=echelle,
              axis=alt.Axis(tickCount=4, labelExpr="replace(format(datum.value, ',.0f'), ',', ' ') + ' $'",
                            domain=False, ticks=False, gridOpacity=0.35, labelFontSize=12, titleFontSize=12,
                            labelColor=douce, titleColor=douce))
    palette = alt.Scale(domain=noms, range=[gris, bleu])
    couleur = alt.Color("Série:N", sort=noms, scale=palette,
                        legend=alt.Legend(title=None, orient="top", direction="horizontal", symbolType="stroke",
                                          symbolStrokeWidth=3, labelFontSize=13, offset=10))
    lignes = alt.Chart(long).mark_line(strokeWidth=2).encode(x=x, y=y, color=couleur)
    fins = long[long["date"] == long["date"].max()]
    noms_fin = (alt.Chart(fins).mark_text(align="right", dy=-14, fontSize=12, fontWeight=600, color=ENCRE[theme])
                .encode(x=x, y=y, text="Série:N"))
    survol = alt.selection_point(fields=["date"], nearest=True, on="pointerover", empty=False, clear="pointerout")
    cibles = alt.Chart(large).mark_rule(opacity=0, strokeWidth=12).encode(
        x=x, tooltip=[alt.Tooltip("jour:N", title="Date"), alt.Tooltip("texte_actuel:N", title=noms[0]),
                      alt.Tooltip("texte_scenario:N", title=noms[1])]).add_params(survol)
    repere = alt.Chart(large).mark_rule(color=douce, strokeWidth=1).encode(x=x).transform_filter(survol)
    points = (alt.Chart(long).mark_point(filled=True, size=70, stroke=FOND[theme], strokeWidth=2)
              .encode(x=x, y=y, color=alt.Color("Série:N", sort=noms, scale=palette, legend=None))
              .transform_filter(survol))
    couches = [lignes, noms_fin, repere, points, cibles]
    if periode:  # 2022 en fond gris, pour relier cet onglet à celui de la crise
        bande = pd.DataFrame({"debut": [pd.Timestamp("2022-01-01")], "fin": [pd.Timestamp("2022-12-31")],
                              "texte": ["Crise de 2022"]})
        couches.insert(0, alt.Chart(bande).mark_rect(color=douce, opacity=0.12)
                       .encode(x="debut:T", x2="fin:T"))
        couches.insert(1, alt.Chart(bande).mark_text(align="left", baseline="top", dx=6, dy=6, fontSize=12,
                                                     color=douce)
                       .encode(x="debut:T", y=alt.value(0), text="texte:N"))
    if seuil:
        regle = pd.DataFrame({"date": [dates[0]], "valeur": [seuil],
                              "texte": [f"Votre limite : baisse de {pourcent(limite, 0)} ({dollars(seuil)})"]})
        couches.insert(0, alt.Chart(regle).mark_rule(color=douce, strokeDash=[6, 4], strokeWidth=1.5)
                       .encode(y=alt.Y("valeur:Q", scale=echelle)))
        couches.append(alt.Chart(regle).mark_text(align="left", dy=-8, dx=4, fontSize=12, color=douce)
                       .encode(x=x, y=alt.Y("valeur:Q", scale=echelle), text="texte:N"))
    return alt.layer(*couches).properties(height=320)


def afficher_changements(scenario):
    """Onglet « Changements » d'un scénario : poids avant et après, ce qui s'améliore et se dégrade."""
    # Tableau des titres dont le poids change : plus lisible que la phrase dès 3 lignes.
    p0, p1 = scenario.get("poids_avant", {}), scenario.get("poids_apres", {})
    lignes = [{"Titre": s, "Avant": pourcent(p0.get(s, 0)), "Après": pourcent(p1.get(s, 0)),
               "Écart (points)": round(100 * (p1.get(s, 0) - p0.get(s, 0)), 1)}
              for s in dict.fromkeys(list(p0) + list(p1)) if abs(p1.get(s, 0) - p0.get(s, 0)) >= 0.005]
    if len(lignes) > 2:
        lignes.sort(key=lambda l: l["Écart (points)"])
        st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")
    mieux, moins_bien = st.columns(2)
    mieux.markdown("**Ce qui s'améliore**")
    for ligne in scenario["ameliore"] or ["Rien"]:
        mieux.write("- " + md(ligne))
    moins_bien.markdown("**Ce qui se dégrade**")
    for ligne in scenario["degrade"] or ["Rien"]:
        moins_bien.write("- " + md(ligne))


def afficher_crise_scenario(portefeuille, scenario, resultat):
    """Onglet « Et pendant la crise de 2022 ? » : le portefeuille actuel et le scénario rejoués en 2022."""
    actuel = trajectoire_memo(portefeuille)
    apres = trajectoire_memo(appliquer(portefeuille, scenario["changement"]))
    if actuel is None or apres is None:
        st.info("Pas de prix en 2022 pour l'un des titres : la crise ne peut pas être rejouée.")
        return
    note_crise = next((n for n in resultat["notes"] if n["nom"] == "resistance_crise"), None)
    limite = note_crise["cible"] if note_crise else None
    st.markdown(md(f"Baisse au pire moment : **{dollars(actuel['perte_dollars'])}** actuellement "
                   f"({pourcent(actuel['perte'])}), **{dollars(apres['perte_dollars'])}** dans ce scénario "
                   f"({pourcent(apres['perte'])})."))
    st.altair_chart(graphique_crise_comparee(actuel, apres, limite), width="stretch")
    st.warning("Ce scénario a été trouvé à partir de ces mêmes données : il est normal qu'il ait mieux traversé "
               "2022. C'est une illustration, pas une preuve qu'il résisterait à une autre crise.")


def signe(x):
    """+12,3 % ou −4,5 %, pour une variation."""
    return ("+" if x >= 0 else "−") + pourcent(abs(x))


def afficher_periode_scenario(portefeuille, scenario):
    """Onglet « Et sur cinq ans ? » : le portefeuille actuel et le scénario sur toute la période du jeu.
    Un rendement passé et descriptif, qui montre ce que le scénario aurait coûté ou rapporté ; il
    n'entre pas dans le score, qui ne mesure que le risque."""
    actuel = periode_memo(portefeuille)
    apres = periode_memo(appliquer(portefeuille, scenario["changement"]))
    if actuel is None or apres is None:
        st.info("Pas assez de dates communes pour rejouer toute la période.")
        return
    debut, fin = pd.Timestamp(actuel["debut"]), pd.Timestamp(actuel["fin"])
    periode = f"Du {debut.day} {MOIS[debut.month - 1]} {debut.year} au {fin.day} {MOIS[fin.month - 1]} {fin.year}"
    ecart = apres["valeur_fin"] - actuel["valeur_fin"]
    st.markdown(md(
        f"{periode}, avec les mêmes montants, le portefeuille actuel serait passé de "
        f"{dollars(actuel['capital'])} à **{dollars(actuel['valeur_fin'])}** ({signe(actuel['variation'])}, soit "
        f"{signe(actuel['variation_annuelle'])} par an) ; ce scénario, à **{dollars(apres['valeur_fin'])}** "
        f"({signe(apres['variation'])}, soit {signe(apres['variation_annuelle'])} par an). Écart en fin de "
        f"période : **{('+' if ecart >= 0 else '−') + dollars(abs(ecart))}** pour le scénario."))
    st.altair_chart(graphique_crise_comparee(actuel, apres, None, periode=True), width="stretch")
    if ecart < 0:
        st.info("**Pourquoi le scénario fait moins bien ici ?** Les scénarios cherchent à réduire le risque pour "
                "rapprocher le portefeuille de votre profil, jamais à gagner plus. Or de 2021 à 2026, les titres les "
                "plus agités ont souvent le plus monté : en déplacer une partie vers des titres plus stables coûte du "
                "rendement en regardant en arrière. C'est la contrepartie de la réduction du risque, qui se voit "
                "surtout dans les baisses : comparez avec l'onglet « Et pendant la crise de 2022 ? ».")
    st.warning("Rendement passé, sur une seule période de cinq ans : ce n'est pas une prévision, et une autre "
               "période donnerait un autre résultat. Les 31 titres ont été choisis en 2026 parmi ceux qui sont "
               "devenus gros (biais du survivant) : les portefeuilles concentrés sur ces titres en profitent ici. "
               "Ce rendement n'entre pas dans le score, qui ne mesure que le risque.")


# Calculs mémorisés : Streamlit relance tout le script à chaque clic et à chaque message envoyé à
# l'agent. Les mêmes portefeuille et profil redonnent le même résultat, sans tout recalculer.
@st.cache_data(show_spinner=False, max_entries=64)
def analyser_memo(portefeuille):
    return analyser(portefeuille)


@st.cache_data(show_spinner="Recherche des scénarios…", max_entries=64)
def scenarios_memo(portefeuille, profil):
    return proposer_scenarios(portefeuille, profil, analyser)


@st.cache_data(show_spinner=False, max_entries=256)
def trajectoire_memo(portefeuille):
    return trajectoire_crise_2022(portefeuille)


@st.cache_data(show_spinner=False, max_entries=256)
def periode_memo(portefeuille):
    return trajectoire_periode(portefeuille)


# ------------------------------------------------------------------ état et page
etat = st.session_state
etat.setdefault("etape", "questionnaire")
etat.setdefault("persona", "Amira")
etat.setdefault("messages", [])
if etat.etape == "resultats" and not (etat.get("profil") and etat.get("portefeuille")):
    etat.etape = "questionnaire"

st.set_page_config(page_title="Calibre · le diagnostic sur mesure", layout="wide",
                   initial_sidebar_state="collapsed")
# Largeur bornée plutôt que la mise en page « centered » : on choisit le nombre de pixels,
# plus large pour les résultats (un tableau de cinq colonnes) que pour le questionnaire.
st.markdown(style(900 if etat.etape == "questionnaire" else 1180), unsafe_allow_html=True)


# ------------------------------------------------------------ 1. questionnaire
def questionnaire():
    st.title("Calibre")
    st.subheader("Le diagnostic sur mesure")
    st.markdown("Les outils habituels donnent la même note de diversification à tout le monde. Ici, votre "
                "portefeuille est mesuré une fois, puis chaque mesure est comparée à une cible qui dépend de "
                "**votre** profil, et chaque chiffre est expliqué.")
    st.caption(AVERTISSEMENT)

    st.header("1. Votre profil", divider="gray")
    with st.container(key="choix_persona"):  # la clé donne la classe CSS st-key-choix_persona (voir style)
        persona = st.radio("Point de départ", ["Personnalisé"] + list(PERSONAS), horizontal=True, key="persona",
                           captions=["Vos propres réponses"] + [PORTRAITS[p] for p in PERSONAS])
    k = persona  # les clés changent avec le persona : les champs reprennent ses valeurs
    base = dict(PERSONAS.get(persona, PERSONAS["Mateo"]))
    if etat.get("profil") and etat.get("persona_du_profil") == persona:
        base = dict(etat.profil)  # retour depuis les résultats : on retrouve ses réponses

    risque = st.select_slider("Tolérance au risque", options=list(RISQUES),
                              value=etiquette(RISQUES, base["risque"]), key=f"risque_{k}",
                              help="Le niveau retenu est le plus prudent entre cette tolérance et ce que permet l'horizon.")
    horizon = st.slider("Horizon de placement (années)", 1, 30, int(base["horizon_annees"]), key=f"horizon_{k}")
    objectif = st.radio("Objectif", list(OBJECTIFS), horizontal=True, key=f"objectif_{k}",
                        index=list(OBJECTIFS.values()).index(base["objectif"]))
    experience = st.radio("Expérience en investissement", list(EXPERIENCES), horizontal=True, key=f"experience_{k}",
                          index=list(EXPERIENCES.values()).index(base.get("experience") or "intermediaire"),
                          help="Même contenu, vocabulaire adapté dans les explications de l'agent.")
    crypto = st.toggle("J'accepte les cryptoactifs", value=base["crypto"] == "oui", key=f"crypto_{k}")
    perte = None
    if st.checkbox("Préciser la perte maximale que je tolère", key=f"preciser_{k}",
                   value=base.get("perte_max_toleree") is not None):
        perte = st.slider("Perte maximale tolérée (%)", 5, 60,
                          int(round(100 * (base.get("perte_max_toleree") or 0.20))), key=f"perte_{k}") / 100
    exclus = st.multiselect("Secteurs à exclure (approximation ESG, par secteur)", SECTEURS, placeholder="Aucun",
                            default=base["exclure_secteurs"], key=f"exclus_{k}")
    interet = st.multiselect("Secteurs d'intérêt", SECTEURS, default=base["secteurs_interet"], key=f"interet_{k}",
                             placeholder="Aucun")
    # Pas de champ « montant à atteindre » dans le questionnaire : les clés restent dans le profil
    # (contrat), à vide. Un objectif chiffré écrit dans la discussion passe par l'agent, qui le
    # transmet à evaluer (voir piste_c).
    profil = {
        "risque": RISQUES[risque], "horizon_annees": horizon, "objectif": OBJECTIFS[objectif],
        "perte_max_toleree": perte, "crypto": "oui" if crypto else "non",
        "exclure_secteurs": exclus, "secteurs_interet": interet,
        "montant_vise": None, "cotisation_mensuelle": None,
        "experience": EXPERIENCES[experience],
    }

    st.header("2. Votre portefeuille", divider="gray")
    st.caption("Montants en dollars canadiens. Les 31 titres du jeu de données sont dans la liste déroulante ; "
               "tout autre symbole est signalé plutôt qu'ignoré.")
    options = []
    if etat.get("portefeuille") and etat.get("persona_du_profil") == persona:
        options.append("Mon portefeuille précédent")
    if persona in PERSONAS:
        options.append(f"Portefeuille type de {persona}")
    options += ["Portefeuille de démonstration", "Partir de zéro"]
    depart = st.radio("Point de départ du portefeuille", options, horizontal=True, key=f"depart_{k}")
    fichier = st.file_uploader("Ou déposer un CSV avec les colonnes symbole et montant_cad", type="csv", key=f"csv_{k}")

    if fichier is not None:
        lignes, messages = lire_csv(fichier)
        for message in messages:
            st.warning(message)
        source = f"csv-{fichier.name}-{fichier.size}"
    elif depart == "Mon portefeuille précédent":
        lignes, source = dict(etat.portefeuille), "precedent"
    elif depart.startswith("Portefeuille type"):
        lignes, source = portefeuille_type(persona), "type"
    elif depart == "Portefeuille de démonstration":
        lignes, source = dict(PORTEFEUILLE_DEMO), "demo"
    else:
        lignes, source = {}, "vide"

    tableau = pd.DataFrame({"symbole": pd.Series(list(lignes), dtype=str),
                            "montant_cad": pd.Series([float(v) for v in lignes.values()], dtype=float)})
    edite = st.data_editor(
        tableau, num_rows="dynamic", hide_index=True, width="stretch", key=f"editeur_{k}_{source}",
        column_config={
            "symbole": st.column_config.SelectboxColumn("Titre", options=sorted(univers()), required=True),
            "montant_cad": st.column_config.NumberColumn("Montant (CAD)", min_value=0, step=500, format="%d $"),
        })
    portefeuille = {}
    for ligne in edite.dropna().itertuples():
        s, m = str(ligne.symbole).strip().upper(), float(ligne.montant_cad)
        if s and m > 0:
            portefeuille[s] = portefeuille.get(s, 0.0) + m
    non_couverts = symboles_non_couverts(portefeuille) if portefeuille else []
    if portefeuille:
        st.caption(f"{len(portefeuille)} titre(s), {dollars(sum(portefeuille.values()))} au total.")
    else:
        st.caption("Aucune ligne pour l'instant.")
    if non_couverts:
        st.error("Symboles non couverts par le jeu de données : " + ", ".join(non_couverts)
                 + ". Retirez-les ou remplacez-les par un titre de la liste.")

    if st.button("Analyser mon portefeuille", type="primary", width="stretch",
                 disabled=not portefeuille or bool(non_couverts)):
        etat.profil, etat.portefeuille, etat.persona_du_profil = profil, portefeuille, persona
        etat.etape, etat.messages = "resultats", []
        st.rerun()


# --------------------------------------------------------------- 2. résultats
def resultats():
    # Un seul profil sur cette page : celui du questionnaire. Pour en essayer un autre, on revient
    # au questionnaire, qui garde les réponses déjà données.
    portefeuille, profil = etat.portefeuille, etat.profil
    depart = etat.get("persona_du_profil", "Personnalisé")

    gauche, droite = st.columns([4, 1], vertical_alignment="bottom")
    gauche.title("Calibre")
    gauche.caption(AVERTISSEMENT)
    if droite.button("Modifier mes réponses", width="stretch"):
        # Streamlit oublie la valeur d'un widget absent de la page : on remet le point de départ
        # à la main, sinon le questionnaire reviendrait sur Amira et perdrait les réponses.
        etat.etape, etat.persona = "questionnaire", depart
        st.rerun()

    try:
        mesures = analyser_memo(portefeuille)
    except ValueError as erreur:
        st.error(str(erreur))
        st.stop()
    resultat = evaluer(mesures, profil)

    # ---- le verdict
    # Le score sur toute la largeur, puis les quatre notes sous lui : les quatre chiffres sur une
    # seule ligne se serraient, et le verdict se lisait aussi petit que le reste.
    st.header("Le verdict", divider="gray")
    with st.container(border=True):
        colonne_score, colonne_verdict = st.columns([1, 2], vertical_alignment="center")
        colonne_score.metric("Score d'adéquation", f"{resultat['score']} / 100",
                             help=aide_score(resultat, profil))
        with colonne_verdict:
            bandeau_verdict(resultat["verdict"])
            if resultat.get("raison_verdict"):
                st.write(md(resultat["raison_verdict"]))
            st.caption(f"Niveau de risque retenu : {nombre(resultat['niveau_effectif'])} sur 3, "
                       f"objectif {etiquette(OBJECTIFS, profil['objectif']).lower()}, "
                       f"capital de {dollars(mesures['capital'])}.")
    for colonne, note in zip(st.columns(len(resultat["notes"])), resultat["notes"]):
        with colonne.container(border=True):
            st.metric(NOMS_NOTES[note["nom"]], f"{note['note']} / 100", help=aide_note(note))
            st.progress(int(note["note"]))
            st.write(md(note["explication"]))

    # ---- ce que vous détenez
    # L'anneau et la liste côte à côte : seul, un cercle laisse une large bande vide de chaque
    # côté, et la liste est de toute façon ce qu'on vient chercher juste après le dessin.
    st.header("Ce que vous détenez", divider="gray")
    colonne_anneau, colonne_liste = st.columns([3, 2], vertical_alignment="center")
    colonne_anneau.altair_chart(beignet(mesures), width="stretch")
    colonne_liste.markdown(liste_titres(mesures), unsafe_allow_html=True)
    if len(mesures["poids"]) > 6:
        st.caption("Part de chaque titre dans le capital. Les lignes au-delà des cinq plus "
                   "grosses sont regroupées sous « Autres » dans l'anneau : la liste à droite "
                   "et l'onglet Tableau plus bas gardent le détail, ligne par ligne.")
    else:
        st.caption("Part de chaque titre dans le capital.")

    # ---- par pays et par devise
    # Le pays répond à « où est mon argent » ; la devise, à un risque que les investisseurs
    # canadiens voient rarement : la part cotée en dollars américains bouge aussi avec le change.
    if mesures.get("poids_par_pays"):
        st.subheader("Par pays et par devise")
        st.markdown(repartition_pays(mesures), unsafe_allow_html=True)
        usd = mesures.get("poids_par_devise", {}).get("USD", 0.0)
        if usd > 0:
            st.markdown(md(f"**{pct(usd)} du portefeuille est coté en dollars américains.** Sa valeur en dollars "
                           "canadiens dépend aussi du taux de change : si le dollar canadien montait face au dollar "
                           "américain, cette part perdrait de la valeur en CAD, même sans aucun mouvement en bourse. "
                           "Ce risque de change est déjà compris dans la volatilité et les pertes mesurées."))
        else:
            st.markdown("**Tout le portefeuille est coté en dollars canadiens** : aucune exposition directe au "
                        "taux de change USD/CAD.")
        st.caption("Pays : marché de cotation. Un FNB compte pour son marché, sans voir son contenu ; l'or et les "
                   "cryptoactifs n'ont pas de pays.")

    # ---- d'où vient le risque
    # Le graphique et le tableau portent les mêmes chiffres : deux onglets plutôt que l'un sous
    # l'autre. Le tableau reste à un clic, ce qui est la contrepartie exigée par les couleurs :
    # il se lit sans distinguer le bleu de l'orange et sans survoler les barres.
    st.header("D'où vient le risque", divider="gray")
    onglet_graphique, onglet_tableau, onglet_crise = st.tabs(
        ["Graphique", "Tableau", "En cas de crise (2022)"])
    with onglet_graphique:
        st.altair_chart(graphique(mesures), width="stretch")
        st.caption("Quand la barre orange dépasse la bleue, le titre pèse plus lourd dans le "
                   "risque que dans le capital.")
    with onglet_tableau:
        st.dataframe(
            tableau_poids(mesures), hide_index=True, width="stretch",
            height=min(620, 36 * len(mesures["poids"]) + 45),
            column_config={
                "Secteur": st.column_config.TextColumn("Secteur", width="medium"),
                "Montant (CAD)": st.column_config.NumberColumn("Montant (CAD)", format="%d $"),
            })
        st.caption("Les mêmes chiffres que le graphique, lisibles sans couleur ni survol.")
    with onglet_crise:
        trajet = trajectoire_memo(portefeuille)
        if trajet is None:
            st.info("Ce portefeuille n'a pas de prix en 2022 : la crise ne peut pas être rejouée.")
        else:
            note_crise = next((n for n in resultat["notes"] if n["nom"] == "resistance_crise"), None)
            limite = note_crise["cible"] if note_crise else None
            st.markdown(md(
                f"Si ce portefeuille de **{dollars(trajet['capital'])}** avait traversé la crise de 2022 avec les "
                f"mêmes montants, il serait passé de {dollars(trajet['sommet']['valeur'])} à "
                f"**{dollars(trajet['creux']['valeur'])}** au pire moment : une baisse de "
                f"**{dollars(trajet['perte_dollars'])}** ({pourcent(trajet['perte'])})."))
            c1, c2, c3 = st.columns(3)
            c1.metric("Baisse au pire moment", dollars(trajet["perte_dollars"]),
                      delta=f"-{pourcent(trajet['perte'])}", delta_color="inverse",
                      help="Du sommet au creux, pendant l'année 2022.")
            if limite:
                tolere = trajet["sommet"]["valeur"] * limite
                c2.metric("Ce que ce profil tolère", dollars(tolere),
                          help=f"Baisse de {pourcent(limite, 0)} depuis le sommet : la cible de résistance "
                               "à la crise pour ce niveau de risque (choix de l'équipe).")
            c3.metric("Valeur fin 2022", dollars(trajet["valeur_fin"]),
                      delta=dollars(trajet["valeur_fin"] - trajet["capital"]))
            st.altair_chart(graphique_crise(trajet, limite), width="stretch")
            a, b = trajet["part_effacee_cinq_ans"], trajet["part_effacee_2022"]
            constat = ("La diversification a moins protégé pendant la crise : les titres se sont mis à baisser "
                       "ensemble." if b < a - 0.02 else "La diversification a tenu pendant la crise.")
            st.markdown(md(f"**Et la diversification ?** En temps normal (sur cinq ans), le fait que les titres ne "
                           f"bougent pas ensemble efface {pourcent(a, 0)} du risque de ce portefeuille. Pendant "
                           f"2022, seulement {pourcent(b, 0)}. {constat}"))
            st.caption("Le portefeuille actuel rejoué jour après jour de janvier à décembre 2022, à pondérations "
                       "constantes, en dollars canadiens. C'est la seule crise couverte par les données (à partir "
                       "de novembre 2021) : ni 2008 ni mars 2020, et la prochaine crise peut toucher d'autres "
                       "actifs. Ce n'est pas une prévision.")

    # ---- alertes
    st.header("Alertes", divider="gray")
    if not resultat["alertes"]:
        st.success("Aucune alerte pour ce profil.")
    for alerte in resultat["alertes"]:
        (st.error if alerte["gravite"] == "contrainte" else st.warning)(md(alerte["message"]))

    # ---- scénarios
    st.header("Scénarios fictifs", divider="gray")
    st.caption("Des changements calculés à partir du portefeuille, avec ce qui s'améliore et ce qui se dégrade. "
               "L'outil ne dit jamais quoi faire : la décision vous appartient. " + AVERTISSEMENT)
    scenarios = scenarios_memo(portefeuille, profil)
    voulu = nombre_de_scenarios(resultat)
    contrainte = any(a["gravite"] == "contrainte" for a in resultat["alertes"])
    # Le nombre de scénarios suit le verdict brut du score : on dit pourquoi, pour qu'il ne paraisse pas arbitraire.
    if voulu == 0:
        st.success(md(f"Ce portefeuille est déjà dans les cibles de ce profil (score de {resultat['score']} sur 100) : "
                      "aucun scénario n'est proposé. L'outil rapproche un portefeuille des cibles, il ne cherche pas "
                      "le portefeuille parfait."))
    elif not scenarios:
        st.info("Aucun des changements testés ne rapproche ce portefeuille des cibles de ce profil.")
    else:
        if voulu == 1 and contrainte:
            raison = "le score est dans les cibles, mais une contrainte du profil n'est pas respectée"
        elif voulu == 2:
            raison = f"le score de {resultat['score']} est proche des cibles (60 à 79)"
        else:
            raison = f"le score de {resultat['score']} est loin des cibles (moins de 60)"
        if len(scenarios) == 1:
            st.caption(md(f"Un scénario, parce que {raison} : il montre comment s'en rapprocher."))
        else:
            st.caption(md(f"{len(scenarios)} scénarios, parce que {raison}. Chacun est une façon différente "
                          "de se rapprocher des cibles."))
    # Un scénario par ligne, sur toute la largeur : côte à côte, la phrase et les deux listes
    # tombaient dans des colonnes de quelques mots de large.
    for numero, scenario in enumerate(scenarios, start=1):
        avant, apres = scenario["avant"]["score"], scenario["apres"]["score"]
        with st.container(border=True):
            texte, chiffre = st.columns([3, 1], vertical_alignment="center")
            texte.subheader(f"Scénario {numero}")
            texte.write(md(scenario["phrase"]))
            chiffre.metric("Score après", f"{apres} / 100", delta=apres - avant)
            onglet_changements, onglet_crise_scenario, onglet_periode = st.tabs(
                ["Changements", "Et pendant la crise de 2022 ?", "Et sur cinq ans ?"])
            with onglet_changements:
                afficher_changements(scenario)
            with onglet_crise_scenario:
                afficher_crise_scenario(portefeuille, scenario, resultat)
            with onglet_periode:
                afficher_periode_scenario(portefeuille, scenario)
            with st.expander("Hypothèses de ce scénario"):
                for hypothese in scenario["hypotheses"]:
                    st.write("- " + md(hypothese))

    # ---- hypothèses et limites
    # Repliées : la liste est longue, se lit une fois, et coupait la page entre les scénarios et
    # la discussion. Le compte dans le titre dit qu'il y a quelque chose à ouvrir.
    hypotheses = list(dict.fromkeys(resultat["hypotheses"] + list(mesures.get("hypotheses", []))))
    with st.expander(f"Hypothèses et limites du calcul ({len(hypotheses)})"):
        for hypothese in hypotheses:
            st.markdown("- " + md(hypothese))

    # ---- discussion
    st.header("Discussion avec l'agent", divider="gray")
    st.caption("L'agent lit votre question, choisit les fonctions de calcul à appeler sur AWS et explique leurs "
               "résultats. Il ne calcule rien lui-même et ne donne aucun conseil. Sous chaque réponse : ce qu'il "
               "a fait, les contrôles passés et les limites.")
    question = None
    for colonne, suggestion in zip(st.columns(len(QUESTIONS[depart])), QUESTIONS[depart]):
        if colonne.button(suggestion, key=f"suggestion_{suggestion}", width="stretch"):
            question = suggestion

    for indice, message in enumerate(etat.messages):
        with st.chat_message(message["role"]):
            st.write(md(message["texte"]))
            if message.get("outils"):
                with st.expander("Ce que l'agent a fait", expanded=indice == len(etat.messages) - 1):
                    for appel in message["outils"]:
                        st.write(md(f"- {appel['outil']} : {appel['resume']}"))
                    for limite in message.get("limites", []):
                        st.caption(md(limite))

    saisie = st.chat_input("Posez votre question sur ce portefeuille")
    question = saisie or question
    if question:
        etat.messages.append({"role": "user", "texte": question})
        with st.chat_message("user"):
            st.write(md(question))
        with st.chat_message("assistant"):
            with st.spinner("L'agent consulte les outils sur AWS…"):
                reponse = demander(question, portefeuille, profil, historique=etat.messages)
        etat.messages.append({
            "role": "assistant",
            "texte": reponse["reponse"],
            "outils": reponse.get("outils_appeles", []),
            "limites": reponse.get("limites", []),
        })
        st.rerun()


if etat.etape == "questionnaire":
    questionnaire()
else:
    resultats()
