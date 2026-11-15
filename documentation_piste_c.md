# Piste C : l'agent et AWS

Matériel pour la documentation de la piste D. État au 14 novembre 2026.

## Paragraphe d'architecture

L'interface Streamlit envoie la question, le portefeuille et le profil à la fonction `demander`
(`piste_c.py`). Celle-ci ouvre une conversation avec Claude Opus 5.5 sur **Amazon Bedrock** (API
Converse, via boto3) en lui déclarant quatre outils : `analyser`, `evaluer`, `simuler` et
`proposer_scenarios`. Le modèle ne calcule jamais : il choisit un outil, le code Python l'exécute
avec le portefeuille et le profil injectés par l'application (le modèle ne les retape pas), et le
résultat lui est renvoyé. La boucle continue jusqu'à une réponse en texte, avec un maximum de huit
tours. Avant l'affichage, un contrôle de gouvernance écrit en code vérifie deux choses : l'absence
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
| Amazon S3 | Seau `alphaforge-<compte>-donnees` : le jeu de données sous `alphaforge_starter/`, lu par `donnees.py` (l'agent y lit la liste des actifs couverts) | Utilisé par l'application |
| AWS Lambda | Fonctions de calcul de la piste A, rôle `alphaforge-lambda-role` | Prouvé avec une fonction « bonjour », pas encore branché |

## Capture de trace (CloudWatch, flux `session-20261114-184601`)

Question d'Amira (profil risque 3, expérience débutante) : « Suis-je trop concentrée ? »

```json
{"evenement": "demande", "texte": "Suis-je trop concentrée ?", "modele": "us.anthropic.claude-opus-5-5", "experience": "debutant"}
{"evenement": "modele", "tour": 1, "stop": "tool_use", "usage": {"inputTokens": 2225, "outputTokens": 27, "totalTokens": 2252}}
{"evenement": "outil", "outil": "evaluer", "arguments": {}, "resume": "score de 94 sur 100, verdict adequat, 1 alerte(s)"}
{"evenement": "modele", "tour": 2, "stop": "end_turn", "usage": {"inputTokens": 2814, "outputTokens": 942, "totalTokens": 3756}}
{"evenement": "verification", "problemes": [], "correction": 0}
{"evenement": "reponse", "duree_s": 12.2, "outils": 1, "corrections": 0}
```

## Le test de Robert (profil risque 1,5, horizon 4 ans, préservation)

Demande : « Je veux ajouter 15 000 $ de NVDA, tout le monde en parle. »

L'agent a appelé `simuler` avec `{"type": "ajouter", "symbole": "NVDA", "montant": 15000}` et a
répondu, sans refuser ni approuver : le score passerait de 20 à 7, la volatilité de 21,5 % à 27,4 %
pour une plage cible de 6 % à 10,5 %, la perte maximale historique de 40,9 % à 52 % pour une limite
de 15 %, les paris effectifs de 3,99 à 2,08 pour un minimum de 5,5. Il a nommé l'écart entre la
demande et le profil, rappelé que la décision appartient à la personne, et terminé par ce que la
mesure ne dit pas (rendements futurs, contenu des FNB larges). Volet « Ce que l'agent a fait » :
`simuler : ajout de 15 000 $ de NVDA : score de 20 à 7`.

Les chiffres ci-dessus viennent de `faux.py` et changeront avec la vraie piste A.
