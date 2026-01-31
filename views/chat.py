"""
Page AI Assistant avec RAG (Retrieval-Augmented Generation)
============================================================

Fonctionnalités:
1. Chat intelligent sur les sessions (courante + historique)
2. RAG : Recherche dans les données CSV + LLM
3. Analyse contextuelle des urgences
4. Recommandations basées sur l'historique
5. Extraction d'informations structurées
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
import os
from dotenv import load_dotenv

# LLM
try:
    from mistralai import Mistral
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False
    st.error("❌ mistralai non installé. Installez avec: pip install mistralai")

# Embeddings & Vector Search (optionnel mais recommandé pour RAG)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    VECTORIZATION_AVAILABLE = True
except ImportError:
    VECTORIZATION_AVAILABLE = False
    st.warning("⚠️ scikit-learn recommandé pour RAG optimal")

# =============================================================================
# CONFIGURATION
# =============================================================================

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MODEL_NAME = "mistral-large-latest"

HISTORIQUE_DIR = Path("data/historique")
STATE_PATH = Path("data/state/urgence_state.json")

# =============================================================================
# CHARGEMENT DES DONNÉES (RAG DATA SOURCE)
# =============================================================================

@st.cache_data(ttl=60)
def load_historical_sessions():
    """Charge toutes les sessions historiques pour le RAG."""
    if not HISTORIQUE_DIR.exists():
        return pd.DataFrame(), pd.DataFrame(), []
    
    all_patients = []
    all_staff = []
    session_metadata = []
    
    for csv_file in HISTORIQUE_DIR.glob("*_patients.csv"):
        try:
            df = pd.read_csv(csv_file, sep=';')
            session_id = csv_file.stem.replace("_patients", "")
            df['session_id'] = session_id
            all_patients.append(df)
            
            # Métadonnées de la session
            session_metadata.append({
                "session_id": session_id,
                "nb_patients": len(df['id'].unique()),
                "nb_events": len(df),
                "duration_min": df['timestamp'].max() if not df.empty else 0,
                "severities": df['severity'].value_counts().to_dict() if 'severity' in df.columns else {}
            })
        except Exception as e:
            st.warning(f"Erreur lecture {csv_file.name}: {e}")
    
    for csv_file in HISTORIQUE_DIR.glob("*_staff.csv"):
        try:
            df = pd.read_csv(csv_file, sep=';')
            session_id = csv_file.stem.replace("_staff", "")
            df['session_id'] = session_id
            all_staff.append(df)
        except Exception as e:
            st.warning(f"Erreur lecture {csv_file.name}: {e}")
    
    patients_df = pd.concat(all_patients, ignore_index=True) if all_patients else pd.DataFrame()
    staff_df = pd.concat(all_staff, ignore_index=True) if all_staff else pd.DataFrame()
    
    return patients_df, staff_df, session_metadata


@st.cache_data(ttl=10)
def load_current_session_state():
    """Charge l'état actuel de la session en cours."""
    if not STATE_PATH.exists():
        return None
    
    try:
        with open(STATE_PATH, 'r', encoding='utf-8') as f:
            state = json.load(f)
        return state
    except Exception as e:
        st.error(f"Erreur chargement état actuel: {e}")
        return None


# =============================================================================
# RAG : CONSTRUCTION DU CONTEXTE
# =============================================================================

