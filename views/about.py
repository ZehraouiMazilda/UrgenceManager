import streamlit as st


def show_about():
    
    # =========================================================================
    # HEADER
    # =========================================================================
    st.title("ℹ️ À Propos")
    st.divider()
    
    # =========================================================================
    # SECTION 1 : PROJET + VERSION
    # =========================================================================
    col_main, col_version = st.columns([2.5, 1], gap="medium")
    
    with col_main:
        with st.container(border=True):
            st.markdown("#### 📌 Projet")
            st.info(
                "**Urgence Manager** — Application de simulation et d'aide à la décision pour la gestion logistique "
                "des services d'accueil des urgences. Projet réalisé dans un cadre académique."
            )
            
            st.markdown("##### 🎓 Cadre Institutionnel")
            
            # Tableau propre avec colonnes alignées
            info_col1, info_col2 = st.columns([1, 2])
            with info_col1:
                st.markdown("**Université**")
                st.markdown("**Formation**")
                st.markdown("**Module**")
            with info_col2:
                st.markdown("Université Lyon 2")
                st.markdown("Master 2 SISE")
                st.markdown("NLP/LLM")
            
            st.markdown("")
            st.markdown(
                """
                <a href="https://github.com/ZehraouiMazilda/UrgenceManager" target="_blank" rel="noopener noreferrer"
                   style="display: block; width: 100%; text-decoration: none; box-sizing: border-box;">
                    <div style="
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        width: 100%;
                        max-width: 100%;
                        padding: 0.75rem 1.25rem;
                        background-color: #E53E3E;
                        color: #ffffff;
                        border-radius: 8px;
                        font-weight: 600;
                        font-size: 1rem;
                        box-sizing: border-box;
                    ">
                        <img src="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
                             width="22" height="22" alt="GitHub"
                             style="filter: invert(1) brightness(2); flex-shrink: 0; margin-right: 0.75rem;">
                        <span style="color: #ffffff; letter-spacing: 0.02em;">Accéder au Code Source</span>
                    </div>
                </a>
                """,
                unsafe_allow_html=True,
            )

    
    with col_version:
        with st.container(border=True):
            st.markdown("#### 🔖 Informations")
            st.metric(label="Version", value="v0.2")
            st.caption("Modular")
            st.markdown("**Statut**")
            st.success("✅ En développement")
            
            st.markdown("**Stack**")
            st.caption("🐍 Python · Streamlit")
            st.caption("🤖 Claude AI · Pydantic")
    
    st.divider()
    
    # =========================================================================
    # SECTION 2 : ÉQUIPE
    # =========================================================================
    with st.container(border=True):
        st.markdown("#### 👥 Équipe de Développement")
        
        st.info(
            "💡 Projet collaboratif réalisé par les étudiants du **Master 2 SISE** dans le cadre du module **NLP/LLM**. "
            "Les responsabilités incluent le développement, la modélisation, l'interface utilisateur et la documentation."
        )
        
        st.markdown("")
        st.markdown("##### Membres de l'équipe")
        
        # Grid de 5 colonnes pour 5 membres
        c1, c2, c3, c4, c5 = st.columns(5)
        
        with c1:
            st.markdown("""
            <div style='text-align: center; padding: 1rem; background-color: #f0f2f6; border-radius: 8px;'>
                <div style='font-size: 2.5rem;'>👩‍💻</div>
                <div style='margin-top: 0.5rem; font-weight: bold;'>Mazilda<br>Zehraoui</div>
            </div>
            """, unsafe_allow_html=True)
        
        with c2:
            st.markdown("""
            <div style='text-align: center; padding: 1rem; background-color: #f0f2f6; border-radius: 8px;'>
                <div style='font-size: 2.5rem;'>👩‍🔬</div>
                <div style='margin-top: 0.5rem; font-weight: bold;'>Aya<br>Macheri</div>
            </div>
            """, unsafe_allow_html=True)
        
        with c3:
            st.markdown("""
            <div style='text-align: center; padding: 1rem; background-color: #f0f2f6; border-radius: 8px;'>
                <div style='font-size: 2.5rem;'>👩‍💼</div>
                <div style='margin-top: 0.5rem; font-weight: bold;'>Maissa<br>Lajimi</div>
            </div>
            """, unsafe_allow_html=True)
        
        with c4:
            st.markdown("""
            <div style='text-align: center; padding: 1rem; background-color: #f0f2f6; border-radius: 8px;'>
                <div style='font-size: 2.5rem;'>👩‍🎨</div>
                <div style='margin-top: 0.5rem; font-weight: bold;'>Razafimahefa<br>Noro</div>
            </div>
            """, unsafe_allow_html=True)
        
        with c5:
            st.markdown("""
            <div style='text-align: center; padding: 1rem; background-color: #f0f2f6; border-radius: 8px;'>
                <div style='font-size: 2.5rem;'>👩‍🏫</div>
                <div style='margin-top: 0.5rem; font-weight: bold;'>Lamia<br>Hatem</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.divider()
    
    # =========================================================================
    # SECTION 3 : NOTE ACADÉMIQUE
    # =========================================================================
    with st.container(border=True):
        st.markdown("#### 📝 Note Académique")
        
        st.markdown("""
        Ce projet s'inscrit dans une **démarche pédagogique** visant à appliquer les concepts avancés 
        d'intelligence artificielle et de traitement du langage naturel à un cas d'usage réel.
        
        **Objectifs du projet** :
        - Maîtriser les architectures multi-agents
        - Implémenter des modèles de langage (LLM)
        - Développer une application full-stack fonctionnelle
        - Résoudre une problématique concrète du secteur hospitalier
        """)
    
    # =========================================================================
    # FOOTER
    # =========================================================================
    st.divider()
    
    # Footer avec liens
    footer_col1, footer_col2, footer_col3 = st.columns([1, 1, 1])
    
    with footer_col1:
        st.caption("🏥 **Urgence Manager**")
        st.caption("Version 0.2 · Hackathon 2026")
    
    with footer_col2:
        st.caption("🎓 **Master 2 SISE**")
        st.caption("Université Lyon 2 · Module NLP/LLM")
    
    with footer_col3:
        st.caption("🔗 **Liens**")
        st.caption("[GitHub Repository](https://github.com/ZehraouiMazilda/UrgenceManager)")


if __name__ == "__main__":
    show_about()