# Contexte du projet : datathon AlphaForge AI

Ce fichier résume tout ce qui a été décidé avant d'ouvrir ce dossier dans Claude Code.
Il est partagé par toute l'équipe et couvre les quatre pistes (A, B, C, D).
**Au début de chaque session, la personne dit quelle piste est la sienne** ; ne travaille
que sur cette piste et ne modifie pas les fichiers des autres sans le signaler.
Réponds en français. L'équipe débute avec AWS, les agents et Streamlit : explique le
pourquoi de chaque étape, pas seulement la commande.

## Le datathon

- Datathon 2026 de PolyFinances, avec la Banque Nationale et AWS. Défi « AlphaForge AI ». Durée : 36 heures.
- Consigne : concevoir une **solution agentique auto-explicative** qui exploite des données
  financières publiques pour éclairer une décision d'investissement selon différents profils.
- Trois personas servent de tests :
  - **Amira**, 26 ans, risque élevé, horizon 15 ans et plus, croissance, intéressée par l'IA et la crypto.
    Test : « risque élevé » ne veut pas dire « tout est acceptable ».
  - **Mateo**, 41 ans, risque modéré, horizon 8 à 12 ans, préférences ESG.
    Test : intégrer autre chose que le rendement et le risque.
  - **Robert**, 59 ans, risque faible à modéré, horizon 3 à 5 ans, préservation du capital,
    tenté par un titre très médiatisé.
    Test : remettre en question une demande incohérente avec le profil, sans acquiescer.
- Grille : solution 20 %, agentique et explicabilité 20 %, données 20 %, UX 10 %, AWS 15 %, pitch 15 %.
- **AWS est une condition d'admissibilité** : AWS doit contribuer réellement et de façon démontrable.
  Ne pas multiplier les services pour impressionner ; chaque service doit avoir un rôle.

## L'énoncé officiel

Le PDF et les diapositives des organisateurs sont dans `docs/enonce/`, avec un résumé fidèle
(`resume_enonce.md`). Trois exigences qui vont au-delà de ce fichier :

- **Rendre les contrôles visibles** (piste « agent de gouvernance ») : `demander` renvoie une clé
  `controles` et une ligne `gouvernance` dans `outils_appeles`.
- **Deux situations contrastées** dans la démo et la vidéo : un portefeuille, trois verdicts.
- **README et documentation technique** avec dépendances, sources de données et leurs conditions,
  configuration, reproduction, mécanisme d'explicabilité avec un exemple relié aux traces,
  validations, limites et améliorations.

## Règles à ne jamais enfreindre

1. **Simulation seulement.** Aucune transaction réelle, aucune donnée bancaire réelle.
2. **Aucun conseil financier personnalisé.** L'outil ne dit jamais « achète », « vends »,
   « tu devrais », « nous recommandons », « le meilleur choix ». Il décrit des faits
   (« NVDA porte 40 % du risque ») et montre des **scénarios fictifs** (« si X passait de
   20 % à 10 %, le score passerait de 64 à 78 ») avec ce qui s'améliore et ce qui se dégrade.
3. **Le modèle de langage ne calcule jamais.** Tous les chiffres viennent des fonctions Python.
   L'agent choisit quelles fonctions appeler et explique leurs résultats.
4. **Pas de prévision de rendement.** Les mesures utilisent la covariance, jamais un rendement espéré.
5. **Chaque chiffre affiché porte sa cible, son hypothèse et sa limite.** L'outil dit ce qu'il ne sait pas.
6. **Aucune clé AWS dans le code, dans Git ou dans une conversation.**

## L'idée du projet : « Diversifié pour qui ? »

Les outils existants (ex. Wealthscope, offert par Banque Nationale Courtage direct) donnent la
même note de diversification à tout le monde. Le nôtre mesure le portefeuille une fois, puis
compare chaque mesure à une **cible qui dépend du profil**. Démo visée : un même portefeuille,
trois verdicts différents pour Amira, Mateo et Robert.

## Architecture

```
App Streamlit  <->  Agent sur Bedrock  <->  Outils Python (Lambda)  <-  S3 (données)
   (piste D)          (piste C, moi)        (pistes A et B)
                           |
                      CloudWatch (traces)
```

Quatre pistes en parallèle :

