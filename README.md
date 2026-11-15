# Diversifié pour qui ?

Datathon PolyFinances 2026, défi AlphaForge AI. Les outils existants donnent la même note de
diversification à tout le monde. Celui-ci mesure un portefeuille une fois, puis compare chaque
mesure à une cible qui dépend du profil : un même portefeuille, trois verdicts pour Amira, Mateo
et Robert. Un agent sur Amazon Bedrock explique les résultats sans jamais calculer lui-même, et
sans jamais donner de conseil. Simulation à but éducatif, aucune transaction réelle.

## Lancer

```powershell
pip install streamlit pandas numpy boto3
python -m streamlit run app.py     # l'interface
python piste_c.py                  # démonstration de l'agent sur le persona Robert
python piste_a.py                  # vérifications des calculs et portefeuilles de référence
```

Les identifiants AWS vont dans `~/.aws/credentials`, jamais dans le code : voir `CLAUDE.md`,
section « État AWS ». Sans AWS, l'interface fonctionne avec la copie locale des données et les
calculs locaux ; seul l'agent a besoin de Bedrock.

## Organisation

| Emplacement | Contenu |
|---|---|
| `app.py`, `piste_a.py`, `piste_b.py`, `piste_c.py`, `donnees.py` | Le code de l'application : interface, calculs, score, agent, données |
| `aws/` | Déploiement de la fonction Lambda des outils, et les trois preuves AWS |
| `data/alphaforge_starter/` | Jeu de départ des organisateurs (aussi sur S3) |
| `data/portefeuilles/` | Portefeuilles d'exemple à déposer dans l'interface (CSV : `symbole,montant_cad`) |
| `docs/` | Documentation technique et maquette du guide de la piste A |
| `tests/` | Fausse piste A pour tester l'interface sans données |
| `CLAUDE.md` | Le contexte complet du projet : règles, contrat entre pistes, état, AWS |

## Architecture

```
App Streamlit  <->  Agent sur Bedrock  <->  Outils sur Lambda (pistes A et B)  <-  S3 (données)
                           |                            |
                      CloudWatch (trace de l'agent)   CloudWatch (un JSON par outil)
```
