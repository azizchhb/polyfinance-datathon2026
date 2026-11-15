"""Interface Streamlit de la piste D. Lancer avec : python -m streamlit run app.py

Deux écrans dans une seule application :
1. le questionnaire, plein écran : le profil, puis le portefeuille ;
2. les résultats, une longue page où rien n'est caché : verdict, notes, graphique, alertes,
   un portefeuille trois verdicts, scénarios, hypothèses, et la discussion avec l'agent en bas.
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
              "diversification": "Diversification"}
# Deux premières couleurs de la palette catégorielle validée (paire sûre pour le daltonisme),
# avec leurs pas pour fond sombre. Les textes ne portent jamais la couleur des séries.
COULEURS = {"clair": ["#2a78d6", "#eb6834"], "sombre": ["#3987e5", "#d95926"]}
ENCRE = {"clair": "#31333f", "sombre": "#fafafa"}
SERIES = ["Poids dans le capital", "Part du risque"]

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


def md(texte):
    """Texte sûr pour le Markdown de Streamlit : un « $ » non échappé ouvre une formule mathématique."""
    return str(texte).replace("$", "\\$")


def dollars(x):
    return f"{x:,.0f}".replace(",", " ") + " $"


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


# ------------------------------------------------------------------ état et page
etat = st.session_state
etat.setdefault("etape", "questionnaire")
etat.setdefault("persona", "Amira")
etat.setdefault("persona_affiche", "Mon profil")
etat.setdefault("messages", [])
if etat.etape == "resultats" and not (etat.get("profil") and etat.get("portefeuille")):
    etat.etape = "questionnaire"

st.set_page_config(page_title="Diversifié pour qui ?",
                   layout="centered" if etat.etape == "questionnaire" else "wide",
                   initial_sidebar_state="collapsed")


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
    st.header("Le verdict", divider="gray")
    colonne_score, colonne_notes = st.columns([1, 3])
    with colonne_score:
        st.metric("Score d'adéquation", f"{resultat['score']} / 100", border=True)
        bandeau_verdict(resultat["verdict"])
        st.caption(f"Niveau de risque retenu : {nombre(resultat['niveau_effectif'])} sur 3, "
                   f"objectif {etiquette(OBJECTIFS, profil['objectif']).lower()}, "
                   f"capital de {dollars(mesures['capital'])}.")
    with colonne_notes:
        for colonne, note in zip(st.columns(3), resultat["notes"]):
            with colonne.container(border=True):
                st.metric(NOMS_NOTES[note["nom"]], f"{note['note']} / 100")
                st.progress(int(note["note"]))
                st.write(md(note["explication"]))

    # ---- d'où vient le risque
    st.header("D'où vient le risque", divider="gray")
    colonne_graphique, colonne_tableau = st.columns([3, 2])
    with colonne_graphique:
        st.altair_chart(graphique(mesures), use_container_width=True)
        st.caption("Quand la barre orange dépasse la bleue, le titre pèse plus lourd dans le risque que dans le capital.")
    with colonne_tableau:
        st.dataframe(tableau_poids(mesures), hide_index=True, width="stretch")

    # ---- alertes
    st.header("Alertes", divider="gray")
    if not resultat["alertes"]:
        st.success("Aucune alerte pour ce profil.")
    for alerte in resultat["alertes"]:
        (st.error if alerte["gravite"] == "contrainte" else st.warning)(md(alerte["message"]))

    # ---- un portefeuille, trois verdicts
    st.header("Un portefeuille, trois verdicts", divider="gray")
    st.caption("Le même portefeuille, mesuré une seule fois, comparé aux cibles de chaque persona.")
    for colonne, (nom, profil_persona) in zip(st.columns(3), PERSONAS.items()):
        r = evaluer(mesures, profil_persona)
        with colonne.container(border=True):
            st.subheader(nom)
            st.caption(PORTRAITS[nom])
            st.metric("Score", f"{r['score']} / 100")
            bandeau_verdict(r["verdict"])
            if r["alertes"]:
                st.write(md(r["alertes"][0]["message"]))
                if len(r["alertes"]) > 1:
                    st.caption(f"Et {len(r['alertes']) - 1} autre(s) alerte(s).")
            else:
                st.write("Aucune alerte.")

    # ---- scénarios
    st.header("Scénarios fictifs", divider="gray")
    st.caption("Des changements calculés à partir du portefeuille, avec ce qui s'améliore et ce qui se dégrade. "
               "L'outil ne dit jamais quoi faire : la décision vous appartient. " + AVERTISSEMENT)
    scenarios = proposer_scenarios(portefeuille, profil, analyser)
    if not scenarios:
        st.info("Aucun des changements testés ne rapproche ce portefeuille des cibles de ce profil.")
    for numero, (colonne, scenario) in enumerate(zip(st.columns(max(1, len(scenarios))), scenarios), start=1):
        avant, apres = scenario["avant"]["score"], scenario["apres"]["score"]
        with colonne.container(border=True):
            st.subheader(f"Scénario {numero}")
            st.write(md(scenario["phrase"]))
            st.metric("Score après", f"{apres} / 100", delta=apres - avant)
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
    st.header("Hypothèses et limites du calcul", divider="gray")
    for hypothese in dict.fromkeys(resultat["hypotheses"] + list(mesures.get("hypotheses", []))):
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
