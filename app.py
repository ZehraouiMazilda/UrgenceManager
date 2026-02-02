import streamlit as st
import os

# Import des pages depuis le dossier views
from views.context import show_context
from views.simulation import show_simulation
from views.stats import main as show_stats
from views.about import show_about

# --- 1. CONFIGURATION GLOBALE ---
st.set_page_config(
    page_title="Urgence Manager",
    page_icon="img/logo.png" if os.path.exists("img/logo.png") else "🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- 2. GESTION DE L'ÉTAT (NAVIGATION) ---
# On initialise la page par défaut si elle n'existe pas
if "current_page" not in st.session_state:
    st.session_state.current_page = "Simulateur Live"

# Fonction pour changer de page (callback)
def navigate_to(page_name):
    st.session_state.current_page = page_name

# --- 3. CSS PERSONNALISÉ (DESIGN) ---
st.markdown("""
<style>
    /* Supprime les marges excessives en haut */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Style pour le titre de la sidebar */
    .sidebar-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 20px;
    }
    
    /* Amélioration visuelle des boutons du menu */
    div.stButton > button {
        text-align: left;
        padding-left: 20px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- 4. BARRE LATÉRALE (MENU) ---
with st.sidebar:
    # A. Logo et Titre
    if os.path.exists("img/logo.png"):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image("img/logo.png", use_container_width=True)
    
    st.markdown('<div class="sidebar-title">Urgence Manager</div>', unsafe_allow_html=True)
    st.write("") # Espaceur

    # B. Menu de Navigation (Boutons Natifs)
    # L'astuce : Le bouton de la page active est en type "primary" (rouge/coloré), les autres en "secondary" (gris)
    
    if st.button("🏠  Accueil & Contexte", 
                 key="nav_home", 
                 use_container_width=True, 
                 type="primary" if st.session_state.current_page == "Accueil & Contexte" else "secondary"):
        navigate_to("Accueil & Contexte")
        st.rerun()

    if st.button("🎮  Simulateur Live", 
                 key="nav_sim", 
                 use_container_width=True, 
                 type="primary" if st.session_state.current_page == "Simulateur Live" else "secondary"):
        navigate_to("Simulateur Live")
        st.rerun()

    if st.button("📊  Dashboard & KPIs", 
                 key="nav_stats", 
                 use_container_width=True, 
                 type="primary" if st.session_state.current_page == "Dashboard & KPIs" else "secondary"):
        navigate_to("Dashboard & KPIs")
        st.rerun()

    if st.button("ℹ️  À Propos", 
                 key="nav_about", 
                 use_container_width=True, 
                 type="primary" if st.session_state.current_page == "À Propos" else "secondary"):
        navigate_to("À Propos")
        st.rerun()

    # C. Footer Sidebar
    st.markdown("---")
    # Affichage conditionnel du temps si la simulation tourne
    if "sim_time" in st.session_state and st.session_state.sim_time > 0:
        minutes = st.session_state.sim_time
        st.metric("⏱️ Temps Hôpital", f"{minutes // 60}h{minutes % 60:02d}")
    
    st.caption("Urgence Manager")

# --- 5. ROUTAGE DES PAGES ---
if st.session_state.current_page == "Accueil & Contexte":
    show_context()
elif st.session_state.current_page == "Simulateur Live":
    show_simulation()
elif st.session_state.current_page == "Dashboard & KPIs":
    show_stats()
elif st.session_state.current_page == "À Propos":
    show_about()

