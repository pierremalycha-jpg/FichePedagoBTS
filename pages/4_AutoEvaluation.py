import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import datetime
import os
from fpdf import FPDF # On ajoute la génération PDF ici aussi

# --- 1. CONFIGURATION ET CHEMINS ---
st.set_page_config(page_title="Auto-Évaluation", page_icon="🎯", layout="wide")

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
DB_FILE_PATH = os.path.join(root_dir, "pedago.db")

# --- 2. UTILITAIRES PDF (BILAN) ---
def clean_text(text):
    if not isinstance(text, str): return str(text)
    replacements = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "…": "...", "œ": "oe", "€": "Eur"}
    for char, rep in replacements.items(): text = text.replace(char, rep)
    return text.encode('latin-1', 'replace').decode('latin-1')

class PDFBilan(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'BILAN INDIVIDUEL DE COMPETENCES', 0, 1, 'C')
        self.ln(10)

def create_bilan_pdf(identite, df_res):
    pdf = PDFBilan()
    pdf.add_page()
    
    # Infos Élève
    pdf.set_font('Arial', '', 12)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 10, clean_text(f"Eleve : {identite['nom']} {identite['prenom']}  |  Classe : {identite['classe']}"), 1, 1, 'L', 1)
    pdf.cell(0, 10, clean_text(f"Date : {datetime.datetime.now().strftime('%d/%m/%Y')}"), 1, 1, 'L', 1)
    pdf.ln(10)
    
    # Tableau Résultats
    pdf.set_font('Arial', 'B', 11)
    pdf.set_fill_color(50, 50, 50)
    pdf.set_text_color(255, 255, 255)
    
    # En-têtes
    w_poste = 60
    w_score = 20
    w_statut = 30
    w_conseil = 80
    
    pdf.cell(w_poste, 10, "Poste / Activite", 1, 0, 'C', 1)
    pdf.cell(w_score, 10, "Note", 1, 0, 'C', 1)
    pdf.cell(w_statut, 10, "Statut", 1, 0, 'C', 1)
    pdf.cell(w_conseil, 10, "Suggestions", 1, 1, 'C', 1)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 10)
    
    for index, row in df_res.iterrows():
        # Couleur de fond selon le statut
        if row['Priorite'] == 1: # Critique
            pdf.set_fill_color(255, 235, 235)
        elif row['Priorite'] == 2: # Moyen
            pdf.set_fill_color(255, 245, 230)
        else: # Bon
            pdf.set_fill_color(235, 255, 235)
            
        # Hauteur dynamique (basée sur le conseil qui est le plus long)
        conseil_clean = clean_text(row['Conseil'])
        lines = pdf.multi_cell(w_conseil, 6, conseil_clean, split_only=True)
        h_line = max(10, len(lines) * 6 + 4)
        
        # Position de départ
        y_curr = pdf.get_y()
        
        # Poste
        pdf.set_xy(10, y_curr)
        pdf.cell(w_poste, h_line, clean_text(row['Poste']), 1, 0, 'L', 1)
        
        # Score
        pdf.set_xy(10 + w_poste, y_curr)
        score_txt = f"{row['Score']}/{row['Max']}"
        pdf.cell(w_score, h_line, score_txt, 1, 0, 'C', 1)
        
        # Statut (Nettoyage des emojis pour le PDF)
        statut_clean = clean_text(row['Statut'].replace("🟢", "").replace("🟠", "").replace("🔴", "").strip())
        pdf.set_xy(10 + w_poste + w_score, y_curr)
        pdf.cell(w_statut, h_line, statut_clean, 1, 0, 'C', 1)
        
        # Conseil (Multi-cell)
        pdf.set_xy(10 + w_poste + w_score + w_statut, y_curr)
        pdf.multi_cell(w_conseil, 6, conseil_clean, border=0, align='L')
        # Cadre par dessus
        pdf.set_xy(10 + w_poste + w_score + w_statut, y_curr)
        pdf.cell(w_conseil, h_line, "", 1, 0)
        
        pdf.set_y(y_curr + h_line)
        
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 3. GESTION BASE DE DONNÉES ---
def init_results_db():
    conn = sqlite3.connect(DB_FILE_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS resultats_quiz (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date_heure TEXT, nom TEXT, prenom TEXT, 
            classe TEXT, poste TEXT, score INTEGER, score_max INTEGER, pourcentage REAL, statut TEXT)''')
    conn.commit()
    conn.close()

def save_student_results(identite, df_resultats):
    conn = sqlite3.connect(DB_FILE_PATH)
    c = conn.cursor()
    date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for index, row in df_resultats.iterrows():
        c.execute('''INSERT INTO resultats_quiz (date_heure, nom, prenom, classe, poste, score, score_max, pourcentage, statut)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
            (date_now, identite['nom'], identite['prenom'], identite['classe'], row['Poste'], 
             int(row['Score']), int(row['Max']), float(row['Pourcentage']), row['Statut']))
    conn.commit()
    conn.close()

