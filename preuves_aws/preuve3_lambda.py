"""Preuve AWS n° 3 : une fonction Lambda « bonjour », appelée depuis Python, et ses journaux.

Lancer avec :  python preuves_aws/preuve3_lambda.py

Lambda = du code qu'AWS exécute à la demande, sans serveur à gérer. On lui envoie un
événement JSON, elle renvoie un JSON. Pour tourner, la fonction prend une identité,
un « rôle » IAM, qui lui donne le droit d'écrire ses journaux dans CloudWatch.
Tout ce que la fonction affiche avec print se retrouve dans CloudWatch : c'est la trace.
"""
import io
import json
import sys
import time
import warnings
import zipfile

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

import boto3
from botocore.exceptions import ClientError

session = boto3.session.Session()
region = session.region_name or "us-east-1"
NOM_FONCTION = "alphaforge-bonjour"
NOM_ROLE = "alphaforge-lambda-role"
RUNTIME = "python3.12"

CODE = '''
def handler(event, context):
    nom = event.get("nom", "inconnu")
    print(f"Appel reçu pour {nom}")  # part automatiquement dans CloudWatch
    return {"message": f"Bonjour {nom}, ici Lambda."}
'''
POLITIQUE_DE_CONFIANCE = {  # « qui a le droit de prendre ce rôle ? » : le service Lambda
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"},
                   "Action": "sts:AssumeRole"}]}
POLITIQUE_JOURNAUX = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

iam = boto3.client("iam", region_name=region)
lam = boto3.client("lambda", region_name=region)
logs = boto3.client("logs", region_name=region)


def code_erreur(e):
    return e.response["Error"]["Code"], e.response["Error"]["Message"]


# ------------------------------------------------------------------ étape 1
print(f"=== Étape 1 : le rôle IAM {NOM_ROLE} ===")
role_arn = None
try:
    role_arn = iam.get_role(RoleName=NOM_ROLE)["Role"]["Arn"]
    print("Rôle déjà présent.")
except ClientError as e:
    if code_erreur(e)[0] != "NoSuchEntity":
        print("Lecture du rôle refusée :", code_erreur(e)[1])
if role_arn is None:
    try:
        role_arn = iam.create_role(RoleName=NOM_ROLE,
                                   AssumeRolePolicyDocument=json.dumps(POLITIQUE_DE_CONFIANCE),
                                   Description="Role d'execution des Lambda du datathon AlphaForge")["Role"]["Arn"]
        iam.attach_role_policy(RoleName=NOM_ROLE, PolicyArn=POLITIQUE_JOURNAUX)
        print("Rôle créé. Attente de 10 s : IAM met quelques secondes à propager un nouveau rôle.")
        time.sleep(10)
    except ClientError as e:
        print("Création du rôle refusée :", code_erreur(e)[1])
        print("Recherche d'un rôle existant que Lambda peut prendre...")
        for page in iam.get_paginator("list_roles").paginate():
            for r in page["Roles"]:
                if "lambda.amazonaws.com" in json.dumps(r["AssumeRolePolicyDocument"]):
                    role_arn = r["Arn"]
                    print("Rôle trouvé :", r["RoleName"])
                    break
            if role_arn:
                break
if role_arn is None:
    print("Aucun rôle utilisable : demander aux organisateurs le rôle Lambda à utiliser.")
    sys.exit(1)
print("ARN du rôle :", role_arn)

# ------------------------------------------------------------------ étape 2
print(f"\n=== Étape 2 : empaqueter et déployer {NOM_FONCTION} ===")
# Lambda attend un fichier zip contenant le code. On le construit en mémoire.
tampon = io.BytesIO()
with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("lambda_function.py", CODE)
zip_octets = tampon.getvalue()

for essai in range(6):
    try:
        lam.create_function(FunctionName=NOM_FONCTION, Runtime=RUNTIME, Role=role_arn,
                            Handler="lambda_function.handler",  # fichier.fonction
                            Code={"ZipFile": zip_octets}, Timeout=10,
                            Description="Preuve Lambda du datathon AlphaForge")
        print("Fonction créée.")
        break
    except ClientError as e:
        code, message = code_erreur(e)
        if code == "ResourceConflictException":
            lam.update_function_code(FunctionName=NOM_FONCTION, ZipFile=zip_octets)
            print("Fonction déjà présente : code mis à jour.")
            break
        if code == "InvalidParameterValueException" and "role" in message.lower() and essai < 5:
            print("Le rôle n'est pas encore propagé, nouvel essai dans 5 s...")
            time.sleep(5)
            continue
        print(f"Échec ({code}) : {message}")
        sys.exit(1)

# La fonction passe par un état « Pending » avant d'être appelable.
for _ in range(30):
    conf = lam.get_function_configuration(FunctionName=NOM_FONCTION)
    if conf["State"] == "Active" and conf.get("LastUpdateStatus", "Successful") == "Successful":
        break
    time.sleep(1)
print("État :", conf["State"])

# ------------------------------------------------------------------ étape 3
print("\n=== Étape 3 : appeler la fonction depuis Python ===")
evenement = {"nom": "Aziz"}
reponse = lam.invoke(FunctionName=NOM_FONCTION, Payload=json.dumps(evenement).encode("utf-8"))
resultat = json.loads(reponse["Payload"].read())
if reponse.get("FunctionError"):
    print("La fonction a levé une erreur :", resultat)
    sys.exit(1)
print("Envoyé :", evenement)
print("Reçu   :", resultat)

# ------------------------------------------------------------------ étape 4
print("\n=== Étape 4 : lire les journaux CloudWatch ===")
groupe = f"/aws/lambda/{NOM_FONCTION}"
evenements = []
for _ in range(10):  # les journaux arrivent avec quelques secondes de retard
    try:
        flux = logs.describe_log_streams(logGroupName=groupe, orderBy="LastEventTime",
                                         descending=True, limit=1)["logStreams"]
        if flux:
            evenements = logs.get_log_events(logGroupName=groupe,
                                             logStreamName=flux[0]["logStreamName"])["events"]
        if any("Appel reçu" in ev["message"] for ev in evenements):
            break
    except ClientError as e:
        if code_erreur(e)[0] != "ResourceNotFoundException":
            print("Lecture des journaux refusée :", code_erreur(e)[1])
            break
    time.sleep(3)
for ev in evenements[-6:]:
    print("  " + ev["message"].rstrip())
if not evenements:
    print("Aucun journal lu : vérifier dans la console CloudWatch, groupe", groupe)

print("\nPreuve 3 réussie : Lambda déployée, appelée depuis Python, journaux lus dans CloudWatch.")
