"""Interface AlphaForge. Lancer : .venv/bin/streamlit run app.py"""

import copy
import json

import pandas as pd
import plotly.express as px
import streamlit as st

import analytics as A
from profiles import PROFILES

st.set_page_config(page_title="AlphaForge AI", page_icon="📊", layout="wide")

# --------------------------------------------------------------------------- barre latérale
st.sidebar.title("AlphaForge AI")
st.sidebar.caption("Analyse de portefeuille auto-explicative. **Simulation uniquement, ce n'est pas un conseil financier.**")
name = st.sidebar.selectbox("Investisseur", list(PROFILES))

if st.session_state.get("persona") != name:
    st.session_state.persona = name
    st.session_state.profile = copy.deepcopy(PROFILES[name])
    st.session_state.holdings = dict(PROFILES[name]["portefeuille"])
    st.session_state.chat = []
    st.session_state.agent = None

profile = st.session_state.profile
st.sidebar.markdown(f"**{profile['age']} ans · {profile['profession']}**  \n"
                    f"Risque : **{profile['profil_risque']}** · Horizon : **{profile['horizon']}**")
st.sidebar.markdown("**Préférences**\n" + "\n".join(f"- {p}" for p in profile["preferences"]))
if profile["exclusions"]:
    st.sidebar.markdown("**Exclusions** : " + ", ".join(profile["exclusions"]))
st.sidebar.info(f"Ce que ce persona teste : {profile['test_enonce']}")

with st.sidebar.expander("Limites du profil (hypothèses modifiables)"):
    labels = {"volatilite_max_pct": "Volatilité max (%)", "baisse_max_toleree_pct": "Baisse max tolérée (%)",
              "ligne_max_pct": "Ligne individuelle max (%)", "crypto_max_pct": "Crypto max (%)",
              "techno_max_pct": "Techno max (%)", "defensif_min_pct": "Défensif min (%)"}
    for k, lab in labels.items():
        profile["limites"][k] = st.number_input(lab, 0, 100, int(profile["limites"][k]), key=f"{name}-{k}")

# --------------------------------------------------------------------------- portefeuille éditable
st.header(f"Portefeuille de {profile['nom']}")
universe = A.load_universe()
df = pd.DataFrame({"ticker": list(st.session_state.holdings), "montant_cad": list(st.session_state.holdings.values())})
edited = st.data_editor(
    df, num_rows="dynamic", width="stretch", key=f"editor-{name}",
    column_config={
        "ticker": st.column_config.SelectboxColumn("Actif", options=list(universe.index), required=True),
        "montant_cad": st.column_config.NumberColumn("Montant (CAD)", min_value=0, step=1000, format="%d $"),
    },
)
holdings = {r.ticker: float(r.montant_cad) for r in edited.dropna().itertuples() if r.montant_cad > 0}
if holdings != st.session_state.holdings:
    st.session_state.holdings = holdings
    st.session_state.agent = None  # le portefeuille a changé : l'agent repart avec les nouvelles données

try:
    res = A.analyze(profile, holdings)
except Exception as e:
    st.error(str(e))
    st.stop()

tab_diag, tab_chat, tab_trace, tab_src = st.tabs(["📋 Diagnostic", "💬 Chat avec l'agent", "🔍 Traçabilité", "📚 Sources et limites"])

# --------------------------------------------------------------------------- diagnostic
with tab_diag:
    m, e = res["metriques_historiques"], res["expositions"]
    c = st.columns(5)
    c[0].metric("Adéquation au profil", f"{res['score_adequation_sur_100']}/100")
    c[1].metric("Volatilité annualisée", f"{m['volatilite_annualisee_pct']} %", help=f"Limite : {profile['limites']['volatilite_max_pct']} %")
    c[2].metric("Baisse max historique", f"{m['baisse_max_pct']} %", help=f"Creux le {m['date_creux']}")
    c[3].metric("Rendement 2022", f"{m['rendement_2022_pct']} %", help="Année où actions et obligations ont baissé ensemble")
    c[4].metric("Rendement annualisé (passé)", f"{m['rendement_annualise_pct']} %", help="Le passé ne prédit pas le futur")

    st.subheader("Constats de gouvernance")
    if not res["constats_gouvernance"]:
        st.success("Aucune règle du profil n'est violée.")
    icon = {"élevée": "🔴", "moyenne": "🟠", "info": "🔵"}
    for f in res["constats_gouvernance"]:
        with st.expander(f"{icon[f['gravite']]} {f['id']} · {f['titre']} : {f['observe']} (seuil {f['seuil']})"):
            st.write(f["explication"])
            st.caption(f"Source : {f['source']}")

    g1, g2 = st.columns(2)
    alloc = pd.DataFrame({"actif": list(res["poids_pct"]), "poids": list(res["poids_pct"].values())})
    g1.plotly_chart(px.pie(alloc, names="actif", values="poids", hole=0.5, title="Répartition par actif"), width="stretch")
    sect = pd.DataFrame({"secteur": list(e["par_secteur_pct"]), "poids": list(e["par_secteur_pct"].values())})
    g2.plotly_chart(px.bar(sect, x="poids", y="secteur", orientation="h", title="Répartition par secteur (%)"), width="stretch")

    series = A.portfolio_value_series(A.normalize(holdings)) * res["montant_total_cad"]
    st.plotly_chart(px.line(series.rename("Valeur (CAD)"), title="Valeur historique simulée (poids actuels, en CAD)"),
                    width="stretch")

