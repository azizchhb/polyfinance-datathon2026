"""Interface Streamlit de la piste D. Lancer avec : python -m streamlit run app.py

Deux écrans dans une seule application :
1. le questionnaire, plein écran : le profil, puis le portefeuille ;
2. les résultats, une longue page où rien n'est caché : verdict, notes, graphique, alertes,
   scénarios, hypothèses, et la discussion avec l'agent en bas.
L'interface ne calcule rien : elle appelle analyser (piste A), evaluer et proposer_scenarios
(piste B), demander (piste C), et affiche ce qu'elles renvoient.
"""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from piste_a import analyser, symboles_non_couverts, univers
from piste_b import evaluer, nombre, proposer_scenarios
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
              "Je veux avoir 150 000 $ dans 10 ans, qu'est-ce que ça exige ?",
              "Quels changements rapprocheraient ce portefeuille de mon profil ?"],
    "Robert": ["J'ai lu plein d'articles sur NVIDIA. Je veux y mettre 15 000 $.",
               "Ce portefeuille me convient-il ?",
               "D'où vient le chiffre de perte maximale ?"],
    "Mon profil": ["Ce portefeuille me convient-il ?",
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

/* onglets : les libellés gardent leur taille par défaut, trop petite à cette échelle */
[data-testid="stTabs"] button p {{ font-size: 1rem; }}

/* alertes, boutons et saisie à la taille du reste */
[data-testid="stAlert"] {{ border-radius: 12px; padding: 1rem 1.1rem; }}
[data-testid="stAlert"] p {{ font-size: 1rem; }}
.stButton button {{ border-radius: 10px; padding: 0.55rem 1.1rem; font-size: 1rem; }}
[data-testid="stChatInput"] textarea {{ font-size: 1.02rem; }}
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
                      f'<span class="nom">{titre}</span>'
                      f'<span class="montant">{montant}</span>'
                      f'<span class="poids">{pourcentage} %</span></div>')
    return "".join(lignes)


def etiquette(dico, valeur):
    """Le libellé affiché pour une valeur du contrat (1.5 -> « Faible à modéré »)."""
    return next((e for e, v in dico.items() if v == valeur), next(iter(dico)))


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


def graphique_diversification(mesures):
    """Volatilité de chaque titre pris seul, moyenne pondérée des titres, volatilité réelle du portefeuille.

    Forme « mise en relief » : une seule série porte l'histoire, le portefeuille réel, en bleu ;
    les titres pris isolément et leur moyenne pondérée sont le contexte, en gris. L'écart entre
    la moyenne pondérée et le portefeuille est le gain de diversification de Markowitz : il ne
    fait intervenir aucun rendement espéré, seulement les covariances.
    """
    theme = mode_theme()
    titres = sorted(mesures["volatilite_par_titre"].items(), key=lambda couple: couple[1], reverse=True)
    types = ["Portefeuille réel", "Moyenne pondérée des titres", "Titre pris seul"]
    df = pd.DataFrame(
        [{"Ligne": "Portefeuille réel", "Type": types[0], "Valeur": 100 * mesures["volatilite"]},
         {"Ligne": "Si tout bougeait ensemble", "Type": types[1],
          "Valeur": 100 * mesures["volatilite_sans_diversification"]}]
        + [{"Ligne": s, "Type": types[2], "Valeur": 100 * v} for s, v in titres])
    gris_clair, gris = ("#c3c2b7", "#898781") if theme == "clair" else ("#52514e", "#898781")

    base = alt.Chart(df).transform_calculate(
        etiquette="replace(format(datum.Valeur, '.1f'), '.', ',') + ' %'",
    ).encode(
        y=alt.Y("Ligne:N", sort=list(df["Ligne"]), title=None,
                axis=alt.Axis(labelFontSize=15, ticks=False, domain=False, labelPadding=14, labelLimit=320)),
        x=alt.X("Valeur:Q", title="Volatilité annuelle (%)",
                scale=alt.Scale(domain=[0, float(df["Valeur"].max()) * 1.2], nice=False),
                axis=alt.Axis(tickCount=5, format=".0f", domain=False, gridOpacity=0.35,
                              labelFontSize=13, titleFontSize=13, titlePadding=12)),
        color=alt.Color("Type:N", sort=types,
                        scale=alt.Scale(domain=types, range=[COULEURS[theme][0], gris, gris_clair]),
                        legend=alt.Legend(title=None, orient="top", direction="horizontal",
                                          symbolType="square", labelFontSize=14, symbolSize=180, offset=14)),
        tooltip=[alt.Tooltip("Ligne:N", title="Ligne"), alt.Tooltip("etiquette:N", title="Volatilité annuelle")],
    )
    barres = base.mark_bar(size=24, cornerRadiusTopRight=5, cornerRadiusBottomRight=5)
    etiquettes = (base.mark_text(align="left", baseline="middle", dx=8, fontSize=14)
                  .encode(text="etiquette:N", color=alt.value(ENCRE[theme])))
    return (barres + etiquettes).properties(height=max(240, 52 * len(df)))


