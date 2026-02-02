import streamlit as st
import os

def show_about():
    
    st.markdown("""
    <style>
        .main-title {
            font-size: 3.5rem;
            font-weight: 900;
            text-align: center;
            background: -webkit-linear-gradient(45deg, #1e3a8a, #2563eb);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
            padding-top: 20px;
        }
        .section-header {
            font-size: 2rem;
            text-align: center;
            font-weight: 800;
            color: #0f172a;
            margin-top: 50px;
            margin-bottom: 30px;
            text-transform: uppercase;
        }
        .info-card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 15px;
            padding: 25px;
            height: 100%;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }
        .info-card h3 { color: #1e3a8a !important; font-weight: 700; margin-bottom: 15px; }
        .info-card p, .info-card li { color: #334155 !important; font-size: 1rem; line-height: 1.6; }
        
        .tech-badge {
            display: inline-block;
            background-color: #f1f5f9;
            color: #1e293b;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: 600;
            margin: 5px;
            border: 1px solid #cbd5e1;
        }
        .github-btn {
            display: inline-flex;
            align-items: center;
            background-color: #24292e;
            color: white !important;
            padding: 12px 30px;
            border-radius: 30px;
            font-weight: 600;
            text-decoration: none;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
            transition: transform 0.2s;
        }
        .github-btn:hover { transform: scale(1.05); background-color: #000; }
    </style>
    """, unsafe_allow_html=True)

    # 2. EN-TÊTE
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if os.path.exists("img/logo.png"):
            st.image("img/logo.png", use_container_width=True)
        else:
            st.markdown("<div style='text-align:center; font-size:4rem;'>🏥</div>", unsafe_allow_html=True)

    st.markdown('<h1 class="main-title">À Propos</h1>', unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#64748b; font-style:italic;'>Les coulisses d'UrgenceManager</p>", unsafe_allow_html=True)

    st.divider()

    # 3. CONTEXTE ACADÉMIQUE
    
    st.markdown('<h2 class="section-header">🎓 Contexte du Projet</h2>', unsafe_allow_html=True)
    
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.markdown("""
        <div class="info-card">
            <h3>Master 2 SISE - Data Science</h3>
            <p>
                Ce projet a été réalisé dans le cadre du Master 2 <b>Statistique et Informatique pour la Science des Données (SISE)</b> 
                de l'Université Lumière Lyon 2 (Année 2025-2026).
            </p>
            <p>
                Il répond à un besoin critique : appliquer les dernières avancées en <b>Intelligence Artificielle Générative (GenAI)</b> 
                à une problématique de santé publique concrète.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown("""
        <div class="info-card" style="text-align: center;">
            <h3>L'Équipe</h3>
            <hr style="margin: 10px 0;">
            <p><b>Lamia HATEM</b></p>
            <p><b>Maissa LAJIMI</b></p>
            <p><b>Aya MECHERI</b></p>
            <p><b>Rina RAZAFIMAHEFA</b></p>
            <p><b>Mazilda ZEHRAOUI</b></p>
        </div>
        """, unsafe_allow_html=True)

    # 4. STACK TECHNIQUE 
    
    st.divider()
    st.markdown('<h2 class="section-header">🛠️ Stack Technique</h2>', unsafe_allow_html=True)
    
    t1, t2, t3 = st.columns(3)
    
    with t1:
        st.markdown("""
        <div class="info-card">
            <h4 style="text-align:center; color:#2563eb;">💻 Core & Backend</h4>
            <div style="text-align:center;">
                <span class="tech-badge">Python 3.11+</span>
                <span class="tech-badge">Pandas</span>
                <span class="tech-badge">Simulation Event-Based</span>
            </div>
            <p style="margin-top:15px; font-size:0.9rem;">
                Moteur de règles déterministe pour gérer l'état de l'hôpital, les ressources et le temps.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
    with t2:
        st.markdown("""
        <div class="info-card">
            <h4 style="text-align:center; color:#2563eb;">🧠 IA & Data Science</h4>
            <div style="text-align:center;">
                <span class="tech-badge">Mistral AI (LLM)</span>
                <span class="tech-badge">Scikit-Learn</span>
                <span class="tech-badge">RAG</span>
            </div>
            <p style="margin-top:15px; font-size:0.9rem;">
                Modèles prédictifs (Random Forest, K-Means) et IA générative pour l'assistance contextuelle.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
    with t3:
        st.markdown("""
        <div class="info-card">
            <h4 style="text-align:center; color:#2563eb;">🎨 Interface</h4>
            <div style="text-align:center;">
                <span class="tech-badge">Streamlit</span>
                <span class="tech-badge">Plotly</span>
                <span class="tech-badge">HTML/CSS</span>
            </div>
            <p style="margin-top:15px; font-size:0.9rem;">
                Tableau de bord interactif, diagrammes de Sankey et visualisation temps réel.
            </p>
        </div>
        """, unsafe_allow_html=True)

    # 5. FOOTER & GITHUB
    
    st.write("")
    st.write("")
    st.divider()
    
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <a href="https://github.com/ZehraouiMazilda/UrgenceManager/tree/main" target="_blank" class="github-btn">
            <span style="margin-right: 10px;">📂</span> Accéder au Code Source (GitHub)
        </a>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="text-align: center; color: #94a3b8; font-size: 0.9rem;">
        <p>Projet académique développé à des fins éducatives et de recherche.</p>
        <p>© 2025-2026 Université Lumière Lyon 2</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    show_about()

