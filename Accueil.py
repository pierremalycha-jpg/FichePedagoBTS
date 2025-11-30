import streamlit as st

# Configuration de la page
st.set_page_config(
    page_title="Portail Enseignant",
    page_icon="🏫",
    layout="centered"
)

# Masquer la barre latérale sur la page d'accueil si vous voulez (optionnel)
# st.markdown("<style> ul {display: none;} </style>", unsafe_allow_html=True)

st.title("🏫 Portail de Gestion Pédagogique")
st.write("### Que souhaitez-vous faire aujourd'hui ?")

st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    st.info("Pour préparer une séance unique.")
    # ATTENTION : Le nom doit correspondre EXACTEMENT au nom du fichier dans le dossier pages
    if st.button("📝 Fiche Pédagogique", use_container_width=True):
        st.switch_page("pages/1_Fiche_Pedagogique.py")

with col2:
    st.warning("Pour organiser une séquence complète.")
    if st.button("📅 Fiche Séquence", use_container_width=True):
        st.switch_page("pages/2_Fiche_Sequence.py")

with col3:
    st.success("Pour créer une grille de notation.")
    if st.button("🎓 Fiche Évaluation", use_container_width=True):
        st.switch_page("pages/3_Fiche_Evaluation.py")

st.markdown("---")
st.caption("BTS Audiovisuel - Lycée Henri Martin")
