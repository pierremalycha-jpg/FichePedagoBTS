import streamlit as st
import pandas as pd
import os
from huggingface_hub import InferenceClient

# --- 1. CONFIGURATION ET CHEMINS UNIVERSELS ---
st.set_page_config(page_title="Assistant Pédagogique IA", page_icon="🤖", layout="wide")

# On trouve le dossier racine peu importe où on est (Cloud, Mac, PC)
current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path)
root_dir = os.path.dirname(current_dir)

# Noms théoriques des fichiers CSV
CSV_FILES = {
    "TIEE": "TIEE.csv",
    "IMAGE": "Image.csv",
    "MONTAGE": "montage.csv"
}

# --- 2. FONCTIONS DE CHARGEMENT ---
def get_real_file_path(filename):
    """Cherche le vrai nom du fichier (gestion majuscules/minuscules pour Linux)"""
    target = os.path.join(root_dir, filename)
    if os.path.exists(target):
        return target
    
    # Si pas trouvé, on cherche dans le dossier racine
    try:
        files = os.listdir(root_dir)
        for f in files:
            if f.lower() == filename.lower():
                return os.path.join(root_dir, f)
    except:
        return None
    return None

def get_data_lists(domaine):
    """Récupère la liste du matériel et des compétences depuis les CSV"""
    filename = CSV_FILES.get(domaine)
    file_path = get_real_file_path(filename)

    if not file_path:
        return [], []
    
    try:
        df = pd.read_csv(file_path, sep=None, engine='python', encoding='utf-8')
        df.columns = df.columns.str.strip().str.lower()
        
        rename_map = {'matériel': 'materiel', 'competence': 'competence'}
        df.rename(columns=rename_map, inplace=True)
        
        list_mat = []
        if 'materiel' in df.columns:
            raw_mat = df['materiel'].dropna().unique().tolist()
            for item in raw_mat:
                for p in str(item).replace(';', ',').split(','):
                    if p.strip(): list_mat.append(p.strip())
        
        list_comp = []
        if 'competence' in df.columns:
            list_comp = df['competence'].dropna().unique().tolist()
            
        return sorted(list(set(list_mat))), sorted(list_comp)
        
    except Exception as e:
        st.error(f"Erreur CSV : {e}")
        return [], []

def generate_activity_free(token, domaine, materiel, competences, niveau, duree):
    """Génère l'activité via l'API Gratuite Hugging Face"""
    
    # --- CHOIX DU MODÈLE (Stable & Gratuit) ---
    # Mistral Nemo est excellent en français et très disponible
    repo_id = "mistralai/Mistral-Nemo-Instruct-2407"
    
    client = InferenceClient(token=token)
    
    prompt_system = "Tu es un professeur expert en BTS Audiovisuel. Tu réponds en Français."
    prompt_user = f"""
    Agis comme un expert pédagogique. Crée une fiche d'activité pratique (TP) pour : {domaine}.
    
    INFORMATIONS :
    - Niveau : {niveau}
    - Durée : {duree}
    - Matériel DISPONIBLE : {', '.join(materiel)}
    - Compétences À VALIDER : {', '.join(competences)}
    
    Structure ta réponse en Markdown avec les sections suivantes :
    1. Titre de l'activité
    2. Contexte professionnel
    3. Objectifs pédagogiques
    4. Déroulement étape par étape
    5. Critères d'évaluation
    """
    
    try:
        messages = [
            {"role": "system", "content": prompt_system},
            {"role": "user", "content": prompt_user}
        ]
        
        response = client.chat_completion(
            model=repo_id,
            messages=messages,
            max_tokens=1500, 
            temperature=0.7
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"Erreur IA : {str(e)}"

# --- 3. INTERFACE ---
st.title("🤖 Générateur d'Activités (IA)")
st.caption("Assistant pédagogique propulsé par Mistral Nemo (Gratuit)")

# Vérification Clé API
hf_token = st.secrets.get("HUGGINGFACE_TOKEN")
if not hf_token:
    st.warning("⚠️ Token Hugging Face introuvable. Ajoutez `HUGGINGFACE_TOKEN` dans vos Secrets.")
    st.stop()

col_config, col_result = st.columns([1, 1.5])

with col_config:
    st.subheader("1. Paramètres")
    with st.container(border=True):
        sel_domaine = st.radio("Domaine", list(CSV_FILES.keys()), horizontal=True)
        
        liste_materiel, liste_competences = get_data_lists(sel_domaine)
        
        st.markdown("**Matériel dispo :**")
        sel_mat = st.multiselect("Choisir le matériel", liste_materiel)
        
        st.markdown("**Compétences :**")
        sel_comp = st.multiselect("Choisir les compétences", liste_competences)
        
        c1, c2 = st.columns(2)
        niveau = c1.selectbox("Niveau", ["Débutant", "Intermédiaire", "Avancé"])
        duree = c2.select_slider("Durée", options=["30 min", "1h", "2h", "4h"])

    if st.button("✨ Générer l'activité", type="primary", use_container_width=True):
        if not sel_mat or not sel_comp:
            st.error("Sélectionnez du matériel et des compétences.")
        else:
            with st.spinner("L'IA rédige votre sujet..."):
                resultat = generate_activity_free(hf_token, sel_domaine, sel_mat, sel_comp, niveau, duree)
                st.session_state.last_result_free = resultat

with col_result:
    st.subheader("📝 Résultat")
    
    if 'last_result_free' in st.session_state:
        st.markdown(st.session_state.last_result_free)
        
        st.download_button(
            label="📥 Télécharger la fiche",
            data=st.session_state.last_result_free,
            file_name="activite_ia.md",
            mime="text/markdown"
        )
    else:
        st.info("Configurez les paramètres à gauche et cliquez sur Générer.")
