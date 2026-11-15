# Piste C : l'agent et AWS

Matériel pour la documentation de la piste D. État au 14 novembre 2026.

## Paragraphe d'architecture

L'interface Streamlit envoie la question, le portefeuille et le profil à la fonction `demander`
(`piste_c.py`). Celle-ci ouvre une conversation avec Claude Opus 5.5 sur **Amazon Bedrock** (API
Converse, via boto3) en lui déclarant quatre outils : `analyser`, `evaluer`, `simuler` et
`proposer_scenarios`. Le modèle ne calcule jamais : il choisit un outil, et l'outil s'exécute dans
une fonction **AWS Lambda** (`alphaforge-outils`) qui embarque le code des pistes A et B, lit les
cours et les taux de change sur **Amazon S3**, et renvoie le résultat. Le portefeuille et le profil
sont injectés par l'application, le modèle ne les retape pas. Si Lambda est injoignable, l'application
exécute le même code en local et le signale dans `limites`. La boucle continue jusqu'à une réponse en
texte, avec un maximum de huit tours. Avant l'affichage, un contrôle de gouvernance écrit en code vérifie deux choses : l'absence
de vocabulaire prescriptif (achète, vends, tu devrais, recommande, conseille) et la présence de
chaque nombre cité dans les résultats des outils. En cas d'écart, la réponse est régénérée au plus
deux fois, puis remplacée par un résumé factuel produit sans modèle. Chaque appel d'outil est ajouté
à `outils_appeles`, affiché dans le volet « Ce que l'agent a fait », et journalisé en JSON dans
**Amazon CloudWatch Logs** (groupe `/alphaforge/agent`, un flux par session). Si un outil échoue ou
si Bedrock est injoignable, l'application le dit dans `limites` et renvoie le résumé factuel.

## Rôle de chaque service AWS

| Service | Rôle | État |
|---|---|---|
| Amazon Bedrock | Fait tourner le modèle et ses appels d'outils (`us.anthropic.claude-opus-5-5`) | Utilisé par l'application |
| Amazon CloudWatch Logs | Trace de chaque demande, appel d'outil, vérification et réponse | Utilisé par l'application |
| Amazon S3 | Seau `alphaforge-<compte>-donnees` : le jeu de données sous `alphaforge_starter/`, lu par `donnees.py`. La piste A y lit les prix et les taux de change, l'agent la liste des actifs couverts | Utilisé par l'application |
| AWS Lambda | Fonction `alphaforge-outils` : les quatre outils de l'agent (code des pistes A et B, couche AWS pandas), rôle `alphaforge-lambda-role` | Utilisé par l'application |

## Capture de trace (CloudWatch, flux `session-20261114-184601`)

Question d'Amira (profil risque 3, expérience débutante) : « Suis-je trop concentrée ? »
Mesures de `faux.py` à cette date ; avec les vraies données, le score d'Amira est de 93.

```json
{"evenement": "demande", "texte": "Suis-je trop concentrée ?", "modele": "us.anthropic.claude-opus-5-5", "experience": "debutant"}
{"evenement": "modele", "tour": 1, "stop": "tool_use", "usage": {"inputTokens": 2225, "outputTokens": 27, "totalTokens": 2252}}
{"evenement": "outil", "outil": "evaluer", "arguments": {}, "resume": "score de 94 sur 100, verdict adequat, 1 alerte(s)"}
{"evenement": "modele", "tour": 2, "stop": "end_turn", "usage": {"inputTokens": 2814, "outputTokens": 942, "totalTokens": 3756}}
{"evenement": "verification", "problemes": [], "correction": 0}
{"evenement": "reponse", "duree_s": 12.2, "outils": 1, "corrections": 0}
```

## Capture de trace de la fonction Lambda (CloudWatch, `/aws/lambda/alphaforge-outils`, 15 novembre 2026)

Une ligne JSON par outil exécuté, suivie du rapport de facturation d'AWS. Le premier appel paie
le démarrage à froid (chargement de pandas et lecture des données sur S3), les suivants durent
quelques millisecondes.

```
{"outil": "evaluer", "ok": true, "duree_ms": 995, "titres": 5}
REPORT Duration: 1005.38 ms  Billed Duration: 3730 ms  Memory Size: 1024 MB  Max Memory Used: 220 MB  Init Duration: 2724.56 ms
{"outil": "simuler", "ok": true, "duree_ms": 10, "titres": 5}
REPORT Duration: 12.14 ms  Billed Duration: 13 ms  Memory Size: 1024 MB  Max Memory Used: 220 MB
{"outil": "evaluer", "ok": false, "duree_ms": 0, "titres": 2}
{"outil": "proposer_scenarios", "ok": true, "duree_ms": 120, "titres": 5}
```

La ligne `"ok": false` est un portefeuille contenant PLTR, hors des 31 actifs : l'outil renvoie
l'erreur à l'agent au lieu d'inventer une mesure. Dans l'interface, le volet « Ce que l'agent a
fait » affiche par exemple `evaluer : score de 18 sur 100, verdict inadequat, 3 alerte(s) · calculé sur AWS Lambda`.

## Le test de Robert (profil risque 1,5, horizon 4 ans, préservation)

Demande : « Je veux ajouter 15 000 $ de NVDA, tout le monde en parle. »

L'agent a appelé `simuler` avec `{"type": "ajouter", "symbole": "NVDA", "montant": 15000}` et a
répondu, sans refuser ni approuver : le score passerait de 18 à 6, la volatilité de 20,6 % à 26,9 %
pour une plage cible de 6 % à 10,5 %, la perte maximale historique de 33,6 % à 41,5 % pour une limite
de 15 %, les paris effectifs de 3,57 à 1,91 pour un minimum de 5,5. Il a nommé l'écart entre la
demande et le profil, signalé que QQQ contient lui-même NVDA, et terminé par ce que la mesure ne dit
pas (rendements futurs, raisons de l'engouement). Volet « Ce que l'agent a fait » :
`simuler : ajout de 15 000 $ de NVDA : score de 18 à 6`.

Chiffres calculés le 15 novembre 2026 sur les vraies données du jeu de départ, lues depuis S3
(cours ajustés du 2021-11-12 au 2026-11-12, convertis en dollars canadiens).
