import streamlit as st
from fpdf import FPDF
import datetime
import sqlite3
import pandas as pd
import os
import io
from pypdf import PdfWriter, PdfReader

# --- CHEMINS UNIVERSELS ---
# 1. On trouve où est le fichier actuel (dans le dossier 'pages')
current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path)

# 2. On remonte d'un cran pour trouver la racine du projet (là où sont les CSV)
# dirname de ".../pages" donne la racine du projet
ROOT_PATH = os.path.dirname(current_dir)

# 3. On construit les chemins dynamiques
DB_FILE_PATH = os.path.join(ROOT_PATH, "pedago.db")

CSV_FILES = {
    "TIEE": os.path.join(ROOT_PATH, "TIEE.csv"),
    "IMAGE": os.path.join(ROOT_PATH, "Image.csv"),
    "MONTAGE": os.path.join(ROOT_PATH, "montage.csv")
}

# Petite sécurité pour éviter les plantages silencieux
if not os.path.exists(os.path.join(ROOT_PATH, "TIEE.csv")):
    # Si on ne trouve pas le fichier, on tente de regarder dans le dossier courant (cas rare)
    if os.path.exists("TIEE.csv"):
        ROOT_PATH = "."
        CSV_FILES = {k: k+".csv" for k in ["TIEE", "IMAGE", "MONTAGE"]}
        DB_FILE_PATH = "pedago.db"

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
    """Crée le cadre rouge pour les annexes"""
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
    """Initialise la base de données à partir des 3 fichiers CSV"""
    conn = sqlite3.connect(DB_FILE_PATH)
    all_data = []
    
    # On parcourt le dictionnaire des fichiers
    for domaine, file_path in CSV_FILES.items():
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path, sep=None, engine='python', encoding='utf-8')
                df.columns = df.columns.str.strip().str.lower()
                rename_map = {
                    'pré-requis': 'prerequis', 'pre-requis': 'prerequis',
                    'matériel': 'materiel', 'lien': 'liens', 'liens matières': 'liens'
                }
                df.rename(columns=rename_map, inplace=True)
                df['domaine'] = domaine
                
                required = ['competence', 'skill', 'label', 'prerequis', 'materiel', 'liens']
                for col in required:
                    if col not in df.columns: df[col] = ""
                
                df = df[['domaine'] + required]
                all_data.append(df)
            except Exception as e:
                print(f"Erreur lecture {file_path}: {e}")
    
    if all_data:
        final_df = pd.concat(all_data).fillna("")
        final_df.to_sql('competences', conn, if_exists='replace', index=False)
    
    conn.close()