| Piste | Livre | État |
|---|---|---|
| A · Calculs | `analyser(portefeuille)` -> mesures | **Écrit** : `piste_a.py` (moteur du collègue + `analyser` du contrat, données lues sur S3). Repris par Aziz. |
| B · Profil et score | `evaluer`, `simuler`, `proposer_scenarios` | **Écrit et testé** : `piste_b.py` (version du collègue du 15 novembre, 7 tests dans `tests/test_piste_b.py`). Cibles à calibrer avec les vrais chiffres. |
| C · Agent et AWS | `demander(texte, portefeuille, profil)` | **Écrit et testé** : `piste_c.py` (Bedrock, gouvernance, trace CloudWatch) |
| D · Interface | `app.py` (Streamlit) | **Reprise par Aziz le 15 novembre** : deux écrans (questionnaire plein écran, puis une longue page de résultats avec la discussion en bas), thème clair dans `.streamlit/config.toml`, portefeuille éditable avec la liste des 31 titres. Livrables (vidéo, one-pager, documentation) à faire. |

## Les données : le dossier `alphaforge_starter`

On utilise le jeu de départ fourni par les organisateurs, copié dans `data/alphaforge_starter/`
et déposé sur S3 sous `s3://alphaforge-<compte>-donnees/alphaforge_starter/` (voir `donnees.py`).
Ce sont déjà des données Yahoo Finance (téléchargées avec `yfinance` le 13 novembre 2026), plus
la Banque du Canada et FRED. **Ne pas rappeler Yahoo en direct** : les valeurs de `adj_close`
changent à chaque téléchargement, donc les résultats ne seraient plus reproductibles. Pour ajouter
un actif, modifier `UNIVERSE` dans `build_dataset.py` et régénérer, puis documenter la source.

- `prices_daily.csv` : `date, ticker, open, high, low, close, adj_close, volume, currency`.
  40 049 lignes, 31 actifs, du 2021-11-12 au 2026-11-12.
- `assets_universe.csv` : `asset_id, ticker, name, asset_class, market, currency, sector`.
- `fx_usdcad_daily.csv` : `date, usdcad, cadusd`.
- `macro_rates.csv`, `corporate_actions.csv`, `sources_metadata.csv`, `build_dataset.py`, `README.md`.

Les 31 actifs : RY.TO, TD.TO, MFC.TO, ENB.TO, CNQ.TO, CNR.TO, FTS.TO, ATD.TO, SHOP.TO, CSU.TO,
AAPL, MSFT, NVDA, GOOGL, AMZN, TSLA, JPM, JNJ, PG, XOM, XIU.TO, SPY, QQQ, ESGV, XBB.TO, ZST.TO,
AGG, TLT, GLD, BTC-USD, ETH-USD. Tout autre symbole est « non couvert » et doit être signalé.

Pièges signalés par le README du jeu de données (à respecter dans la piste A, à citer dans les limites) :

- Utiliser `adj_close` pour les rendements. Ne pas réappliquer les fractionnements.
- Les titres `.TO` sont en CAD, le reste en USD. Convertir avec `fx_usdcad_daily.csv`, en
  reportant le dernier taux les jours sans cotation.
- Aucun alignement de calendrier : la crypto cote 7 jours sur 7 (1 827 lignes contre 1 255 pour
  les actions) et les jours fériés diffèrent entre Toronto et New York. Aligner les dates et dire comment.
- Biais du survivant : l'univers a été choisi en 2026 parmi des titres devenus gros.
- Aucune cote ESG, aucune nouvelle, aucune donnée fondamentale, aucune composition de FNB.

Correspondance entre `assets_universe.csv` et les noms du contrat (à appliquer dans la piste A) :

| `asset_class` | `classe` du contrat |
|---|---|
| `equity`, `etf_equity` | `actions` |
| `etf_bond` | `obligations` |
| `etf_commodity` | `or` |
| `crypto` | `crypto` |

