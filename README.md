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

## Configuration

| Variable d'environnement | Rôle | Défaut |
|---|---|---|
| `AWS_DEFAULT_REGION` ou `~/.aws/config` | Région AWS | `us-east-1` |
| `MODELE_BEDROCK` | Modèle de l'agent (profil d'inférence Bedrock) | `us.anthropic.claude-opus-5-5` |
| `OUTILS_LAMBDA` | `0` pour exécuter les outils en local plutôt que sur Lambda | `1` |
| `FONCTION_LAMBDA` | Nom de la fonction Lambda des outils | `alphaforge-outils` |
| `JOURNAL_CLOUDWATCH` | `0` pour ne pas envoyer la trace de l'agent dans CloudWatch | `1` |
| `SEAU_DONNEES` | Seau S3 des données | `alphaforge-<compte>-donnees` |
| `CACHE_DONNEES` | Dossier du cache local des fichiers S3 | `.cache_donnees/` |

## Reproduire l'installation AWS

```powershell
python aws/preuves/preuve1_bedrock.py   # vérifie l'accès à Bedrock et les modèles disponibles
python donnees.py televerser            # crée le seau S3 s'il manque et dépose les données
python aws/deployer_lambda.py           # crée ou met à jour la fonction Lambda des outils
python tests/test_piste_b.py            # les 7 tests du score
python piste_a.py                       # vérifications des mesures sur les vraies données
```

## Sources de données et conditions

Jeu de départ des organisateurs (`data/alphaforge_starter/`, détail dans son `README.md` et
`sources_metadata.csv`) : cours quotidiens ajustés de 31 actifs du 12 novembre 2021 au
12 novembre 2026 via Yahoo Finance (bibliothèque `yfinance`, extraction du 13 novembre 2026),
taux de change USD/CAD de la Banque du Canada (API Valet), séries macroéconomiques de la Banque
du Canada et de FRED (non utilisées par l'application). Conditions : Yahoo Finance
(https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html), Banque du Canada
(https://www.bankofcanada.ca/terms/), FRED (https://fred.stlouisfed.org/legal/).

Traitements : cours ajustés des dividendes et fractionnements, conversion en dollars canadiens
au taux du jour (dernier taux reporté les jours sans cotation), intersection des dates où tous
les titres du portefeuille cotent, rendements simples quotidiens, covariance annualisée sur
252 jours. Aucune cote ESG, nouvelle ni donnée fondamentale : les exclusions sont approximées
par secteur et affichées comme telles. Biais du survivant documenté dans chaque réponse.

## Architecture

```
App Streamlit  <->  Agent sur Bedrock  <->  Outils sur Lambda (pistes A et B)  <-  S3 (données)
                           |                            |
                      CloudWatch (trace de l'agent)   CloudWatch (un JSON par outil)
```
