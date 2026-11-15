"""Piste C : l'agent. Expose demander(texte, portefeuille, profil).

L'agent tourne sur Amazon Bedrock (API Converse, via boto3). Il ne calcule rien :
il choisit des outils Python (piste A pour les mesures, piste B pour le score et les
scénarios), lit leurs résultats et les explique. Le code vérifie ensuite la réponse
(mots interdits, nombres cités) avant de la renvoyer à l'interface.

Lancer `python piste_c.py` pour une démonstration sur le persona Robert.
Changer de modèle :  MODELE_BEDROCK=us.anthropic.claude-sonnet-5-5 python piste_c.py
"""
import csv
import json
import logging
import math
import os
import re
import time
import unicodedata
import warnings

warnings.filterwarnings("ignore", module="boto3")  # avertissement « Python 3.9 »

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

import donnees
from piste_b import dollars, evaluer, pct, proposer_scenarios, simuler

try:  # la vraie piste A quand elle existe, sinon les chiffres inventés de faux.py
    from piste_a import analyser
    SOURCE_MESURES = "piste_a"
except ImportError:
    from faux import analyser
    SOURCE_MESURES = "faux"

# ------------------------------------------------------------------ réglages
REGION = boto3.session.Session().region_name or "us-east-1"
MODELE = os.environ.get("MODELE_BEDROCK", "us.anthropic.claude-opus-5-5")
MAX_TOURS = 8            # appels au modèle par demande, outils compris
MAX_CORRECTIONS = 2      # régénérations permises quand la gouvernance refuse une réponse
MAX_JETONS_SORTIE = 4000

journal = logging.getLogger("piste_c")
journal.setLevel(logging.INFO)
_client = None
_journal_actif = False


class JournalCloudWatch(logging.Handler):
    """Envoie chaque ligne de trace dans CloudWatch Logs : groupe /alphaforge/agent, un flux par session."""
    GROUPE = "/alphaforge/agent"

    def __init__(self):
        super().__init__()
        self.logs = boto3.client("logs", region_name=REGION)
        self.flux = time.strftime("session-%Y%m%d-%H%M%S")
        self.panne = False
        for creer, args in ((self.logs.create_log_group, {"logGroupName": self.GROUPE}),
                            (self.logs.create_log_stream, {"logGroupName": self.GROUPE, "logStreamName": self.flux})):
            try:
                creer(**args)
            except ClientError as e:
                if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                    raise

    def emit(self, record):
        if self.panne:
            return
        try:
            self.logs.put_log_events(logGroupName=self.GROUPE, logStreamName=self.flux,
                                     logEvents=[{"timestamp": int(record.created * 1000),
                                                 "message": self.format(record)}])
        except Exception as e:  # identifiants expirés, réseau coupé : on continue sans CloudWatch
            self.panne = True
            journal.warning("Trace CloudWatch interrompue : %s", e)


def activer_journal():
    """Branche la trace au premier appel : console en local, CloudWatch si AWS répond.
    Mettre JOURNAL_CLOUDWATCH=0 dans l'environnement pour rester en local."""
    global _journal_actif
    if _journal_actif:
        return
    _journal_actif = True
    if not journal.handlers and not logging.getLogger().handlers:
        import sys
        sys.stderr.reconfigure(errors="backslashreplace")
        journal.addHandler(logging.StreamHandler())
    if os.environ.get("JOURNAL_CLOUDWATCH", "1") == "0":
        return
    try:
        journal.addHandler(JournalCloudWatch())
    except (ClientError, BotoCoreError) as e:
        journal.warning("Trace CloudWatch indisponible : %s", e)


def client_bedrock():
    """Client créé au premier appel, pas à l'import : app.py doit pouvoir démarrer sans AWS."""
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=REGION,
                               config=Config(retries={"max_attempts": 6, "mode": "adaptive"},
                                             read_timeout=180))
    return _client


def journaliser(evenement, **champs):
    """Une ligne JSON par événement : lisible en local, et prête pour CloudWatch."""
    journal.info(json.dumps({"evenement": evenement, **champs}, ensure_ascii=False, default=str))


