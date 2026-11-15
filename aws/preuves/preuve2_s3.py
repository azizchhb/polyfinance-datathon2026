"""Preuve AWS n° 2 : déposer un fichier sur S3, le relire, lister le seau.

Lancer avec :  python preuves_aws/preuve2_s3.py

S3 = Simple Storage Service. Un « seau » (bucket) contient des objets, c'est-à-dire
des fichiers repérés par une clé qui ressemble à un chemin, par exemple donnees/prix.csv.
Les noms de seaux sont uniques dans tout AWS, d'où le numéro de compte dans le nom.
"""
import sys
import warnings

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

import boto3
from botocore.exceptions import ClientError

session = boto3.session.Session()
region = session.region_name or "us-east-1"
compte = boto3.client("sts", region_name=region).get_caller_identity()["Account"]

SEAU = f"alphaforge-{compte}-donnees"
CLE = "preuves/bonjour.txt"
CONTENU = "Bonjour depuis le datathon AlphaForge.".encode("utf-8")

s3 = boto3.client("s3", region_name=region)


def echec(e):
    print(f"Échec ({e.response['Error']['Code']}) : {e.response['Error']['Message']}")
    sys.exit(1)


print(f"=== Étape 1 : créer le seau {SEAU} dans {region} ===")
try:
    params = {"Bucket": SEAU}
    if region != "us-east-1":  # particularité AWS : us-east-1 refuse ce paramètre
        params["CreateBucketConfiguration"] = {"LocationConstraint": region}
    s3.create_bucket(**params)
    print("Seau créé.")
except ClientError as e:
    if e.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
        print("Le seau existe déjà, on le réutilise.")
    else:
        echec(e)

print(f"\n=== Étape 2 : déposer {CLE} ===")
try:
    s3.put_object(Bucket=SEAU, Key=CLE, Body=CONTENU)
except ClientError as e:
    echec(e)
print(f"{len(CONTENU)} octets déposés.")

print("\n=== Étape 3 : relire l'objet ===")
try:
    texte = s3.get_object(Bucket=SEAU, Key=CLE)["Body"].read().decode("utf-8")
except ClientError as e:
    echec(e)
print("Contenu relu :", texte)
assert texte == CONTENU.decode("utf-8"), "le contenu relu diffère"

print("\n=== Étape 4 : lister le seau ===")
for o in s3.list_objects_v2(Bucket=SEAU).get("Contents", []):
    print(f"  {o['Key']}  ({o['Size']} octets, modifié le {o['LastModified']:%Y-%m-%d %H:%M} UTC)")

print("\nPreuve 2 réussie : le seau S3 est prêt pour les données.")
print(f"Nom du seau à retenir : {SEAU}")
