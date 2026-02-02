"""
Page de Contexte - VERSION FINALE (README INTEGRATED & DESIGN)
Basé sur le README.md officiel et le design 'Premium'.
"""

import streamlit as st
import os

def show_context():
    # ==============================================================================
    # 1. STYLE CSS (AVEC CORRECTION DARK MODE)
    # ==============================================================================
    st.markdown("""
    <style>
        /* Titre Principal */
        .main-title {
            font-size: 3.8rem;
            font-weight: 900;
            text-align: center;
            background: -webkit-linear-gradient(45deg, #1e3a8a, #2563eb);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
            padding-top: 20px;
        }
        
        /* Sous-titre slogan */
        .slogan {
            font-size: 1.6rem;
            font-style: italic;
            text-align: center;
            color: #64748b;
            margin-bottom: 40px;
            font-family: 'Georgia', serif;
        }

        /* Texte courant élégant et centré */
        .narrative-text {
            font-size: 1.2rem;
            line-height: 1.8;
            text-align: justify;
            text-justify: inter-word;
            color: #334155;
            margin: 0 auto;
            max-width: 900px;
            padding-bottom: 20px;
        }

        /* Cartes Blanches (CORRIGÉ POUR DARK MODE) */
        .feature-card {
            background-color: #ffffff; /* Fond blanc forcé */
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
        
        /* FORCE LA COULEUR DU TEXTE DANS LES CARTES (Pour éviter le blanc sur blanc) */
        .feature-card h3 {
            color: #1e3a8a !important;
            font-size: 1.3rem;
            margin-bottom: 10px;
            font-weight: 700;
        }
        .feature-card h4 {
            color: #2563eb !important;
            font-weight: 600;
        }
        .feature-card p, .feature-card li {
            color: #475569 !important;
            font-size: 1rem;
            line-height: 1.5;
        }
        .feature-card strong {
            color: #0f172a !important;
        }

        /* Titres de section */
        .section-title {
            font-size: 2.2rem;
            text-align: center;
            font-weight: 800;
            color: #0f172a; /* Visible en light, à gérer en dark si fond transparent */
            margin-top: 60px;
            margin-bottom: 30px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .highlight {
            color: #2563eb;
            font-weight: 700;
        }
        
        /* Box CTA Finale */
        .cta-box {
            background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
            padding: 40px;
            border-radius: 20px;
            text-align: center;
            margin-top: 50px;
            margin-bottom: 30px;
            color: white !important;
        }
        .cta-box h2, .cta-box p {
            color: white !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # ==============================================================================
    # 2. HEADER
    # ==============================================================================
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if os.path.exists("img/logo.png"):
            st.image("img/logo.png", use_container_width=True)
        else:
            st.markdown("<div style='text-align:center; font-size:4rem;'>🏥</div>", unsafe_allow_html=True)

    st.markdown('<h1 class="main-title">UrgenceManager</h1>', unsafe_allow_html=True)
    st.markdown('<p class="slogan">Gestion logistique agentique des urgences hospitalières</p>', unsafe_allow_html=True)

    st.markdown("""
    <div class="narrative-text" style="text-align: center;">
        <b>Urgence Manager</b> est un assistant d'aide à la décision logistique conçu pour répondre aux défis critiques des services d'urgences : 
        ressources limitées, arrivées imprévisibles et pression temporelle continue.
        <br><br>
        Ce projet ne vise pas à remplacer le médecin, mais à fournir un <b>support opérationnel</b> capable de 
        détecter les engorgements, d'optimiser les flux et d'expliquer ses recommandations en langage naturel.
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ==============================================================================
    # 3. NAVIGATION (L'Espace de Travail)
    # ==============================================================================
    
    st.markdown('<h2 class="section-header">🧭 Structure du Projet</h2>', unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)

    with c1:
        st.markdown("""
        <div class="feature-card">
            <h3>1. Contexte & Vision</h3>
            <p><i>(Page actuelle)</i></p>
            <p>Comprendre la philosophie du projet : une architecture hybride mêlant <b>Règles Métier</b> strictes et <b>Intelligence Artificielle</b> supervisée.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        st.markdown("""
        <div class="feature-card" style="border-left: 5px solid #2563eb;">
            <h3>2. Simulateur de Régulation</h3>
            <p><i>(Vue Simulation)</i></p>
            <p>Le cœur du système. Une interface interactive pour <b>injecter des patients</b>, observer les files d'attente en temps réel et tester les capacités de triage de l'IA.</p>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div class="feature-card">
            <h3>3. Tableau de Bord</h3>
            <p><i>(Vue Dashboard)</i></p>
            <p>Supervision analytique. Suivi des <b>KPIs hospitaliers</b> (temps d'attente, saturation) et monitoring technique (coût LLM, latence, éco-score).</p>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown("""
        <div class="feature-card">
            <h3>4. À Propos</h3>
            <p><i>(Documentation)</i></p>
            <p>Détails sur l'équipe, la méthodologie académique et la stack technique utilisée (Python, Mistral AI, Streamlit).</p>
        </div>
        """, unsafe_allow_html=True)

    # ==============================================================================
    # 4. OBJECTIFS STRATEGIQUES (Issu du README)
    # ==============================================================================
    
    st.divider()
    st.markdown('<h2 class="section-header">🎯 Les 3 Piliers du Projet</h2>', unsafe_allow_html=True)

    obj1, obj2, obj3 = st.columns(3)

    with obj1:
        st.markdown("""
        <div class="feature-card">
            <h4>📦 Gestion Logistique</h4>
            <p>Modélisation explicite du parcours patient.</p>
            <ul style="text-align: left;">
                <li>Gestion des ressources limitées (lits, box).</li>
                <li>Détection des goulots d'étranglement.</li>
                <li>Respect strict des contraintes médicales.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with obj2:
        st.markdown("""
        <div class="feature-card">
            <h4>🧠 Aide à la Décision</h4>
            <p>Interaction en langage naturel.</p>
            <ul style="text-align: left;">
                <li>Analyse de l'état courant du service.</li>
                <li>Explication des priorités et des risques.</li>
                <li>Traçabilité complète des événements.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with obj3:
        st.markdown("""
        <div class="feature-card">
            <h4>🌱 IA Responsable</h4>
            <p>Sobriété et maîtrise.</p>
            <ul style="text-align: left;">
                <li>Priorité aux règles métier déterministes.</li>
                <li>Usage contrôlé des LLM (coût/énergie).</li>
                <li>Séparation stricte entre Analyse et Action.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # ==============================================================================
    # 5. ARCHITECTURE TECHNIQUE (ML & IA)
    # ==============================================================================
    
    st.markdown('<h2 class="section-header">⚙️ Une Architecture Hybride</h2>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="narrative-text">
        Le système ne repose pas uniquement sur une IA générative. Il s'appuie sur un <b>Moteur Central de Règles</b> (Source de Vérité) 
        qui garantit la sécurité des patients, complété par des briques d'intelligence avancée.
    </div>
    """, unsafe_allow_html=True)

    # Colonnes pour ML et LLM
    tech_col1, tech_col2 = st.columns(2)

    with tech_col1:
        st.markdown("""
        <div class="feature-card">
            <h3>📊 Machine Learning (3 Briques)</h3>
            <p>Des modèles statistiques pour quantifier le risque :</p>
            <div style="text-align: left; margin-top: 15px;">
                <p><b>1. Régression :</b> Prédiction du temps d'attente estimé selon la charge.</p>
                <p><b>2. Clustering :</b> Identification des motifs de saturation (États "Calme", "Tendu", "Critique").</p>
                <p><b>3. Classification :</b> Prédiction du risque de blocage en aval (hospitalisation impossible).</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with tech_col2:
        st.markdown("""
        <div class="feature-card">
            <h3>🤖 LLM, RAG & Agent</h3>
            <p>L'utilisation des modèles de langage est strictement encadrée :</p>
            <div style="text-align: left; margin-top: 15px;">
                <p><b>RAG (Retrieval-Augmented Gen) :</b> Utilisé pour l'analyse et l'explication. Il lit l'état mais <u>ne le modifie jamais</u>.</p>
                <p><b>Agent (Action) :</b> Capable de proposer des actions atomiques (ex: déplacer un patient), toujours sous validation des règles métier.</p>
                <p><i>Principe clé : Analyse ≠ Action.</i></p>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ==============================================================================
    # 6. LIMITES & CREDIT
    # ==============================================================================
    
    st.divider()
    
    col_limits, col_authors = st.columns([1, 1])
    
    with col_limits:
        st.warning("""
        **⚠️ Limites du Projet**
        
        Ce système est un **prototype académique**.
        * Il ne pose aucun diagnostic médical.
        * Il ne remplace pas les professionnels de santé.
        * Il ne revendique aucune validité clinique officielle.
        """)
        
    with col_authors:
        st.info("""
        **🎓 Projet Master 2 SISE - Université Lyon 2**
        
        **Auteures :**
        Lamia HATEM • Maissa LAJIMI • Aya MECHERI • Rina RAZAFIMAHEFA • Mazilda Zehraoui
        """)

    # ==============================================================================
    # 7. CTA FINAL
    # ==============================================================================
    
    st.markdown("""
    <div class="cta-box">
        <h2 style="color:white; margin-bottom:10px;">L'Hôpital Virtuel vous attend</h2>
        <p style="font-size: 1.2rem; margin-bottom: 20px;">
            Testez la robustesse de notre architecture face à des scénarios de crise.
        </p>
        <p style="font-size: 1rem; opacity: 0.9;">
            👉 Cliquez sur <b>"Simulateur de Régulation"</b> dans le menu latéral pour lancer l'expérience.
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    show_context()