import streamlit as st
import os
import hmac

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Portail Enseignant",
    page_icon="🏫",
    layout="centered"
)

# --- 2. CONFIGURATION DES CHEMINS (SÉCURITÉ) ---
# On définit où on est, pour être sûr que tout fonctionne sur le Pi
ROOT_PATH = "/home/pi/ApplicationPython"

# Petite vérification silencieuse (pour le debug si besoin)
if not os.path.exists(ROOT_PATH):
    st.error(f"Attention : Le dossier {ROOT_PATH} n'est pas détecté. Vérifiez votre installation.")

# --- 3. SYSTÈME DE MOT DE PASSE ---
def check_password():
    """Renvoie True si l'utilisateur est connecté, sinon affiche le formulaire."""
    
    def password_entered():
        # Vérifie si le mot de passe correspond à celui stocké dans secrets.toml
        if st.session_state["username"] in st.secrets["passwords"] and \
           st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]:
            st.session_state["password_correct"] = True
            # On efface le mot de passe de la mémoire pour la sécurité
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Premier chargement : On montre les champs
        st.text_input("Identifiant", key="username")
        st.text_input("Mot de passe", type="password", key="password", on_change=password_entered)
        return False
    
    elif not st.session_state["password_correct"]:
        # Mot de passe incorrect
        st.text_input("Identifiant", key="username")
        st.text_input("Mot de passe", type="password", key="password", on_change=password_entered)
        st.error("😕 Identifiant ou mot de passe incorrect.")
        return False
    
    else:
        # Mot de passe correct -> On autorise l'accès
        return True

# --- VÉRIFICATION AVANT D'AFFICHER LE CONTENU ---
# Si le mot de passe n'est pas bon, on arrête le script ici.
if not check_password():
    st.stop()

# =========================================================
# CONTENU DE LA PAGE D'ACCUEIL (Visible seulement si connecté)
# =========================================================

st.title("🏫 Portail de Gestion Pédagogique")
st.write("### Bienvenue sur votre espace de travail")
st.markdown("---")

# Organisation en 2 colonnes pour les 4 boutons
col1, col2 = st.columns(2)

with col1:
    st.info("📝 **Préparation de Séance**")
    if st.button("Créer une Fiche Pédagogique", use_container_width=True):
        st.switch_page("pages/1_Fiche_Pedagogique.py")
    
    st.warning("🎓 **Évaluation**")
    if st.button("Créer une Grille de Notation", use_container_width=True):
        st.switch_page("pages/3_Fiche_Evaluation.py")

with col2:
    st.success("📅 **Organisation**")
    if st.button("Créer une Fiche Séquence", use_container_width=True):
        st.switch_page("pages/2_Fiche_Sequence.py")

    st.error("🎯 **Élèves**")
    if st.button("Lancer l'Auto-Évaluation", use_container_width=True):
        st.switch_page("pages/4_Auto_Evaluation.py")

st.markdown("---")
st.caption(f"Serveur local Raspberry Pi - Dossier : {ROOT_PATH}")
