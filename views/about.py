"""
Page À Propos - VERSION FINALE (AVEC LIEN GITHUB)
Présentation de l'équipe, du contexte académique, de la stack technique et accès au code.
"""

import streamlit as st
import os

def show_about():
    # ==============================================================================
    # 1. STYLE CSS (IDENTIQUE À CONTEXT.PY POUR LA COHÉRENCE)
    # ==============================================================================
    st.markdown("""
    <style>
        /* Titre Principal */
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
        
        /* Sous-titre */
        .slogan {
            font-size: 1.5rem;
            font-style: italic;
            text-align: center;
            color: #64748b;
            margin-bottom: 40px;
            font-family: 'Georgia', serif;
        }

        /* Cartes Blanches (CORRIGÉ DARK MODE) */
        .info-card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 15px;
            padding: 25px;
            height: 100%;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            transition: transform 0.3s ease;
        }
        .info-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 15px rgba(0,0,0,0.1);
        }
        
        /* Force les couleurs pour le Dark Mode */
        .info-card h3 {
            color: #1e3a8a !important;
            font-weight: 700;
            margin-bottom: 15px;
        }
        .info-card h4 {
            color: #2563eb !important;
            font-weight: 600;
            margin-top: 15px;
        }
        .info-card p, .info-card li {
            color: #334155 !important;
            font-size: 1rem;
            line-height: 1.6;
        }
        
        /* Badges Techniques */
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

        /* Section Header */
        .section-header {
            font-size: 2rem;
            text-align: center;
            font-weight: 800;
            color: #0f172a;
            margin-top: 50px;
            margin-bottom: 30px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        /* Bouton GitHub Custom */
        .github-btn {
            display: inline-flex;
            align-items: center;
            background-color: #24292e; /* Couleur GitHub */
            color: white !important;
            padding: 12px 30px;
            border-radius: 30px;
            font-weight: 600;
            font-size: 1.1rem;
            text-decoration: none;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
        }
        .github-btn:hover {
            background-color: #000000;
            transform: scale(1.05);
            box-shadow: 0 6px 15px rgba(0,0,0,0.3);
        }
    </style>
    """, unsafe_allow_html=True)

    # ==============================================================================
    # 2. EN-TÊTE
    # ==============================================================================
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if os.path.exists("img/logo.png"):
            st.image("img/logo.png", use_container_width=True)
        else:
            st.markdown("<div style='text-align:center; font-size:4rem;'>🏥</div>", unsafe_allow_html=True)

    st.markdown('<h1 class="main-title">À Propos</h1>', unsafe_allow_html=True)
    st.markdown('<p class="slogan">Les coulisses d\'UrgenceManager</p>', unsafe_allow_html=True)

    st.divider()

    # ==============================================================================
    # 3. LE CONTEXTE ACADÉMIQUE
    # ==============================================================================
    
    st.markdown('<h2 class="section-header">🎓 Contexte du Projet</h2>', unsafe_allow_html=True)
    
    col_ctx1, col_ctx2 = st.columns([2, 1])
    
    with col_ctx1:
        st.markdown("""
        <div class="info-card">
            <h3>Master 2 SISE - Data Science</h3>
            <p>
                Ce projet a été réalisé dans le cadre du Master 2 <b>Statistique et Informatique pour la Science des Données (SISE)</b> 
                de l'Université Lumière Lyon 2 (Année 2025-2026).
            </p>
            <p>
                Il répond à un besoin critique : appliquer les dernières avancées en <b>Intelligence Artificielle Générative (GenAI)</b> 
                à une problématique de santé publique concrète et complexe.
            </p>
            <h4>🎯 Objectifs Pédagogiques</h4>
            <ul>
                <li>Concevoir une architecture <b>Agentique</b> robuste.</li>
                <li>Implémenter un pipeline <b>RAG</b> (Retrieval-Augmented Generation).</li>
                <li>Garantir une approche <b>Responsable & Explicable</b> de l'IA.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
    with col_ctx2:
        st.markdown("""
        <div class="info-card" style="text-align: center;">
            <h3>L'Équipe</h3>
            <p>Projet réalisé par :</p>
            <hr style="margin: 10px 0;">
            <p><b>Lamia HATEM</b></p>
            <p><b>Maissa LAJIMI</b></p>
            <p><b>Aya MECHERI</b></p>
            <p><b>Rina RAZAFIMAHEFA</b></p>
            <p><b>Mazilda ZEHRAOUI</b></p>
        </div>
        """, unsafe_allow_html=True)

    # ==============================================================================
    # 4. LA STACK TECHNIQUE (Visualisation "Tech")
    # ==============================================================================
    
    st.divider()
    st.markdown('<h2 class="section-header">🛠️ Sous le Capot</h2>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("""
        <div class="info-card">
            <h3 style="text-align:center;">💻 Core & Backend</h3>
            <div style="text-align:center;">
                <span class="tech-badge">Python 3.11+</span>
                <span class="tech-badge">Pydantic</span>
                <span class="tech-badge">Pandas</span>
                <span class="tech-badge">Scikit-Learn</span>
            </div>
            <p style="margin-top:15px;">
                Une architecture modulaire basée sur des classes robustes (Typage strict) et un moteur de simulation événementiel déterministe.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown("""
        <div class="info-card">
            <h3 style="text-align:center;">🧠 Intelligence Artificielle</h3>
            <div style="text-align:center;">
                <span class="tech-badge">Mistral AI</span>
                <span class="tech-badge">RAG</span>
                <span class="tech-badge">Agentique</span>
                <span class="tech-badge">Random Forest</span>
            </div>
            <p style="margin-top:15px;">
                Utilisation de <b>Mistral-Large</b> pour le raisonnement complexe et de modèles de Machine Learning classiques pour la prédiction de flux.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown("""
        <div class="info-card">
            <h3 style="text-align:center;">🎨 Interface & Viz</h3>
            <div style="text-align:center;">
                <span class="tech-badge">Streamlit</span>
                <span class="tech-badge">Plotly</span>
                <span class="tech-badge">HTML/CSS</span>
            </div>
            <p style="margin-top:15px;">
                Un tableau de bord interactif temps réel permettant la visualisation des données et l'interaction en langage naturel.
            </p>
        </div>
        """, unsafe_allow_html=True)

    # ==============================================================================
    # 5. PHILOSOPHIE DU PROJET
    # ==============================================================================
    
    st.write("")
    st.write("")
    
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 30px; border-radius: 15px; border-left: 5px solid #2563eb;">
        <h3 style="color: #1e3a8a; margin-top: 0;">🛡️ Éthique et Responsabilité</h3>
        <p style="color: #475569; font-size: 1.1rem;">
            Ce projet adopte une approche <b>"Human-in-the-loop"</b>. L'IA ne prend jamais de décision critique seule. 
            Elle agit comme un <b>système de recommandation</b> soumis à la validation du personnel médical.
            <br><br>
            De plus, nous avons intégré une dimension <b>Green IT</b> en monitorant l'impact carbone de chaque requête générée, 
            prouvant qu'une IA performante peut aussi être sobre.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ==============================================================================
    # 6. CODE SOURCE & LICENCE (FOOTER)
    # ==============================================================================
    
    st.divider()
    
    # Section GitHub
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <a href="https://github.com/ZehraouiMazilda/UrgenceManager/tree/main" target="_blank" class="github-btn">
            <span style="margin-right: 10px;">📂</span> Accéder au Code Source (GitHub)
        </a>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="text-align: center; color: #94a3b8; font-size: 0.9rem;">
        <p>© 2025-2026 Université Lumière Lyon 2</p>
        <p>Projet développé à des fins éducatives et de recherche.</p>
        <p><i>Licence Académique</i></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    show_about()