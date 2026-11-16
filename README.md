# Diversifié pour qui ?

Datathon PolyFinances 2026, défi AlphaForge AI. Les outils de diversification donnent souvent la
même note à tout le monde. Celui-ci mesure un portefeuille une fois, puis compare chaque mesure à
une cible qui dépend du profil de la personne : un même portefeuille obtient un verdict différent
pour Amira, Mateo et Robert. Un agent sur Amazon Bedrock explique les résultats sans jamais calculer
lui-même et sans jamais donner de conseil. Simulation à but éducatif : aucune transaction réelle,
aucune donnée bancaire réelle, aucun conseil financier personnalisé.

**Application en ligne : https://dw5l2fp67oxxw.cloudfront.net** (Amazon CloudFront en HTTPS devant
Amazon EC2, dans le compte AWS de l'événement, active jusqu'à la fermeture de ce compte).

## Ce que fait l'application

1. **Questionnaire.** Point de départ (Amira, Mateo, Robert ou réponses personnalisées), tolérance
   au risque, horizon, objectif, expérience, crypto acceptée ou non, perte maximale tolérée
   (facultatif), secteurs à exclure et secteurs d'intérêt. Portefeuille en dollars canadiens :
   portefeuille type, démonstration, saisie libre ou CSV (`symbole,montant_cad`). Un symbole hors des
   31 actifs couverts est signalé, jamais ignoré.
2. **Verdict.** Score d'adéquation sur 100, verdict, et quatre notes expliquées : niveau de risque,
   risque de perte, diversification, résistance à la crise de 2022 (méthode plus bas).
3. **Ce que vous détenez** et **d'où vient le risque** : poids de chaque titre dans le capital et
   dans le risque (graphique et tableau), et l'onglet **En cas de crise (2022)** : le portefeuille
   rejoué en dollars jour après jour pendant 2022, avec la limite de perte du profil.
4. **Alertes** : contraintes violées (crypto refusée, secteur exclu) et avertissements (titre ou
   secteur trop lourd, profil contradictoire).
5. **Scénarios fictifs** : 3 si le verdict est inadéquat, 2 s'il est à surveiller, aucun s'il est
   adéquat (1 si une contrainte reste violée). Chacun montre les poids avant et après, ce qui
   s'améliore, ce qui se dégrade (montant déplacé, titres retirés, concentration), ses hypothèses,
   et le même scénario rejoué pendant la crise de 2022.
6. **Discussion avec l'agent** : diagnostic, scénario (« je veux ajouter 15 000 $ de NVDA »),
   question d'explication (« d'où vient ce chiffre ? »). Sous chaque réponse, « Ce que l'agent a
   fait » : les outils appelés et la ligne de gouvernance.

## Lancer

Python 3.10 ou plus (Streamlit 1.67 ou plus).

```bash
pip install -r requirements.txt          # sur Mac : python3 -m pip install -r requirements.txt
python -m streamlit run app.py           # l'interface (python3 sur Mac)
python piste_a.py                        # vérifications des calculs et portefeuilles de référence
python tests/test_piste_b.py             # les 10 tests du score et des scénarios
python piste_c.py                        # démonstration de l'agent sur le persona Robert
```

Les identifiants AWS vont dans `~/.aws/credentials`, jamais dans le code ni dans Git. Sans AWS,
l'interface fonctionne avec la copie locale des données et les calculs locaux ; seul l'agent a
besoin de Bedrock, et il le dit dans ses limites quand Bedrock est injoignable.

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

```bash
python aws/preuves/preuve1_bedrock.py   # vérifie l'accès à Bedrock et les modèles disponibles
python donnees.py televerser            # crée le seau S3 s'il manque et dépose les données
python aws/deployer_lambda.py           # crée ou met à jour la fonction Lambda des outils
python aws/deployer_app.py              # met l'application en ligne (EC2 + CloudFront en HTTPS) et affiche son adresse
python aws/deployer_app.py --fermer-port     # une fois le HTTPS vérifié : la machine n'accepte plus que CloudFront
python aws/deployer_app.py --mettre-a-jour   # la machine récupère la dernière version de main
```

