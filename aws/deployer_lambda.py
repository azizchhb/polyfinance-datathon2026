"""Déploie les outils de calcul sur AWS Lambda : fonction alphaforge-outils.

Lancer, depuis la racine du dépôt :  python aws/deployer_lambda.py
À relancer après toute modification de piste_a.py, piste_b.py, donnees.py ou aws/lambda_outils.py.

Ce que fait le script, et pourquoi :
1. Le rôle IAM alphaforge-lambda-role (créé par la preuve 3) reçoit le droit de lire le seau S3
   des données : une fonction Lambda n'a aucun droit par défaut.
2. Le code est empaqueté en zip : seulement nos quatre fichiers. pandas et numpy pèsent des
   dizaines de Mo, on les prend dans la couche « AWS SDK for pandas » publiée par AWS.
3. La fonction est créée ou mise à jour : runtime Python 3.12, 1024 Mo (plus de mémoire veut
   aussi dire plus de processeur), 60 s, variables SEAU_DONNEES et CACHE_DONNEES=/tmp/...
4. Un appel de test (outil evaluer, portefeuille de démo, profil de Robert) mesure le premier
   appel (démarrage à froid) et le second (fonction chaude).
"""
import io
import json
import sys
import time
import warnings
import zipfile
from pathlib import Path

warnings.filterwarnings("ignore", module="boto3")
sys.stdout.reconfigure(encoding="utf-8")

import boto3
from botocore.exceptions import ClientError

RACINE = Path(__file__).resolve().parent.parent  # le dépôt : les pistes A et B et donnees.py y sont
sys.path.insert(0, str(RACINE))
import donnees  # noqa: E402

REGION = boto3.session.Session().region_name or "us-east-1"
NOM_FONCTION = "alphaforge-outils"
NOM_ROLE = "alphaforge-lambda-role"
RUNTIME = "python3.12"
# nom dans le zip -> fichier source ; dans le zip tout est à plat, d'où les imports simples du handler
FICHIERS = {"lambda_outils.py": Path(__file__).with_name("lambda_outils.py"),
            "piste_a.py": RACINE / "piste_a.py",
            "piste_b.py": RACINE / "piste_b.py",
            "donnees.py": RACINE / "donnees.py"}
