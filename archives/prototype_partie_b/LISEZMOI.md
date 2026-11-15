# Prototype parallèle de la partie B (archivé le 15 novembre 2026)

Trois fichiers du collègue de la piste B qui forment une application complète à part :
`profiles.py` (personas avec limites en pourcentage), `analytics.py` (moteur de métriques et
règles R1 à R8), `app.py` (interface Plotly avec un `agent.py` qui n'a pas été fourni).

Ils ne suivent pas le contrat du CLAUDE.md (autres formats de profil et de mesures) et ne
tournent pas tels quels (dépendances `plotly` et `agent` absentes). Ils sont gardés ici pour
les idées à reprendre : exposition techno « par transparence » des FNB, scénario de stress
2022, pire mois, portefeuille éditable avec liste déroulante de l'univers, boutons de
questions suggérées, onglet de traçabilité. Rien ici n'est importé par l'application.

Ce qui a été repris dans l'application : `piste_b.py` (identique au nôtre, avec XIC.TO et
ZAG.TO gardés dans les FNB larges pour les tests du guide), `tests/test_piste_b.py`, et les
trois portefeuilles de personas dans `data/portefeuilles/` (`amira.csv`, `mateo.csv`, `robert.csv`).
