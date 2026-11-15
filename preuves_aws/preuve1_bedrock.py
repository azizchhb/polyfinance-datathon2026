"""Preuve AWS n° 1 : identité, région, modèles Bedrock, premier appel d'outil.

Lancer avec :  python preuves_aws/preuve1_bedrock.py
Choisir un autre modèle :  MODELE_BEDROCK=<identifiant> python preuves_aws/preuve1_bedrock.py

Aucune clé dans ce fichier. boto3 lit les identifiants tout seul, dans cet ordre :
variables d'environnement AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, puis ~/.aws/credentials.
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")  # masque l'avertissement « Python 3.9 » de boto3
sys.stdout.reconfigure(encoding="utf-8")

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

REGION_DEFAUT = "us-east-1"
# Identifiant à confirmer avec la liste affichée à l'étape 3.
MODELE = os.environ.get("MODELE_BEDROCK", "us.anthropic.claude-haiku-5-5")


def etape(numero, titre):
    print(f"\n=== Étape {numero} : {titre} ===")


def erreur(e):
    return e.response["Error"]["Code"], e.response["Error"]["Message"]


# ------------------------------------------------------------------ étape 1
etape(1, "région")
# boto3 cherche la région dans AWS_DEFAULT_REGION puis dans ~/.aws/config.
session = boto3.session.Session()
region = session.region_name or REGION_DEFAUT
origine = "configurée" if session.region_name else f"aucune configurée, {REGION_DEFAUT} prise par défaut"
print(f"Région : {region} ({origine})")

# ------------------------------------------------------------------ étape 2
etape(2, "identité (service STS)")
# STS = Security Token Service. get_caller_identity répond « avec quel compte et
# quel utilisateur es-tu connecté ? » sans jamais afficher de secret.
try:
    identite = boto3.client("sts", region_name=region).get_caller_identity()
except NoCredentialsError:
    print("Aucun identifiant trouvé : créer ~/.aws/credentials (modèle dans la discussion).")
    sys.exit(1)
except ClientError as e:
    print("Identifiants refusés :", erreur(e)[1])
    sys.exit(1)
print("Compte AWS :", identite["Account"])
print("Identité   :", identite["Arn"])

# ------------------------------------------------------------------ étape 3
etape(3, "modèles Bedrock visibles dans cette région")
# Deux clients distincts chez AWS : « bedrock » gère le catalogue et la configuration,
# « bedrock-runtime » sert à appeler les modèles.
bedrock = boto3.client("bedrock", region_name=region)
try:
    modeles = bedrock.list_foundation_models(byOutputModality="TEXT")["modelSummaries"]
except ClientError as e:
    print("Impossible de lister les modèles :", erreur(e)[1])
    modeles = []
print("Modèles Anthropic et Amazon actifs (identifiant, puis mode d'appel) :")
for m in sorted(modeles, key=lambda m: m["modelId"]):
    if m["providerName"] in ("Anthropic", "Amazon") and m.get("modelLifecycle", {}).get("status") == "ACTIVE":
        print(f"  {m['modelId']:<60} {', '.join(m.get('inferenceTypesSupported', []))}")

print("\nProfils d'inférence (c'est l'identifiant à utiliser quand le mode est INFERENCE_PROFILE) :")
try:
    for p in sorted(bedrock.list_inference_profiles()["inferenceProfileSummaries"],
                    key=lambda p: p["inferenceProfileId"]):
        if "anthropic" in p["inferenceProfileId"] or "nova" in p["inferenceProfileId"]:
            print("  " + p["inferenceProfileId"])
except ClientError as e:
    print("Impossible de lister les profils :", erreur(e)[1])

# ------------------------------------------------------------------ étape 4
etape(4, f"premier appel au modèle {MODELE}")
runtime = boto3.client("bedrock-runtime", region_name=region)
messages = [{"role": "user", "content": [{"text": "Réponds en un mot : quelle est la capitale du Canada ?"}]}]
try:
    reponse = runtime.converse(modelId=MODELE, messages=messages, inferenceConfig={"maxTokens": 50})
except ClientError as e:
    code, message = erreur(e)
    print(f"Échec ({code}) : {message}")
    if code == "AccessDeniedException":
        print("-> Le modèle n'est sans doute pas activé sur ce compte : console Bedrock > Model access.")
    else:
        print("-> Choisir un identifiant de l'étape 3 et relancer avec MODELE_BEDROCK=<identifiant>.")
    sys.exit(1)
print("Réponse :", reponse["output"]["message"]["content"][0]["text"].strip())
usage = reponse["usage"]
print(f"Jetons : {usage['inputTokens']} en entrée, {usage['outputTokens']} en sortie")

# ------------------------------------------------------------------ étape 5
etape(5, "appel d'outil : le modèle demande, Python calcule")
# On déclare UN outil au modèle. Le modèle ne l'exécute pas : il renvoie une
# demande (toolUse) avec les arguments, et c'est notre code qui calcule.
outils = {"tools": [{"toolSpec": {
    "name": "additionner",
    "description": "Additionne deux nombres entiers.",
    "inputSchema": {"json": {
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"]}}}}]}
messages = [{"role": "user", "content": [{"text":
    "Combien font 48 213 + 97 568 ? Utilise l'outil, ne calcule pas toi-même."}]}]
try:
    reponse = runtime.converse(modelId=MODELE, messages=messages, toolConfig=outils,
                               inferenceConfig={"maxTokens": 300})
    print("stopReason :", reponse["stopReason"])
    if reponse["stopReason"] != "tool_use":
        print("Le modèle n'a pas demandé l'outil : il ne gère peut-être pas les appels d'outils.")
        sys.exit(1)

    message_modele = reponse["output"]["message"]
    messages.append(message_modele)  # l'historique doit contenir la demande du modèle
    resultats = []
    for bloc in message_modele["content"]:
        if "toolUse" in bloc:
            demande = bloc["toolUse"]
            print(f"Le modèle demande : {demande['name']}({demande['input']})")
            somme = demande["input"]["a"] + demande["input"]["b"]  # Python calcule
            resultats.append({"toolResult": {"toolUseId": demande["toolUseId"],
                                             "content": [{"json": {"somme": somme}}]}})
    messages.append({"role": "user", "content": resultats})  # on renvoie le résultat

    reponse = runtime.converse(modelId=MODELE, messages=messages, toolConfig=outils,
                               inferenceConfig={"maxTokens": 300})
    print("stopReason :", reponse["stopReason"])
    texte = " ".join(b["text"] for b in reponse["output"]["message"]["content"] if "text" in b)
    print("Réponse finale :", texte.strip())
except ClientError as e:
    print("Échec de l'appel d'outil :", erreur(e)[1])
    sys.exit(1)

print("\nPreuve 1 réussie : identité, région, modèle et appels d'outils fonctionnent.")
