import streamlit as st

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Portail Enseignant",
    page_icon="🏫",
    layout="centered"
)

# --- TÉLÉCHARGEMENT CSS (Optionnel : Pour cacher la sidebar si besoin) ---
# st.markdown("""<style> [data-testid="stSidebar"] { display: none; } </style>""", unsafe_allow_html=True)

# --- EN-TÊTE ---
st.title("🏫 Portail de Gestion Pédagogique")
st.write("### Tableau de bord enseignant")
st.markdown("---")

# --- LIGNE 1 : PRÉPARATION ---
st.subheader("📚 Préparation")
c1, c2 = st.columns(2)

with c1:
    st.info("Créer une séance unique.")
    if st.button("📝 Fiche Pédagogique", use_container_width=True):
        st.switch_page("pages/1_Fiche_Pedagogique.py")

with c2:
    st.info("Organiser une séquence.")
    if st.button("📅 Fiche Séquence", use_container_width=True):
        st.switch_page("pages/2_Fiche_Sequence.py")

# --- LIGNE 2 : ÉVALUATION & OUTILS ---
st.subheader("🎓 Évaluation & Outils")
c3, c4 = st.columns(2)

with c3:
    st.warning("Noter les étudiants.")
    if st.button("🎓 Fiche Évaluation", use_container_width=True):
        st.switch_page("pages/3_Fiche_Evaluation.py")

with c4:
    st.success("Générer des idées par IA.")
    if st.button("🤖 Assistant IA", use_container_width=True):
        st.switch_page("pages/5_Assistant_IA.py")

# --- LIGNE 3 : STATISTIQUES ---
st.markdown("---")
# On centre le bouton stats ou on le met en pleine largeur
if st.button("📊 Voir les Statistiques de progression", use_container_width=True):
    st.switch_page("pages/4_Statistiques.py")

# --- PIED DE PAGE ---
st.markdown("---")
st.caption("BTS Audiovisuel - Lycée Henri Martin")