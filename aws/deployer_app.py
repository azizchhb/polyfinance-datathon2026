"""Met l'application Streamlit en ligne sur une machine EC2 du compte AWS.

Lancer depuis la racine du dépôt : python aws/deployer_app.py
    (sans option)   crée ce qui manque, ou affiche l'adresse si la machine tourne déjà
    --mettre-a-jour redémarre la machine : au démarrage, elle récupère la dernière version de main
    --supprimer     arrête et supprime la machine (le rôle et le pare-feu restent, ils ne coûtent rien)
    --fermer-port   n'accepte plus que CloudFront sur le port 80 (à lancer une fois le HTTPS vérifié)

Pourquoi EC2 avec un rôle IAM : la machine reçoit ses droits AWS par son rôle, comme la Lambda.
Aucune clé n'est copiée nulle part (règle 6). Le rôle ne permet que ce dont l'application a
besoin : appeler Bedrock, invoquer la Lambda des outils, lire le seau de données, écrire les traces.

Au démarrage, la machine clone le dépôt public GitHub, installe requirements.txt et lance
Streamlit comme service systemd sur le port 80 (relancé automatiquement en cas d'arrêt).

Devant la machine, une distribution CloudFront sert le site en HTTPS (certificat fourni par AWS)
et garde la même adresse si la machine redémarre. Aucun cache : chaque page est dynamique.
Streamlit passe par une WebSocket, que CloudFront relaie.
"""
import json
import sys
import time

import boto3

REGION = boto3.session.Session().region_name or "us-east-1"
DEPOT = "https://github.com/azizchhb/polyfinance-datathon2026.git"
NOM = "alphaforge-app"
TYPE_MACHINE = "t3.small"  # 2 Go de mémoire : pandas et Streamlit tiennent à l'aise
AMI = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"

iam = boto3.client("iam")
ec2 = boto3.client("ec2", region_name=REGION)
compte = boto3.client("sts").get_caller_identity()["Account"]

# Script exécuté une fois par la machine à son premier démarrage (« user data »).
DEMARRAGE = f"""#!/bin/bash
set -ex
dnf install -y git python3.11 python3.11-pip
git clone {DEPOT} /opt/app
python3.11 -m pip install -r /opt/app/requirements.txt
cat > /etc/systemd/system/alphaforge.service <<'FIN'
[Unit]
Description=Application AlphaForge (Streamlit)
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/opt/app
Environment=AWS_DEFAULT_REGION={REGION}
Environment=HOME=/root
# À chaque démarrage : dernière version de main, puis dépendances au besoin.
ExecStartPre=-/usr/bin/git -C /opt/app pull --ff-only
ExecStartPre=-/usr/bin/python3.11 -m pip install -q -r /opt/app/requirements.txt
ExecStart=/usr/bin/python3.11 -m streamlit run app.py --server.port 80 --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
FIN
systemctl daemon-reload
systemctl enable --now alphaforge.service
"""


def role():
    """Rôle et profil d'instance : les droits AWS de la machine, sans aucune clé."""
    confiance = {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
    droits = {"Version": "2012-10-17", "Statement": [
        {"Sid": "Agent", "Effect": "Allow", "Resource": "*",
         "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]},
        {"Sid": "Outils", "Effect": "Allow", "Action": "lambda:InvokeFunction",
         "Resource": f"arn:aws:lambda:{REGION}:{compte}:function:alphaforge-outils"},
        {"Sid": "Donnees", "Effect": "Allow", "Action": ["s3:GetObject", "s3:ListBucket"],
         "Resource": [f"arn:aws:s3:::alphaforge-{compte}-donnees",
                      f"arn:aws:s3:::alphaforge-{compte}-donnees/*"]},
        {"Sid": "Traces", "Effect": "Allow", "Resource": "*",
         "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
                    "logs:DescribeLogStreams"]},
    ]}
    try:
        iam.create_role(RoleName=f"{NOM}-role", AssumeRolePolicyDocument=json.dumps(confiance),
                        Description="Droits de la machine EC2 qui sert l'application AlphaForge")
        print(f"Rôle {NOM}-role créé.")
    except iam.exceptions.EntityAlreadyExistsException:
        pass
    iam.put_role_policy(RoleName=f"{NOM}-role", PolicyName="alphaforge-app-droits",
                        PolicyDocument=json.dumps(droits))
    try:
        iam.create_instance_profile(InstanceProfileName=f"{NOM}-profil")
        iam.add_role_to_instance_profile(InstanceProfileName=f"{NOM}-profil", RoleName=f"{NOM}-role")
        print("Profil d'instance créé ; IAM met quelques secondes à le propager.")
        time.sleep(15)
    except iam.exceptions.EntityAlreadyExistsException:
        pass


def pare_feu():
    """Groupe de sécurité : seul le port 80 (web) est ouvert, à tout le monde."""
    vpc = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])["Vpcs"][0]["VpcId"]
    existants = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [f"{NOM}-web"]},
                                                      {"Name": "vpc-id", "Values": [vpc]}])["SecurityGroups"]
    if existants:
        return existants[0]["GroupId"]
    groupe = ec2.create_security_group(GroupName=f"{NOM}-web", VpcId=vpc,
                                       Description="Application AlphaForge : port 80 public")["GroupId"]
    ec2.authorize_security_group_ingress(GroupId=groupe, IpPermissions=[{
        "IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])
    print(f"Pare-feu {groupe} créé (port 80).")
    return groupe


def machine_existante():
    reservations = ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": [NOM]},
        {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}])
    instances = [i for r in reservations["Reservations"] for i in r["Instances"]]
    return instances[0] if instances else None


def lancer(groupe):
    ami = boto3.client("ssm", region_name=REGION).get_parameter(Name=AMI)["Parameter"]["Value"]
    for essai in range(6):  # le profil d'instance tout neuf peut ne pas être encore visible
        try:
            instance = ec2.run_instances(
                ImageId=ami, InstanceType=TYPE_MACHINE, MinCount=1, MaxCount=1,
                SecurityGroupIds=[groupe], UserData=DEMARRAGE,
                IamInstanceProfile={"Name": f"{NOM}-profil"},
                MetadataOptions={"HttpTokens": "required", "HttpPutResponseHopLimit": 2},
                TagSpecifications=[{"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": NOM}]}],
            )["Instances"][0]
            print(f"Machine {instance['InstanceId']} lancée ({TYPE_MACHINE}).")
            return instance["InstanceId"]
        except ec2.exceptions.ClientError as erreur:
            if "iamInstanceProfile" not in str(erreur) or essai == 5:
                raise
            time.sleep(10)


