# ==========================================================
# MON VOISIN ARTISAN
# Application de mise en relation artisans / particuliers
# ==========================================================

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

import os
import sqlite3
import pandas as pd
import requests
import bcrypt

from datetime import datetime, timedelta


# ==========================================================
# CONFIGURATION
# ==========================================================

APP_NAME = "Mon Voisin Artisan"

DATABASE = "mon_voisin_artisan.db"

# Google Sheets
SHEET_ID = ""

# Make
WEBHOOK_URL = ""

# Stripe - ESSAI GRATUIT 7 JOURS
TRIAL_LINK = "https://buy.stripe.com/eVq7sM9YK9RH1HJeek9fW0l"

# Stripe - 1 MOIS : 20 € HT / 24 € TTC
STRIPE_LINK = "https://buy.stripe.com/dRm7sM8UG9RH1HJc6c9fW0m"

# Tarifs
TRIAL_DAYS = 7
PRICE_HT = 20
PRICE_TTC = 24

# Clé de session
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "mon-voisin-artisan-secret-key"
)


# ==========================================================
# APPLICATION FLASK
# ==========================================================

app = Flask(__name__)

app.secret_key = SECRET_KEY

app.config["SESSION_PERMANENT"] = False

app.config["TEMPLATES_AUTO_RELOAD"] = True

# ==========================================================
# SQLITE
# ==========================================================

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ==========================================================
# INITIALISATION DE LA BASE DE DONNÉES
# ==========================================================

def init_database():

    conn = get_connection()
    cursor = conn.cursor()

    # ------------------------------------------------------
    # ARTISANS
    # ------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artisans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            entreprise TEXT NOT NULL,
            responsable TEXT,
            telephone TEXT,
            adresse TEXT,
            code_postal TEXT,
            ville TEXT,
            photo TEXT,
            description TEXT,
            activites TEXT,
            sous_categories TEXT,
            regions TEXT,
            rayon TEXT,
            disponibilites TEXT,
            photo1 TEXT,
            photo2 TEXT,
            photo3 TEXT,
            valide INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    # ------------------------------------------------------
    # PARTICULIERS
    # ------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS particuliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nom TEXT,
            telephone TEXT,
            created_at TEXT
        )
    """)

    # ------------------------------------------------------
    # DEMANDES DE TRAVAUX
    # ------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS demandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            particulier_id INTEGER NOT NULL,
            activite TEXT NOT NULL,
            sous_categorie TEXT,
            region TEXT NOT NULL,
            code_postal TEXT,
            ville TEXT,
            description TEXT NOT NULL,
            photo1 TEXT,
            photo2 TEXT,
            photo3 TEXT,
            created_at TEXT
        )
    """)

    # ------------------------------------------------------
    # RÉPONSES DES ARTISANS
    # ------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reponses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            demande_id INTEGER NOT NULL,
            artisan_id INTEGER NOT NULL,
            message TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


# Initialisation de la base
init_database()

# ==========================================================
# GOOGLE SHEETS
# ==========================================================