| `sector` | `secteur` du contrat |
|---|---|
| Information Technology | `technologie` |
| Energy | `energie` |
| Financials | `finance` |
| Health Care | `sante` |
| Industrials | `industrie` |
| Utilities | `services_publics` |
| Communication Services | `communication` |
| Consumer Staples | `consommation_de_base` |
| Consumer Discretionary | `consommation_discretionnaire` |
| Broad market (sauf QQQ), Bonds | `diversifie` |
| Broad market (U.S. growth/tech-heavy), soit QQQ | `technologie` (hypothèse de l'équipe) |
| Gold | `or` |
| Crypto asset | `crypto` |

FNB traités comme « larges » dans `piste_b.py` : XIU.TO, SPY, ESGV, XBB.TO, ZST.TO, AGG.
QQQ, TLT et GLD n'y sont pas.

Les fichiers sont sur S3 et les fonctions de calcul les lisent de là, par `donnees.py` :

```python
from donnees import charger, provenance
prix = charger("prices_daily.csv")  # S3 d'abord, cache local, copie du dépôt en secours
```

`provenance()` renvoie une phrase par fichier lu. Si les données changent : `python donnees.py televerser`.

## Le contrat (formats à ne pas changer sans prévenir les autres)

Conventions : pourcentages en décimales (0.164 = 16,4 %), pertes en nombre positif,
clés en minuscules sans accent, JSON simple (pas d'objets pandas ou numpy).

- `portefeuille` : dictionnaire symbole -> montant en dollars canadiens, ex. `{"NVDA": 10000, "XIC.TO": 17500}`.
- `profil` :
  ```json
  {"risque": 2, "horizon_annees": 10, "objectif": "equilibre", "perte_max_toleree": 0.20,
   "crypto": "non", "exclure_secteurs": ["energie"], "secteurs_interet": ["technologie"],
   "montant_vise": null, "cotisation_mensuelle": null, "experience": "intermediaire"}
  ```
  `risque` : 1 faible, 2 modéré, 3 élevé, demi-niveaux permis. `objectif` : preservation, equilibre, croissance.
- `analyser(portefeuille)` -> `mesures` : `volatilite`, `perte_max`, `poids`, `contributions`,
  `poids_par_classe`, `poids_par_secteur`, `classe_par_titre`, `secteur_par_titre`, `capital`,
  plus `hypotheses` (liste de phrases : période, alignement des dates, devises, biais du survivant),
  que `piste_c` reprend automatiquement dans `limites`, et depuis le 15 novembre le gain de
  diversification de Markowitz : `volatilite_par_titre`, `volatilite_sans_diversification` (moyenne
  pondérée des volatilités), `gain_diversification` (écart, en décimal) et `ratio_diversification`.
  Aucun rendement espéré n'intervient. Ces clés restent dans le contrat, mais l'onglet « Gain de diversification » a été remplacé par « En cas de crise (2022) », qui appelle `piste_a.trajectoire_crise_2022(portefeuille)` (hors contrat d'`analyser`, pour ne pas alourdir ce que reçoit l'agent) : valeur en dollars jour après jour pendant 2022, sommet, creux, et part du risque effacée par la diversification sur cinq ans puis en 2022.
  Aussi depuis le 15 novembre, la résistance à la crise de 2022 (portefeuille rejoué sur l'année 2022) :
  `perte_crise_2022` (pire baisse pendant 2022), `variation_2022`, `perte_crise_2022_par_titre`. `evaluer`
  en fait une quatrième note, `resistance_crise` (cible `crise_max` : 12 %, 20 %, 35 % selon le niveau,
  poids dans `POIDS_AVEC_CRISE`) ; sans ces clés (fausse piste A), il garde les trois notes et les anciens poids. Un symbole hors des 31 actifs fait lever
  `ValueError` avec la liste des symboles non couverts ; `piste_a.symboles_non_couverts(portefeuille)`
  permet de les afficher avant d'appeler `analyser`.
- `evaluer(mesures, profil)` -> `score` (0 à 100), `verdict`, `niveau_effectif`, `notes` (trois notes
  avec valeur, cible, note, poids, explication), `alertes` (code, gravite, message), `hypotheses`.
  Depuis le 15 novembre : une alerte de gravité `contrainte` (secteur exclu, crypto refusée) plafonne le
  verdict à `a_surveiller` même si le score dépasse 80 ; `raison_verdict` le dit (sinon `None`).
- `simuler(portefeuille, changement, profil, analyser)` -> `avant`, `apres`, `ameliore`, `degrade`,
  `phrase`, `hypotheses`, et depuis le 15 novembre `poids_avant` et `poids_apres` (symbole -> poids).
  Types de changement : `plafonner`, `ajouter`, `retirer` (`plafonner` et `retirer` acceptent `vers`, le titre
  qui reçoit le montant libéré), `combiner` (`etapes`) et `reallouer` (`poids_cibles`, total inchangé).
- `proposer_scenarios(portefeuille, profil, analyser)` -> liste d'au plus trois résultats de `simuler`.
  Depuis le 15 novembre : recherche gloutonne de 1 à 6 changements (contraintes d'abord, puis score,
  puis écart aux cibles), montant libéré envoyé vers un FNB large ou l'or, présentés comme une réallocation
  finale. Nombre de scénarios fixé par `nombre_de_scenarios(evaluation)` : 3 si inadéquat (score < 60), 2 si
  à surveiller (60 à 79), 0 si adéquat (80 et plus), 1 si adéquat mais avec une contrainte violée. Des
  recherches de rechange comblent les doublons (deux scénarios menant au même portefeuille comptent pour un).
- **`demander(texte, portefeuille, profil)`**, livré par la piste C :
  ```json
  {"reponse": "texte affiché dans le chat",
   "outils_appeles": [{"outil": "simuler", "resume": "ajout de 15 000 $ de NVDA"}],
   "limites": ["Perte maximale mesurée sur 2021 à 2026 seulement."]}
  ```
  L'interface affiche `outils_appeles` dans un volet « Ce que l'agent a fait » : c'est la
  preuve visible de l'explicabilité.

Lire `piste_a.py` et `piste_b.py` pour les formats exacts.

## Piste A · Calculs : ce qu'il faut faire

Un fichier `piste_a.py` qui expose `analyser(portefeuille)` et lit les données par `donnees.py`
(S3, copie locale en secours). État : **écrit**. Le moteur de calcul du collègue (classe
`PisteACalculations`) est conservé ; `analyser` l'enveloppe pour respecter le contrat. Les
vérifications ci-dessous et les trois portefeuilles de référence se lancent avec `python piste_a.py`.
`tests/faux.py` garde une fausse piste A, aux chiffres inventés, pour tester l'interface sans données.

1. Charger `prices_daily.csv` et garder `adj_close` par date et par symbole.
2. Convertir les actifs en USD vers le CAD avec `fx_usdcad_daily.csv` (dernier taux reporté les
   jours sans cotation). On mesure le risque d'un investisseur canadien.
3. Aligner les calendriers : garder les dates où tous les titres du portefeuille ont un prix.
   Ne pas remplir les trous, ce qui créerait de faux rendements nuls.
4. Rendements simples quotidiens : `r_t = P_t / P_(t-1) - 1`.
5. Covariance annualisée (multiplier par 252), puis volatilité du portefeuille : racine de `w' Σ w`.
6. Contribution au risque de chaque titre : `w_i × (Σ w)_i / (w' Σ w)`. La somme vaut 1.
7. Perte maximale : pire baisse du sommet au creux de la valeur du portefeuille, à pondérations
   constantes (hypothèse à afficher).
8. Poids par titre, par classe et par secteur, avec la table de correspondance ci-dessus.
9. Symboles hors des 31 actifs : les signaler, ne jamais les ignorer en silence.
10. Renvoyer des nombres Python simples (`float`), pas d'objets numpy ou pandas.

Vérifications : la somme des contributions vaut 1 ; un portefeuille d'un seul titre a une
volatilité égale à celle du titre ; la sortie a exactement les clés de `faux.analyser`.
Ensuite : calculer trois portefeuilles de référence (20/80, 60/40, 100 % actions) pour calibrer
les cibles de la piste B. Après le MVP : ratio de diversification, corrélations en 2022.

## Piste B · Profil et score : ce qu'il reste à faire

Le fichier `piste_b.py` est **écrit et testé** : cibles par profil, trois notes, score, huit
alertes, `simuler`, `proposer_scenarios`. Le détail des formules est dans le guide de la piste B.

- Test de référence : avec les fausses mesures du guide, les scores sont 82 (Amira), 45 (Mateo), 21 (Robert).
  Depuis le 15 novembre, chaque note est graduée : 100 avec une marge de confort, 70 pile à la limite du profil,
  0 au double de la limite (`NOTE_LIMITE`, `MARGE_CONFORT`). Avant, elle valait 100 partout sous la limite, ce qui
  donnait des notes en tout ou rien et des scores optimistes (les anciens tests donnaient 97, 64 et 30).
  Lancer `python tests/test_piste_b.py` depuis la racine. Après toute modification de `piste_b.py`,
  relancer aussi `python aws/deployer_lambda.py` : la fonction Lambda embarque ce fichier.
- Reste à faire : calibrer les cibles (`CIBLES`) dès que la piste A fournit les trois portefeuilles
  de référence, puis rejouer les tests.
- Ne pas changer les clés de sortie sans prévenir les pistes C et D.
- Les messages et les phrases de scénario sortent de gabarits fixes : aucun mot de conseil.

## Piste D · Interface et livrables : ce qu'il reste à faire

Le fichier `app.py` est **écrit** : barre latérale (persona, formulaire, CSV), onglets Diagnostic,
Scénarios et Discussion. Sa logique a été testée avec un substitut de Streamlit, pas dans Streamlit.

- Premier lancement réel : `pip install streamlit pandas numpy boto3`, puis `python -m streamlit run app.py`.
  Le graphique « Poids et part du risque » est en Altair (natif Streamlit), plus matplotlib.
- Brancher les vraies pistes en changeant une ligne d'import en haut de `app.py`, une piste à la fois.
- Afficher les symboles non couverts renvoyés par la piste A.
- Livrables : vidéo d'environ 5 minutes (deux personas contrastés), one-pager d'une page,
  documentation technique, README. Le plan de chacun est dans le guide de la piste D.

## Piste C · Agent et AWS : ce qu'il faut faire

Un fichier `piste_c.py` qui expose `demander`. À l'intérieur :

1. **La boucle d'agent.** Envoyer au modèle la demande, le profil et la liste des outils.
   Tant que le modèle demande un outil : exécuter la fonction Python correspondante, lui renvoyer
   le résultat, recommencer. Quand il répond en texte, c'est fini. Limiter à un nombre fixe de tours.
   Piste la plus simple : l'API Converse de Bedrock avec les appels d'outils, depuis boto3.
   Exemple officiel à lire avant d'écrire le code :
   https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-examples.html
2. **Quatre outils** déclarés au modèle : `analyser`, `evaluer`, `simuler`, `proposer_scenarios`.
   Le portefeuille et le profil sont injectés par le code, pas retapés par le modèle, pour
   qu'il ne puisse pas se tromper sur un montant.
3. **Trois types de demandes** à reconnaître : diagnostic (« suis-je trop concentrée ? »),
   scénario (« je veux ajouter 15 000 $ de X »), question d'explication (« d'où vient ce chiffre ? »).
   Pour un scénario, l'agent reformule ce qu'il a compris avant de conclure. Ajout du 15 novembre : l'objectif
   chiffré (« je veux 75 000 $ dans 10 ans ») passe par `evaluer` avec `montant_vise` et `cotisation_mensuelle` ;
   le résultat contient `objectif` (rendement annuel requis, calculé par `piste_b.rendement_requis`, et seuil du profil).
4. **Le test de Robert.** Sur une demande d'ajout d'un titre risqué, l'agent appelle `simuler`,
   constate le dépassement, signale l'incohérence avec le profil et montre les chiffres.
   Il ne refuse pas et il n'approuve pas : il met la demande en contexte.
5. **La gouvernance**, en code et pas seulement dans la consigne :
   - refuser de renvoyer une réponse qui contient un mot interdit (achète, vends, tu devrais,
     recommande, conseille) et la faire régénérer ;
   - vérifier que les nombres cités dans la réponse figurent dans les résultats des outils ;
   - si un outil échoue ou qu'une donnée manque, le dire dans `limites` au lieu d'inventer.
6. **La trace.** Chaque appel d'outil est ajouté à `outils_appeles` et journalisé.
7. **L'adaptation au niveau d'expérience** (`profil["experience"]`) : même contenu, vocabulaire différent.

## Piste C : ordre de travail proposé

1. **Preuves AWS minimales, avant tout code réel** : un appel à un modèle Bedrock depuis Python,
   un fichier déposé puis relu sur S3, une fonction Lambda « bonjour ». Vérifier la région, les
   modèles activés sur le compte du datathon, et que le modèle choisi gère les appels d'outils.
2. La boucle d'agent en local, avec `faux.analyser` et le vrai `piste_b`.
3. Les quatre outils, puis les trois types de demandes, puis le test de Robert.
4. La gouvernance et la trace.
5. Brancher `demander` dans `app.py` (une ligne d'import à changer) et tester dans l'interface.
6. Les données sur S3, puis les fonctions de calcul sur Lambda, puis les journaux dans CloudWatch.
   Attention : pandas et numpy sont lourds à empaqueter pour Lambda.
7. Fournir à la piste D un paragraphe sur l'architecture et une capture de trace pour la documentation.

## État AWS (vérifié les 14 et 15 novembre 2026)

- Compte d'événement AWS Workshop Studio (rôle `WSParticipantRole`), région `us-east-1`. Les identifiants
  sont **temporaires** : une erreur « Identifiants refusés » ou `ExpiredToken` veut dire qu'il faut les
  recopier depuis la page de l'événement dans `~/.aws/credentials`, pas que le code est cassé.
- Modèle : `us.anthropic.claude-opus-5-5` (profil d'inférence, environ 10 s par réponse). Changer avec la
  variable `MODELE_BEDROCK`, par exemple `us.anthropic.claude-sonnet-5-5` pour aller plus vite.
- Ressources : seau S3 `alphaforge-<compte>-donnees` (données sous `alphaforge_starter/`), Lambda
  `alphaforge-outils` (les quatre outils de l'agent) et `alphaforge-bonjour` (preuve), rôle IAM
  `alphaforge-lambda-role` avec lecture du seau, groupes CloudWatch `/alphaforge/agent` (trace de
  l'agent) et `/aws/lambda/alphaforge-outils` (un JSON par appel d'outil).
- Rôle de chaque service dans l'application : **Bedrock** fait tourner l'agent ; **Lambda** exécute
  ses quatre outils avec le code des pistes A et B (pandas et numpy viennent de la couche AWS
  « AWSSDKPandas », déploiement par `python aws/deployer_lambda.py`, à relancer après toute modification
  de `piste_a.py`, `piste_b.py`, `donnees.py` ou `aws/lambda_outils.py`) ; **S3** fournit les données ;
  **CloudWatch** garde les traces. Si Lambda est injoignable, l'agent calcule en local et le dit dans
  `limites` ; `OUTILS_LAMBDA=0` force le calcul local. Les onglets Diagnostic et Scénarios de
  l'interface calculent en local avec le même code, pour réagir sans attente aux réglages du profil.

## Ce qui n'est pas encore vérifié

- Les seuils de `piste_b.py` sont des hypothèses de l'équipe, à calibrer avec les trois portefeuilles
  de référence de `python piste_a.py`.
- Les livrables de la piste D (vidéo, one-pager, documentation, README) ne sont pas commencés.
- Ce fichier est régénéré de temps en temps hors du dépôt : **repartir toujours de la version dans Git**,
  sinon les mises à jour d'état des autres pistes sont perdues.

## Organisation du dépôt

À la racine, seulement le code de l'application (tous les scripts se lancent depuis la racine) :

- `app.py` : interface Streamlit. Lancer avec `python -m streamlit run app.py`. Passe l'historique du chat à `demander`.
- `piste_a.py` : mesures du portefeuille à partir des vraies données (moteur du collègue + `analyser`). `python piste_a.py` : vérifications.
- `piste_b.py` : profil, score, alertes, scénarios. Testé : redonne 82, 45 et 21 sur l'exemple du guide.
- `piste_c.py` : l'agent (boucle Converse, quatre outils sur Lambda, gouvernance, trace). Démo : `python piste_c.py`.
- `donnees.py` : lecture des données depuis S3 avec cache local, et téléversement.
- `README.md` : présentation courte et commandes de lancement.

Dossiers :

- `aws/` : `deployer_lambda.py` et `lambda_outils.py` (la fonction `alphaforge-outils`), `preuves/` (les trois preuves Bedrock, S3, Lambda, relançables).
- `data/alphaforge_starter/` : le jeu de départ. `Claude outputs/` à l'intérieur est ignoré par Git.
- `data/portefeuilles/` : portefeuilles d'exemple pour l'interface, CSV à deux colonnes `symbole,montant_cad`
  (démo, équilibré 60/40, techno concentré, canadien avec énergie, un cas de symbole non couvert, et les
  portefeuilles d'Amira, Mateo et Robert imaginés par la piste B).
- `docs/` : `documentation_piste_c.md` (architecture et traces pour la piste D), `guide_piste_a/` (maquette HTML du guide de la piste A).
- `tests/` : `test_piste_b.py` (les 7 tests du guide de la piste B) et `faux.py`, fausse piste A aux chiffres
  inventés pour tester l'interface sans données.
- `archives/prototype_partie_b/` : application parallèle du collègue de la piste B (autre contrat, non branchée),
  gardée pour ses idées. Voir son `LISEZMOI.md`.

## Documents de référence

- Plan et architecture (Whiteboard) : https://claude.ai/artifact/VYiUCZiFM9Hn95dS6THPsD
- Guide de la piste B : https://claude.ai/artifact/1yHxkS5hXGs4oAB5LuZZvA
- Guide de la piste D : https://claude.ai/artifact/E91axwsXhTVJ3eQtbct9yM
