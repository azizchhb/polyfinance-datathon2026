"""Interface Streamlit de la piste D. Lancer avec : streamlit run app.py"""
import altair as alt
import pandas as pd
import streamlit as st

from piste_b import evaluer, proposer_scenarios
# Pour tester l'interface sans données, remplacer la ligne suivante par : from tests.faux import analyser
from piste_a import analyser
from piste_c import demander

AVERTISSEMENT = ("Simulation à but éducatif, à partir de données historiques. "
                 "Aucune transaction réelle, aucun conseil financier personnalisé.")

RISQUES = {"Faible": 1, "Faible à modéré": 1.5, "Modéré": 2, "Modéré à élevé": 2.5, "Élevé": 3}
OBJECTIFS = {"Préserver le capital": "preservation", "Équilibre": "equilibre", "Croissance": "croissance"}
# Secteurs de assets_universe.csv, traduits (voir la table de correspondance du contrat)
SECTEURS = ["technologie", "energie", "finance", "sante", "industrie", "services_publics",
            "communication", "consommation_de_base", "consommation_discretionnaire"]
VERDICTS = {"adequat": "Adéquat", "a_surveiller": "À surveiller", "inadequat": "Inadéquat"}
NOMS_NOTES = {"niveau_de_risque": "Niveau de risque",
              "risque_de_perte": "Risque de perte",
              "diversification": "Diversification"}
# Deux premières couleurs de la palette catégorielle validée (paire sûre pour le daltonisme),
# avec leurs pas pour fond sombre. Les textes ne portent jamais la couleur des séries.
COULEURS = {"clair": ["#2a78d6", "#eb6834"], "sombre": ["#3987e5", "#d95926"]}
ENCRE = {"clair": "#31333f", "sombre": "#fafafa"}
SERIES = ["Poids dans le capital", "Part du risque"]

PERSONAS = {
    "Amira": {"risque": 3, "horizon_annees": 15, "objectif": "croissance", "crypto": "oui",
              "exclure_secteurs": [], "secteurs_interet": ["technologie"], "experience": "intermediaire"},
    "Mateo": {"risque": 2, "horizon_annees": 10, "objectif": "equilibre", "crypto": "non",
              "exclure_secteurs": ["energie"], "secteurs_interet": [], "experience": "intermediaire"},
    "Robert": {"risque": 1.5, "horizon_annees": 4, "objectif": "preservation", "crypto": "non",
               "exclure_secteurs": [], "secteurs_interet": [], "experience": "avance"},
}
PORTEFEUILLE_DEMO = {"NVDA": 10000, "QQQ": 12500, "BTC-USD": 5000, "XIU.TO": 17500, "XBB.TO": 5000}


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