# ------------------------------------------------------------ consigne système
CONSIGNE = """Tu es l'agent de « Diversifié pour qui ? », un outil pédagogique de simulation. Il mesure
un portefeuille une fois, puis compare chaque mesure à une cible qui dépend du profil de la personne.

Règles absolues :
1. Tu ne calcules jamais. Tous les chiffres viennent des outils. Tu ne cites que des nombres présents
   dans leurs résultats, avec le même arrondi, et tu dis de quel outil ou de quelle mesure chacun vient.
2. Aucun conseil personnalisé. Jamais « achète », « vends », « tu devrais », « vous devriez »,
   « je recommande », « je conseille », « le meilleur choix ». Tu décris des faits (« NVDA porte 41,7 %
   du risque ») et des scénarios fictifs (« si X passait de 20 % à 10 %, le score passerait de 64 à 78 »),
   avec ce qui s'améliore et ce qui se dégrade. La décision appartient à la personne.
3. Aucune prévision de rendement. Les mesures reposent sur la covariance historique, jamais sur un
   rendement espéré.
4. Chaque chiffre porte sa cible, son hypothèse ou sa limite. Tu dis ce que l'outil ne sait pas.
5. Simulation seulement : aucune transaction réelle, aucune donnée bancaire.

Trois types de demandes :
- Diagnostic (« suis-je trop concentrée ? ») : appelle evaluer, puis explique les trois notes et les alertes.
- Scénario (« je veux ajouter 15 000 $ de X ») : reformule d'abord ce que tu as compris (type de
  changement, titre, montant), appelle simuler, puis présente avant et après.
- Explication (« d'où vient ce chiffre ? ») : appelle evaluer et explique la mesure, sa cible et son hypothèse.

Si une demande est incohérente avec le profil (par exemple un titre très risqué pour un profil prudent),
tu ne refuses pas et tu n'approuves pas : tu appelles simuler, tu montres avec les chiffres quelles cibles
seraient dépassées, et tu nommes l'écart entre la demande et le profil.

Style : français, au plus trois paragraphes courts ou une liste courte, sans titre ni tableau. Écris les
nombres exactement comme les outils les donnent (virgule décimale, « % », « $ »). Termine par une phrase
sur ce que la mesure ne dit pas.
Niveau d'expérience de la personne : {experience}. {consigne_experience}

Profil, déjà fourni par l'interface (ne pas le redemander) : {profil}
Portefeuille en dollars canadiens, déjà fourni : {portefeuille}
Source des mesures : {source}.
Univers couvert par les données ({nb_actifs} actifs) : {univers}.
Symboles du portefeuille non couverts par les données : {non_couverts}. S'il y en a, dis-le : leurs
mesures ne sont pas fiables. Aucun ajout d'un symbole hors de l'univers ne peut être simulé."""

CONSIGNES_EXPERIENCE = {
    "debutant": "Définis chaque terme technique en quelques mots simples (volatilité, perte maximale, "
                "paris effectifs, contribution au risque) et évite le jargon.",
    "intermediaire": "Utilise les termes techniques courants sans les définir longuement.",
    "avance": "Vocabulaire technique direct, pas de définitions, va droit aux chiffres.",
}

# ------------------------------------------------------------------- outils
# Le portefeuille et le profil ne sont jamais des paramètres : le code les injecte,
# le modèle ne peut donc pas se tromper sur un montant.
SANS_PARAMETRE = {"json": {"type": "object", "properties": {}}}
OUTILS = [
    {"toolSpec": {
        "name": "analyser",
        "description": "Mesure le portefeuille : volatilité annuelle, perte maximale historique, poids "
                       "et contribution au risque de chaque titre, répartition par classe et par secteur, "
                       "capital total. Aucun paramètre : le portefeuille est déjà fourni.",
        "inputSchema": SANS_PARAMETRE}},
    {"toolSpec": {
        "name": "evaluer",
        "description": "Compare les mesures du portefeuille aux cibles du profil : score de 0 à 100, "
                       "verdict, trois notes (niveau_de_risque, risque_de_perte, diversification) avec "
                       "valeur, cible et explication, alertes (contrainte ou avertissement) et hypothèses. "
                       "Aucun paramètre.",
        "inputSchema": SANS_PARAMETRE}},
    {"toolSpec": {
        "name": "simuler",
        "description": "Calcule un scénario fictif et compare avant et après : score, notes, alertes levées "
                       "ou nouvelles, ce qui s'améliore et ce qui se dégrade. Types : « ajouter » (argent "
                       "nouveau sur un titre, le total augmente), « plafonner » (ramener un titre à un poids "
                       "maximal, le montant libéré réparti au prorata sur les autres lignes), « retirer » "
                       "(sortir un titre, montant réparti au prorata).",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["ajouter", "plafonner", "retirer"]},
                "symbole": {"type": "string", "description": "Symbole boursier de l'univers couvert, ex. NVDA ou XIU.TO"},
                "montant": {"type": "number", "description": "Pour « ajouter » : montant en dollars canadiens"},
                "poids_max": {"type": "number", "description": "Pour « plafonner » : poids maximal en décimal, "
                                                               "ex. 0.10 pour 10 %"}},
            "required": ["type", "symbole"]}}}},
    {"toolSpec": {
        "name": "proposer_scenarios",
        "description": "Propose jusqu'à trois scénarios fictifs qui rapprochent le portefeuille des cibles du "
                       "profil, chacun avec avant, après, ce qui s'améliore et ce qui se dégrade. Aucun paramètre.",
        "inputSchema": SANS_PARAMETRE}},
]


