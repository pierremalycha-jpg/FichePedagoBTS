import streamlit as st
from fpdf import FPDF
import datetime
import sqlite3
import pandas as pd
import os
import io
from pypdf import PdfWriter, PdfReader

# --- 1. CONFIGURATION ET CHEMINS ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
DB_FILE_PATH = os.path.join(root_dir, "pedago.db")

CSV_FILES = {
    "TIEE": os.path.join(root_dir, "TIEE.csv"),
    "IMAGE": os.path.join(root_dir, "Image.csv"),
    "MONTAGE": os.path.join(root_dir, "montage.csv")
}

# --- 2. FONCTIONS UTILITAIRES ---
def clean_text(text):
    if not isinstance(text, str):
        return str(text) if text is not None else ""
    replacements = {
        "’": "'", "‘": "'", "“": '"', "”": '"',
        "–": "-", "…": "...", "œ": "oe", "€": "Eur", "•": "-"
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text.encode('latin-1', 'replace').decode('latin-1')

def create_annex_overlay():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(200, 0, 0)
    pdf.set_y(5)
    pdf.cell(0, 10, "Documents pour la seance", 0, 1, 'C')
    pdf.set_line_width(1)
    pdf.rect(5, 5, 200, 287)
    return pdf.output(dest='S').encode('latin-1')

# --- 3. GESTION BDD ---
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
        final_df.to_sql('competences_eval', conn, if_exists='replace', index=False)
    conn.close()

def get_data_for_domain(selected_domain):
    init_db()
    conn = sqlite3.connect(DB_FILE_PATH)
    c = conn.cursor()
    try:
        c.execute('SELECT label, competence, skill FROM competences_eval WHERE domaine = ?', (selected_domain,))
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

# --- 4. GESTION ÉTAT ---
st.set_page_config(page_title="Générateur d'Évaluation", layout="wide", page_icon="🎓")

if 'eval_blocks' not in st.session_state: st.session_state.eval_blocks = []

def add_block(competence, skills, label, domain, all_skills_available):
    st.session_state.eval_blocks.append({
        "id": datetime.datetime.now().timestamp(),
        "domain": domain, "competence": competence, "skills": skills,
        "all_skills": all_skills_available, "label": label
    })

def remove_block(index):
    st.session_state.eval_blocks.pop(index)

# --- 5. CLASSE PDF COMPACTE ---
class PDFEval(FPDF):
    def header(self):
        pass

    def draw_grading_header(self):
        # Police réduite (9) et hauteur réduite (5mm)
        self.set_font('Arial', 'B', 9)
        self.set_fill_color(220, 220, 220)
        w_text = 150
        w_note = 10
        h_head = 5 # Hauteur fine
        self.cell(w_text, h_head, "Competences / Savoirs-faire Evalues", 1, 0, 'C', 1)
        self.cell(w_note, h_head, "0", 1, 0, 'C', 1)
        self.cell(w_note, h_head, "1", 1, 0, 'C', 1)
        self.cell(w_note, h_head, "2", 1, 0, 'C', 1)
        self.cell(w_note, h_head, "3", 1, 1, 'C', 1) 

    def check_space(self, height):
        if 297 - 10 - self.get_y() < height: # Marge bas réduite à 10
            self.add_page()
            self.draw_grading_header()

def create_eval_pdf(info, blocks):
    pdf = PDFEval()
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    # --- EN-TÊTE COMPACT ---
    pdf.set_font('Arial', 'B', 16) # Titre un peu plus petit
    pdf.cell(0, 8, "FICHE D'EVALUATION", 0, 1, 'C')
    pdf.ln(2)
    
    pdf.set_font('Arial', '', 10) # Police infos réduite
    y_start = pdf.get_y()
    
    # Cadre réduit en hauteur (18mm au lieu de 25)
    pdf.rect(10, y_start, 190, 18) 
    
    pdf.set_xy(15, y_start + 4)
    pdf.cell(100, 6, "Nom / Prenom : ............................................................", 0, 0)
    pdf.cell(80, 6, f"Date : {clean_text(str(info['date']))}", 0, 1, 'R')
    
    pdf.set_xy(15, y_start + 10)
    txt_seq = f"Seq {info['seq']}" if info['seq'] else ""
    txt_sea = f"Sea {info['sea']}" if info['sea'] else ""
    full_context = f"Classe : {clean_text(info['classe'])}   |   {info['type_eval']}   |   {txt_seq}  {txt_sea}"
    pdf.cell(0, 6, clean_text(full_context), 0, 1, 'L')
    
    pdf.set_y(y_start + 22) # On colle le reste juste dessous

    if info['desc']:
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(0, 5, "Contexte :", 0, 1)
        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(0, 4, clean_text(info['desc'])) # Interligne 4mm
        pdf.ln(3)

    # --- TABLEAU ---
    pdf.draw_grading_header()
    
    w_text = 150
    w_note = 10
    
    for block in blocks:
        # --- ENTÊTE SPLITTÉ COMPACT ---
        pdf.check_space(20)
        y_head_start = pdf.get_y()
        
        pdf.set_fill_color(240, 245, 255)
        pdf.set_text_color(0, 50, 100)
        
        # Case Gauche
        w_act = 70
        pdf.set_font('Arial', 'B', 9) # Police 9
        pdf.set_xy(10, y_head_start)
        pdf.multi_cell(w_act, 6, f"Act : {clean_text(block['label'])}", 1, 'L', 1)
        h_left = pdf.get_y() - y_head_start
        
        # Case Droite
        w_comp = 120
        pdf.set_font('Arial', 'I', 8) # Police 8
        pdf.set_xy(10 + w_act, y_head_start)
        pdf.multi_cell(w_comp, 6, f"Comp : {clean_text(block['competence'])}", 1, 'L', 1)
        h_right = pdf.get_y() - y_head_start
        
        # Ajustement hauteur
        h_max = max(h_left, h_right)
        pdf.set_xy(10, y_head_start)
        pdf.cell(w_act, h_max, "", 1, 0)
        pdf.set_xy(10 + w_act, y_head_start)
        pdf.cell(w_comp, h_max, "", 1, 0)
        
        pdf.set_y(y_head_start + h_max)
        
        # --- LISTE CRITÈRES FINE ---
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Arial', '', 8) # Police 8 pour les items !
        
        for skill in block['skills']:
            skill_clean = clean_text(skill)
            y_current = pdf.get_y()
            
            # Calcul hauteur (interligne très fin : 4mm)
            lines = pdf.multi_cell(w_text, 4, f"- {skill_clean}", border=0, split_only=True)
            nb_lines = len(lines)
            h_line = max(5, nb_lines * 4) # Min 5mm de haut
            
            pdf.check_space(h_line)
            y_current = pdf.get_y()
            
            # Cases notes
            x_start_notes = 10 + w_text
            pdf.set_xy(x_start_notes, y_current)
            for _ in range(4):
                pdf.cell(w_note, h_line, "", 1, 0)
            
            # Texte
            pdf.set_xy(10, y_current)
            pdf.multi_cell(w_text, 4, f"- {skill_clean}", border=1, align='L') # Interligne 4
            pdf.set_y(y_current + h_line)

        # --- NON ÉVALUÉS ---
        all_s = set(block['all_skills'])
        selected_s = set(block['skills'])
        not_evaluated = list(all_s - selected_s)
        
        if not_evaluated:
            pdf.check_space(10)
            pdf.set_font('Arial', 'I', 7) # Police très petite (7)
            pdf.set_text_color(100, 100, 100)
            pdf.set_fill_color(250, 250, 250)
            
            missing_txt = ", ".join(sorted(not_evaluated))
            full_txt = f"Non evalue : {clean_text(missing_txt)}"
            
            # Hauteur fine (4mm par ligne)
            pdf.multi_cell(190, 4, full_txt, 1, 'L', 1)
            pdf.set_text_color(0, 0, 0)

    # --- COMMENTAIRES ---
    # On regarde s'il reste de la place en bas
    space_left = 297 - 15 - pdf.get_y()
    if space_left > 20: # S'il reste au moins 2cm
        pdf.ln(3)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(0, 5, "Commentaires :", 0, 1)
        # Le cadre prend toute la place restante (max 40mm pour pas être moche)
        h_comments = min(space_left - 10, 40) 
        pdf.rect(10, pdf.get_y(), 190, h_comments)

    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 6. INTERFACE ---
st.title("🎓 Création de Fiche d'Évaluation")
col_edit, col_preview = st.columns([1, 1.2])

with col_edit:
    st.subheader("1. Configuration")
    with st.container(border=True):
        types_eval = ["Evaluation Formative", "Evaluation Sommative", "Evaluation Diagnostique", "CCF Blanc"]
        sel_type = st.selectbox("Type d'évaluation", types_eval)
        c_seq, c_sea = st.columns(2)
        info_seq = c_seq.text_input("Séquence N°", placeholder="3")
        info_sea = c_sea.text_input("Séance N°", placeholder="1")
        c1, c2 = st.columns(2)
        info_date = c1.date_input("Date", datetime.date.today())
        info_classe = c2.text_input("Classe", placeholder="TIEE")
        info_desc = st.text_area("Description / Consignes globales", placeholder="Ex: Câblage complet...")

    st.subheader("2. Critères")
    with st.container(border=True):
        selected_domain = st.radio("Source :", list(CSV_FILES.keys()), horizontal=True)
        DATA_SOURCE = get_data_for_domain(selected_domain)
        labels = [""] + list(DATA_SOURCE.keys())
        sel_label = st.selectbox("Activité / Focus", labels)
        
        official_comp = ""
        all_skills_list = []
        sel_skills = []
        if sel_label:
            data_act = DATA_SOURCE[sel_label]
            official_comp = data_act['official_name']
            all_skills_list = data_act['skills']
            st.info(f"📌 {official_comp}")
            sel_skills = st.multiselect("Critères à évaluer", all_skills_list)
        
        if st.button("➕ Ajouter", disabled=not(sel_label and sel_skills)):
            add_block(official_comp, sel_skills, sel_label, selected_domain, all_skills_list)
            st.success("Ajouté !")
            st.rerun()

    if st.session_state.eval_blocks:
        st.markdown("---")
        for idx, block in enumerate(st.session_state.eval_blocks):
            c_txt, c_btn = st.columns([5, 1])
            c_txt.markdown(f"**[{block['domain']}] {block['label']}**")
            if c_btn.button("❌", key=f"del_{idx}"):
                remove_block(idx)
                st.rerun()

with col_preview:
    st.subheader("👁️ Aperçu")
    html_content = """<style>table {width: 100%; border-collapse: collapse; font-size:0.8em;} th, td {border: 1px solid #ddd; padding: 4px;} .grade {width: 30px;}</style>"""
    html_content += f"<h5>{sel_type}</h5>"
    if st.session_state.eval_blocks:
        html_content += "<table><tr><th>Compétences</th><th class='grade'>0</th><th class='grade'>1</th><th class='grade'>2</th><th class='grade'>3</th></tr>"
        for block in st.session_state.eval_blocks:
            html_content += f"<tr><td colspan='5' style='background:#e6f0ff; font-weight:bold; font-size:0.9em;'>{block['label']}</td></tr>"
            for skill in block['skills']:
                html_content += f"<tr><td>- {skill}</td><td></td><td></td><td></td><td></td></tr>"
            missing = list(set(block['all_skills']) - set(block['skills']))
            if missing:
                txt_miss = ", ".join(missing)
                html_content += f"<tr><td colspan='5' style='font-size:0.7em; color:gray; font-style:italic;'>Non évalué: {txt_miss}</td></tr>"
        html_content += "</table>"
    else:
        html_content += "<p style='color:gray;'>Grille vide.</p>"
    st.markdown(html_content, unsafe_allow_html=True)
    
    st.divider()
    uploaded_annexe = st.file_uploader("📎 Joindre une annexe PDF", type="pdf")
    
    info_data = {"type_eval": sel_type, "seq": info_seq, "sea": info_sea, "date": info_date, "classe": info_classe, "desc": info_desc}
    
    if st.button("🖨️ Générer la Fiche d'Évaluation", type="primary", use_container_width=True):
        if not st.session_state.eval_blocks:
            st.warning("La grille est vide.")
        else:
            pdf_bytes = create_eval_pdf(info_data, st.session_state.eval_blocks)
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
                except Exception as e:
                    st.error(f"Erreur fusion : {e}")
            clean_cls = info_classe.replace(" ", "") if info_classe else "Classe"
            fname = f"Eval_{clean_cls}_{info_seq}_{info_sea}.pdf"
            st.download_button(label="📥 Télécharger PDF", data=final_pdf_bytes, file_name=fname, mime='application/pdf', use_container_width=True)
