# Énoncé officiel AlphaForge AI : résumé fidèle

Source : `enonce_officiel_2026.pdf` (PolyFinances, Banque Nationale, AWS, 19 pages) et
`presentation_participants.pptx` (12 diapositives). Résumé rédigé le 15 novembre 2026 pour
l'équipe ; en cas de doute, le PDF fait foi.

## Le défi

Concevoir une **solution agentique auto-explicative** qui exploite des données financières
publiques pour éclairer la décision d'investissement selon différents profils. La solution
explique ses résultats ; les actifs, les outils et l'architecture restent au choix des équipes.
L'objectif n'est pas de sélectionner le portefeuille au meilleur rendement, mais de démontrer
une démarche crédible, innovante et utile. L'outil peut comparer des actifs, analyser des
scénarios, expliquer des risques ou proposer une allocation fictive.

## Les trois personas et ce qu'ils testent (pages 5 à 7)

| Persona | Profil | Ce que le persona teste |
|---|---|---|
| Amira, 26 ans, ingénieure logicielle, risque élevé, 15 ans et plus, expérience intermédiaire. Intéressée par l'IA, les technologies émergentes, les cryptoactifs ; veut garder une certaine diversification. | Croissance à long terme | « Jusqu'où le système accepte-t-il le risque ? Il doit tenir compte de son profil offensif sans interpréter risque élevé comme tout est acceptable. Garder une diversification cohérente avec ses préférences demeure important. » |
| Mateo, 41 ans, gestionnaire des opérations, risque modéré, 8 à 12 ans, intermédiaire. Grande importance aux facteurs ESG ; éviter les entreprises liées à des controverses environnementales ou sociales ; peu intéressé par le spéculatif. | Croissance équilibrée | « Le système sait-il intégrer autre chose que le rendement et le risque ? Il doit tenir compte à la fois des critères financiers et des préférences personnelles. » |
| Robert, 59 ans, professionnel de la santé, risque faible à modéré, 3 à 5 ans, expérience avancée. Entreprises établies, stabilité ; peu intéressé par la crypto ; peut être tenté par une entreprise très médiatisée. | Préserver le capital avec un potentiel de croissance | « Le système sait-il remettre en question une demande incohérente avec le profil ? Il doit relever la tension entre l'intérêt ponctuel et ses objectifs, expliquer les risques et éviter d'acquiescer automatiquement. » |

Conseil répété dans les deux documents : **démontrer au moins deux situations contrastées**
pour rendre l'adaptation visible.

## Démarche proposée (page 8) et pistes (page 9)

Cinq décisions : formuler une question utile ; concevoir la démarche agentique (rôle des agents,
données, outils, coordination, points de contrôle) ; tenir compte du contexte (personas,
contraintes) ; **mettre les résultats à l'épreuve** (sensibilité à des hypothèses, données ou
scénarios différents : « changez une hypothèse, changez un scénario, changez un profil ») ;
rendre la solution auto-explicative (relier les résultats aux sources, hypothèses, étapes
observables et limites).

Deux pistes nommées : un **agent d'explicabilité** (synthétiser ce qui soutient le résultat,
citer les données, expliciter les hypothèses, signaler les incertitudes) et un **agent de
gouvernance** (vérifier que les actions respectent les contraintes de l'investisseur et les
limites du défi, signaler les conflits ou informations manquantes, **rendre les contrôles
visibles**). Ni l'un ni l'autre n'impose une architecture.

Conseils : approche simple, focalisée et vérifiable ; la sophistication et le nombre d'agents ne
sont pas des fins en soi ; « pourquoi cet agent existe-t-il et quelle valeur apporte-t-il ? ».

## Données (pages 10 à 14)

- Le jeu de départ est facultatif ; aucun actif ni classe n'est obligatoire ; les symboles sont des repères.
- **Sources, dates, traitements et conditions d'utilisation doivent être documentés.** Pour chaque
  source : pertinence, origine, date, traitements, limites, conditions d'accès et de réutilisation.
- Règles : traçabilité (source, date, devise, traitements) ; cohérence temporelle (date d'observation
  contre date de publication) ; comparabilité (dividendes, fractionnements, biais de sélection,
  données manquantes, conversion CAD/USD) ; licences ; aucune donnée bancaire réelle, portefeuilles
  et profils fictifs.
- Période du jeu de départ : 12 novembre 2021 au 12 novembre 2026, qui inclut 2022.

## AWS (diapositive 7)

**Condition d'admissibilité** : « AWS doit contribuer réellement et de manière démontrable au
fonctionnement de la solution. Absence d'intégration effective = projet non admissible. »
Trois attentes : pertinence (choisir les services qui servent vraiment le cas), intégration
(montrer le rôle concret d'AWS dans le flux), architecture (compréhensible et évolutive). Bonnes
pratiques : sécurité, accès, données, utilisation efficace des ressources. « Ne multipliez pas
les services pour impressionner. Justifiez chaque choix. »

## Livrables (pages 15 et 16)

1. **Prototype et code source** : un prototype démontrable avec un cas d'utilisation complet et
   une explication accessible du résultat (sources, hypothèses, principaux facteurs, limites) ;
   un dépôt de code et un **README** résumant dépendances, sources de données, configuration et
   instructions de démarrage ou de reproduction.
2. **Vidéo de démonstration**, environ 5 minutes : problème choisi, rôle des agents, données et
   outils mobilisés, résultat et explication fournie à l'utilisateur, de bout en bout. Deux
   situations d'investisseurs distinctes peuvent illustrer l'adaptation.
3. **Documentation technique** : méthodes, modèles, technologies et leur justification ; sources,
   actifs retenus, traitements et hypothèses ; **le mécanisme d'explicabilité et un exemple
   reliant une conclusion aux données ou aux traces d'exécution** ; validations des résultats et
   des explications, limites, améliorations envisagées.
4. **One pager** : problématique, approche agentique, originalité, sources de données, capacité
   d'explication, bénéfices concrets pour l'utilisateur.

Dates limites, plateformes de dépôt et formats : dans les consignes logistiques officielles (non
incluses dans ces documents).

## Appréciation et cadre responsable (pages 17 et 18)

- Le jury valorise la pertinence de la démarche agentique et la capacité de la solution à
  expliquer ses propres résultats, plus que la complexité ou la performance passée des actifs.
- Simulation uniquement : aucune transaction réelle, aucun conseil financier personnalisé.
  Distinguer faits, hypothèses et scénarios fictifs ; présenter les incertitudes importantes ;
  explications synthétiques, vérifiables, fidèles aux sources et aux actions observables, **sans
  inventer de justification après coup ni exposer les raisonnements internes détaillés des modèles**.
- « Le défi ne demande pas de prédire les rendements futurs à partir des performances passées. »
  La volatilité est un indicateur parmi d'autres : horizon, diversification et préférences comptent.

## Grille d'évaluation simplifiée (annexe 1)

| Critère | Poids |
|---|---|
| Qualité, pertinence et innovation de la solution | 20 % |
| Intelligence agentique et explicabilité | 20 % |
| Capacité d'analyse et traitement des données | 20 % |
| Expérience utilisateur UX/UI | 10 % |
| Qualité de l'intégration AWS | 15 % |
| Présentation, valeur business et marketing | 15 % |

La grille complète est réservée au jury.