_univers = None


def univers_couvert():
    """Symboles de assets_universe.csv, lus via donnees.py (S3, puis copie locale). None si introuvable."""
    global _univers
    if _univers is None:
        try:
            with open(donnees.chemin_local("assets_universe.csv"), encoding="utf-8", newline="") as f:
                _univers = {ligne["ticker"].strip().upper() for ligne in csv.DictReader(f)}
        except Exception as e:  # sans la liste, on ne bloque pas : on le dira dans les limites
            journal.warning("Univers des actifs indisponible : %s", e)
            _univers = set()
    return _univers or None


def symboles_non_couverts(symboles):
    """Symboles absents du jeu de données ; liste vide si l'univers n'est pas disponible."""
    univers = univers_couvert()
    if univers is None:
        return []
    return sorted(s for s in symboles if str(s).strip().upper() not in univers)


def valider_changement(args, portefeuille, univers=None):
    """Transforme les arguments du modèle en changement valide pour piste_b.simuler."""
    genre = args.get("type")
    symbole = str(args.get("symbole", "")).strip().upper()
    if genre not in ("ajouter", "plafonner", "retirer"):
        raise ValueError(f"type de changement inconnu : {genre}")
    if not symbole:
        raise ValueError("symbole manquant")
    if genre == "ajouter":
        montant = float(args.get("montant") or 0)
        if montant <= 0:
            raise ValueError("montant manquant ou négatif pour un ajout")
        if univers is not None and symbole not in univers:
            raise ValueError(f"{symbole} n'est pas couvert par le jeu de données ({len(univers)} actifs) : "
                             "son ajout ne peut pas être simulé")
        return {"type": "ajouter", "symbole": symbole, "montant": montant}
    if symbole not in portefeuille:
        raise ValueError(f"{symbole} n'est pas dans le portefeuille")
    if genre == "retirer":
        return {"type": "retirer", "symbole": symbole}
    poids = float(args.get("poids_max", -1))
    if poids > 1:
        poids = poids / 100  # le modèle a donné un pourcentage
    if not 0 <= poids < 1:
        raise ValueError("poids_max doit être un décimal entre 0 et 1")
    return {"type": "plafonner", "symbole": symbole, "poids_max": poids}


def resume_changement(c):
    if c["type"] == "ajouter":
        return f"ajout de {dollars(c['montant'])} de {c['symbole']}"
    if c["type"] == "plafonner":
        return f"plafonnement de {c['symbole']} à {pct(c['poids_max'])}"
    return f"retrait de {c['symbole']}"


def executer_outil(nom, args, portefeuille, profil):
    """Renvoie (résultat, résumé d'une ligne pour le volet « Ce que l'agent a fait »)."""
    if nom == "analyser":
        r = analyser(portefeuille)
        return r, f"{len(portefeuille)} titres analysés, capital de {dollars(r['capital'])}"
    if nom == "evaluer":
        r = evaluer(analyser(portefeuille), profil)
        return r, f"score de {r['score']} sur 100, verdict {r['verdict']}, {len(r['alertes'])} alerte(s)"
    if nom == "simuler":
        changement = valider_changement(args, portefeuille, univers_couvert())
        r = simuler(portefeuille, changement, profil, analyser)
        return r, f"{resume_changement(changement)} : score de {r['avant']['score']} à {r['apres']['score']}"
    if nom == "proposer_scenarios":
        r = proposer_scenarios(portefeuille, profil, analyser)
        return r, f"{len(r)} scénario(s) retenu(s)"
    raise ValueError(f"outil inconnu : {nom}")