def formulaire(persona):
    """Affiche les champs dans la barre latérale et renvoie le profil."""
    base = PERSONAS.get(persona, PERSONAS["Mateo"])
    k = persona  # les clés changent avec le persona : les champs reprennent ses valeurs
    barre = st.sidebar

    etiquette = next(e for e, v in RISQUES.items() if v == base["risque"])
    risque = barre.select_slider("Tolérance au risque", options=list(RISQUES), value=etiquette, key=f"risque_{k}")
    horizon = barre.slider("Horizon (années)", 1, 30, base["horizon_annees"], key=f"horizon_{k}")
    objectif = barre.selectbox("Objectif", list(OBJECTIFS),
                               index=list(OBJECTIFS.values()).index(base["objectif"]), key=f"objectif_{k}")
    perte = None
    if barre.checkbox("Préciser la perte maximale tolérée", key=f"preciser_{k}"):
        perte = barre.slider("Perte maximale tolérée (%)", 5, 60, 20, key=f"perte_{k}") / 100
    crypto = barre.checkbox("Cryptoactifs acceptés", value=base["crypto"] == "oui", key=f"crypto_{k}")
    exclus = barre.multiselect("Secteurs à exclure (approximation ESG)", SECTEURS,
                               default=base["exclure_secteurs"], key=f"exclus_{k}")
    interet = barre.multiselect("Secteurs d'intérêt", SECTEURS,
                                default=base["secteurs_interet"], key=f"interet_{k}")
    return {
        "risque": RISQUES[risque],
        "horizon_annees": horizon,
        "objectif": OBJECTIFS[objectif],
        "perte_max_toleree": perte,
        "crypto": "oui" if crypto else "non",
        "exclure_secteurs": exclus,
        "secteurs_interet": interet,
        "experience": base["experience"],
    }


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
                axis=alt.Axis(labelFontSize=13, ticks=False, domain=False, labelPadding=10)),
        yOffset=alt.YOffset("Mesure:N", sort=SERIES),
        x=alt.X("Valeur:Q", title="% du total",
                scale=alt.Scale(domain=[0, float(df["Valeur"].max()) * 1.2], nice=False),
                axis=alt.Axis(tickCount=5, format=".0f", domain=False, gridOpacity=0.35)),
        color=alt.Color("Mesure:N", sort=SERIES, scale=alt.Scale(domain=SERIES, range=COULEURS[theme]),
                        legend=alt.Legend(title=None, orient="top", direction="horizontal", symbolType="square")),
        tooltip=[alt.Tooltip("Titre:N", title="Titre"), alt.Tooltip("Mesure:N", title="Mesure"),
                 alt.Tooltip("affichage:N", title="% du total")],
    )
    barres = base.mark_bar(size=18, cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
    etiquettes = (base.transform_filter(alt.datum.Mesure == SERIES[1])
                  .mark_text(align="left", baseline="middle", dx=6, fontSize=12)
                  .encode(text="etiquette:N", color=alt.value(ENCRE[theme])))
    return (barres + etiquettes).properties(height=max(120, 48 * len(symboles)))


def tableau_poids(mesures):
    """Les mêmes chiffres que le graphique, en tableau : lisibles sans couleur ni survol."""
    symboles = sorted(mesures["poids"], key=mesures["contributions"].get, reverse=True)
    return pd.DataFrame({
        "Titre": symboles,
        "Classe": [mesures["classe_par_titre"].get(s, "") for s in symboles],
        "Secteur": [mesures["secteur_par_titre"].get(s, "") for s in symboles],
        "Poids (%)": [round(100 * mesures["poids"][s], 1) for s in symboles],
        "Part du risque (%)": [round(100 * mesures["contributions"][s], 1) for s in symboles],
    })


# ---------------------------------------------------------------------- page
st.set_page_config(page_title="Diversifié pour qui ?", layout="wide")
st.title("Diversifié pour qui ?")
st.caption(AVERTISSEMENT)

st.sidebar.header("1. Profil")
persona = st.sidebar.radio("Point de départ", list(PERSONAS) + ["Personnalisé"], horizontal=True)
profil = formulaire(persona)

st.sidebar.header("2. Portefeuille")
fichier = st.sidebar.file_uploader("CSV avec les colonnes symbole et montant_cad", type="csv")
if fichier is not None:
    portefeuille, messages = lire_csv(fichier)
    for message in messages:
        st.sidebar.warning(message)
else:
    portefeuille = dict(PORTEFEUILLE_DEMO)
    st.sidebar.info("Aucun fichier déposé : le portefeuille de démonstration est utilisé.")

if not portefeuille:
    st.error("Aucun portefeuille valide à analyser.")
    st.stop()

try:
    mesures = analyser(portefeuille)
except ValueError as erreur:  # symbole hors des 31 actifs couverts, ou portefeuille vide
    st.error(str(erreur))
    st.stop()
resultat = evaluer(mesures, profil)

onglet_diagnostic, onglet_scenarios, onglet_discussion = st.tabs(["Diagnostic", "Scénarios", "Discussion"])

# ------------------------------------------------------------------ diagnostic
with onglet_diagnostic:
    gauche, droite = st.columns([1, 3])
    with gauche:
        st.metric("Score d'adéquation", f"{resultat['score']} / 100")
        bandeau = {"adequat": st.success, "a_surveiller": st.warning, "inadequat": st.error}[resultat["verdict"]]
        bandeau(VERDICTS[resultat["verdict"]])
    with droite:
        for colonne, note in zip(st.columns(3), resultat["notes"]):
            with colonne:
                st.metric(NOMS_NOTES[note["nom"]], f"{note['note']} / 100")
                st.progress(int(note["note"]))
                st.caption(note["explication"])

    st.subheader("Poids et part du risque")
    colonne_graphique, colonne_tableau = st.columns([3, 2])
    with colonne_graphique:
        st.altair_chart(graphique(mesures), use_container_width=True)
        st.caption("Quand la barre orange dépasse la bleue, le titre pèse plus lourd dans le risque que dans le capital.")
    with colonne_tableau:
        st.dataframe(tableau_poids(mesures), hide_index=True, width="stretch")

    st.subheader("Alertes")
    if not resultat["alertes"]:
        st.success("Aucune alerte pour ce profil.")
    for alerte in resultat["alertes"]:
        if alerte["gravite"] == "contrainte":
            st.error(alerte["message"])
        else:
            st.warning(alerte["message"])

    st.subheader("Un portefeuille, trois verdicts")
    lignes = []
    for nom, profil_persona in PERSONAS.items():
        r = evaluer(mesures, profil_persona)
        lignes.append({"Persona": nom, "Score": r["score"], "Verdict": VERDICTS[r["verdict"]]})
    st.dataframe(pd.DataFrame(lignes), hide_index=True)

    with st.expander("Hypothèses et limites de ce calcul"):
        for hypothese in resultat["hypotheses"]:
            st.write("- " + hypothese)

# ------------------------------------------------------------------- scénarios
with onglet_scenarios:
    st.caption("Scénarios fictifs calculés à partir du portefeuille. " + AVERTISSEMENT)
    scenarios = proposer_scenarios(portefeuille, profil, analyser)
    if not scenarios:
        st.info("Aucun des changements testés ne rapproche ce portefeuille des cibles du profil.")
    else:
        for numero, (colonne, scenario) in enumerate(zip(st.columns(len(scenarios)), scenarios), start=1):
            avant, apres = scenario["avant"]["score"], scenario["apres"]["score"]
            with colonne:
                st.subheader(f"Scénario {numero}")
                st.write(scenario["phrase"])
                st.metric("Score", f"{apres} / 100", delta=apres - avant)
                st.markdown("**Ce qui s'améliore**")
                for ligne in scenario["ameliore"] or ["Rien"]:
                    st.write("- " + ligne)
                st.markdown("**Ce qui se dégrade**")
                for ligne in scenario["degrade"] or ["Rien"]:
                    st.write("- " + ligne)
                with st.expander("Hypothèses de ce scénario"):
                    for hypothese in scenario["hypotheses"]:
                        st.write("- " + hypothese)

# ------------------------------------------------------------------ discussion
with onglet_discussion:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["texte"])
            if message.get("outils"):
                with st.expander("Ce que l'agent a fait"):
                    for appel in message["outils"]:
                        st.write(f"- {appel['outil']} : {appel['resume']}")
                    for limite in message.get("limites", []):
                        st.caption(limite)

    question = st.chat_input("Pose une question sur ce portefeuille")
    if question:
        st.session_state.messages.append({"role": "user", "texte": question})
        reponse = demander(question, portefeuille, profil, historique=st.session_state.messages)
        st.session_state.messages.append({
            "role": "assistant",
            "texte": reponse["reponse"],
            "outils": reponse.get("outils_appeles", []),
            "limites": reponse.get("limites", []),
        })
        st.rerun()