def save_session_to_history(info, blocks):
    """Enregistre les stats"""
    conn = sqlite3.connect(DB_FILE_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS historique (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, classe TEXT, domaine TEXT, competence TEXT, skill TEXT)''')
    
    date_iso = info['date']
    classe = info['classe']
    for block in blocks:
        domaine = block.get('domain', 'Inconnu')
        comp = block['competence']
        for skill in block['skills']:
            c.execute('INSERT INTO historique (date, classe, domaine, competence, skill) VALUES (?, ?, ?, ?, ?)', 
                      (date_iso, classe, domaine, comp, skill))
    conn.commit()
    conn.close()

def get_data_for_domain(selected_domain):
    """C'est cette fonction qui posait problème. Elle est maintenant corrigée."""
    init_db()
    conn = sqlite3.connect(DB_FILE_PATH)
    
    # Fonction interne pour récupérer les options uniques
    def get_options(col):
        try:
            df = pd.read_sql(f"SELECT DISTINCT {col} FROM competences WHERE domaine = ? AND {col} != ''", conn, params=(selected_domain,))
            final_set = set()
            if not df.empty:
                for item in df[col].tolist():
                    for p in item.replace(';', ',').split(','):
                        if p.strip(): final_set.add(p.strip())
            return sorted(list(final_set))
        except: return []

    opts_pre = get_options('prerequis')
    opts_mat = get_options('materiel')
    opts_lie = get_options('liens')

    # Récupération des compétences
    c = conn.cursor()
    rows = []
    try:
        c.execute('SELECT label, competence, skill FROM competences WHERE domaine = ?', (selected_domain,))
        rows = c.fetchall()
    except: 
        rows = []
    conn.close()
    
    data_abc = {}
    for label, comp, skill in rows:
        if label not in data_abc: data_abc[label] = {"official_name": comp, "skills": []}
        if skill not in data_abc[label]["skills"]: data_abc[label]["skills"].append(skill)
    
    # Le RETURN est bien aligné tout à gauche maintenant !
    return data_abc, opts_pre, opts_mat, opts_lie

# --- 4. GESTION ÉTAT ---
st.set_page_config(page_title="Générateur Pédagogique", layout="wide", page_icon="📝")

if 'blocks' not in st.session_state: st.session_state.blocks = []
if 'content' not in st.session_state:
    st.session_state.content = [
        {"title": "Échauffement", "duration": "10'", "desc": ""},
        {"title": "Corps de séance", "duration": "35'", "desc": ""},
        {"title": "Retour au calme", "duration": "10'", "desc": ""}
    ]

def add_block(competence, skills, label, prerequis_str, materiel_str, liens_str, domain_src):
    st.session_state.blocks.append({
        "id": datetime.datetime.now().timestamp(),
        "domain": domain_src,
        "competence": competence, "skills": skills, "label": label,
        "prerequis": prerequis_str, "materiel": materiel_str, "liens": liens_str
    })

def remove_block(index):
    st.session_state.blocks.pop(index)

# --- 5. CLASSE PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Fiche de Preparation Pedagogique', 0, 1, 'C')
        self.ln(5)

    def section_title(self, label):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(230, 240, 255)
        self.cell(0, 8, f"  {label}", 0, 1, 'L', 1)
        self.ln(2)
        
    def check_space(self, height_needed):
        if 297 - 15 - self.get_y() < height_needed:
            self.add_page()

def create_pdf(info, blocks, content):
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    if info.get('doc_id'):
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, clean_text(info['doc_id']), 0, 1, 'R')
        pdf.ln(5)
        pdf.set_text_color(0, 0, 0)

    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, clean_text(info['title']), 0, 1, 'L')
    
    if info['seq'] or info['sea']:
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(80, 80, 80)
        txt_seq = f"Sequence : {clean_text(info['seq'])}" if info['seq'] else ""
        txt_sea = f"Seance : {clean_text(info['sea'])}" if info['sea'] else ""
        sep = "  |  " if (txt_seq and txt_sea) else ""
        pdf.cell(0, 6, f"{txt_seq}{sep}{txt_sea}", 0, 1, 'L')
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    pdf.set_font('Arial', '', 10)
    pdf.cell(60, 6, f"Date : {clean_text(str(info['date']))}", 0)
    pdf.cell(60, 6, f"Classe : {clean_text(info['classe'])}", 0)
    pdf.cell(60, 6, f"Duree : {clean_text(info['duration'])}", 0, 1)
    pdf.ln(5)

    if info['goal']:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, "Objectifs Pedagogiques :", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 5, clean_text(info['goal']))
        pdf.ln(3)
    
    if info['desc']:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, "Description / Contexte :", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 5, clean_text(info['desc']))
        pdf.ln(5)

    if blocks:
        pdf.section_title("Competences & Activites")
        for block in blocks:
            pdf.check_space(40) 
            dom_prefix = f"[{block.get('domain', '?')}] " if block.get('domain') else ""
            act_label = block.get('label', '')
            
            pdf.set_font('Arial', 'B', 11)
            pdf.set_fill_color(220, 220, 220)
            pdf.set_text_color(0, 50, 100)
            pdf.multi_cell(0, 8, f" {dom_prefix}Activite : {clean_text(act_label)}", border=1, align='L', fill=True)
            pdf.set_text_color(0, 0, 0)
            
            skills_cleaned = [clean_text(s) for s in block['skills']]
            skills_text = "\n".join([f"- {s}" for s in skills_cleaned])
            
            y_comp = pdf.get_y()
            pdf.set_font('Arial', 'I', 9)
            pdf.set_xy(10, y_comp)
            pdf.multi_cell(60, 6, clean_text(block['competence']), border=1, align='L')
            h_left = pdf.get_y() - y_comp
            
            pdf.set_font('Arial', '', 10)
            pdf.set_xy(70, y_comp)
            pdf.multi_cell(0, 6, skills_text, border=1, align='L')
            h_right = pdf.get_y() - y_comp
            
            pdf.set_y(y_comp + max(h_left, h_right))
            pdf.ln(4) 
        pdf.ln(2)

    pdf.check_space(20)
    pdf.section_title("Deroulement de la seance")
    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(20, 8, "Duree", 1, 0, 'C', 1)
    pdf.cell(40, 8, "Phase", 1, 0, 'C', 1)
    pdf.cell(0, 8, "Consignes / Actions", 1, 1, 'C', 1)

    pdf.set_font('Arial', '', 9)
    for part in content:
        if pdf.get_y() > 260: 
            pdf.add_page()
            pdf.set_font('Arial', 'B', 9)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(20, 8, "Duree", 1, 0, 'C', 1)
            pdf.cell(40, 8, "Phase", 1, 0, 'C', 1)
            pdf.cell(0, 8, "Consignes / Actions", 1, 1, 'C', 1)
            pdf.set_font('Arial', '', 9)

        y_start = pdf.get_y()
        desc = clean_text(part['desc']) if part['desc'] else "-"
        pdf.set_xy(70, y_start)
        pdf.multi_cell(0, 6, desc, border=1)
        h_desc = pdf.get_y() - y_start
        h_final = max(h_desc, 8)
        pdf.set_xy(10, y_start)
        pdf.cell(20, h_final, clean_text(part['duration']), 1, 0, 'C')
        pdf.cell(40, h_final, clean_text(part['title']), 1, 0, 'L')
        pdf.set_xy(70, y_start)
        pdf.cell(0, h_final, "", 1, 0) 
        pdf.set_xy(70, y_start)
        pdf.multi_cell(0, 6, desc)
        pdf.set_y(y_start + h_final)
    
    pdf.ln(5)

    if blocks:
        all_mat, all_pre, all_lie = set(), set(), set()
        for block in blocks:
            if block.get('materiel'): all_mat.update([x.strip() for x in block['materiel'].replace(';', ',').split(',') if x.strip()])
            if block.get('prerequis'): all_pre.update([x.strip() for x in block['prerequis'].replace(';', ',').split(',') if x.strip()])
            if block.get('liens'): all_lie.update([x.strip() for x in block['liens'].replace(';', ',').split(',') if x.strip()])

        if all_mat or all_pre or all_lie:
            pdf.check_space(50)
            pdf.section_title("Ressources & Informations Complementaires")
            
            def draw_box(title, items, x, w):
                y = pdf.get_y()
                pdf.set_font('Arial', 'B', 10)
                pdf.set_xy(x, y)
                pdf.cell(w, 8, title, 1, 1, 'C', 1)
                c = "\n".join([f"- {i}" for i in sorted(list(items))]) if items else "-"
                pdf.set_font('Arial', '', 9)
                pdf.set_xy(x, y + 8)
                pdf.multi_cell(w, 6, clean_text(c), border='LRB', align='L')
                return pdf.get_y() - y

            w_col = 63
            y_start = pdf.get_y()
            h1 = draw_box("Pre-requis", all_pre, 10, w_col)
            pdf.set_y(y_start)
            h2 = draw_box("Materiel", all_mat, 10 + w_col, w_col)
            pdf.set_y(y_start)
            h3 = draw_box("Liens Matieres", all_lie, 10 + (w_col * 2), w_col)
            pdf.set_y(y_start + max(h1, h2, h3))

    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- 6. INTERFACE UTILISATEUR ---
st.title("📝 Générateur de Fiche Pédagogique")
col_edit, col_preview = st.columns([1, 1.2])

with col_edit:
    st.subheader("1. Informations Générales")
    with st.container(border=True):
        info_title = st.text_input("Thème de la séance", placeholder="Ex: Hand-ball - Attaque placée")
        c_seq, c_sea = st.columns(2)
        info_seq = c_seq.text_input("Séquence N°", placeholder="Ex: 3")
        info_sea = c_sea.text_input("Séance N°", placeholder="Ex: 1")
        c1, c2, c3 = st.columns(3)
        info_date = c1.date_input("Date", datetime.date.today())
        info_classe = c2.text_input("Classe", placeholder="Ex: 3ème B")
        info_duration = c3.text_input("Durée", value="55 min")
        info_goal = st.text_area("Objectifs Pédagogiques", placeholder="Ex: Améliorer la prise d'information...")
        info_desc = st.text_area("Description / Contexte", placeholder="Ex: Séance axée sur le jeu réduit...")

    st.subheader("2. Compétences & Savoir-faire")
    with st.container(border=True):
        list_domains = list(CSV_FILES.keys())
        selected_domain = st.radio("📚 Choisir la base de données :", list_domains, horizontal=True)
        
        # APPEL DE LA FONCTION (QUI NE PLANTERA PLUS)
        DATA_SOURCE, OPTIONS_PRE, OPTIONS_MAT, OPTIONS_LIE = get_data_for_domain(selected_domain)
        
        labels = [""] + list(DATA_SOURCE.keys())
        sel_label = st.selectbox("Activité (Définit la Compétence)", labels)
        
        official_comp = ""
        sel_skills = []
        if sel_label:
            data_act = DATA_SOURCE[sel_label]
            official_comp = data_act['official_name']
            st.info(f"📌 Compétence ({selected_domain}): {official_comp}")
            sel_skills = st.multiselect("Savoir-faire", data_act['skills'])

        st.markdown("---")
        st.caption(f"Options complémentaires ({selected_domain}) :")
        sel_materiel = st.multiselect("🛠️ Matériel", OPTIONS_MAT)
        sel_prerequis = st.multiselect("⚠️ Pré-requis", OPTIONS_PRE)
        sel_liens = st.multiselect("🔗 Liens matières", OPTIONS_LIE)
        
        if st.button("➕ Ajouter ce bloc", disabled=not(sel_label and sel_skills)):
            add_block(
                official_comp, sel_skills, sel_label,
                ", ".join(sel_prerequis), ", ".join(sel_materiel), ", ".join(sel_liens),
                selected_domain
            )
            st.success("Bloc ajouté !")
            st.rerun()

        if st.session_state.blocks:
            st.markdown("---")
            for idx, block in enumerate(st.session_state.blocks):
                c_txt, c_btn = st.columns([4, 1])
                dom = block.get('domain', '??')
                c_txt.markdown(f"**[{dom}] {block.get('label', 'Activite')}**")
                if c_btn.button("🗑️", key=f"del_{idx}"):
                    remove_block(idx)
                    st.rerun()

    st.subheader("3. Déroulement")
    with st.container(border=True):
        for idx, part in enumerate(st.session_state.content):
            st.markdown(f"**Phase : {part['title']}**")
            c_time, c_desc = st.columns([1, 3])
            new_time = c_time.text_input(f"Durée", value=part['duration'], key=f"time_{idx}")
            new_desc = c_desc.text_area(f"Consignes", value=part['desc'], key=f"desc_{idx}", height=70)
            st.session_state.content[idx]['duration'] = new_time
            st.session_state.content[idx]['desc'] = new_desc

with col_preview:
    st.subheader("👁️ Aperçu")
    doc_id = ""
    if info_seq and info_sea:
        doc_id = f"SEQ{info_seq.strip().replace(' ', '')}SE{info_sea.strip().replace(' ', '')}"

    st.markdown(f"""
    <div style="border:1px solid #ddd; padding:20px; border-radius:5px; background:white; color:black;">
        <div style="text-align:right; color:#888; font-weight:bold;">{doc_id}</div>
        <h2 style="color:#2563eb; margin:0;">{info_title if info_title else "Titre"}</h2>
        <hr>
        <b>Date:</b> {info_date} | <b>Classe:</b> {info_classe}
        <br><br>
        <div style="background:#eff6ff; padding:10px;"><b>🎯 Objectifs:</b> {info_goal}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    uploaded_annexe = st.file_uploader("📎 Joindre un document PDF (Annexe)", type="pdf")

    current_info = {
        "title": info_title if info_title else "Séance sans titre",
        "seq": info_seq, "sea": info_sea, "doc_id": doc_id,
        "date": str(info_date), "classe": info_classe,
        "duration": info_duration, "goal": info_goal, "desc": info_desc
    }
    
    if st.button("🖨️ Générer le PDF", type="primary", use_container_width=True):
        if not info_title:
            st.warning("Il faut un titre.")
        else:
            # 1. Sauvegarde Stats
            save_session_to_history(current_info, st.session_state.blocks)
            
            # 2. Création Fiche
            pdf_bytes = create_pdf(current_info, st.session_state.blocks, st.session_state.content)
            final_pdf_bytes = pdf_bytes
            
            # 3. Fusion Annexe
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
                    st.success("✅ Annexe encadrée fusionnée !")
                except Exception as e:
                    st.error(f"Erreur fusion : {e}")

            fname = f"{doc_id}_{info_title.replace(' ', '_')}.pdf" if doc_id else f"Fiche_{info_title}.pdf"
            st.download_button(label=f"📥 Télécharger ({fname})", data=final_pdf_bytes, file_name=fname, mime='application/pdf', use_container_width=True)
