import streamlit as st
from fpdf import FPDF
import datetime
import os
import io
import sqlite3
import pandas as pd
from pypdf import PdfWriter, PdfReader

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Générateur de Séquence", layout="wide", page_icon="📅")

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
DB_FILE_PATH = os.path.join(root_dir, "pedago.db")

CSV_FILES = {
    "TIEE": os.path.join(root_dir, "TIEE.csv"),
    "IMAGE": os.path.join(root_dir, "Image.csv"),
    "MONTAGE": os.path.join(root_dir, "montage.csv")
}

# --- 2. GESTION DONNÉES ---
def init_db():
    conn = sqlite3.connect(DB_FILE_PATH)
    all_data = []
    for domaine, file_path in CSV_FILES.items():
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path, sep=None, engine='python', encoding='utf-8')
                df.columns = df.columns.str.strip().str.lower()
                rename_map = {
                    'pré-requis': 'prerequis', 'pre-requis': 'prerequis',
                    'matériel': 'materiel', 'lien': 'liens', 'categorie': 'base'
                }
                df.rename(columns=rename_map, inplace=True)
                df['domaine'] = domaine
                required = ['competence', 'skill', 'label']
                for col in required:
                    if col not in df.columns: df[col] = ""
                df = df[['domaine'] + required]
                all_data.append(df)
            except Exception as e:
                print(f"Erreur lecture {file_path}: {e}")
    if all_data:
        final_df = pd.concat(all_data).fillna("")
        final_df.to_sql('competences_seq', conn, if_exists='replace', index=False)
    conn.close()

def get_data_for_domain(selected_domain):
    init_db()
    conn = sqlite3.connect(DB_FILE_PATH)
    c = conn.cursor()
    try:
        c.execute('SELECT label, competence, skill FROM competences_seq WHERE domaine = ?', (selected_domain,))
        rows = c.fetchall()
    except: rows = []
    conn.close()
    
    data_abc = {}
    for label, comp, skill in rows:
        if label not in data_abc:
            data_abc[label] = {"official_name": comp, "skills": []}
        if skill not in data_abc[label]["skills"]:
            data_abc[label]["skills"].append(skill)
    return data_abc

# --- 3. UTILITAIRES ---
def clean_text(text):
    if not isinstance(text, str): return str(text) if text is not None else ""
    replacements = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "…": "...", "œ": "oe", "€": "Eur", "•": "-"}
    for char, rep in replacements.items(): text = text.replace(char, rep)
    return text.encode('latin-1', 'replace').decode('latin-1')

def create_annex_overlay():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(200, 0, 0)
    pdf.set_y(5)
    pdf.cell(0, 10, "Documents Annexes", 0, 1, 'C')
    pdf.set_line_width(1)
    pdf.rect(5, 5, 200, 287)
    return pdf.output(dest='S').encode('latin-1')

# --- 4. GESTION ÉTAT ---
if 'seq_steps' not in st.session_state: st.session_state.seq_steps = []
if 'seq_skills' not in st.session_state: st.session_state.seq_skills = [] 

def add_step(type_step, num, title, duration, desc):
    st.session_state.seq_steps.append({
        "type": type_step, "num": num, "title": title, "duration": duration, "desc": desc
    })

def remove_step(index): st.session_state.seq_steps.pop(index)

def move_step(index, direction):
    new_index = index + direction
    if 0 <= new_index < len(st.session_state.seq_steps):
        st.session_state.seq_steps[index], st.session_state.seq_steps[new_index] = \
        st.session_state.seq_steps[new_index], st.session_state.seq_steps[index]

def add_skill_block(domain, label, competence, skills):
    st.session_state.seq_skills.append({
        "domain": domain, "label": label, "competence": competence, "skills": skills
    })

def remove_skill_block(index): st.session_state.seq_skills.pop(index)

# --- 5. CLASSE PDF COMPACTE ---
class PDFSeq(FPDF):
    def header(self): pass 
    def check_space(self, height):
        if 297 - 10 - self.get_y() < height: self.add_page()