# Couche publique d'AWS avec pandas, numpy et pyarrow (compte AWS 336392948345 = AWS SDK for pandas)
COUCHE_PANDAS = f"arn:aws:lambda:{REGION}:336392948345:layer:AWSSDKPandas-Python312"
POLITIQUE_DE_CONFIANCE = {"Version": "2012-10-17", "Statement": [{
    "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}

iam = boto3.client("iam", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)


def code_erreur(e):
    return e.response["Error"]["Code"], e.response["Error"]["Message"]


def role_arn():
    try:
        return iam.get_role(RoleName=NOM_ROLE)["Role"]["Arn"]
    except ClientError as e:
        if code_erreur(e)[0] != "NoSuchEntity":
            raise
    arn = iam.create_role(RoleName=NOM_ROLE, AssumeRolePolicyDocument=json.dumps(POLITIQUE_DE_CONFIANCE),
                          Description="Role d'execution des Lambda du datathon AlphaForge")["Role"]["Arn"]
    iam.attach_role_policy(RoleName=NOM_ROLE,
                           PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
    print("Rôle créé, attente de 10 s pour la propagation IAM.")
    time.sleep(10)
    return arn


def autoriser_lecture_s3(seau):
    """Politique en ligne, limitée à notre seau : lister et lire, rien d'autre."""
    politique = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": f"arn:aws:s3:::{seau}/*"},
        {"Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": f"arn:aws:s3:::{seau}"}]}
    iam.put_role_policy(RoleName=NOM_ROLE, PolicyName="alphaforge-lecture-s3", PolicyDocument=json.dumps(politique))
    print(f"Rôle autorisé à lire s3://{seau}")


def couche_pandas_arn():
    """ARN complet (avec numéro de version) de la couche AWS SDK for pandas la plus récente."""
    try:
        versions = lam.list_layer_versions(LayerName=COUCHE_PANDAS)["LayerVersions"]
        if versions:
            return versions[0]["LayerVersionArn"]
    except ClientError:
        pass
    for v in range(80, 0, -1):  # la liste n'est pas toujours permise sur une couche publique : on sonde
        try:
            return lam.get_layer_version_by_arn(Arn=f"{COUCHE_PANDAS}:{v}")["LayerVersionArn"]
        except ClientError:
            continue
    raise RuntimeError("couche AWSSDKPandas-Python312 introuvable dans cette région")


def empaqueter():
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        for nom, chemin in FICHIERS.items():
            z.write(chemin, nom)
    octets = tampon.getvalue()
    print(f"Code empaqueté : {len(octets):,} octets ({', '.join(FICHIERS)})".replace(",", " "))
    return octets


def deployer(zip_octets, arn_role, couche, seau):
    configuration = dict(
        Runtime=RUNTIME, Role=arn_role, Handler="lambda_outils.handler", Timeout=60, MemorySize=1024,
        Layers=[couche], Environment={"Variables": {"SEAU_DONNEES": seau, "CACHE_DONNEES": "/tmp/cache_donnees"}},
        Description="Outils de calcul de l'agent AlphaForge (pistes A et B), données lues sur S3")
    try:
        lam.get_function(FunctionName=NOM_FONCTION)
        existe = True
    except ClientError as e:
        if code_erreur(e)[0] != "ResourceNotFoundException":
            raise
        existe = False

    if not existe:
        for essai in range(6):
            try:
                lam.create_function(FunctionName=NOM_FONCTION, Code={"ZipFile": zip_octets}, **configuration)
                print("Fonction créée.")
                break
            except ClientError as e:
                code, message = code_erreur(e)
                if code == "InvalidParameterValueException" and "role" in message.lower() and essai < 5:
                    print("Rôle pas encore propagé, nouvel essai dans 5 s.")
                    time.sleep(5)
                    continue
                raise
    else:
        lam.update_function_code(FunctionName=NOM_FONCTION, ZipFile=zip_octets)
        lam.get_waiter("function_updated_v2").wait(FunctionName=NOM_FONCTION)
        lam.update_function_configuration(FunctionName=NOM_FONCTION, **configuration)
        print("Fonction mise à jour (code et configuration).")
    lam.get_waiter("function_active_v2").wait(FunctionName=NOM_FONCTION)
    lam.get_waiter("function_updated_v2").wait(FunctionName=NOM_FONCTION)
    print("État : Active")


def appeler(evenement):
    debut = time.time()
    reponse = lam.invoke(FunctionName=NOM_FONCTION, Payload=json.dumps(evenement).encode("utf-8"))
    charge = json.loads(reponse["Payload"].read())
    return charge, reponse.get("FunctionError"), time.time() - debut


def test_de_fumee():
    demo = {"NVDA": 10000, "QQQ": 12500, "BTC-USD": 5000, "XIU.TO": 17500, "XBB.TO": 5000}
    robert = {"risque": 1.5, "horizon_annees": 4, "objectif": "preservation", "perte_max_toleree": None,
              "crypto": "non", "exclure_secteurs": [], "secteurs_interet": [], "experience": "avance"}
    evenement = {"outil": "evaluer", "portefeuille": demo, "profil": robert}
    for essai in range(4):  # la politique S3 met quelques secondes à se propager
        charge, erreur, duree = appeler(evenement)
        if erreur or not charge.get("ok"):
            print(f"Essai {essai + 1} : {erreur or ''} {charge}")
            time.sleep(5)
            continue
        print(f"Premier appel (démarrage à froid) : {duree:.1f} s, score {charge['resultat']['score']}, "
              f"verdict {charge['resultat']['verdict']}")
        break
    else:
        raise SystemExit("Le test de fumée a échoué : voir les journaux CloudWatch /aws/lambda/" + NOM_FONCTION)
    charge, erreur, duree = appeler({"outil": "simuler", "portefeuille": demo, "profil": robert,
                                     "changement": {"type": "ajouter", "symbole": "NVDA", "montant": 15000}})
    print(f"Second appel (fonction chaude, simuler) : {duree:.1f} s, score de "
          f"{charge['resultat']['avant']['score']} à {charge['resultat']['apres']['score']}")
    charge, erreur, duree = appeler({"outil": "evaluer", "portefeuille": {"NVDA": 1000, "PLTR": 1000}, "profil": robert})
    print("Symbole non couvert :", charge.get("erreur"))


if __name__ == "__main__":
    seau = donnees.seau()
    print(f"=== Déploiement de {NOM_FONCTION} dans {REGION} ===")
    arn = role_arn()
    autoriser_lecture_s3(seau)
    couche = couche_pandas_arn()
    print("Couche pandas :", couche)
    deployer(empaqueter(), arn, couche, seau)
    print("\n=== Test de fumée ===")
    test_de_fumee()
    print(f"\nJournaux : CloudWatch > Log groups > /aws/lambda/{NOM_FONCTION}")
