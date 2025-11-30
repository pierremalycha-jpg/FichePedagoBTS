import streamlit as st
import sqlite3
import pandas as pd
import os
import plotly.express as px # Pour les graphiques jolis

# --- CONFIGURATION ---
st.set_page_config(page_title="Statistiques Pédagogiques", page_icon="📊", layout="wide")

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
DB_FILE_PATH = os.path.join(root_dir, "pedago.db")

# --- FONCTIONS ---
def get_stats_data():
    conn = sqlite3.connect(DB_FILE_PATH)
    
    # 1. Récupérer TOUT le référentiel (ce qui est possible de faire)
    # On suppose que la table 'competences' est à jour via l'autre page
    df_ref = pd.read_sql("SELECT domaine, competence, skill FROM competences", conn)
    
    # 2. Récupérer TOUT l'historique (ce qui a été fait)
    try:
        df_hist = pd.read_sql("SELECT date, classe, domaine, competence, skill FROM historique", conn)
    except:
        # Si la table n'existe pas encore (aucune fiche générée avec la nouvelle version)
        df_hist = pd.DataFrame(columns=['date', 'classe', 'domaine', 'competence', 'skill'])
        
    conn.close()
    return df_ref, df_hist

# --- INTERFACE ---
st.title("📊 Suivi de la progression")
st.info("Cette page compare l'ensemble des savoir-faire présents dans vos CSV avec ceux que vous avez réellement utilisés dans vos fiches générées.")

# Chargement
df_ref, df_hist = get_stats_data()

if df_ref.empty:
    st.error("Aucune compétence trouvée. Veuillez vérifier vos fichiers CSV.")
    st.stop()

# --- FILTRES ---
col1, col2 = st.columns(2)
with col1:
    # Filtre par domaine
    domaines_dispo = ["Tous"] + sorted(df_ref['domaine'].unique().tolist())
    choix_domaine = st.selectbox("Filtrer par Base de données", domaines_dispo)

with col2:
    # Filtre par classe (si dispo dans l'historique)
    if not df_hist.empty:
        classes_dispo = ["Toutes"] + sorted(df_hist['classe'].unique().tolist())
        choix_classe = st.selectbox("Filtrer par Classe (Historique)", classes_dispo)
    else:
        choix_classe = "Toutes"

# --- FILTRAGE DES DONNÉES ---
# 1. Filtrer le Référentiel (Objectif total)
if choix_domaine != "Tous":
    df_ref_filtered = df_ref[df_ref['domaine'] == choix_domaine]
else:
    df_ref_filtered = df_ref

# 2. Filtrer l'Historique (Réalisé)
df_hist_filtered = df_hist.copy()
if choix_domaine != "Tous":
    df_hist_filtered = df_hist_filtered[df_hist_filtered['domaine'] == choix_domaine]
if choix_classe != "Toutes":
    df_hist_filtered = df_hist_filtered[df_hist_filtered['classe'] == choix_classe]

# --- CALCULS ---
# Nombre total de savoir-faire uniques dans le référentiel
total_skills = df_ref_filtered['skill'].nunique()

# Nombre de savoir-faire uniques validés (faits au moins 1 fois)
if not df_hist_filtered.empty:
    # On regarde quels skills du référentiel sont dans l'historique filtré
    skills_faits = df_hist_filtered['skill'].unique()
    # On intersecte pour être sûr (au cas où un skill a changé de nom)
    skills_validated = [s for s in skills_faits if s in df_ref_filtered['skill'].values]
    nb_faits = len(skills_validated)
else:
    nb_faits = 0
    skills_validated = []

pourcentage = round((nb_faits / total_skills) * 100, 1) if total_skills > 0 else 0

# --- KPI ---
k1, k2, k3 = st.columns(3)
k1.metric("Total Savoir-faire (Référentiel)", total_skills)
k2.metric("Savoir-faire abordés", nb_faits)
k3.metric("Couverture", f"{pourcentage}%")

# Barre de progression
st.progress(pourcentage / 100)

st.divider()

# --- TABLEAUX DÉTAILLÉS ---
tab1, tab2 = st.tabs(["✅ Ce qui est FAIT", "❌ Ce qu'il RESTE à faire"])

with tab1:
    st.subheader("Savoir-faire déjà travaillés")
    if nb_faits > 0:
        # On compte combien de fois chaque skill a été fait
        counts = df_hist_filtered['skill'].value_counts().reset_index()
        counts.columns = ['skill', 'Nb Fois']
        
        # On recole les infos de domaine/compétence depuis le référentiel
        df_done = pd.merge(counts, df_ref_filtered, on='skill', how='left')
        
        # Affichage tableau
        st.dataframe(
            df_done[['domaine', 'competence', 'skill', 'Nb Fois']],
            use_container_width=True,
            hide_index=True
        )
        
        # Graphique
        if st.checkbox("Afficher le graphique des fréquences"):
            fig = px.bar(df_done.head(20), x='skill', y='Nb Fois', color='domaine', title="Top 20 des savoir-faire les plus utilisés")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Aucun savoir-faire validé pour cette sélection.")

with tab2:
    st.subheader("⚠️ Savoir-faire JAMAIS abordés")
    
    # On prend tous les skills du référentiel qui NE SONT PAS dans la liste des validés
    df_missing = df_ref_filtered[~df_ref_filtered['skill'].isin(skills_validated)]
    
    if not df_missing.empty:
        st.dataframe(
            df_missing[['domaine', 'competence', 'skill']],
            use_container_width=True,
            hide_index=True
        )
        st.caption(f"Il reste {len(df_missing)} savoir-faire à traiter dans cette sélection.")
    else:
        st.success("Bravo ! Tout le référentiel a été couvert pour cette sélection ! 🎉")

st.divider()
st.caption("Note : Les statistiques se basent uniquement sur les fiches générées depuis la mise en place de ce système.")
