"""Accès aux données du datathon : S3 d'abord, copie locale du dépôt en secours.

Pour la piste A :
    from donnees import charger, chemin_local, provenance
    prix = charger("prices_daily.csv")        # DataFrame pandas
    univers = charger("assets_universe.csv")
    print(provenance())                       # d'où vient chaque fichier lu, à reprendre dans les limites

En ligne de commande :
    python donnees.py televerser    # dépose data/alphaforge_starter/ sur S3 (à refaire si les données changent)
    python donnees.py               # test : lit l'univers et les prix depuis S3 et les résume

Ordre de lecture : cache local de S3 (.cache_donnees/), sinon téléchargement depuis S3,
sinon la copie du dépôt (data/alphaforge_starter/). Sur Lambda, seul S3 existe.
Le seau : variable d'environnement SEAU_DONNEES, sinon alphaforge-<numéro de compte>-donnees.
"""
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", module="boto3")

import boto3
from botocore.exceptions import BotoCoreError, ClientError

ICI = Path(__file__).resolve().parent
DOSSIER_LOCAL = ICI / "data" / "alphaforge_starter"
DOSSIER_CACHE = Path(os.environ.get("CACHE_DONNEES", ICI / ".cache_donnees"))
PREFIXE = "alphaforge_starter/"  # « dossier » dans le seau
FICHIERS = ["prices_daily.csv", "assets_universe.csv", "fx_usdcad_daily.csv", "macro_rates.csv",
            "corporate_actions.csv", "sources_metadata.csv", "data_quality_warnings.txt",
            "README.md", "build_dataset.py"]
REGION = boto3.session.Session().region_name or "us-east-1"

_seau = None
_provenance = {}


def seau():
    """Nom du seau, résolu une seule fois (le numéro de compte vient de STS)."""
    global _seau
    if _seau is None:
        _seau = os.environ.get("SEAU_DONNEES")
        if not _seau:
            compte = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
            _seau = f"alphaforge-{compte}-donnees"
    return _seau


def chemin_local(nom, forcer_s3=False):
    """Renvoie un chemin lisible pour `nom`, en le téléchargeant depuis S3 si besoin."""
    cache = DOSSIER_CACHE / nom
    if cache.exists() and not forcer_s3:
        _provenance[nom] = "cache local du fichier S3"
        return cache
    try:
        DOSSIER_CACHE.mkdir(parents=True, exist_ok=True)
        boto3.client("s3", region_name=REGION).download_file(seau(), PREFIXE + nom, str(cache))
        _provenance[nom] = f"s3://{seau()}/{PREFIXE}{nom}"
        return cache
    except (ClientError, BotoCoreError, OSError) as e:  # S3 injoignable, identifiants expirés, cache inaccessible
        local = DOSSIER_LOCAL / nom
        if local.exists():
            _provenance[nom] = f"copie locale du dépôt (S3 injoignable : {type(e).__name__})"
            return local
        raise FileNotFoundError(f"{nom} introuvable : ni sur S3 ({e}), ni dans {DOSSIER_LOCAL}") from e


def charger(nom, forcer_s3=False, **options):
    """Lit un CSV en DataFrame pandas. pandas est importé ici pour que piste_c n'en dépende pas."""
    import pandas as pd
    return pd.read_csv(chemin_local(nom, forcer_s3), **options)


def provenance():
    """Une phrase par fichier lu, prête pour les limites affichées à l'utilisateur."""
    return [f"{nom} lu depuis {source}." for nom, source in _provenance.items()]


def televerser():
    s3 = boto3.client("s3", region_name=REGION)
    for nom in FICHIERS:
        chemin = DOSSIER_LOCAL / nom
        if not chemin.exists():
            print("  absent, ignoré :", nom)
            continue
        s3.upload_file(str(chemin), seau(), PREFIXE + nom)
        print(f"  {PREFIXE + nom:<42} {chemin.stat().st_size:>10} octets")
    objets = s3.list_objects_v2(Bucket=seau(), Prefix=PREFIXE).get("Contents", [])
    print(f"{len(objets)} objets sous s3://{seau()}/{PREFIXE}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "televerser":
        televerser()
    else:
        univers = charger("assets_universe.csv", forcer_s3=True)
        prix = charger("prices_daily.csv", forcer_s3=True)
        print(f"{len(univers)} actifs ; {len(prix)} lignes de prix, du {prix['date'].min()} au {prix['date'].max()}")
        for ligne in provenance():
            print("-", ligne)