init_results_db()

# --- 4. BANQUE DE QUESTIONS ---
QUIZ_DATA = {
    "Chef Équipement Plateau Vert": [
        {"niveau": "Débutant (1pt)", "points": 1, "question": "Quel câble est utilisé pour relier une caméra standard à la grille vidéo ?", "options": ["XLR", "BNC (SDI)", "RJ45", "HDMI"], "reponse": "BNC (SDI)"},
        {"niveau": "Intermédiaire (2pts)", "points": 2, "question": "Lors de l'installation, quelle est la priorité absolue ?", "options": ["La propreté du plateau", "La sécurisation des câbles au sol (Gaffer)", "La rapidité", "L'esthétique"], "reponse": "La sécurisation des câbles au sol (Gaffer)"},
        {"niveau": "Expert (3pts)", "points": 3, "question": "Si une caméra ne reçoit pas de Genlock, quel est le symptôme visuel probable ?", "options": ["L'image est noire", "L'image saute ou 'roll'", "Les couleurs sont inversées", "Le son est désynchronisé"], "reponse": "L'image saute ou 'roll'"}
    ],
    "Truquiste Plateau Bleu": [
        {"niveau": "Débutant (1pt)", "points": 1, "question": "Quelle couleur est généralement utilisée pour l'incrustation (Chroma Key) ?", "options": ["Rouge", "Vert ou Bleu", "Blanc", "Noir"], "reponse": "Vert ou Bleu"},
        {"niveau": "Intermédiaire (2pts)", "points": 2, "question": "Sur un mélangeur, qu'est-ce qu'un DSK (Downstream Keyer) ?", "options": ["Une incrustation amont", "Une couche graphique finale", "Une transition", "Un réglage audio"], "reponse": "Une couche graphique finale"},
        {"niveau": "Expert (3pts)", "points": 3, "question": "Pour réussir une incrustation, quel élément est critique avant le mélangeur ?", "options": ["Le choix de la caméra", "L'éclairage uniforme du fond", "Le logiciel", "Le micro"], "reponse": "L'éclairage uniforme du fond"}
    ],
    "Sondier Plateau": [
        {"niveau": "Débutant (1pt)", "points": 1, "question": "Quel type de micro tient-on généralement à la main ?", "options": ["Cravate", "Micro main (dynamique)", "Canon", "Contact"], "reponse": "Micro main (dynamique)"},
        {"niveau": "Intermédiaire (2pts)", "points": 2, "question": "Qu'est-ce que l'alimentation fantôme (48V) ?", "options": ["Batterie de secours", "Pour les micros statiques", "Effet sonore", "Alimentation enceinte"], "reponse": "Pour les micros statiques"},
        {"niveau": "Expert (3pts)", "points": 3, "question": "Niveau de référence (Test Tone) standard en broadcast numérique (EBU) ?", "options": ["0 dBFS", "-9 dBFS", "-18 dBFS", "-10 dB"], "reponse": "-18 dBFS"}
    ]
}

def calculer_resultats(user_answers):
    resultats = []
    for role, questions in QUIZ_DATA.items():
        score_role = 0
        max_score = 0
        for i, q in enumerate(questions):
            max_score += q['points']
            key = f"{role}_{i}"
            if user_answers.get(key) == q['reponse']:
                score_role += q['points']
        
        pourcentage = (score_role / max_score) * 100
        
        if score_role == max_score: 
            statut, priorite, conseil = "🟢 Maîtrisé", 3, "Excellent travail. Tu peux passer au rôle suivant ou aider tes camarades."
        elif score_role >= (max_score / 2): 
            statut, priorite, conseil = "🟠 En cours", 2, "Bon début. Relis les fiches techniques sur les points experts."
        else: 
            statut, priorite, conseil = "🔴 Critique", 1, "⚠️ À retravailler d'urgence. Reprends les bases théoriques avant de manipuler."
            
        resultats.append({
            "Poste": role, "Score": score_role, "Max": max_score,
            "Pourcentage": round(pourcentage, 1), "Statut": statut, "Conseil": conseil, "Priorite": priorite
        })
    return pd.DataFrame(resultats)

