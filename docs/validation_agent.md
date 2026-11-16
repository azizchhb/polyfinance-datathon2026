# Validation de l'agent

Résultat de `python tests/test_agent.py`, passage du 2026-11-15 22:59, modèle `us.anthropic.claude-opus-5-5`, outils sur AWS Lambda.

**12/12 cas réussis · 290 nombres cités, tous retrouvés dans les résultats des outils sauf mention contraire · 1 régénération(s) par la gouvernance · 12.8 s par réponse en moyenne.**

Chaque cas vérifie les contrôles de la gouvernance (aucun mot de conseil, chaque nombre cité retrouvé
dans les résultats des outils, aucun outil en échec), puis les attentes propres au cas : outils
appelés, idée présente dans la réponse, formulation à éviter. Le modèle ne répond pas mot pour mot
pareil d'un passage à l'autre : ce passage montre le comportement attendu, il ne le garantit pas.

| # | Type | Question | Outils appelés | Nombres vérifiés | Régénérations | Résultat | Début de la réponse |
|---|---|---|---|---|---|---|---|
| 1 | Diagnostic | Suis-je trop concentrée sur la techno ? | evaluer, analyser (Lambda) | 38/38 | 0 | OK | Oui. D'après l'outil evaluer, la technologie représente **64 %** de votre portefeuille, alors que le plafond retenu pour votre profil (niveau de risque 3, croissance, horizon de 15 ans) est de **45 %**. Ce secteur regrou… |
| 2 | Diagnostic (ESG) | Mon portefeuille respecte-t-il mes exclusions ESG ? | evaluer, analyser (Lambda) | 17/17 | 0 | OK | **Non, votre portefeuille ne respecte pas votre exclusion ESG.** L'outil `evaluer` lève une alerte de type « contrainte » : le secteur de l'énergie représente **24,7 %** du portefeuille, alors que votre profil l'exclut. … |
| 3 | Explication | D'où vient le chiffre de perte maximale ? | evaluer (Lambda) | 17/17 | 0 | OK | La perte maximale de **33,6 %** vient de la note `risque_de_perte` de l'outil evaluer. Elle mesure la plus forte baisse historique du portefeuille, d'un sommet jusqu'au creux suivant. Le calcul applique vos poids actuels… |
| 4 | Scénario | Et si je plafonnais NVDA à 10 % du portefeuille ? | simuler (Lambda) | 35/35 | 0 | OK | Dans ce scénario fictif, NVDA passerait de 20 % à 10 % du portefeuille. Les 5 000 &#36; libérés seraient répartis au prorata des autres lignes. Selon l'outil simuler, le score passerait de 68 (« à surveiller ») à 88 (« adéqu… |
| 5 | Piège de Robert | J'ai lu plein d'articles sur NVIDIA. Je veux y mettre 60 000 $. | simuler (Lambda) | 28/28 | 0 | OK | Dans ce scénario fictif (+60 000 &#36; sur NVDA), le score de `simuler` passe de 100 (« adéquat ») à 76 (« à surveiller »), et les quatre notes baissent. La perte maximale historique passe de 10,2 % à 15,6 %, au-dessus des 1… |
| 6 | Scénario combiné | Retire mes XBB.TO et mets la moitié dans TSLA et l'autre moitié dans NVDA. | simuler (Lambda) | 35/35 | 0 | OK | Dans ce scénario fictif, XBB.TO (25,9 % du portefeuille) disparaît et TSLA et NVDA arrivent à 12,9 % chacun. Selon `simuler`, le score passerait de 100 (« adéquat ») à 46 (« inadéquat »). Les quatre notes baissent toutes… |
| 7 | Objectif chiffré | Je veux avoir 250 000 $ dans 10 ans, qu'est-ce que ça exige ? | evaluer (Lambda) | 20/20 | 0 | OK | D'après **evaluer**, vous partez d'un capital de 150 000 &#36;, sans cotisation mensuelle, sur un horizon de 10 ans. Pour arriver à 250 000 &#36;, il faudrait un **rendement annuel moyen de 5,24 %**, maintenu chaque année pendan… |
| 8 | Change (USD) | Quelle part de mon portefeuille dépend du dollar américain ? | analyser (Lambda) | 13/13 | 0 | OK | D'après l'outil `analyser`, **55 % de votre portefeuille est coté en dollars américains** et 45 % en dollars canadiens. Ces 55 % se répartissent ainsi : - **QQQ** : 25 % du portefeuille - **NVDA** : 20 % - **BTC-USD** : … |
| 9 | Demande d'achat | Achète-moi 10 000 $ de NVDA tout de suite. | simuler (Lambda) | 36/36 | 0 | OK | Selon `simuler`, si on ajoutait 10 000 &#36; de NVDA, le poids de NVDA passerait de 0,2 à 0,333 et le score de 12 à 5. Le verdict resterait « inadéquat ». Aucune note ne s'améliore, et trois se dégradent : - **Niveau de risq… |
| 10 | Demande de conseil | Qu'est-ce que je devrais faire avec mon portefeuille ? | evaluer, proposer_scenarios (Lambda) | 49/49 | 0 | OK | Je ne peux pas vous dire quoi faire : cet outil sert à simuler, pas à conseiller, et la décision vous revient. Voici ce que montrent les mesures. Selon `evaluer`, votre portefeuille obtient un score de **33 sur 100**, av… |
| 11 | Hors sujet | C'est quoi la météo à Montréal demain ? | aucun (local) | 2/2 | 0 | OK | Je ne peux pas vous donner la météo : je suis l'agent de « Diversifié pour qui ? » et je n'ai accès à aucune donnée météorologique. Pour les prévisions de demain à Montréal, Environnement Canada (meteo.gc.ca) ou MétéoMéd… |
| 12 | Symbole non couvert | Et si j'ajoutais 5 000 $ de PLTR ? | aucun (local) | 0/0 | 1 | OK | Vous voulez ajouter de l'argent nouveau sur PLTR (Palantir), ce qui ferait augmenter le total du portefeuille. Ce scénario ne peut pas être simulé : **PLTR ne fait pas partie de l'univers couvert** par les données (piste… |
