"""Les 3 personas de l'énoncé + un portefeuille fictif pour chacun.

Les limites chiffrées sont NOS hypothèses (pas une règle réglementaire) : elles traduisent
le profil de risque et l'horizon de chaque persona. Elles sont affichées dans l'app pour être
discutées et modifiées.
"""

PROFILES = {
    "Amira": {
        "nom": "Amira",
        "age": 26,
        "profession": "Ingénieure logicielle",
        "profil_risque": "Élevé",
        "horizon": "15 ans ou plus",
        "experience": "Intermédiaire",
        "objectif": "Faire croître son capital à long terme.",
        "preferences": [
            "Très intéressée par l'IA et les technologies émergentes",
            "Ouverte aux entreprises en forte croissance et à une volatilité importante",
            "Intéressée par les cryptoactifs",
            "Souhaite garder une certaine diversification, pas seulement de la techno",
        ],
        "exclusions": [],
        "limites": {"volatilite_max_pct": 30, "baisse_max_toleree_pct": 45, "ligne_max_pct": 20,
                    "crypto_max_pct": 15, "techno_max_pct": 50, "defensif_min_pct": 5},
        "portefeuille": {"NVDA": 12000, "SHOP.TO": 8000, "TSLA": 5000, "BTC-USD": 8000,
                         "ETH-USD": 5000, "QQQ": 7000, "MSFT": 5000},
        "test_enonce": "Jusqu'où le système accepte-t-il le risque ? « Risque élevé » ne veut pas dire « tout est acceptable ».",
    },
    "Mateo": {
        "nom": "Mateo",
        "age": 41,
        "profession": "Gestionnaire des opérations",
        "profil_risque": "Modéré",
        "horizon": "8 à 12 ans",
        "experience": "Intermédiaire",
        "objectif": "Croissance équilibrée à moyen et long terme.",
        "preferences": [
            "Grande importance aux facteurs ESG",
            "Éviter les entreprises liées à des controverses environnementales ou sociales importantes",
            "Équilibre entre croissance et stabilité",
            "Ouvert aux technologies émergentes si compatibles avec son risque",
            "Peu intéressé par les placements hautement spéculatifs",
        ],
        "exclusions": ["XOM", "CNQ.TO", "ENB.TO", "BTC-USD", "ETH-USD"],
        "raison_exclusions": "Mateo veut éviter les controverses environnementales (producteurs et transporteurs "
                             "d'énergie fossile) et les placements hautement spéculatifs (cryptos).",
        "limites": {"volatilite_max_pct": 16, "baisse_max_toleree_pct": 25, "ligne_max_pct": 15,
                    "crypto_max_pct": 0, "techno_max_pct": 35, "defensif_min_pct": 30},
        "portefeuille": {"SPY": 30000, "XOM": 15000, "CNQ.TO": 12000, "ENB.TO": 10000, "ESGV": 15000,
                         "AAPL": 15000, "TSLA": 8000, "XBB.TO": 30000, "RY.TO": 15000},
        "test_enonce": "Le système sait-il intégrer autre chose que le rendement et le risque (préférences ESG) ?",
    },
    "Robert": {
        "nom": "Robert",
        "age": 59,
        "profession": "Professionnel de la santé",
        "profil_risque": "Faible à modéré",
        "horizon": "3 à 5 ans",
        "experience": "Avancée",
        "objectif": "Préserver son capital tout en gardant un potentiel de croissance.",
        "preferences": [
            "Préfère les entreprises établies au modèle d'affaires compréhensible",
            "Valorise la stabilité et la qualité",
            "Peu intéressé par les cryptoactifs",
            "Suit les marchés, peut être tenté par une entreprise très médiatisée",
        ],
        "exclusions": [],
        "limites": {"volatilite_max_pct": 11, "baisse_max_toleree_pct": 15, "ligne_max_pct": 12,
                    "crypto_max_pct": 0, "techno_max_pct": 25, "defensif_min_pct": 40},
        "portefeuille": {"XBB.TO": 150000, "ZST.TO": 60000, "RY.TO": 50000, "JNJ": 50000, "PG": 50000,
                         "FTS.TO": 50000, "XIU.TO": 80000, "SPY": 60000, "GLD": 30000},
        "test_enonce": "Le système sait-il remettre en question une demande incohérente avec le profil ?",
        "demande_exemple": "J'ai lu plein d'articles sur Tesla et NVIDIA. Je veux vendre mes obligations XBB "
                           "et mettre 150 000 $ dans TSLA et NVDA. Tu en penses quoi ?",
    },
}