def load_users():

    try:

        url = (
            f"https://docs.google.com/spreadsheets/d/"
            f"{SHEET_ID}/export?format=csv"
        )

        df = pd.read_csv(url)

        # Vérification de la structure de la feuille
        required_columns = [
            "username",
            "password",
            "expire",
            "trial",
            "price"
        ]

        for column in required_columns:
            if column not in df.columns:
                df[column] = ""

        # Nettoyage
        df["username"] = (
            df["username"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        df["expire"] = pd.to_datetime(
            df["expire"],
            errors="coerce"
        )

        df["trial"] = (
            df["trial"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        return df

    except Exception:

        return pd.DataFrame(
            columns=[
                "username",
                "password",
                "expire",
                "trial",
                "price"
            ]
        )


# ==========================================================
# CONTRÔLE DE L'ACCÈS ARTISAN
# ==========================================================

def check_artisan_access(email):

    df = load_users()

    if df.empty:
        return "error"

    user = df[
        df["username"] == str(email).strip().lower()
    ]

    if user.empty:
        return "error"

    expire_date = pd.to_datetime(
        user.iloc[0]["expire"],
        errors="coerce"
    )

    if pd.isna(expire_date):
        return "expired"

    # Date actuelle
    now = pd.Timestamp.now().normalize()

    # Accès encore valable
    if expire_date >= now:

        trial = str(
            user.iloc[0]["trial"]
        ).strip().upper()

        if trial == "TRUE":
            return "trial"

        return "paid"

    # Accès expiré
    trial = str(
        user.iloc[0]["trial"]
    ).strip().upper()

    if trial == "TRUE":
        return "trial_expired"

    return "paid_expired"


# ==========================================================
# LIENS DE PAIEMENT
# ==========================================================

def get_trial_link():

    return TRIAL_LINK


def get_paid_link():

    return STRIPE_LINK


# ==========================================================
# WEBHOOK MAKE
# ==========================================================

def send_to_make(email, price, trial):

    if not WEBHOOK_URL:
        return False

    data = {
        "username": email,
        "price": price,
        "trial": trial
    }

    try:

        response = requests.post(
            WEBHOOK_URL,
            json=data,
            timeout=10
        )

        return response.ok

    except Exception:

        return False

  # ==========================================================
# MOTS DE PASSE
# ==========================================================

def hash_password(password):

    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(password, hashed_password):

    try:

        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )

    except Exception:

        return False


# ==========================================================
# ACTIVITÉS ET SOUS-CATÉGORIES
# ==========================================================

ACTIVITES = {

    "Plomberie": [
        "Dépannage plomberie",
        "Fuite d'eau",
        "Installation plomberie",
        "Salle de bains",
        "Canalisation",
        "Débouchage",
        "Robinetterie"
    ],

    "Chauffage": [
        "Installation chauffage",
        "Réparation chauffage",
        "Chaudière",
        "Pompe à chaleur",
        "Radiateur",
        "Entretien chauffage"
    ],

    "Électricité": [
        "Dépannage électrique",
        "Installation électrique",
        "Tableau électrique",
        "Prises et interrupteurs",
        "Éclairage",
        "Mise aux normes"
    ],

    "Jardin": [
        "Tonte",
        "Débroussaillage",
        "Taille de haies",
        "Élagage",
        "Entretien espaces verts",
        "Abattage",
        "Création de jardin"
    ],

    "Peinture": [
        "Peinture intérieure",
        "Peinture extérieure",
        "Tapissage",
        "Enduit",
        "Rénovation murs",
        "Plafonds"
    ],

    "Parquet": [
        "Pose de parquet",
        "Dépose de parquet",
        "Ponçage",
        "Vitrification",
        "Réparation de parquet"
    ],

    "Carrelage": [
        "Pose de carrelage",
        "Dépose de carrelage",
        "Faïence",
        "Terrasse",
        "Réparation de carrelage"
    ],

    "Maçonnerie": [
        "Petite maçonnerie",
        "Mur",
        "Dalle",
        "Terrasse",
        "Rénovation",
        "Ouverture de mur"
    ],

    "Menuiserie": [
        "Menuiserie intérieure",
        "Menuiserie extérieure",
        "Portes",
        "Fenêtres",
        "Escalier",
        "Meubles sur mesure"
    ],

    "Couverture / Toiture": [
        "Réparation toiture",
        "Pose de toiture",
        "Nettoyage toiture",
        "Gouttières",
        "Étanchéité"
    ],

    "Clôture": [
        "Pose de clôture",
        "Réparation de clôture",
        "Grillage",
        "Portail",
        "Palissade"
    ],

    "Nettoyage": [
        "Nettoyage intérieur",
        "Nettoyage extérieur",
        "Nettoyage après travaux",
        "Nettoyage vitres"
    ],

    "Terrassement": [
        "Terrassement",
        "Nivellement",
        "Tranchée",
        "Évacuation de terre"
    ],

    "Isolation": [
        "Isolation intérieure",
        "Isolation extérieure",
        "Isolation des combles",
        "Isolation toiture"
    ],

    "Rénovation": [
        "Rénovation intérieure",
        "Rénovation extérieure",
        "Rénovation complète"
    ]
}


# ==========================================================
# RÉGIONS
# ==========================================================

REGIONS = [
    "Auvergne-Rhône-Alpes",
    "Bourgogne-Franche-Comté",
    "Bretagne",
    "Centre-Val de Loire",
    "Corse",
    "Grand Est",
    "Hauts-de-France",
    "Île-de-France",
    "Normandie",
    "Nouvelle-Aquitaine",
    "Occitanie",
    "Pays de la Loire",
    "Provence-Alpes-Côte d'Azur"
]

# ==========================================================
# FONCTIONS UTILITAIRES
# ==========================================================

def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_email(email):
    return str(email).strip().lower()


def save_list(values):
    if not values:
        return ""
    return "|||".join(
        str(value).strip()
        for value in values
        if str(value).strip()
    )


def load_list(value):
    if not value:
        return []

    return [
        item.strip()
        for item in str(value).split("|||")
        if item.strip()
    ]


def get_current_user():

    user_type = session.get("user_type")
    user_id = session.get("user_id")

    if not user_type or not user_id:
        return None

    conn = get_connection()

    if user_type == "artisan":

        user = conn.execute(
            "SELECT * FROM artisans WHERE id = ?",
            (user_id,)
        ).fetchone()

    elif user_type == "particulier":

        user = conn.execute(
            "SELECT * FROM particuliers WHERE id = ?",
            (user_id,)
        ).fetchone()

    else:

        user = None

    conn.close()

    return user


def artisan_logged():
    return (
        session.get("user_type") == "artisan"
        and session.get("user_id") is not None
    )


def particulier_logged():
    return (
        session.get("user_type") == "particulier"
        and session.get("user_id") is not None
    )


def logout_user():

    session.pop("user_id", None)
    session.pop("user_type", None)
    session.pop("email", None)

# ==========================================================
# ACCUEIL
# ==========================================================

@app.route("/")
def home():

    return render_template(
        "index.html",
        app_name=APP_NAME,
        trial_link=TRIAL_LINK,
        stripe_link=STRIPE_LINK
    )


# ==========================================================
# INSCRIPTION
# ==========================================================

@app.route("/inscription")
def inscription():

    return render_template(
        "inscription.html",
        activites=ACTIVITES,
        regions=REGIONS
    )


# ==========================================================
# INSCRIPTION ARTISAN
# ==========================================================

@app.route("/inscription/artisan", methods=["POST"])
def inscription_artisan():

    email = clean_email(
        request.form.get("email", "")
    )

    password = request.form.get(
        "password",
        ""
    ).strip()

    entreprise = request.form.get(
        "entreprise",
        ""
    ).strip()

    responsable = request.form.get(
        "responsable",
        ""
    ).strip()

    telephone = request.form.get(
        "telephone",
        ""
    ).strip()

    adresse = request.form.get(
        "adresse",
        ""
    ).strip()

    code_postal = request.form.get(
        "code_postal",
        ""
    ).strip()

    ville = request.form.get(
        "ville",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    activites = request.form.getlist(
        "activites"
    )

    sous_categories = request.form.getlist(
        "sous_categories"
    )

    regions = request.form.getlist(
        "regions"
    )

    rayon = request.form.get(
        "rayon",
        ""
    ).strip()

    if not email:
        flash("Veuillez saisir votre adresse e-mail.")
        return redirect(url_for("inscription"))

    if not password:
        flash("Veuillez choisir un mot de passe.")
        return redirect(url_for("inscription"))

    if not entreprise:
        flash("Veuillez saisir le nom de votre entreprise.")
        return redirect(url_for("inscription"))

    if not telephone:
        flash("Veuillez saisir votre numéro de téléphone.")
        return redirect(url_for("inscription"))

    if not activites:
        flash("Veuillez sélectionner au moins une activité.")
        return redirect(url_for("inscription"))

    if not regions:
        flash("Veuillez sélectionner au moins une région.")
        return redirect(url_for("inscription"))

    conn = get_connection()

    existing = conn.execute(
        "SELECT id FROM artisans WHERE email = ?",
        (email,)
    ).fetchone()

    if existing:

        conn.close()

        flash(
            "Un compte artisan existe déjà avec cette adresse e-mail."
        )

        return redirect(
            url_for("inscription")
        )

    hashed_password = hash_password(
        password
    )

    cursor = conn.execute(
        """
        INSERT INTO artisans (
            email,
            password,
            entreprise,
            responsable,
            telephone,
            adresse,
            code_postal,
            ville,
            description,
            activites,
            sous_categories,
            regions,
            rayon,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            email,
            hashed_password,
            entreprise,
            responsable,
            telephone,
            adresse,
            code_postal,
            ville,
            description,
            save_list(activites),
            save_list(sous_categories),
            save_list(regions),
            rayon,
            now_string()
        )
    )

    artisan_id = cursor.lastrowid

    conn.commit()
    conn.close()

    session["user_id"] = artisan_id
    session["user_type"] = "artisan"
    session["email"] = email

    flash(
        "Votre compte artisan a été créé. "
        "Veuillez maintenant effectuer votre essai gratuit de 7 jours."
    )

    return redirect(
        url_for("artisan")
    )


# ==========================================================
# INSCRIPTION PARTICULIER
# ==========================================================

@app.route("/inscription/particulier", methods=["POST"])
def inscription_particulier():

    email = clean_email(
        request.form.get("email", "")
    )

    password = request.form.get(
        "password",
        ""
    ).strip()

    nom = request.form.get(
        "nom",
        ""
    ).strip()

    telephone = request.form.get(
        "telephone",
        ""
    ).strip()

    if not email:
        flash("Veuillez saisir votre adresse e-mail.")
        return redirect(url_for("inscription"))

    if not password:
        flash("Veuillez choisir un mot de passe.")
        return redirect(url_for("inscription"))

    if not nom:
        flash("Veuillez saisir votre nom.")
        return redirect(url_for("inscription"))

    if not telephone:
        flash("Veuillez saisir votre numéro de téléphone.")
        return redirect(url_for("inscription"))

    conn = get_connection()

    existing = conn.execute(
        "SELECT id FROM particuliers WHERE email = ?",
        (email,)
    ).fetchone()

    if existing:

        conn.close()

        flash(
            "Un compte particulier existe déjà avec cette adresse e-mail."
        )

        return redirect(
            url_for("inscription")
        )

    hashed_password = hash_password(
        password
    )

    cursor = conn.execute(
        """
        INSERT INTO particuliers (
            email,
            password,
            nom,
            telephone,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            email,
            hashed_password,
            nom,
            telephone,
            now_string()
        )
    )

    particulier_id = cursor.lastrowid

    conn.commit()
    conn.close()

    session["user_id"] = particulier_id
    session["user_type"] = "particulier"
    session["email"] = email

    return redirect(
        url_for("demande")
    )

# ==========================================================
# CONNEXION
# ==========================================================

@app.route("/connexion", methods=["GET", "POST"])
def connexion():

    if request.method == "GET":

        return render_template(
            "connexion.html"
        )

    email = clean_email(
        request.form.get("email", "")
    )

    password = request.form.get(
        "password",
        ""
    )

    if not email or not password:

        flash(
            "Veuillez saisir votre adresse e-mail et votre mot de passe."
        )

        return redirect(
            url_for("connexion")
        )

    conn = get_connection()

    # ------------------------------------------------------
    # RECHERCHE ARTISAN
    # ------------------------------------------------------

    artisan = conn.execute(
        """
        SELECT *
        FROM artisans
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    if artisan:

        conn.close()

        if not verify_password(
            password,
            artisan["password"]
        ):

            flash(
                "Adresse e-mail ou mot de passe incorrect."
            )

            return redirect(
                url_for("connexion")
            )

        session["user_id"] = artisan["id"]
        session["user_type"] = "artisan"
        session["email"] = artisan["email"]

        return redirect(
            url_for("artisan")
        )

    # ------------------------------------------------------
    # RECHERCHE PARTICULIER
    # ------------------------------------------------------

    particulier = conn.execute(
        """
        SELECT *
        FROM particuliers
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    conn.close()

    if particulier:

        if not verify_password(
            password,
            particulier["password"]
        ):

            flash(
                "Adresse e-mail ou mot de passe incorrect."
            )

            return redirect(
                url_for("connexion")
            )

        session["user_id"] = particulier["id"]
        session["user_type"] = "particulier"
        session["email"] = particulier["email"]

        return redirect(
            url_for("demande")
        )

    flash(
        "Adresse e-mail ou mot de passe incorrect."
    )

    return redirect(
        url_for("connexion")
    )


# ==========================================================
# DÉCONNEXION
# ==========================================================

@app.route("/deconnexion")
def deconnexion():

    logout_user()

    return redirect(
        url_for("home")
    )

# ==========================================================
# ESPACE ARTISAN
# ==========================================================

@app.route("/artisan")
def artisan():

    if not artisan_logged():

        return redirect(
            url_for("connexion")
        )

    artisan_user = get_current_user()

    if not artisan_user:

        logout_user()

        return redirect(
            url_for("connexion")
        )

    # ------------------------------------------------------
    # CONTRÔLE DU PAIEMENT / ESSAI
    # ------------------------------------------------------

    access = check_artisan_access(
        artisan_user["email"]
    )

    if access == "error":

        flash(
            "Votre accès artisan n'est pas encore activé."
        )

        return render_template(
            "artisan.html",
            artisan=artisan_user,
            access="error",
            trial_link=TRIAL_LINK,
            stripe_link=STRIPE_LINK,
            demandes=[]
        )

    if access == "trial_expired":

        flash(
            "Votre essai gratuit de 7 jours est terminé."
        )

        return render_template(
            "artisan.html",
            artisan=artisan_user,
            access="trial_expired",
            trial_link=TRIAL_LINK,
            stripe_link=STRIPE_LINK,
            demandes=[]
        )

    if access == "paid_expired":

        flash(
            "Votre accès d'un mois est arrivé à expiration."
        )

        return render_template(
            "artisan.html",
            artisan=artisan_user,
            access="paid_expired",
            trial_link=TRIAL_LINK,
            stripe_link=STRIPE_LINK,
            demandes=[]
        )

    # ------------------------------------------------------
    # RÉCUPÉRATION DES CRITÈRES DE L'ARTISAN
    # ------------------------------------------------------

    activites = load_list(
        artisan_user["activites"]
    )

    sous_categories = load_list(
        artisan_user["sous_categories"]
    )

    regions = load_list(
        artisan_user["regions"]
    )

    # ------------------------------------------------------
    # RECHERCHE DES DEMANDES CORRESPONDANTES
    # ------------------------------------------------------

    conn = get_connection()

    demandes = conn.execute(
        """
        SELECT
            demandes.*,
            particuliers.nom AS particulier_nom,
            particuliers.telephone AS particulier_telephone,
            particuliers.email AS particulier_email
        FROM demandes
        JOIN particuliers
            ON demandes.particulier_id = particuliers.id
        ORDER BY demandes.id DESC
        """
    ).fetchall()

    conn.close()

    demandes_filtrees = []

    for demande in demandes:

        # Activité
        activite_ok = (
            demande["activite"] in activites
        )

        if not activite_ok:
            continue

        # Sous-catégorie
        if sous_categories:

            sous_categorie_ok = (
                not demande["sous_categorie"]
                or demande["sous_categorie"]
                in sous_categories
            )

            if not sous_categorie_ok:
                continue

        # Région
        region_ok = (
            demande["region"] in regions
        )

        if not region_ok:
            continue

        demandes_filtrees.append(
            demande
        )

    return render_template(
        "artisan.html",
        artisan=artisan_user,
        access=access,
        activites=activites,
        sous_categories=sous_categories,
        regions=regions,
        demandes=demandes_filtrees,
        trial_link=TRIAL_LINK,
        stripe_link=STRIPE_LINK
    )


# ==========================================================
# PAIEMENT / ESSAI ARTISAN
# ==========================================================

@app.route("/artisan/paiement")
def artisan_paiement():

    if not artisan_logged():

        return redirect(
            url_for("connexion")
        )

    return redirect(
        STRIPE_LINK
    )


@app.route("/artisan/essai")
def artisan_essai():

    if not artisan_logged():

        return redirect(
            url_for("connexion")
        )

    return redirect(
        TRIAL_LINK
    )

# ==========================================================
# DÉPOSER UNE DEMANDE
# ==========================================================

@app.route("/demande", methods=["GET", "POST"])
def demande():

    if not particulier_logged():

        return redirect(
            url_for("connexion")
        )

    if request.method == "GET":

        return render_template(
            "demande.html",
            activites=ACTIVITES,
            regions=REGIONS
        )

    # ------------------------------------------------------
    # RÉCUPÉRATION DES INFORMATIONS
    # ------------------------------------------------------

    activite = request.form.get(
        "activite",
        ""
    ).strip()

    sous_categorie = request.form.get(
        "sous_categorie",
        ""
    ).strip()

    region = request.form.get(
        "region",
        ""
    ).strip()

    code_postal = request.form.get(
        "code_postal",
        ""
    ).strip()

    ville = request.form.get(
        "ville",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    if not activite:

        flash(
            "Veuillez sélectionner une activité."
        )

        return redirect(
            url_for("demande")
        )

    if not region:

        flash(
            "Veuillez sélectionner une région."
        )

        return redirect(
            url_for("demande")
        )

    if not description:

        flash(
            "Veuillez décrire les travaux à réaliser."
        )

        return redirect(
            url_for("demande")
        )

    particulier_id = session.get(
        "user_id"
    )

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO demandes (
            particulier_id,
            activite,
            sous_categorie,
            region,
            code_postal,
            ville,
            description,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            particulier_id,
            activite,
            sous_categorie,
            region,
            code_postal,
            ville,
            description,
            now_string()
        )
    )

    conn.commit()
    conn.close()

    flash(
        "Votre demande a été publiée."
    )

    return redirect(
        url_for("demande")
    )


# ==========================================================
# LISTE DES DEMANDES
# ==========================================================

@app.route("/demandes")
def demandes():

    if not artisan_logged():

        return redirect(
            url_for("connexion")
        )

    artisan_user = get_current_user()

    if not artisan_user:

        logout_user()

        return redirect(
            url_for("connexion")
        )

    # ------------------------------------------------------
    # VÉRIFICATION DE L'ACCÈS
    # ------------------------------------------------------

    access = check_artisan_access(
        artisan_user["email"]
    )

    if access not in ["trial", "paid"]:

        return redirect(
            url_for("artisan")
        )

    activites = load_list(
        artisan_user["activites"]
    )

    sous_categories = load_list(
        artisan_user["sous_categories"]
    )

    regions = load_list(
        artisan_user["regions"]
    )

    conn = get_connection()

    toutes_demandes = conn.execute(
        """
        SELECT
            demandes.*,
            particuliers.nom AS particulier_nom,
            particuliers.telephone AS particulier_telephone,
            particuliers.email AS particulier_email
        FROM demandes
        JOIN particuliers
            ON demandes.particulier_id = particuliers.id
        ORDER BY demandes.id DESC
        """
    ).fetchall()

    conn.close()

    demandes_filtrees = []

    for demande_item in toutes_demandes:

        # --------------------------------------------------
        # ACTIVITÉ
        # --------------------------------------------------

        if demande_item["activite"] not in activites:
            continue

        # --------------------------------------------------
        # SOUS-CATÉGORIE
        # --------------------------------------------------

        if (
            sous_categories
            and demande_item["sous_categorie"]
            and demande_item["sous_categorie"]
            not in sous_categories
        ):
            continue

        # --------------------------------------------------
        # RÉGION
        # --------------------------------------------------

        if demande_item["region"] not in regions:
            continue

        demandes_filtrees.append(
            demande_item
        )

    return render_template(
        "demandes.html",
        demandes=demandes_filtrees,
        artisan=artisan_user
    )

# ==========================================================
# DÉTAIL D'UNE DEMANDE
# ==========================================================

@app.route("/demande/<int:demande_id>")
def detail_demande(demande_id):

    if not artisan_logged():

        return redirect(
            url_for("connexion")
        )

    artisan_user = get_current_user()

    if not artisan_user:

        logout_user()

        return redirect(
            url_for("connexion")
        )

    # ------------------------------------------------------
    # VÉRIFICATION DE L'ACCÈS ARTISAN
    # ------------------------------------------------------

    access = check_artisan_access(
        artisan_user["email"]
    )

    if access not in ["trial", "paid"]:

        return redirect(
            url_for("artisan")
        )

    conn = get_connection()

    demande_item = conn.execute(
        """
        SELECT
            demandes.*,
            particuliers.nom AS particulier_nom,
            particuliers.telephone AS particulier_telephone,
            particuliers.email AS particulier_email
        FROM demandes
        JOIN particuliers
            ON demandes.particulier_id = particuliers.id
        WHERE demandes.id = ?
        """,
        (demande_id,)
    ).fetchone()

    conn.close()

    if not demande_item:

        flash(
            "Cette demande n'existe pas."
        )

        return redirect(
            url_for("demandes")
        )

    # ------------------------------------------------------
    # VÉRIFICATION ACTIVITÉ / RÉGION
    # ------------------------------------------------------

    activites = load_list(
        artisan_user["activites"]
    )

    sous_categories = load_list(
        artisan_user["sous_categories"]
    )

    regions = load_list(
        artisan_user["regions"]
    )

    if demande_item["activite"] not in activites:

        flash(
            "Cette demande ne correspond pas à votre activité."
        )

        return redirect(
            url_for("demandes")
        )

    if (
        sous_categories
        and demande_item["sous_categorie"]
        and demande_item["sous_categorie"]
        not in sous_categories
    ):

        flash(
            "Cette demande ne correspond pas à vos travaux."
        )

        return redirect(
            url_for("demandes")
        )

    if demande_item["region"] not in regions:

        flash(
            "Cette demande ne correspond pas à votre secteur."
        )

        return redirect(
            url_for("demandes")
        )

    return render_template(
        "demande_detail.html",
        demande=demande_item,
        artisan=artisan_user
    )


# ==========================================================
# RÉPONDRE À UNE DEMANDE
# ==========================================================

@app.route(
    "/demande/<int:demande_id>/repondre",
    methods=["POST"]
)
def repondre_demande(demande_id):

    if not artisan_logged():

        return redirect(
            url_for("connexion")
        )

    artisan_user = get_current_user()

    if not artisan_user:

        logout_user()

        return redirect(
            url_for("connexion")
        )

    # ------------------------------------------------------
    # VÉRIFICATION DE L'ACCÈS
    # ------------------------------------------------------

    access = check_artisan_access(
        artisan_user["email"]
    )

    if access not in ["trial", "paid"]:

        return redirect(
            url_for("artisan")
        )

    message = request.form.get(
        "message",
        ""
    ).strip()

    if not message:

        flash(
            "Veuillez saisir un message."
        )

        return redirect(
            url_for(
                "detail_demande",
                demande_id=demande_id
            )
        )

    conn = get_connection()

    demande_item = conn.execute(
        """
        SELECT *
        FROM demandes
        WHERE id = ?
        """,
        (demande_id,)
    ).fetchone()

    if not demande_item:

        conn.close()

        flash(
            "Cette demande n'existe pas."
        )

        return redirect(
            url_for("demandes")
        )

    # ------------------------------------------------------
    # ENREGISTREMENT DE LA RÉPONSE
    # ------------------------------------------------------

    conn.execute(
        """
        INSERT INTO reponses (
            demande_id,
            artisan_id,
            message,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            demande_id,
            artisan_user["id"],
            message,
            now_string()
        )
    )

    conn.commit()
    conn.close()

    flash(
        "Votre réponse a été enregistrée."
    )

    return redirect(
        url_for(
            "detail_demande",
            demande_id=demande_id
        )
    )

# ==========================================================
# PROFIL ARTISAN
# ==========================================================

@app.route("/profil")
def profil():

    user = get_current_user()

    if not user:
        return redirect(
            url_for("connexion")
        )

    user_type = session.get("user_type")

    user_activites = []
    user_sous_categories = []
    user_regions = []

    if user_type == "artisan":

        user_activites = load_list(
            user["activites"]
        )

        user_sous_categories = load_list(
            user["sous_categories"]
        )

        user_regions = load_list(
            user["regions"]
        )

    return render_template(
        "profil.html",
        user=user,
        user_type=user_type,
        activites=ACTIVITES,
        regions=REGIONS,
        user_activites=user_activites,
        user_sous_categories=user_sous_categories,
        user_regions=user_regions
    )

# ==========================================================
# MODIFICATION DU PROFIL ARTISAN
# ==========================================================

@app.route(
    "/profil/artisan",
    methods=["POST"]
)
def modifier_profil_artisan():

    if not artisan_logged():
        return redirect(
            url_for("connexion")
        )

    artisan_user = get_current_user()

    if not artisan_user:
        return redirect(
            url_for("connexion")
        )

    entreprise = request.form.get(
        "entreprise",
        ""
    ).strip()

    responsable = request.form.get(
        "responsable",
        ""
    ).strip()

    telephone = request.form.get(
        "telephone",
        ""
    ).strip()

    email = clean_email(
        request.form.get(
            "email",
            ""
        )
    )

    adresse = request.form.get(
        "adresse",
        ""
    ).strip()

    code_postal = request.form.get(
        "code_postal",
        ""
    ).strip()

    ville = request.form.get(
        "ville",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    activites = request.form.getlist(
        "activites"
    )

    sous_categories = request.form.getlist(
        "sous_categories"
    )

    regions = request.form.getlist(
        "regions"
    )

    rayon = request.form.get(
        "rayon",
        ""
    ).strip()

    disponibilites = request.form.get(
        "disponibilites",
        ""
    ).strip()

    if not entreprise:
        flash(
            "Veuillez saisir le nom de votre entreprise."
        )
        return redirect(
            url_for("profil")
        )

    if not email:
        flash(
            "Veuillez saisir votre adresse e-mail."
        )
        return redirect(
            url_for("profil")
        )

    if not telephone:
        flash(
            "Veuillez saisir votre numéro de téléphone."
        )
        return redirect(
            url_for("profil")
        )

    if not activites:
        flash(
            "Veuillez sélectionner au moins une activité."
        )
        return redirect(
            url_for("profil")
        )

    if not regions:
        flash(
            "Veuillez sélectionner au moins une région."
        )
        return redirect(
            url_for("profil")
        )

    conn = get_connection()

    # Vérification qu'un autre compte n'utilise pas déjà cet email
    existing = conn.execute(
        """
        SELECT id
        FROM artisans
        WHERE email = ?
        AND id != ?
        """,
        (
            email,
            artisan_user["id"]
        )
    ).fetchone()

    if existing:

        conn.close()

        flash(
            "Cette adresse e-mail est déjà utilisée."
        )

        return redirect(
            url_for("profil")
        )

    conn.execute(
        """
        UPDATE artisans
        SET
            email = ?,
            entreprise = ?,
            responsable = ?,
            telephone = ?,
            adresse = ?,
            code_postal = ?,
            ville = ?,
            description = ?,
            activites = ?,
            sous_categories = ?,
            regions = ?,
            rayon = ?,
            disponibilites = ?
        WHERE id = ?
        """,
        (
            email,
            entreprise,
            responsable,
            telephone,
            adresse,
            code_postal,
            ville,
            description,
            save_list(activites),
            save_list(sous_categories),
            save_list(regions),
            rayon,
            disponibilites,
            artisan_user["id"]
        )
    )

    conn.commit()
    conn.close()

    session["email"] = email

    flash(
        "Votre profil a été mis à jour."
    )

    return redirect(
        url_for("profil")
    )


# ==========================================================
# MODIFICATION DU PROFIL PARTICULIER
# ==========================================================

@app.route(
    "/profil/particulier",
    methods=["POST"]
)
def modifier_profil_particulier():

    if not particulier_logged():
        return redirect(
            url_for("connexion")
        )

    particulier = get_current_user()

    if not particulier:
        return redirect(
            url_for("connexion")
        )

    nom = request.form.get(
        "nom",
        ""
    ).strip()

    email = clean_email(
        request.form.get(
            "email",
            ""
        )
    )

    telephone = request.form.get(
        "telephone",
        ""
    ).strip()

    if not nom:
        flash(
            "Veuillez saisir votre nom."
        )
        return redirect(
            url_for("profil")
        )

    if not email:
        flash(
            "Veuillez saisir votre adresse e-mail."
        )
        return redirect(
            url_for("profil")
        )

    if not telephone:
        flash(
            "Veuillez saisir votre numéro de téléphone."
        )
        return redirect(
            url_for("profil")
        )

    conn = get_connection()

    existing = conn.execute(
        """
        SELECT id
        FROM particuliers
        WHERE email = ?
        AND id != ?
        """,
        (
            email,
            particulier["id"]
        )
    ).fetchone()

    if existing:

        conn.close()

        flash(
            "Cette adresse e-mail est déjà utilisée."
        )

        return redirect(
            url_for("profil")
        )

    conn.execute(
        """
        UPDATE particuliers
        SET
            email = ?,
            nom = ?,
            telephone = ?
        WHERE id = ?
        """,
        (
            email,
            nom,
            telephone,
            particulier["id"]
        )
    )

    conn.commit()
    conn.close()

    session["email"] = email

    flash(
        "Votre profil a été mis à jour."
    )

    return redirect(
        url_for("profil")
    )

# ==========================================================
# PHOTOS DES RÉALISATIONS
# ==========================================================

ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}


def allowed_image(filename):

    if not filename:
        return False

    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()

    return extension in ALLOWED_IMAGE_EXTENSIONS


# ==========================================================
# AJOUT / MODIFICATION DES 3 PHOTOS
# ==========================================================

@app.route(
    "/profil/photos",
    methods=["POST"]
)
def modifier_photos():

    if not artisan_logged():

        return redirect(
            url_for("connexion")
        )

    artisan_user = get_current_user()

    if not artisan_user:

        return redirect(
            url_for("connexion")
        )

    photo1 = request.files.get("photo1")
    photo2 = request.files.get("photo2")
    photo3 = request.files.get("photo3")

    photos = [
        photo1,
        photo2,
        photo3
    ]

    fichiers = []

    for photo in photos:

        if photo and photo.filename:

            if not allowed_image(
                photo.filename
            ):

                flash(
                    "Format de photo non accepté. "
                    "Utilisez JPG, JPEG, PNG ou WEBP."
                )

                return redirect(
                    url_for("profil")
                )

            fichiers.append(
                photo.read()
            )

        else:

            fichiers.append(
                None
            )

    conn = get_connection()

# Conserver les anciennes photos si aucune nouvelle photo
# n'a été sélectionnée.

photo1 = fichiers[0] if fichiers[0] is not None else artisan_user["photo1"]
photo2 = fichiers[1] if fichiers[1] is not None else artisan_user["photo2"]
photo3 = fichiers[2] if fichiers[2] is not None else artisan_user["photo3"]

conn.execute(
    """
    UPDATE artisans
    SET
        photo1 = ?,
        photo2 = ?,
        photo3 = ?
    WHERE id = ?
    """,
    (
        photo1,
        photo2,
        photo3,
        artisan_user["id"]
    )
)

conn.commit()
conn.close()

flash(
    "Vos photos ont été enregistrées."
)

    return redirect(
        url_for("profil")
    )


# ==========================================================
# AFFICHAGE D'UNE PHOTO
# ==========================================================

@app.route(
    "/photo/<int:artisan_id>/<int:numero>"
)
def afficher_photo(
    artisan_id,
    numero
):

    if numero not in [1, 2, 3]:
        return "", 404

    colonne = f"photo{numero}"

    conn = get_connection()

    artisan_user = conn.execute(
        f"""
        SELECT {colonne}
        FROM artisans
        WHERE id = ?
        """,
        (artisan_id,)
    ).fetchone()

    conn.close()

    if not artisan_user:
        return "", 404

    image = artisan_user[colonne]

    if not image:
        return "", 404

    from flask import Response

    return Response(
        image,
        mimetype="image/jpeg"
    )


# ==========================================================
# ENVOI DU KBIS ET DE L'ATTESTATION RC PAR EMAIL
# ==========================================================

import smtplib

from email.message import EmailMessage


# Adresse qui recevra les documents
EMAIL_VERIFICATION = "studio.web.applications@gmail.com"

# Paramètres de messagerie
SMTP_SERVER = os.environ.get(
    "SMTP_SERVER",
    ""
)

SMTP_PORT = int(
    os.environ.get(
        "SMTP_PORT",
        "465"
    )
)

SMTP_EMAIL = os.environ.get(
    "SMTP_EMAIL",
    ""
)

SMTP_PASSWORD = os.environ.get(
    "SMTP_PASSWORD",
    ""
)


def send_documents_by_email(
    artisan_email,
    entreprise,
    kbis,
    rc
):

    if not EMAIL_VERIFICATION:
        return False

    if not SMTP_SERVER:
        return False

    if not SMTP_EMAIL:
        return False

    if not SMTP_PASSWORD:
        return False

    try:

        message = EmailMessage()

        message["Subject"] = (
            f"Mon Voisin Artisan - "
            f"Documents professionnel - {entreprise}"
        )

        message["From"] = SMTP_EMAIL
        message["To"] = EMAIL_VERIFICATION

        message.set_content(
            f"""
Nouvelle inscription artisan.

Entreprise : {entreprise}
Email : {artisan_email}

Veuillez vérifier le Kbis et l'attestation RC professionnelle.

Les documents sont joints à cet email.
"""
        )

        # --------------------------------------------------
        # KBIS
        # --------------------------------------------------

        if kbis and kbis.filename:

            kbis_data = kbis.read()

            message.add_attachment(
                kbis_data,
                maintype="application",
                subtype="octet-stream",
                filename=kbis.filename
            )

        # --------------------------------------------------
        # RC PROFESSIONNELLE
        # --------------------------------------------------

        if rc and rc.filename:

            rc_data = rc.read()

            message.add_attachment(
                rc_data,
                maintype="application",
                subtype="octet-stream",
                filename=rc.filename
            )

        # --------------------------------------------------
        # ENVOI
        # --------------------------------------------------

        with smtplib.SMTP_SSL(
            SMTP_SERVER,
            SMTP_PORT
        ) as server:

            server.login(
                SMTP_EMAIL,
                SMTP_PASSWORD
            )

            server.send_message(
                message
            )

        return True

    except Exception:

        return False


# ==========================================================
# RÉCEPTION DES DOCUMENTS ARTISAN
# ==========================================================

@app.route(
    "/inscription/artisan/documents",
    methods=["POST"]
)
def documents_artisan():

    if not artisan_logged():

        return redirect(
            url_for("connexion")
        )

    artisan_user = get_current_user()

    if not artisan_user:

        return redirect(
            url_for("connexion")
        )

    kbis = request.files.get(
        "kbis"
    )

    rc = request.files.get(
        "rc"
    )

    if not kbis or not kbis.filename:

        flash(
            "Veuillez joindre votre Kbis."
        )

        return redirect(
            url_for("artisan")
        )

    if not rc or not rc.filename:

        flash(
            "Veuillez joindre votre attestation RC professionnelle."
        )

        return redirect(
            url_for("artisan")
        )

    sent = send_documents_by_email(
        artisan_user["email"],
        artisan_user["entreprise"],
        kbis,
        rc
    )

    if sent:

        flash(
            "Vos documents ont été envoyés pour vérification."
        )

    else:

        flash(
            "Impossible d'envoyer les documents. "
            "Veuillez réessayer."
        )

    return redirect(
        url_for("artisan")
    )

# ==========================================================
# DÉMARRAGE DE L'APPLICATION
# ==========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True
    )