# ------------------------------------------------------------------ état et page
etat = st.session_state
etat.setdefault("etape", "questionnaire")
etat.setdefault("persona", "Amira")
etat.setdefault("persona_affiche", "Mon profil")
etat.setdefault("messages", [])
if etat.etape == "resultats" and not (etat.get("profil") and etat.get("portefeuille")):
    etat.etape = "questionnaire"

st.set_page_config(page_title="Diversifié pour qui ?", layout="wide",
                   initial_sidebar_state="collapsed")
# Largeur bornée plutôt que la mise en page « centered » : on choisit le nombre de pixels,
# plus large pour les résultats (un tableau de cinq colonnes) que pour le questionnaire.
st.markdown(style(900 if etat.etape == "questionnaire" else 1180), unsafe_allow_html=True)


# ------------------------------------------------------------ 1. questionnaire
def questionnaire():
    st.title("Diversifié pour qui ?")
    st.markdown("Les outils habituels donnent la même note de diversification à tout le monde. Ici, votre "
                "portefeuille est mesuré une fois, puis chaque mesure est comparée à une cible qui dépend de "
                "**votre** profil, et chaque chiffre est expliqué.")
    st.caption(AVERTISSEMENT)

    st.header("1. Votre profil", divider="gray")
    persona = st.radio("Point de départ", list(PERSONAS) + ["Personnalisé"], horizontal=True, key="persona",
                       captions=[PORTRAITS[p] for p in PERSONAS] + ["Vos propres réponses"])
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
    exclus = st.multiselect("Secteurs à exclure (approximation ESG, par secteur)", SECTEURS,
                            default=base["exclure_secteurs"], key=f"exclus_{k}")
    interet = st.multiselect("Secteurs d'intérêt", SECTEURS, default=base["secteurs_interet"], key=f"interet_{k}")
    montant_vise = cotisation = None
    if st.checkbox("J'ai un montant à atteindre", value=bool(base.get("montant_vise")), key=f"vise_{k}"):
        c1, c2 = st.columns(2)
        montant_vise = c1.number_input("Montant visé à la fin de l'horizon ($)", min_value=0, step=5000,
                                       value=int(base.get("montant_vise") or 100000), key=f"montant_{k}")
        cotisation = c2.number_input("Cotisation mensuelle ($)", min_value=0, step=50,
                                     value=int(base.get("cotisation_mensuelle") or 0), key=f"cotisation_{k}")
    profil = {
        "risque": RISQUES[risque], "horizon_annees": horizon, "objectif": OBJECTIFS[objectif],
        "perte_max_toleree": perte, "crypto": "oui" if crypto else "non",
        "exclure_secteurs": exclus, "secteurs_interet": interet,
        "montant_vise": montant_vise or None, "cotisation_mensuelle": cotisation or None,
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
        etat.etape, etat.messages, etat.persona_affiche, etat.persona_chat = "resultats", [], "Mon profil", None
        st.rerun()


# --------------------------------------------------------------- 2. résultats
def resultats():
    portefeuille, profil_saisi = etat.portefeuille, etat.profil

    gauche, droite = st.columns([4, 1], vertical_alignment="bottom")
    gauche.title("Diversifié pour qui ?")
    gauche.caption(AVERTISSEMENT)
    if droite.button("Modifier mes réponses", width="stretch"):
        etat.etape = "questionnaire"
        st.rerun()

    with st.container(border=True):  # la barre de choix se lit comme un réglage, pas comme du texte
        choix = st.radio("Regarder ce portefeuille avec le profil de", ["Mon profil"] + list(PERSONAS),
                         horizontal=True, key="persona_affiche",
                         captions=["Vos réponses au questionnaire"] + [PORTRAITS[p] for p in PERSONAS])
    profil = profil_saisi if choix == "Mon profil" else dict(PERSONAS[choix])
    if etat.get("persona_chat") != choix:  # on change de personne : la discussion repart à zéro
        etat.messages, etat.persona_chat = [], choix

    try:
        mesures = analyser(portefeuille)
    except ValueError as erreur:
        st.error(str(erreur))
        st.stop()
    resultat = evaluer(mesures, profil)

    # ---- le verdict
    # Le score sur toute la largeur, puis les trois notes sous lui : les quatre chiffres sur une
    # seule ligne se serraient, et le verdict se lisait aussi petit que le reste.
    st.header("Le verdict", divider="gray")
    with st.container(border=True):
        colonne_score, colonne_verdict = st.columns([1, 2], vertical_alignment="center")
        colonne_score.metric("Score d'adéquation", f"{resultat['score']} / 100")
        with colonne_verdict:
            bandeau_verdict(resultat["verdict"])
            st.caption(f"Niveau de risque retenu : {nombre(resultat['niveau_effectif'])} sur 3, "
                       f"objectif {etiquette(OBJECTIFS, profil['objectif']).lower()}, "
                       f"capital de {dollars(mesures['capital'])}.")
    for colonne, note in zip(st.columns(len(resultat["notes"])), resultat["notes"]):
        with colonne.container(border=True):
            st.metric(NOMS_NOTES[note["nom"]], f"{note['note']} / 100")
            st.progress(int(note["note"]))
            st.write(md(note["explication"]))

    # ---- ce que vous détenez
    # L'anneau et la liste côte à côte : seul, un cercle laisse une large bande vide de chaque
    # côté, et la liste est de toute façon ce qu'on vient chercher juste après le dessin.
    st.header("Ce que vous détenez", divider="gray")
    colonne_anneau, colonne_liste = st.columns([3, 2], vertical_alignment="center")
    colonne_anneau.altair_chart(beignet(mesures), use_container_width=True)
    colonne_liste.markdown(liste_titres(mesures), unsafe_allow_html=True)
    if len(mesures["poids"]) > 6:
        st.caption("Part de chaque titre dans le capital. Les lignes au-delà des cinq plus "
                   "grosses sont regroupées sous « Autres » dans l'anneau : la liste à droite "
                   "et l'onglet Tableau plus bas gardent le détail, ligne par ligne.")
    else:
        st.caption("Part de chaque titre dans le capital.")

    # ---- d'où vient le risque
    # Le graphique et le tableau portent les mêmes chiffres : deux onglets plutôt que l'un sous
    # l'autre. Le tableau reste à un clic, ce qui est la contrepartie exigée par les couleurs :
    # il se lit sans distinguer le bleu de l'orange et sans survoler les barres.
    st.header("D'où vient le risque", divider="gray")
    onglet_graphique, onglet_tableau, onglet_diversification = st.tabs(
        ["Graphique", "Tableau", "Gain de diversification"])
    with onglet_graphique:
        st.altair_chart(graphique(mesures), use_container_width=True)
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
    with onglet_diversification:
        if "gain_diversification" not in mesures:
            st.info("Le gain de diversification n'est pas fourni par cette version des mesures.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Si tout bougeait ensemble", pourcent(mesures["volatilite_sans_diversification"]),
                      help="Moyenne pondérée des volatilités des titres : la volatilité qu'aurait le "
                           "portefeuille si tous ses titres montaient et baissaient en même temps.")
            c2.metric("Volatilité réelle du portefeuille", pourcent(mesures["volatilite"]))
            c3.metric("Gain de diversification",
                      f"{100 * mesures['gain_diversification']:.1f} points".replace(".", ","),
                      help=f"Ratio de diversification : {mesures['ratio_diversification']:.2f}".replace(".", ","))
            st.altair_chart(graphique_diversification(mesures), use_container_width=True)
            st.caption("Les titres ne montent pas et ne baissent pas tous en même temps : l'écart entre la "
                       "moyenne pondérée des volatilités et la volatilité réelle est le seul gain que la "
                       "théorie de Markowitz garantit. Il repose sur les covariances passées, sans aucun "
                       "rendement espéré.")

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
    scenarios = proposer_scenarios(portefeuille, profil, analyser)
    if not scenarios:
        st.info("Aucun des changements testés ne rapproche ce portefeuille des cibles de ce profil.")
    # Un scénario par ligne, sur toute la largeur : côte à côte, la phrase et les deux listes
    # tombaient dans des colonnes de quelques mots de large.
    for numero, scenario in enumerate(scenarios, start=1):
        avant, apres = scenario["avant"]["score"], scenario["apres"]["score"]
        with st.container(border=True):
            texte, chiffre = st.columns([3, 1], vertical_alignment="center")
            texte.subheader(f"Scénario {numero}")
            texte.write(md(scenario["phrase"]))
            chiffre.metric("Score après", f"{apres} / 100", delta=apres - avant)
            # Tableau des titres dont le poids change : plus lisible que la phrase dès 3 lignes.
            p0, p1 = scenario.get("poids_avant", {}), scenario.get("poids_apres", {})
            lignes = [{"Titre": s, "Avant": f"{100 * p0.get(s, 0):.1f} %", "Après": f"{100 * p1.get(s, 0):.1f} %",
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
    for colonne, suggestion in zip(st.columns(len(QUESTIONS[choix])), QUESTIONS[choix]):
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