# --------------------------------------------------------------------------- chat
with tab_chat:
    if st.session_state.agent is None:
        try:
            from agent import AlphaForgeAgent
            st.session_state.agent = AlphaForgeAgent(profile, holdings)
            st.session_state.chat = []
        except Exception as ex:
            st.error(f"Impossible d'initialiser le LLM : {ex}\n\nConfigure AWS (Bedrock) ou ANTHROPIC_API_KEY : voir README.")
            st.stop()
    agent = st.session_state.agent
    st.caption(f"Modèle : {agent.model} via {agent.provider}")

    suggestions = ["Analyse mon portefeuille et dis-moi s'il me correspond.",
                   "Quels changements concrets me proposes-tu ? Teste-les avant."]
    if profile.get("demande_exemple"):
        suggestions.append(profile["demande_exemple"])
    cols = st.columns(len(suggestions))
    clicked = next((s for col, s in zip(cols, suggestions) if col.button(s[:60] + ("…" if len(s) > 60 else ""), key=s)), None)

    for msg in st.session_state.chat:
        st.chat_message(msg["role"]).markdown(msg["content"])

    prompt = st.chat_input("Pose une question sur le portefeuille…") or clicked
    if prompt:
        st.session_state.chat.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)
        with st.chat_message("assistant"):
            with st.status("Analyse en cours…", expanded=True) as status:
                def show(tool, args):
                    st.write(f"🔧 `{tool}` {json.dumps(args, ensure_ascii=False) if args else ''}")
                try:
                    answer = agent.ask(prompt, on_tool=show)
                    status.update(label="Analyse terminée", state="complete", expanded=False)
                except Exception as ex:
                    answer = f"Erreur lors de l'appel au modèle : {ex}"
                    status.update(label="Erreur", state="error")
            st.markdown(answer)
        st.session_state.chat.append({"role": "assistant", "content": answer})

# --------------------------------------------------------------------------- traçabilité
with tab_trace:
    st.write("Chaque appel d'outil de l'agent, avec ses entrées et sorties exactes. "
             "Chaque chiffre cité dans le chat peut être vérifié ici.")
    agent = st.session_state.get("agent")
    trace = agent.tools.trace if agent else []
    if not trace:
        st.info("Aucun appel d'outil pour l'instant. Pose une question dans le chat.")
    for i, t in enumerate(trace, 1):
        with st.expander(f"{i}. {'✅' if t['ok'] else '❌'} {t['outil']} · {t['duree_ms']} ms"):
            st.json({"entree": t["entree"], "sortie": t["sortie"]}, expanded=False)

# --------------------------------------------------------------------------- sources
with tab_src:
    st.markdown("### Sources de données")
    for k, v in A.SOURCES.items():
        st.markdown(f"- **{k}** : {v}")
    st.markdown("### Hypothèses")
    for h in res["hypotheses"] + [e["hypothese_techno"], e["note_concentration"],
                                  "Les limites par profil sont des hypothèses de l'équipe, modifiables dans la barre latérale."]:
        st.markdown(f"- {h}")
    st.markdown("### Limites")
    st.markdown("""- Période de 5 ans seulement, qui inclut une année exceptionnelle (2022).
- Biais du survivant : l'univers a été choisi en 2026 parmi des titres aujourd'hui importants.
- Aucune cote ESG dans les données : les exclusions de Mateo reposent sur ses préférences déclarées, pas sur une notation.
- La volatilité n'est qu'un indicateur de risque parmi d'autres.
- **Simulation uniquement** : aucune transaction, ce n'est pas un conseil financier personnalisé.""")