# --- 5. INTERFACE ---
st.title("🎯 Auto-Évaluation des Compétences")

with st.container(border=True):
    st.subheader("👤 Identification")
    col_id1, col_id2, col_id3 = st.columns(3)
    eleve_nom = col_id1.text_input("Votre Nom")
    eleve_prenom = col_id2.text_input("Votre Prénom")
    eleve_classe = col_id3.selectbox("Votre Classe", ["TIEE", "Montage", "Gestion", "Image", "Son"])

st.divider()

if not eleve_nom or not eleve_prenom:
    st.info("👋 Veuillez remplir votre Nom et Prénom ci-dessus pour commencer le test.")
else:
    with st.form("quiz_form"):
        user_answers = {}
        for role, questions in QUIZ_DATA.items():
            st.markdown(f"### 📺 {role}")
            for i, q in enumerate(questions):
                key = f"{role}_{i}"
                st.write(f"**{q['niveau']}** : {q['question']}")
                user_answers[key] = st.radio("Réponse", q['options'], key=key, label_visibility="collapsed", index=None)
            st.markdown("---")
        submitted = st.form_submit_button("✅ Valider et envoyer mes résultats", type="primary", use_container_width=True)

    if submitted:
        if None in user_answers.values():
            st.warning("⚠️ Certaines questions n'ont pas de réponse.")
        
        df_res = calculer_resultats(user_answers)
        
        identite = {"nom": eleve_nom, "prenom": eleve_prenom, "classe": eleve_classe}
        save_student_results(identite, df_res)
        st.success("💾 Résultats enregistrés !")
        
        # --- RÉSULTATS VISUELS ---
        st.header(f"Bilan pour {eleve_prenom}")
        
        col_graph, col_tab = st.columns([1, 1.5])
        
        with col_graph:
            df_chart = df_res.sort_values("Pourcentage", ascending=True)
            colors = df_chart['Pourcentage'].apply(lambda x: '#ff4b4b' if x < 50 else ('#ffa421' if x < 100 else '#21c354'))
            fig = px.bar(df_chart, x='Pourcentage', y='Poste', orientation='h', text='Statut', range_x=[0, 100], title="Aperçu Graphique")
            fig.update_traces(marker_color=colors, textposition='auto')
            st.plotly_chart(fig, use_container_width=True)
            
        with col_tab:
            st.subheader("📋 Suggestions de travail")
            # Affichage d'un tableau propre à l'écran
            st.dataframe(
                df_res[['Poste', 'Statut', 'Conseil']],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Poste": st.column_config.TextColumn("Poste visé"),
                    "Statut": st.column_config.TextColumn("Niveau"),
                    "Conseil": st.column_config.TextColumn("Suggestion de travail", width="large"),
                }
            )
            
            # Génération du PDF
            pdf_bytes = create_bilan_pdf(identite, df_res)
            fname = f"Bilan_{eleve_nom}_{eleve_prenom}.pdf"
            st.download_button(
                label="📥 Télécharger ma Fiche Bilan (PDF)",
                data=pdf_bytes,
                file_name=fname,
                mime='application/pdf',
                type='primary',
                use_container_width=True
            )

# --- ADMIN ---
st.markdown("---")
with st.expander("🔒 Zone Professeur"):
    password = st.text_input("Mot de passe", type="password")
    if password == "admin":
        conn = sqlite3.connect(DB_FILE_PATH)
        try:
            df_all = pd.read_sql("SELECT * FROM resultats_quiz ORDER BY date_heure DESC", conn)
            st.dataframe(df_all)
            csv = df_all.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Télécharger CSV", data=csv, file_name="notes_promo.csv", mime="text/csv")
            if st.button("⚠️ Effacer tout"):
                c = conn.cursor()
                c.execute("DELETE FROM resultats_quiz")
                conn.commit()
                st.rerun()
        except: st.write("Rien.")
        conn.close()