def _natif(objet):
    """Convertit les scalaires numpy en types Python pour la sérialisation JSON."""
    if hasattr(objet, "item"):
        return objet.item()
    return str(objet)


def json_simple(resultat):
    return json.loads(json.dumps(resultat, default=_natif))


# -------------------------------------------------------------- gouvernance
_RE_NOMBRE = re.compile(r"(?<![\w.,])\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|(?<![\w.,])\d+(?:[.,]\d+)?")
_RE_MARQUEUR_LISTE = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)
_RE_INTERDITS = re.compile(
    r"\b(achet(e|es|ez|er)|vend(s|ez|re)|tu devrais|vous devriez"
    r"|recommand(e|es|ons|ez|erais|erait|eriez)|conseill(e|es|ons|ez|erais|erait|eriez)"
    r"|meilleur choix)\b")


def sans_accents(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn").lower()


def mots_interdits(texte):
    return sorted({m.group(1) for m in _RE_INTERDITS.finditer(sans_accents(texte))})


def _vers_nombre(chaine):
    propre = re.sub(r"[   ]", "", chaine).replace(",", ".")
    decimales = len(propre.split(".")[1]) if "." in propre else 0
    return float(propre), decimales


def _collecter_nombres(objet, acc):
    """Tous les nombres d'un résultat d'outil, bruts et en pourcentage, y compris dans les textes."""
    if isinstance(objet, bool):
        return
    if isinstance(objet, (int, float)):
        acc.add(float(objet))
        acc.add(100 * float(objet))
    elif isinstance(objet, str):
        for m in _RE_NOMBRE.finditer(objet):
            acc.add(_vers_nombre(m.group())[0])
    elif isinstance(objet, dict):
        if "avant" in objet and "apres" in objet:
            try:  # la différence de score avant/après est tolérée
                acc.add(abs(float(objet["apres"]["score"]) - float(objet["avant"]["score"])))
            except (KeyError, TypeError, ValueError):
                pass
        for v in objet.values():
            _collecter_nombres(v, acc)
    elif isinstance(objet, (list, tuple)):
        for v in objet:
            _collecter_nombres(v, acc)


def nombres_connus(resultats, texte, portefeuille, profil, supplement=None):
    acc = {0.0, 100.0}
    for source in (resultats, texte, portefeuille, profil, supplement):
        _collecter_nombres(source, acc)
    return acc


def _connu(valeur, decimales, connus):
    facteur = 10 ** decimales
    for c in connus:
        if abs(round(c, decimales) - valeur) < 1e-6 or abs(math.floor(c * facteur) / facteur - valeur) < 1e-6:
            return True
    return False


def nombres_inconnus(texte, connus):
    corps = _RE_MARQUEUR_LISTE.sub("", texte)
    inconnus = []
    for m in _RE_NOMBRE.finditer(corps):
        valeur, decimales = _vers_nombre(m.group())
        if not _connu(valeur, decimales, connus) and m.group() not in inconnus:
            inconnus.append(m.group())
    return inconnus


def verifier(reponse, resultats, texte, portefeuille, profil, supplement=None):
    """Renvoie la liste des problèmes de gouvernance (vide si la réponse est acceptable)."""
    problemes = []
    mots = mots_interdits(reponse)
    if mots:
        problemes.append("mots interdits : " + ", ".join(mots))
    inconnus = nombres_inconnus(reponse, nombres_connus(resultats, texte, portefeuille, profil, supplement))
    if inconnus:
        problemes.append("nombres absents des résultats d'outils : " + ", ".join(inconnus))
    return problemes


def consigne_de_correction(problemes):
    return ("Contrôle de gouvernance : ta réponse a été refusée (" + " ; ".join(problemes) + "). "
            "Réécris-la entièrement : aucun mot prescriptif, et uniquement des nombres qui figurent "
            "dans les résultats des outils, avec le même arrondi (rappelle un outil si besoin). "
            "Ne mentionne pas ce contrôle.")


def reponse_de_secours(portefeuille, profil, trace):
    """Réponse factuelle construite sans modèle de langage, à partir de evaluer."""
    r = evaluer(analyser(portefeuille), profil)
    trace.append({"outil": "evaluer", "resume": f"score de {r['score']} sur 100 (réponse de secours)"})
    lignes = [f"Score d'adéquation de {r['score']} sur 100, verdict : {r['verdict'].replace('_', ' ')}."]
    lignes += [n["explication"] for n in r["notes"]]
    lignes += [a["message"] for a in r["alertes"]]
    return " ".join(lignes)


# ----------------------------------------------------------- boucle d'agent
def _messages_initiaux(texte, historique):
    """Convertit l'historique de l'interface en messages Converse, puis ajoute la demande."""
    messages = []
    for m in historique or []:
        role = "assistant" if m.get("role") == "assistant" else "user"
        contenu = str(m.get("texte") or m.get("content") or "").strip()
        if not contenu:
            continue
        if messages and messages[-1]["role"] == role:  # Converse exige l'alternance des rôles
            messages[-1]["content"][0]["text"] += "\n" + contenu
        else:
            messages.append({"role": role, "content": [{"text": contenu}]})
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    if messages and messages[-1]["role"] == "user":
        if messages[-1]["content"][0]["text"].strip() != texte.strip():
            messages[-1]["content"][0]["text"] += "\n" + texte
    else:
        messages.append({"role": "user", "content": [{"text": texte}]})
    return messages


def _hypotheses(resultats):
    """Toutes les hypothèses déclarées par les outils, sans doublon, dans l'ordre."""
    vues, liste = set(), []

    def parcourir(o):
        if isinstance(o, dict):
            for h in o.get("hypotheses", []) or []:
                if h not in vues:
                    vues.add(h)
                    liste.append(h)
            for v in o.values():
                parcourir(v)
        elif isinstance(o, list):
            for v in o:
                parcourir(v)

    parcourir(resultats)
    return liste


def _texte_du_message(message):
    return " ".join(b["text"] for b in message["content"] if "text" in b).strip()


def demander(texte, portefeuille, profil, historique=None):
    """Point d'entrée de la piste C. Ne lève jamais : en cas de panne, réponse de secours + limites."""
    activer_journal()
    debut = time.time()
    trace, limites, resultats = [], [], []
    experience = profil.get("experience") or "intermediaire"
    univers = univers_couvert()
    non_couverts = symboles_non_couverts(portefeuille)
    if univers is None:
        limites.append("Liste des actifs couverts indisponible : la couverture des symboles n'a pas pu être vérifiée.")
    if non_couverts:
        limites.append("Symboles non couverts par le jeu de données : " + ", ".join(non_couverts)
                       + ". Leurs mesures ne sont pas fiables.")
    supplement = {"nb_actifs": len(univers or [])}  # nombres que le modèle peut citer sans outil
    systeme = [{"text": CONSIGNE.format(
        experience=experience,
        consigne_experience=CONSIGNES_EXPERIENCE.get(experience, CONSIGNES_EXPERIENCE["intermediaire"]),
        profil=json.dumps(profil, ensure_ascii=False),
        portefeuille=json.dumps(portefeuille, ensure_ascii=False),
        source=SOURCE_MESURES,
        nb_actifs=len(univers or []),
        univers=", ".join(sorted(univers)) if univers else "inconnu",
        non_couverts=", ".join(non_couverts) or "aucun")}]
    messages = _messages_initiaux(texte, historique)
    reponse, corrections = None, 0
    journaliser("demande", texte=texte, modele=MODELE, experience=experience, non_couverts=non_couverts)

    try:
        for tour in range(1, MAX_TOURS + 1):
            sortie = client_bedrock().converse(
                modelId=MODELE, system=systeme, messages=messages,
                toolConfig={"tools": OUTILS}, inferenceConfig={"maxTokens": MAX_JETONS_SORTIE})
            message = sortie["output"]["message"]
            messages.append(message)  # le message complet, blocs de raisonnement compris
            journaliser("modele", tour=tour, stop=sortie["stopReason"], usage=sortie.get("usage"))

            if sortie["stopReason"] == "tool_use":
                retours = []
                for bloc in message["content"]:
                    if "toolUse" not in bloc:
                        continue
                    appel = bloc["toolUse"]
                    nom, args = appel["name"], appel.get("input") or {}
                    try:
                        resultat, resume = executer_outil(nom, args, portefeuille, profil)
                        resultat = json_simple(resultat)
                        resultats.append(resultat)
                        trace.append({"outil": nom, "resume": resume})
                        journaliser("outil", outil=nom, arguments=args, resume=resume)
                        contenu = {"json": resultat if isinstance(resultat, dict) else {"scenarios": resultat}}
                        retours.append({"toolResult": {"toolUseId": appel["toolUseId"], "content": [contenu]}})
                    except Exception as e:  # l'outil a échoué : on le dit, on n'invente pas
                        trace.append({"outil": nom, "resume": f"échec : {e}"})
                        limites.append(f"L'outil {nom} a échoué ({e}) : la réponse ne s'appuie pas dessus.")
                        journaliser("outil_echec", outil=nom, arguments=args, erreur=str(e))
                        retours.append({"toolResult": {"toolUseId": appel["toolUseId"], "status": "error",
                                                       "content": [{"text": f"Erreur : {e}"}]}})
                messages.append({"role": "user", "content": retours})  # tous les résultats en un message
                continue

            candidat = _texte_du_message(message)
            if sortie["stopReason"] == "max_tokens":
                limites.append("Réponse tronquée : la limite de longueur du modèle a été atteinte.")
            problemes = verifier(candidat, resultats, texte, portefeuille, profil, supplement)
            journaliser("verification", problemes=problemes, correction=corrections)
            if problemes and corrections < MAX_CORRECTIONS:
                corrections += 1
                messages.append({"role": "user", "content": [{"text": consigne_de_correction(problemes)}]})
                continue
            if problemes:
                if any(p.startswith("mots interdits") for p in problemes):
                    candidat = reponse_de_secours(portefeuille, profil, trace)
                    limites.append("La réponse du modèle a été remplacée par un résumé factuel : elle gardait "
                                   "un vocabulaire prescriptif malgré deux corrections.")
                for p in problemes:
                    if p.startswith("nombres"):
                        limites.append("Non vérifié : " + p + ".")
            reponse = candidat
            break
        else:
            limites.append(f"L'agent a atteint la limite de {MAX_TOURS} tours sans conclure.")
            reponse = reponse_de_secours(portefeuille, profil, trace)
    except (ClientError, BotoCoreError) as e:
        code = getattr(e, "response", {}).get("Error", {}).get("Code", type(e).__name__)
        journaliser("bedrock_echec", code=code, erreur=str(e))
        limites.append(f"Bedrock injoignable ({code}) : réponse de secours calculée localement, sans modèle.")
        reponse = reponse_de_secours(portefeuille, profil, trace)

    limites += _hypotheses(resultats)
    try:  # les hypothèses des données (période, devises, source S3) : la piste B ne les fait pas suivre
        limites += analyser(portefeuille).get("hypotheses", [])
    except Exception as e:
        limites.append(f"Les mesures du portefeuille n'ont pas pu être calculées : {e}")
    if SOURCE_MESURES == "faux":
        limites.append("Mesures issues de faux.py (chiffres inventés) : la piste A n'est pas encore branchée.")
    limites = list(dict.fromkeys(limites))
    journaliser("reponse", duree_s=round(time.time() - debut, 1), outils=len(trace), corrections=corrections)
    return {"reponse": reponse, "outils_appeles": trace, "limites": limites}


# ------------------------------------------------------------ démonstration
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    PORTEFEUILLE = {"NVDA": 10000, "QQQ": 12500, "BTC-USD": 5000, "XIU.TO": 17500, "XBB.TO": 5000}
    ROBERT = {"risque": 1.5, "horizon_annees": 4, "objectif": "preservation", "perte_max_toleree": None,
              "crypto": "non", "exclure_secteurs": [], "secteurs_interet": [], "experience": "avance"}
    QUESTIONS = ["Est-ce que ce portefeuille me convient ?",            # diagnostic
                 "Je veux ajouter 15 000 $ de NVDA, tout le monde en parle.",  # scénario : test de Robert
                 "D'où vient le chiffre de perte maximale ?"]             # explication

    print(f"Modèle : {MODELE}  |  région : {REGION}  |  mesures : {SOURCE_MESURES}\n")
    for question in QUESTIONS:
        print("=" * 78)
        print("QUESTION :", question)
        r = demander(question, PORTEFEUILLE, ROBERT)
        print("\nRÉPONSE :\n" + r["reponse"])
        print("\nCe que l'agent a fait :")
        for appel in r["outils_appeles"]:
            print(f"  - {appel['outil']} : {appel['resume']}")
        print("Limites :")
        for limite in r["limites"]:
            print("  - " + limite)
        print()