def create_sequence_pdf(info, steps, skills_blocks):
    pdf = PDFSeq()
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    # TITRE
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 8, clean_text(f"FICHE SEQUENCE {info['num']} : {info['title']}"), 0, 1, 'C')
    
    # INFOS
    pdf.set_font('Arial', '', 9)
    infos = f"Classe : {info['classe']}   |   Dates : {info['dates']}   |   Nb Seances : {len(steps)}"
    pdf.cell(0, 6, clean_text(infos), "B", 1, 'C')
    pdf.ln(3)

    # --- BLOC OBJECTIFS & PROBLÉMATIQUE ---
    y_start = pdf.get_y()
    
    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(95, 6, "Objectif Terminal :", 1, 0, 'L', 1)
    pdf.set_xy(105, y_start)
    pdf.cell(95, 6, "Problematique :", 1, 1, 'L', 1)
    
    y_content = pdf.get_y()
    pdf.set_font('Arial', '', 8)
    pdf.set_xy(10, y_content)
    pdf.multi_cell(95, 4, clean_text(info['obj']), 0, 'L')
    h_obj = pdf.get_y() - y_content
    
    pdf.set_xy(105, y_content)
    pdf.multi_cell(95, 4, clean_text(info['prob']), 0, 'L')
    h_prob = pdf.get_y() - y_content
    
    h_max_infos = max(h_obj, h_prob, 8)
    pdf.rect(10, y_content, 95, h_max_infos)
    pdf.rect(105, y_content, 95, h_max_infos)
    
    pdf.set_y(y_content + h_max_infos + 3)

    # --- COMPÉTENCES VISÉES (Mise en page améliorée) ---
    if skills_blocks:
        pdf.check_space(20)
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(50, 50, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 6, " Competences & Savoir-faire vises", 1, 1, 'L', 1)
        
        pdf.set_text_color(0, 0, 0)
        
        for block in skills_blocks:
            # --- Partie 1 : En-tête Gris (Activité & Compétence) ---
            pdf.check_space(12)
            
            # Fond gris clair pour distinguer l'entête
            pdf.set_fill_color(235, 235, 235)
            pdf.set_font('Arial', 'B', 8)
            
            # On formate le texte : [Domaine] Activité - Compétence
            header_txt = f"[{block['domain']}] {block['label']} : {block['competence']}"
            
            # On écrit l'entête
            pdf.multi_cell(0, 5, clean_text(header_txt), 1, 'L', 1)
            
            # --- Partie 2 : Liste des Savoir-faire (Blanc en dessous) ---
            pdf.set_font('Arial', '', 8)
            # On liste les savoir-faire séparés par des " / " pour gagner de la place
            skills_str = " / ".join(block['skills'])
            body_txt = f"Savoir-faire : {skills_str}"
            
            # On écrit le corps
            pdf.multi_cell(0, 4, clean_text(body_txt), 1, 'L', 0)
            
            # Petit espace après le bloc
            pdf.ln(1)

        pdf.ln(2)

    # --- TABLEAU DÉROULÉ ---
    pdf.check_space(15)
    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(50, 50, 50)
    pdf.set_text_color(255, 255, 255)
    
    w_type = 25
    w_dur = 15
    w_desc = 150
    
    pdf.cell(w_type, 6, "Type", 1, 0, 'C', 1)
    pdf.cell(w_desc, 6, "Contenu / Description", 1, 0, 'C', 1)
    pdf.cell(w_dur, 6, "Duree", 1, 1, 'C', 1)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 8)

    for step in steps:
        if step['type'] == "Evaluation":
            bg_r, bg_g, bg_b = 255, 240, 240
            type_label = f"EVAL {step['num']}"
        else:
            bg_r, bg_g, bg_b = 245, 250, 255
            type_label = f"SEANCE {step['num']}"

        full_desc = f"{step['title']} : {step['desc']}"
        clean_desc = clean_text(full_desc)
        
        lines = pdf.multi_cell(w_desc, 4, clean_desc, border=0, split_only=True)
        h_line = max(6, len(lines) * 4 + 2)
        
        pdf.check_space(h_line)
        y_curr = pdf.get_y()
        
        pdf.set_fill_color(bg_r, bg_g, bg_b)
        pdf.set_font('Arial', 'B', 8)
        pdf.set_xy(10, y_curr)
        pdf.cell(w_type, h_line, type_label, 1, 0, 'C', 1)
        
        pdf.set_font('Arial', '', 8)
        pdf.set_xy(10 + w_type, y_curr)
        pdf.multi_cell(w_desc, 4, clean_desc, border=0, align='L')
        pdf.set_xy(10 + w_type, y_curr)
        pdf.cell(w_desc, h_line, "", 1, 0)
        
        pdf.set_xy(10 + w_type + w_desc, y_curr)
        pdf.set_font('Arial', '', 8)
        pdf.cell(w_dur, h_line, clean_text(step['duration']), 1, 0, 'C')
        
        pdf.set_y(y_curr + h_line)

    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 6. INTERFACE ---
st.title("📅 Création de Fiche Séquence")

col_setup, col_list = st.columns([1, 1.5])

