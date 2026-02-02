import streamlit as st
import os

def show_context():
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
        .slogan {
            font-size: 1.5rem;
            font-style: italic;
            text-align: center;
            color: #64748b;
            margin-bottom: 40px;
            font-family: 'Georgia', serif;
        }
        .narrative-text {
            font-size: 1.2rem;
            line-height: 1.8;
            text-align: justify;
            color: #334155;
            margin: 0 auto;
            max-width: 900px;
            padding-bottom: 20px;
        }
        .feature-card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            height: 100%;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            transition: transform 0.3s ease;
        }
        .feature-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 15px rgba(0,0,0,0.1);
        }
        .feature-card h3 { color: #1e3a8a !important; font-weight: 700; margin-bottom: 10px; }
        .feature-card h4 { color: #2563eb !important; font-weight: 600; }
        .feature-card p, .feature-card li { color: #475569 !important; font-size: 1rem; line-height: 1.5; text-align: left; }
        
        .section-header {
            font-size: 2rem;
            text-align: center;
            font-weight: 800;
            color: #0f172a;
            margin-top: 60px;
            margin-bottom: 30px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .cta-box {
            background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
            padding: 40px;
            border-radius: 20px;
            text-align: center;
            margin-top: 50px;
            margin-bottom: 30px;
            color: white !important;
        }
        .cta-box h2, .cta-box p { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

    # 2. EN-TÊTE
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if os.path.exists("img/logo.png"):
            st.image("img/logo.png", use_container_width=True)
        else:
            st.markdown("<div style='text-align:center; font-size:4rem;'>🏥</div>", unsafe_allow_html=True)

    st.markdown('<h1 class="main-title">Urgence Manager</h1>', unsafe_allow_html=True)
    st.markdown('<p class="slogan">Gestion logistique agentique des urgences hospitalières</p>', unsafe_allow_html=True)

    st.markdown("""
    <div class="narrative-text">
        <b>Urgence Manager</b> est un assistant d'aide à la décision conçu pour répondre aux défis critiques des services d'urgences : 
        flux imprévisibles, ressources limitées et pression temporelle.
        <br><br>
        Notre approche repose sur une <b>architecture hybride</b> : un moteur de règles déterministe pour la sécurité logistique, 
        couplé à une Intelligence Artificielle (Mistral AI & Machine Learning) pour l'analyse et l'anticipation.
    </div>
    """, unsafe_allow_html=True)


    # 3. LES 3 OBJECTIFS 

    
    st.divider()
    st.markdown('<h2 class="section-header">🎯 Les 3 Piliers du Projet</h2>', unsafe_allow_html=True)

    obj1, obj2, obj3 = st.columns(3)

    with obj1:
        st.markdown("""
        <div class="feature-card">
            <h4>📦 Gestion Logistique</h4>
            <p>Modélisation explicite des flux.</p>
            <ul>
                <li>Gestion des ressources limitées (lits, box, personnel).</li>
                <li>Détection des goulots d'étranglement.</li>
                <li>Respect des contraintes médicales.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with obj2:
        st.markdown("""
        <div class="feature-card">
            <h4>🧠 Aide à la Décision</h4>
            <p>Interaction en langage naturel.</p>
            <ul>
                <li>Analyse de l'état du service en temps réel.</li>
                <li>Explication des priorités et risques.</li>
                <li>Traçabilité des événements via logs.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with obj3:
        st.markdown("""
        <div class="feature-card">
            <h4>🌱 IA Responsable</h4>
            <p>Sobriété et maîtrise.</p>
            <ul>
                <li>Priorité aux règles métier (Source de Vérité).</li>
                <li>Usage ciblé du ML et des LLM.</li>
                <li>Séparation stricte : Analyse ≠ Action.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # 4. INTELLIGENCE ARTIFICIELLE & DATA
    
    st.markdown('<h2 class="section-header">⚙️ Sous le Capot</h2>', unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("""
        <div class="feature-card">
            <h3>📊 Machine Learning (Scikit-Learn)</h3>
            <p>Trois modèles statistiques intégrés dans le Dashboard :</p>
            <ul>
                <li><b>Clustering (K-Means) :</b> Classification de l'état de tension (Calme, Normal, Critique).</li>
                <li><b>Classification (Random Forest) :</b> Prédiction du risque d'hospitalisation.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="feature-card">
            <h3>🤖 IA Générative (Mistral)</h3>
            <p>Un pipeline RAG (Retrieval-Augmented Generation) pour l'assistant :</p>
            <ul>
                <li><b>Lecture seule :</b> L'IA analyse l'état et l'historique CSV.</li>
                <li><b>Explication :</b> Répond aux questions ("Pourquoi cette attente ?").</li>
                <li><b>Agentivité :</b> Capacité supervisée à proposer des actions.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # 5. NAVIGATION
   
    st.divider()
    st.markdown('<h2 class="section-header">🧭 Structure de l\'Application</h2>', unsafe_allow_html=True)
    
    nav1, nav2, nav3 = st.columns(3)
    
    with nav1:
        st.info("**🎮 Simulateur Live**\n\nLe cœur du réacteur. Injectez des patients, lancez des scénarios et voyez l'IA interagir avec le moteur de règles.")
    with nav2:
        st.success("**📊 Dashboard & KPIs**\n\nLa tour de contrôle. Analysez les données historiques, visualisez les flux (Sankey) et les prédictions ML.")
    with nav3:
        st.warning("**ℹ️ À Propos**\n\nLes détails du projet. L'équipe, le contexte académique (Master SISE) et la stack technique.")
        
    # 6. CTA FINAL
    
    st.markdown("""
    <div class="cta-box">
        <h2 style="color:white; margin-bottom:10px;">Prêt à réguler ?</h2>
        <p style="font-size: 1.2rem; margin-bottom: 20px;">
            Rendez-vous dans l'onglet <b>Simulateur Live</b> pour lancer votre première session.
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    show_context()