def adresse(identifiant):
    ec2.get_waiter("instance_running").wait(InstanceIds=[identifiant])
    instance = ec2.describe_instances(InstanceIds=[identifiant])["Reservations"][0]["Instances"][0]
    return instance


# Politiques gérées par AWS : aucun cache, et tous les en-têtes, cookies et paramètres transmis
# à la machine (nécessaire pour la WebSocket et les sessions Streamlit).
SANS_CACHE = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"   # Managed-CachingDisabled
TOUT_TRANSMETTRE = "216adef6-5c7f-47e4-b989-5492eafa07d3"  # Managed-AllViewer


def distribution(dns_machine):
    """Distribution CloudFront en HTTPS devant la machine ; la crée si elle manque."""
    cloudfront = boto3.client("cloudfront")
    for d in cloudfront.list_distributions().get("DistributionList", {}).get("Items", []):
        if d["Comment"] == NOM:
            return d["DomainName"], d["Id"]
    config = {
        "CallerReference": f"{NOM}-{int(time.time())}", "Comment": NOM, "Enabled": True,
        "PriceClass": "PriceClass_100", "HttpVersion": "http2",
        "Origins": {"Quantity": 1, "Items": [{
            "Id": "machine", "DomainName": dns_machine,
            "CustomOriginConfig": {"HTTPPort": 80, "HTTPSPort": 443, "OriginProtocolPolicy": "http-only",
                                   "OriginReadTimeout": 60, "OriginKeepaliveTimeout": 60}}]},
        "DefaultCacheBehavior": {
            "TargetOriginId": "machine", "ViewerProtocolPolicy": "redirect-to-https", "Compress": True,
            "CachePolicyId": SANS_CACHE, "OriginRequestPolicyId": TOUT_TRANSMETTRE,
            "AllowedMethods": {"Quantity": 7, "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
                               "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}}},
    }
    d = cloudfront.create_distribution(DistributionConfig=config)["Distribution"]
    print("Distribution CloudFront créée : 5 à 10 minutes avant qu'elle réponde.")
    return d["DomainName"], d["Id"]


def fermer_port():
    """Port 80 réservé aux serveurs de CloudFront : plus d'accès direct par l'adresse IP en HTTP."""
    groupe = pare_feu()
    liste = ec2.describe_managed_prefix_lists(Filters=[{
        "Name": "prefix-list-name", "Values": ["com.amazonaws.global.cloudfront.origin-facing"]}])
    liste = liste["PrefixLists"][0]["PrefixListId"]
    try:
        ec2.authorize_security_group_ingress(GroupId=groupe, IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "PrefixListIds": [{"PrefixListId": liste}]}])
    except ec2.exceptions.ClientError as erreur:
        if "Duplicate" not in str(erreur):
            raise
    try:
        ec2.revoke_security_group_ingress(GroupId=groupe, IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])
    except ec2.exceptions.ClientError:
        pass
    print("Port 80 fermé au public : seul CloudFront atteint la machine.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    existante = machine_existante()
    if "--supprimer" in sys.argv:
        if existante:
            ec2.terminate_instances(InstanceIds=[existante["InstanceId"]])
            print(f"Machine {existante['InstanceId']} supprimée.")
        sys.exit()
    if existante and "--mettre-a-jour" in sys.argv:
        ec2.reboot_instances(InstanceIds=[existante["InstanceId"]])
        print("Redémarrage : la machine récupère main et relance l'application (environ 1 minute).")
    if "--fermer-port" in sys.argv:
        fermer_port()
        sys.exit()
    if existante:
        instance = adresse(existante["InstanceId"])
    else:
        role()
        instance = adresse(lancer(pare_feu()))
        print("Installation en cours sur la machine (environ 3 à 5 minutes avant que la page réponde).")
    domaine, _ = distribution(instance["PublicDnsName"])
    print(f"Machine : http://{instance.get('PublicIpAddress')}")
    print(f"Adresse publique : https://{domaine}")
