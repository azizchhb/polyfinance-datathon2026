"""Point d'entrée AWS Lambda : les quatre outils de l'agent, calculés dans le nuage.

Événement attendu :
    {"outil": "evaluer", "portefeuille": {"NVDA": 10000, ...}, "profil": {...}, "changement": {...}}
Réponse :
    {"ok": true, "resultat": ...}   ou   {"ok": false, "erreur": "ValueError: ..."}

Déployé par deployer_lambda.py avec piste_a.py, piste_b.py et donnees.py. pandas et numpy
viennent de la couche AWS « AWSSDKPandas ». Les données sont lues sur S3 (variable SEAU_DONNEES)
et mises en cache dans /tmp (variable CACHE_DONNEES) : le dossier du code est en lecture seule.
Chaque appel écrit une ligne JSON dans CloudWatch, groupe /aws/lambda/alphaforge-outils.
"""
import json
import time

import piste_a
import piste_b

OUTILS = ("analyser", "evaluer", "simuler", "proposer_scenarios")


def _simple(objet):
    """Scalaires numpy -> Python, pour la sérialisation JSON de la réponse."""
    return objet.item() if hasattr(objet, "item") else str(objet)


def handler(event, context):
    debut = time.time()
    outil = event.get("outil")
    try:
        portefeuille = event["portefeuille"]
        profil = event.get("profil") or {}
        if outil == "analyser":
            r = piste_a.analyser(portefeuille)
        elif outil == "evaluer":
            r = piste_b.evaluer(piste_a.analyser(portefeuille), profil)
        elif outil == "simuler":
            r = piste_b.simuler(portefeuille, event["changement"], profil, piste_a.analyser)
        elif outil == "proposer_scenarios":
            r = piste_b.proposer_scenarios(portefeuille, profil, piste_a.analyser)
        else:
            raise ValueError(f"outil inconnu : {outil} (attendu : {', '.join(OUTILS)})")
        reponse = {"ok": True, "resultat": json.loads(json.dumps(r, default=_simple))}
    except Exception as e:  # erreur métier (symbole non couvert...) renvoyée à l'agent, jamais inventée
        reponse = {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    print(json.dumps({"outil": outil, "ok": reponse["ok"], "duree_ms": round(1000 * (time.time() - debut)),
                      "titres": len(event.get("portefeuille") or {})}, ensure_ascii=False))
    return reponse