with col_setup:
    st.subheader("1. Informations")
    with st.container(border=True):
        info_num = st.text_input("N° Séquence", "1")
        info_title = st.text_input("Titre", placeholder="Ex: Captation multicam")
        c1, c2 = st.columns(2)
        info_class = c1.text_input("Classe", "TIEE")
        info_dates = c2.text_input("Dates", "Sept - Oct")
        info_obj = st.text_area("Objectif Terminal", height=70)
        info_prob = st.text_area("Problématique", height=70)

    st.subheader("2. Déroulé")
    with st.container(border=True):
        step_type = st.radio("Type", ["Séance", "Evaluation"], horizontal=True)
        c_num, c_dur = st.columns([1, 1])
        step_num = c_num.text_input("Numéro", "1")
        step_dur = c_dur.text_input("Durée", "4h")
        step_title = st.text_input("Titre étape")
        step_desc = st.text_area("Contenu rapide", height=80)
        if st.button("⬇️ Ajouter étape"):
            add_step(step_type, step_num, step_title, step_dur, step_desc)
            st.success("Ajouté")
            st.rerun()

    st.subheader("3. Compétences Visées")
    with st.container(border=True):
        sel_domain = st.radio("Base de données :", list(CSV_FILES.keys()), horizontal=True)
        DATA = get_data_for_domain(sel_domain)
        sel_act = st.selectbox("Activité", [""] + list(DATA.keys()))
        sel_comp = ""
        sel_skills = []
        if sel_act:
            sel_comp = DATA[sel_act]['official_name']
            st.caption(f"Compétence : {sel_comp}")
            sel_skills = st.multiselect("Savoir-faire visés", DATA[sel_act]['skills'])
        if st.button("➕ Ajouter compétence"):
            if sel_act and sel_skills:
                add_skill_block(sel_domain, sel_act, sel_comp, sel_skills)
                st.success("Compétence ajoutée")
                st.rerun()
            else: st.warning("Sélectionnez une activité")

with col_list:
    st.subheader("👁️ Aperçu")
    
    if st.session_state.seq_skills:
        with st.expander("🎯 Compétences visées", expanded=False):
            for idx, sk in enumerate(st.session_state.seq_skills):
                c_txt, c_del = st.columns([5, 1])
                c_txt.markdown(f"**[{sk['domain']}] {sk['label']}**")
                if c_del.button("❌", key=f"del_sk_{idx}"):
                    remove_skill_block(idx)
                    st.rerun()
    
    st.divider()

    if not st.session_state.seq_steps:
        st.info("Aucune séance ajoutée.")
    else:
        for idx, step in enumerate(st.session_state.seq_steps):
            color = "red" if step['type'] == "Evaluation" else "blue"
            with st.container(border=True):
                c_info, c_act = st.columns([5, 1])
                with c_info:
                    st.markdown(f":{color}[**{step['type'].upper()} {step['num']}**] : {step['title']}")
                    st.caption(f"⏱️ {step['duration']} | {step['desc'][:80]}...")
                with c_act:
                    if st.button("🗑️", key=f"del_{idx}"):
                        remove_step(idx)
                        st.rerun()
                    c_up, c_down = st.columns(2)
                    if idx > 0:
                        if c_up.button("⬆️", key=f"up_{idx}"):
                            move_step(idx, -1)
                            st.rerun()
                    if idx < len(st.session_state.seq_steps) - 1:
                        if c_down.button("⬇️", key=f"down_{idx}"):
                            move_step(idx, 1)
                            st.rerun()

    st.divider()
    uploaded_annexe = st.file_uploader("📎 Joindre annexe PDF", type="pdf")
    
    info_data = {"num": info_num, "title": info_title, "classe": info_class, "dates": info_dates, "prob": info_prob, "obj": info_obj}
    
    if st.button("🖨️ Générer la Fiche Séquence", type="primary", use_container_width=True):
        if not st.session_state.seq_steps:
            st.warning("Ajoutez au moins une séance.")
        else:
            pdf_bytes = create_sequence_pdf(info_data, st.session_state.seq_steps, st.session_state.seq_skills)
            final_pdf_bytes = pdf_bytes
            if uploaded_annexe:
                try:
                    merger = PdfWriter()
                    merger.append(io.BytesIO(pdf_bytes))
                    overlay_bytes = create_annex_overlay()
                    overlay_pdf = PdfReader(io.BytesIO(overlay_bytes))
                    overlay_page = overlay_pdf.pages[0]
                    annex_reader = PdfReader(uploaded_annexe)
                    for page in annex_reader.pages:
                        page.merge_page(overlay_page)
                        merger.add_page(page)
                    output_buffer = io.BytesIO()
                    merger.write(output_buffer)
                    final_pdf_bytes = output_buffer.getvalue()
                    st.success("✅ Annexe fusionnée !")
                except Exception as e: st.error(f"Erreur fusion : {e}")

            fname = f"Sequence_{info_num}_{info_title.replace(' ', '_')}.pdf"
            st.download_button(label="📥 Télécharger PDF", data=final_pdf_bytes, file_name=fname, mime='application/pdf', use_container_width=True)