`aws/deployer_lambda.py` est à relancer après toute modification de `piste_a.py`, `piste_b.py`,
`donnees.py` ou `aws/lambda_outils.py` : la fonction embarque ce code. La machine EC2, elle, clone
le dépôt public : après un `git push`, `--mettre-a-jour` suffit.

## Architecture et rôle de chaque service AWS

```
App Streamlit  <->  Agent sur Bedrock  <->  Outils sur Lambda (pistes A et B)  <-  S3 (données)
                           |                            |
                      CloudWatch (trace de l'agent)   CloudWatch (un JSON par outil)
```

| Service | Rôle dans l'application |
|---|---|
| **Amazon Bedrock** | Fait tourner l'agent (API Converse avec appels d'outils, Claude Opus 5.5). |
| **AWS Lambda** | `alphaforge-outils` exécute les quatre outils de l'agent (`analyser`, `evaluer`, `simuler`, `proposer_scenarios`) avec le code des pistes A et B. |
| **Amazon S3** | Garde le jeu de données ; `donnees.py` le lit (cache local, copie du dépôt en secours). |
| **Amazon CloudFront** | Sert le site en HTTPS (certificat fourni par AWS), sans cache, et relaie la WebSocket de Streamlit. L'adresse reste la même si la machine redémarre. |
| **Amazon EC2** | `alphaforge-app` fait tourner l'interface Streamlit (port 80, ouvert seulement aux serveurs de CloudFront). Ses droits AWS viennent d'un rôle IAM (`alphaforge-app-role` : Bedrock, invoquer la Lambda, lire le seau, écrire les traces) : aucune clé sur la machine. |
| **Amazon CloudWatch Logs** | Garde la trace de chaque demande, appel d'outil, contrôle et réponse (`/alphaforge/agent`), et un JSON par appel d'outil (`/aws/lambda/alphaforge-outils`). |

Si Lambda est injoignable, l'agent exécute le même code en local et le signale dans ses limites.
Le diagnostic et les scénarios de la page calculent en local avec le même code, pour réagir sans
attente aux réglages du profil.

## Sources de données et conditions