def build_rag_context(patients_df: pd.DataFrame, staff_df: pd.DataFrame, 
                      session_metadata: list, current_state: dict, 
                      user_query: str) -> str:
    """
    Construit le contexte RAG en recherchant les informations pertinentes.
    
    Étapes:
    1. Analyser la requête utilisateur
    2. Extraire les données pertinentes (filtrage)
    3. Formater en contexte pour le LLM
    """
    
    context_parts = []
    
    # === PARTIE 1 : SESSION ACTUELLE ===
    
    context_parts.append("=== SESSION EN COURS ===\n")
    
    if current_state:
        # Informations générales
        context_parts.append(f"Temps actuel: {current_state.get('time', 0)} minutes")
        
        # Patients
        patients = current_state.get('patients', {})
        if patients:
            context_parts.append(f"\nPatients actuels: {len(patients)}")
            
            # Détails par localisation
            locations = {}
            for p_id, patient in patients.items():
                loc = patient.get('location', 'unknown')
                sev = patient.get('severity', {}).get('value', 'UNKNOWN')
                locations.setdefault(loc, []).append(f"{p_id} ({sev})")
            
            context_parts.append("\nRépartition des patients:")
            for loc, pats in locations.items():
                context_parts.append(f"  - {loc}: {', '.join(pats)}")
        
        # Personnel
        staff = current_state.get('staff', {})
        if staff:
            context_parts.append(f"\nPersonnel: {len(staff)}")
            
            staff_status = {"present": 0, "absent": 0, "busy": 0}
            for s_id, agent in staff.items():
                if agent.get('is_present'):
                    staff_status['present'] += 1
                    if agent.get('is_busy'):
                        staff_status['busy'] += 1
                else:
                    staff_status['absent'] += 1
            
            context_parts.append(f"  - Présents: {staff_status['present']}")
            context_parts.append(f"  - Occupés: {staff_status['busy']}")
            context_parts.append(f"  - Absents: {staff_status['absent']}")
        
        # Capacités
        context_parts.append("\nCapacités:")
        sc = current_state.get('soins_critiques', {})
        context_parts.append(f"  - Soins Critiques: {sc.get('occupancy', 0)}/{sc.get('capacity', 5)}")
        
        for wr_id, wr in current_state.get('waiting_rooms', {}).items():
            context_parts.append(f"  - {wr.get('name', wr_id)}: {wr.get('occupancy', 0)}/{wr.get('capacity', 0)}")
    
    else:
        context_parts.append("Aucune session en cours détectée.")
    
    # === PARTIE 2 : DONNÉES HISTORIQUES PERTINENTES ===
    
    context_parts.append("\n\n=== HISTORIQUE ===\n")
    
    if not patients_df.empty:
        context_parts.append(f"Sessions historiques: {len(session_metadata)}")
        context_parts.append(f"Total événements patients: {len(patients_df)}")
        context_parts.append(f"Total événements staff: {len(staff_df)}")
        
        # Statistiques globales
        if 'severity' in patients_df.columns:
            severity_counts = patients_df['severity'].value_counts().to_dict()
            context_parts.append(f"\nRépartition globale par gravité:")
            for sev, count in severity_counts.items():
                context_parts.append(f"  - {sev}: {count}")
        
        # Filtrage intelligent basé sur la requête
        query_lower = user_query.lower()
        
        # Si la requête mentionne une couleur spécifique
        for color in ['rouge', 'jaune', 'vert', 'gris']:
            if color in query_lower:
                color_upper = color.upper()
                filtered = patients_df[patients_df['severity'] == color_upper]
                if not filtered.empty:
                    context_parts.append(f"\n--- Données {color_upper} ---")
                    context_parts.append(f"Nombre de patients {color_upper}: {len(filtered['id'].unique())}")
                    context_parts.append(f"Événements: {len(filtered)}")
                    
                    # Localisations fréquentes
                    top_locs = filtered['location'].value_counts().head(3)
                    context_parts.append(f"Localisations fréquentes: {', '.join([f'{loc} ({count})' for loc, count in top_locs.items()])}")
        
        # Si la requête mentionne un patient spécifique
        for col in patients_df.columns:
            if 'id' in col.lower():
                for patient_id in patients_df[col].unique()[:20]:  # Limiter
                    if str(patient_id).lower() in query_lower:
                        patient_data = patients_df[patients_df[col] == patient_id]
                        context_parts.append(f"\n--- Patient {patient_id} ---")
                        context_parts.append(f"Nombre d'événements: {len(patient_data)}")
                        context_parts.append(f"Parcours: {' -> '.join(patient_data['location'].unique())}")
                        break
        
        # Si la requête mentionne le staff
        if any(word in query_lower for word in ['staff', 'personnel', 'infirmier', 'as_', 'doc_']):
            if not staff_df.empty:
                context_parts.append("\n--- Personnel ---")
                staff_ids = staff_df['id'].unique()
                context_parts.append(f"Personnel actif: {', '.join(staff_ids[:10])}")
                
                # Activité du personnel
                staff_activity = staff_df.groupby('id').size().sort_values(ascending=False)
                context_parts.append(f"Personnel le plus actif: {staff_activity.head(3).to_dict()}")
    
    else:
        context_parts.append("Aucune donnée historique disponible.")
    
    # === PARTIE 3 : MÉTADONNÉES DES SESSIONS ===
    
    if session_metadata:
        context_parts.append("\n\n=== SESSIONS RÉCENTES ===\n")
        for session in session_metadata[-5:]:  # 5 dernières sessions
            context_parts.append(f"\nSession: {session['session_id']}")
            context_parts.append(f"  Patients: {session['nb_patients']}")
            context_parts.append(f"  Durée: {session['duration_min']} min")
            if session['severities']:
                context_parts.append(f"  Gravités: {session['severities']}")
    
    return "\n".join(context_parts)


