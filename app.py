import streamlit as st

# Import des pages depuis le dossier views
from views.context import show_context
from views.simulation import show_simulation
from views.stats import main as show_stats
from views.about import show_about

# --- CONFIGURATION GLOBALE ---
st.set_page_config(
    page_title="Urgence Manager",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- NAVIGATION (SIDEBAR) ---
with st.sidebar:
    st.title("Urgence Manager")
    st.markdown("---")

    page_selection = st.radio(
        "Navigation",
        [
            "Accueil & Contexte",
            "Simulateur Live",
            "Dashboard & KPIs",
            "À Propos",
        ],
        index=2,  # On met le simulateur par défaut pour gagner du temps
    )

    st.markdown("---")
    st.caption("Hackathon 2026 - v0.2 (Modular)")

# --- ROUTAGE ---
if page_selection == "Accueil & Contexte":
    show_context()
elif page_selection == "Simulateur Live":
    show_simulation()
elif page_selection == "Dashboard & KPIs":
    show_stats()
elif page_selection == "À Propos":
    show_about()