Jeu de départ des organisateurs (`data/alphaforge_starter/`, détail dans son `README.md` et
`sources_metadata.csv`) : cours quotidiens ajustés de 31 actifs du 12 novembre 2021 au
12 novembre 2026 via Yahoo Finance (bibliothèque `yfinance`, extraction du 13 novembre 2026),
taux de change USD/CAD de la Banque du Canada (API Valet), séries macroéconomiques de la Banque
du Canada et de FRED (non utilisées par l'application). Conditions : Yahoo Finance
(https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html), Banque du Canada
(https://www.bankofcanada.ca/terms/), FRED (https://fred.stlouisfed.org/legal/).

Le jeu est figé et déposé sur S3 : on ne rappelle pas Yahoo en direct, car les cours ajustés
changent à chaque téléchargement et les résultats ne seraient plus reproductibles.

Traitements : cours ajustés (`adj_close`, dividendes et fractionnements déjà appliqués) ;
conversion en dollars canadiens au taux du jour, dernier taux reporté les jours sans cotation ;
intersection des dates où tous les titres du portefeuille cotent, sans remplir les trous (la
crypto cote 7 jours sur 7, Toronto et New York n'ont pas les mêmes jours fériés) ; rendements
simples quotidiens ; covariance annualisée sur 252 jours. Aucune cote ESG, nouvelle, donnée
fondamentale ni composition de FNB : les exclusions sont approximées par secteur et affichées
comme telles.

## Méthode : comment le score est calculé

Aucun rendement espéré n'intervient : seulement la covariance des titres et leur historique.

1. **Niveau de risque retenu** = le plus prudent entre la tolérance déclarée (1, 1,5, 2, 2,5 ou 3)
   et ce que permet l'horizon (3 ans ou moins : 1 ; 4 à 7 ans : 2 ; 8 ans et plus : 3).
2. **Cibles de ce niveau** (interpolées pour les demi-niveaux) :

   | Cible | Niveau 1 | Niveau 2 | Niveau 3 |
   |---|---|---|---|
   | Plage de volatilité annuelle | 4 à 8 % | 8 à 13 % | 13 à 20 % |
   | Perte maximale tolérée | 10 % | 20 % | 35 % |
   | Minimum de paris effectifs | 6 | 5 | 4 |
   | Pire baisse tolérée pendant la crise de 2022 | 12 % | 20 % | 35 % |

   Si la personne déclare une perte maximale plus stricte, elle remplace les deux limites de perte.
3. **Quatre notes sur 100** :
   - *Niveau de risque* : volatilité du portefeuille, racine de w'Σw. 100 jusqu'au milieu de la
     plage, 70 au bord haut, 0 au double du bord haut ; sous la plage, la note baisse aussi, sauf
     pour l'objectif « préservation ».
   - *Risque de perte* : pire baisse historique du sommet au creux, à pondérations constantes.
     100 jusqu'à 75 % de la limite, 70 à la limite, 0 au double.
   - *Diversification* : paris effectifs = 1 / Σ (contribution au risque)², sans les FNB larges.
     On regarde comment le **risque** se répartit, pas les dollars. 100 dès 1,5 fois le minimum,
     70 au minimum, 0 pour un seul pari.
   - *Résistance à la crise de 2022* : pire baisse du portefeuille actuel rejoué pendant 2022.
     Même barème que le risque de perte.
4. **Score** = moyenne pondérée des quatre notes, selon l'objectif :

   | Objectif | Risque | Perte | Diversification | Crise 2022 |
   |---|---|---|---|---|
   | Préservation | 0,20 | 0,30 | 0,25 | 0,25 |
   | Équilibre | 0,30 | 0,20 | 0,30 | 0,20 |
   | Croissance | 0,30 | 0,15 | 0,40 | 0,15 |

5. **Verdict** : 80 et plus adéquat, 60 à 79 à surveiller, moins de 60 inadéquat. Une contrainte
   violée (crypto refusée, secteur exclu) n'entre pas dans le score, mais plafonne le verdict à
   « à surveiller ».

Toutes les cibles et tous les poids sont des choix de l'équipe, affichés comme tels dans les
hypothèses de l'interface.

**Scénarios.** Recherche gloutonne d'au plus six changements : à chaque étape, le changement qui
retire le plus de contraintes, puis qui monte le plus le score, puis qui rapproche le plus des
cibles. Le montant libéré va vers un FNB large d'obligations ou d'actions, ou vers l'or. Si le
profil exclut un secteur, seulement vers les obligations, l'or ou ESGV (énergie exclue
seulement), jamais vers XIU.TO, SPY ni QQQ, qui contiennent des entreprises de ces secteurs.

## Mécanisme d'explicabilité

Trois garanties, écrites dans le code et non seulement dans la consigne du modèle :

- **Le modèle ne calcule jamais.** Il choisit quelles fonctions appeler ; chaque chiffre vient de
  `piste_a.py` ou `piste_b.py`. Le portefeuille et le profil sont injectés par l'application : le
  modèle ne retape pas les montants.
- **Contrôles de gouvernance avant affichage** (`piste_c.py`) : chaque nombre de la réponse doit
  figurer dans les résultats des outils ; aucun mot prescriptif (achète, vends, tu devrais,
  recommande, conseille). En cas d'écart, la réponse est régénérée au plus deux fois, puis
  remplacée par un résumé factuel sans modèle. Le résultat des contrôles est renvoyé (`controles`)
  et affiché dans « Ce que l'agent a fait ».
- **Chaque chiffre porte sa cible, son hypothèse et sa limite** : l'explication de chaque note
  cite la valeur et la cible ; les hypothèses (période, devises, alignement des dates, biais du
  survivant, choix de l'équipe) sont listées sous les résultats et reprises par l'agent.

### Exemple relié aux données et aux traces : Robert, portefeuille de démonstration

Portefeuille : NVDA 10 000 $, QQQ 12 500 $, BTC-USD 5 000 $, XIU.TO 17 500 $, XBB.TO 5 000 $.
Profil : tolérance 1,5, horizon 4 ans (capacité 2), objectif préservation, crypto refusée.

1. **Données** : cours ajustés du 2021-11-12 au 2026-11-12 lus sur S3, convertis en dollars
   canadiens ; 1 227 rendements quotidiens sur les dates communes aux cinq titres.
2. **`analyser`** (piste A) : volatilité 20,6 %, perte maximale historique 33,6 %, pire baisse
   pendant 2022 30,6 %, 3,57 paris effectifs ; NVDA pèse 20 % du capital mais 44,3 % du risque.
3. **`evaluer`** (piste B) : niveau retenu 1,5 ; notes 3 (volatilité au-dessus de la plage de
   6 % à 10,5 %), 0 (perte au-dessus de la limite de 15 %), 40 (sous le minimum de 5,5 paris),
   6 (crise au-dessus de la limite de 16 %). Score : 0,20 × 3 + 0,30 × 0 + 0,25 × 40 + 0,25 × 6
   = 12,1, soit **12 sur 100, inadéquat**. Alertes : crypto refusée (contrainte), NVDA porte trop
   de risque, secteur technologie trop lourd.
4. **Demande de Robert** : « Je veux ajouter 15 000 $ de NVDA, tout le monde en parle. »
   **`simuler`** : « si 15 000 $ de NVDA étaient ajoutés au portefeuille, le score passerait de 12
   à 4 » ; ce qui se dégrade : niveau de risque 3 → 0, diversification 40 → 14, résistance à la
   crise 6 → 0. L'agent ne refuse pas et n'approuve pas : il met la demande en contexte avec ces
   chiffres.
5. **Trace** (JSON, une ligne par événement, envoyée dans CloudWatch `/alphaforge/agent`). Extrait
   d'une exécution du 15 novembre 2026 sans identifiants Bedrock : l'agent bascule sur la réponse
   de secours, le dit, et les contrôles s'appliquent quand même :

   ```json
   {"evenement": "demande", "texte": "Je veux ajouter 15 000 $ de NVDA, tout le monde en parle.", "experience": "avance", "non_couverts": []}
   {"evenement": "bedrock_echec", "code": "NoCredentialsError", "erreur": "Unable to locate credentials"}
   {"evenement": "gouvernance", "nombres_cites": 18, "nombres_verifies": 18, "nombres_non_verifies": [], "mots_interdits": [], "regenerations": 0, "outils_echoues": 0}
   {"evenement": "reponse", "duree_s": 6.0, "outils": 2, "corrections": 0}
   ```

   Volet « Ce que l'agent a fait » : `evaluer : score de 12 sur 100 (réponse de secours)` et
   `gouvernance : 18 nombre(s) vérifié(s) contre les résultats des outils, aucun mot prescriptif`.
   Des traces avec Bedrock et Lambda (appels d'outils, durées, démarrage à froid) sont dans
   `docs/documentation_piste_c.md` ; elles datent des 14 et 15 novembre, avant les derniers
   réglages du score, d'où des scores légèrement différents.

## Validations

- **Calculs** (`python piste_a.py`) : la somme des contributions au risque vaut 1 ; un portefeuille
  d'un seul titre a la volatilité de ce titre ; la sortie a exactement les clés du contrat, en
  nombres Python simples ; la diversification n'ajoute jamais de risque ; un symbole non couvert
  est signalé.
- **Score et scénarios** (`python tests/test_piste_b.py`, 10 tests) : scores de référence sur les
  mesures du guide, bornes des notes, profil contradictoire, champ facultatif absent, scénarios
  qui retirent une crypto refusée, destinations compatibles avec les secteurs exclus, cible de
  crise qui suit la perte déclarée, coûts toujours affichés.
- **Portefeuilles de référence** (calibrage des cibles) :

  | Portefeuille | Volatilité | Perte maximale | Pire baisse en 2022 |
  |---|---|---|---|
  | 20/80 (prudent) | 6,5 % | 14,7 % | 14,7 % |
  | 60/40 (équilibré) | 9,2 % | 14,8 % | 14,5 % |
  | 100 % actions | 13,9 % | 16,2 % | 15,6 % |

- **Cohérence** : la baisse affichée dans l'onglet de crise est exactement celle de la note de
  crise ; le nombre de scénarios voulu (3, 2, 1 ou 0) est atteint sur les 21 combinaisons des
  portefeuilles d'exemple et des trois personas ; aucun mot interdit dans les textes affichés.
- **Agent** : contrôles de gouvernance à chaque réponse (voir la trace ci-dessus) ; réponse de
  secours testée sans Bedrock.

## Limites

- **Une seule crise** dans les données (2022) : ni 2008 ni mars 2020. La prochaine crise peut
  toucher d'autres actifs. Les scénarios sont trouvés avec ces mêmes données : il est normal
  qu'ils aient mieux traversé 2022 (l'interface le signale).
- **Univers de 31 actifs choisi en 2026** parmi des titres devenus gros : biais du survivant.
- **Aucune composition de FNB** : les FNB larges sont traités comme parfaitement diversifiés, et
  les exclusions ESG sont approximées par secteur (XIU.TO contient de l'énergie, QQQ contient NVDA).
- **Cibles et poids** : choix de l'équipe, calés sur les portefeuilles de référence, pas validés
  auprès de conseillers.
- **Perte maximale et crise de 2022 se recoupent** : sur 2021 à 2026, la pire baisse tombe presque
  toujours en 2022.
- **Pondérations constantes**, sans frais ni impôts ; montants en dollars canadiens seulement.
- **L'agent** dépend d'identifiants AWS temporaires ; sans eux, il donne une réponse de secours.

## Améliorations envisagées

- Contexte des taux en 2022 dans l'onglet de crise, avec les séries de la Banque du Canada déjà
  dans le jeu de données.
- Chocs simulés (actions −30 %, taux +2 points) en plus de la crise de 2022.
- Composition approximative des FNB d'indice (secteurs de XIU.TO, SPY et QQQ d'après leurs fiches
  officielles, avec source et date) pour mieux traiter les exclusions.
- Mode « à vous de jouer » : la personne déplace elle-même les poids et voit le score se recalculer.
- Amazon Bedrock Guardrails en complément des contrôles écrits en code ; application hébergée sur
  AWS plutôt qu'en local.

## Organisation du dépôt

| Emplacement | Contenu |
|---|---|
| `app.py` | Interface Streamlit (questionnaire, résultats, discussion) |
| `piste_a.py` | Mesures du portefeuille sur les vraies données, crise de 2022 |
| `piste_b.py` | Profil, cibles, notes, score, alertes, scénarios |
| `piste_c.py` | L'agent : boucle Converse, quatre outils sur Lambda, gouvernance, trace |
| `donnees.py` | Lecture des données depuis S3 avec cache local, et téléversement |
| `aws/` | Déploiement de la fonction Lambda des outils, et les trois preuves AWS |
| `data/alphaforge_starter/` | Jeu de départ des organisateurs (aussi sur S3) |
| `data/portefeuilles/` | Portefeuilles d'exemple (CSV : `symbole,montant_cad`) |
| `docs/` | Énoncé officiel et son résumé, documentation de l'agent et des traces |
| `tests/` | Tests du score et des scénarios, fausse piste A pour tester l'interface sans données |
| `requirements.txt` | Dépendances |
| `CLAUDE.md` | Contexte complet du projet : règles, contrat entre pistes, état, AWS |