def semantic_search(query: str, documents: list, top_k: int = 3) -> list:
    """
    Recherche sémantique dans les documents (optionnel, si sklearn disponible).
    
    Args:
        query: Question de l'utilisateur
        documents: Liste de textes (logs, descriptions)
        top_k: Nombre de documents à retourner
        
    Returns:
        Liste des top_k documents les plus pertinents
    """
    if not VECTORIZATION_AVAILABLE or not documents:
        return documents[:top_k]
    
    try:
        # Vectorisation TF-IDF
        vectorizer = TfidfVectorizer(stop_words='english', max_features=100)
        doc_vectors = vectorizer.fit_transform(documents)
        query_vector = vectorizer.transform([query])
        
        # Similarité cosinus
        similarities = cosine_similarity(query_vector, doc_vectors).flatten()
        
        # Top K
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        return [documents[i] for i in top_indices]
    
    except Exception as e:
        st.warning(f"Recherche sémantique échouée: {e}")
        return documents[:top_k]


# =============================================================================
# LLM : GÉNÉRATION DE RÉPONSE
# =============================================================================

def generate_response(user_query: str, rag_context: str) -> str:
    """
    Génère une réponse en utilisant le LLM + RAG.
    
    Args:
        user_query: Question de l'utilisateur
        rag_context: Contexte construit par le RAG
        
    Returns:
        Réponse générée par le LLM
    """
    if not MISTRAL_AVAILABLE or not MISTRAL_API_KEY:
        return "❌ API Mistral non configurée. Vérifiez votre clé API dans le fichier .env"
    
    try:
        client = Mistral(api_key=MISTRAL_API_KEY)
        
        # Prompt système
        system_prompt = """Tu es un assistant médical expert en gestion des urgences hospitalières.

Tu as accès aux données en temps réel de la session actuelle ET à l'historique complet des sessions passées.

Tes capacités:
- Analyser l'état actuel des urgences
- Comparer avec les sessions historiques
- Identifier les tendances et patterns
- Faire des recommandations basées sur les données
- Extraire des statistiques précises

Règles:
- Base tes réponses UNIQUEMENT sur les données fournies dans le contexte
- Si l'information n'est pas dans le contexte, dis-le clairement
- Fournis des chiffres précis quand disponibles
- Structure tes réponses de manière claire (utilise des listes, sections)
- Sois concis mais complet"""

        # Prompt utilisateur avec contexte RAG
        user_prompt = f"""Voici le contexte avec les données de la session actuelle et l'historique:

{rag_context}

---

Question de l'utilisateur:
{user_query}

Réponds de manière précise et structurée en te basant UNIQUEMENT sur les données ci-dessus."""

        # Appel API
        response = client.chat.complete(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # Faible température pour réponses factuelles
            max_tokens=1500
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        return f"❌ Erreur lors de l'appel API: {str(e)}\n\nVérifiez votre clé API Mistral et votre quota."


# =============================================================================
# SUGGESTIONS DE QUESTIONS
# =============================================================================

SUGGESTED_QUESTIONS = [
    "📊 Quel est l'état actuel des urgences ?",
    "👥 Combien de patients sont actuellement en attente ?",
    "🚨 Y a-t-il des patients ROUGE en ce moment ?",
    "📈 Comment cette session se compare-t-elle aux sessions précédentes ?",
    "⏰ Quel est le temps d'attente moyen actuel ?",
    "🏥 Quelles sont les capacités disponibles en Soins Critiques ?",
    "👨‍⚕️ Combien de personnel est disponible ?",
    "📉 Quelle est la tendance du nombre de patients ROUGE historiquement ?",
    "🔍 Peux-tu analyser le patient PAT_001 ?",
    "💡 Quelles recommandations pour améliorer le flux actuel ?",
    "📋 Quels sont les parcours patients les plus fréquents ?",
    "⚡ Y a-t-il un pic d'activité dans l'historique ?",
]


# =============================================================================
# INTERFACE STREAMLIT
# =============================================================================

def show_ai_assistant():
    """Page principale de l'AI Assistant avec RAG."""
    
    #st.set_page_config(page_title="🤖 AI Assistant", layout="wide")
    
    st.title("🤖 AI Assistant - Analyse Intelligente des Urgences")
    st.markdown("**RAG (Retrieval-Augmented Generation)** : Questions sur la session actuelle et l'historique")
    
    # Initialiser l'historique de chat
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # Charger les données pour le RAG
    with st.spinner("🔄 Chargement des données RAG..."):
        patients_df, staff_df, session_metadata = load_historical_sessions()
        current_state = load_current_session_state()
    
    # Indicateurs en haut
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "📊 Sessions Historiques",
            len(session_metadata),
            f"{len(patients_df)} événements patients"
        )
    
    with col2:
        st.metric(
            "👥 Session Actuelle",
            len(current_state.get('patients', {})) if current_state else 0,
            "patients en cours"
        )
    
    with col3:
        st.metric(
            "💬 Messages Chat",
            len(st.session_state.chat_history),
            "dans cette conversation"
        )
    
    with col4:
        st.metric(
            "🔗 Contexte RAG",
            "✅ Actif" if (not patients_df.empty or current_state) else "❌ Vide",
            "Données disponibles"
        )
    
    st.divider()
    
    # Layout principal : 2 colonnes
    col_chat, col_context = st.columns([2, 1])
    
    with col_chat:
        st.subheader("💬 Chat")
        
        # Afficher l'historique
        chat_container = st.container(height=400)
        
        with chat_container:
            for message in st.session_state.chat_history:
                if message["role"] == "user":
                    st.chat_message("user").write(message["content"])
                else:
                    st.chat_message("assistant").write(message["content"])
        
        # Input utilisateur
        user_input = st.chat_input("Posez votre question sur les urgences...")
        
        if user_input:
            # Ajouter la question à l'historique
            st.session_state.chat_history.append({
                "role": "user",
                "content": user_input
            })
            
            # Construire le contexte RAG
            with st.spinner("🔍 Recherche dans les données..."):
                rag_context = build_rag_context(
                    patients_df, staff_df, session_metadata, 
                    current_state, user_input
                )
            
            # Générer la réponse
            with st.spinner("🤖 Génération de la réponse..."):
                response = generate_response(user_input, rag_context)
            
            # Ajouter la réponse à l'historique
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response
            })
            
            # Forcer le rechargement pour afficher
            st.rerun()
    
    with col_context:
        st.subheader("💡 Suggestions")
        
        st.markdown("**Questions rapides :**")
        
        # Boutons de suggestions (3 colonnes)
        for i in range(0, len(SUGGESTED_QUESTIONS), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(SUGGESTED_QUESTIONS):
                    question = SUGGESTED_QUESTIONS[i + j]
                    if cols[j].button(question, key=f"suggest_{i}_{j}", use_container_width=True):
                        # Simuler l'envoi de la question
                        st.session_state.chat_history.append({
                            "role": "user",
                            "content": question
                        })
                        
                        rag_context = build_rag_context(
                            patients_df, staff_df, session_metadata, 
                            current_state, question
                        )
                        
                        response = generate_response(question, rag_context)
                        
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response
                        })
                        
                        st.rerun()
        
        st.divider()
        
        # Bouton pour effacer l'historique
        if st.button("🗑️ Effacer la conversation", type="secondary", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
        
        # Expander avec détails du contexte RAG
        with st.expander("🔍 Voir le contexte RAG"):
            if st.session_state.chat_history:
                # Afficher le dernier contexte utilisé
                last_user_msg = [m for m in st.session_state.chat_history if m["role"] == "user"]
                if last_user_msg:
                    last_query = last_user_msg[-1]["content"]
                    context = build_rag_context(
                        patients_df, staff_df, session_metadata, 
                        current_state, last_query
                    )
                    st.code(context, language="text")
            else:
                st.info("Le contexte RAG s'affichera après la première question.")
    
    # Section supplémentaire : Statistiques du RAG
    st.divider()
    
    with st.expander("📊 Statistiques du RAG"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("📁 Sources de données")
            st.write(f"- Sessions historiques: {len(session_metadata)}")
            st.write(f"- Événements patients: {len(patients_df)}")
            st.write(f"- Événements staff: {len(staff_df)}")
            st.write(f"- Session actuelle: {'✅ Chargée' if current_state else '❌ Non disponible'}")
        
        with col2:
            st.subheader("🔍 Capacités de recherche")
            st.write("✅ Recherche par gravité (ROUGE, JAUNE, etc.)")
            st.write("✅ Recherche par patient ID")
            st.write("✅ Recherche par personnel")
            st.write("✅ Analyse de sessions")
            st.write(f"{'✅' if VECTORIZATION_AVAILABLE else '❌'} Recherche sémantique (TF-IDF)")
        
        with col3:
            st.subheader("🤖 Configuration LLM")
            st.write(f"Modèle: {MODEL_NAME}")
            st.write(f"API: {'✅ Configurée' if MISTRAL_API_KEY else '❌ Non configurée'}")
            st.write(f"Temperature: 0.3 (factuelle)")
            st.write(f"Max tokens: 1500")
    
    # Footer
    st.divider()
    st.caption("🤖 AI Assistant propulsé par Mistral AI + RAG | Données en temps réel + Historique complet")


# Point d'entrée alternatif
def main():
    """Alias pour compatibilité."""
    show_ai_assistant()


if __name__ == "__main__":
    show_ai_assistant()