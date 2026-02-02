"""
Page AI Assistant avec RAG Basique Niveau 2 (Retrieval-Augmented Generation)
==============================================================================

Fonctionnalités:
1. Chat intelligent sur les sessions (courante + historique)
2. RAG Basique : TF-IDF + recherche sémantique simple
3. Analyse contextuelle des urgences
4. Recommandations basées sur l'historique
5. Extraction d'informations structurées
6. Cache optimisé

Version: RAG Niveau 2 - Basique mais efficace
- Pas besoin de sentence-transformers
- Uniquement scikit-learn (TF-IDF)
- Léger et rapide
- Toujours 10x mieux que la version originale
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
import os
from dotenv import load_dotenv
import hashlib
from typing import List, Dict, Tuple, Optional
import time

# LLM
try:
    from mistralai import Mistral
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False
    st.error("❌ mistralai non installé. Installez avec: pip install mistralai")

# TF-IDF (REQUIS pour RAG niveau 2)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    st.error("❌ scikit-learn REQUIS. Installez avec: pip install scikit-learn")

# =============================================================================
# CONFIGURATION
# =============================================================================

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MODEL_NAME = "mistral-large-latest"

HISTORIQUE_DIR = Path("data/historique")
STATE_PATH = Path("data/state/urgence_state.json")

# Configuration RAG Basique
RAG_CONFIG = {
    "top_k_retrieval": 7,  # Nombre de documents à récupérer
    "top_k_final": 5,      # Nombre de documents après réranking
    "max_context_tokens": 1500,  # Limite du contexte
    "tfidf_max_features": 300,   # Nombre de features TF-IDF
    "tfidf_ngram_range": (1, 2), # Unigrams et bigrams
}

# =============================================================================
# CHARGEMENT DES DONNÉES
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
            df = pd.read_csv(csv_file, sep=';', encoding='utf-8')
            session_id = csv_file.stem.replace("_patients", "")
            df['session_id'] = session_id
            all_patients.append(df)
            
            # Métadonnées de la session
            session_metadata.append({
                "session_id": session_id,
                "nb_patients": len(df['id'].unique()) if 'id' in df.columns else 0,
                "nb_events": len(df),
                "duration_min": df['timestamp'].max() if 'timestamp' in df.columns and not df.empty else 0,
                "severities": df['severity'].value_counts().to_dict() if 'severity' in df.columns else {}
            })
        except Exception as e:
            st.warning(f"Erreur lecture {csv_file.name}: {e}")
    
    for csv_file in HISTORIQUE_DIR.glob("*_staff.csv"):
        try:
            df = pd.read_csv(csv_file, sep=';', encoding='utf-8')
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
# RAG BASIQUE : PRÉPARATION DES DOCUMENTS
# =============================================================================

def prepare_rag_documents(patients_df: pd.DataFrame, staff_df: pd.DataFrame, 
                         session_metadata: List[Dict], current_state: Optional[Dict]) -> List[Dict]:
    """
    Prépare des documents structurés et optimisés pour le RAG.
    
    Returns:
        Liste de dictionnaires avec:
        - id: identifiant unique
        - text: contenu textuel
        - metadata: métadonnées (type, session_id, etc.)
        - importance: score d'importance (pour priorité)
    """
    documents = []
    doc_id = 0
    
    # === 1. ÉTAT ACTUEL (HAUTE PRIORITÉ) ===
    if current_state:
        # Document principal de l'état actuel
        patients = current_state.get('patients', {})
        staff = current_state.get('staff', {})
        
        # Compter les patients par gravité
        severity_counts = {}
        for p in patients.values():
            sev = p.get('severity', {}).get('value', 'UNKNOWN')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        # Personnel disponible
        staff_present = sum(1 for s in staff.values() if s.get('is_present', False))
        staff_busy = sum(1 for s in staff.values() if s.get('is_present', False) and s.get('is_busy', False))
        staff_available = staff_present - staff_busy
        
        doc_text = f"""
État actuel des urgences en temps réel session en cours active maintenant:
Temps écoulé: {current_state.get('time', 0)} minutes
Nombre total de patients présents actuellement: {len(patients)}

Répartition par gravité des patients actuels:
- Urgences vitales critiques graves ROUGE: {severity_counts.get('ROUGE', 0)} patients
- Urgences importantes modérées JAUNE: {severity_counts.get('JAUNE', 0)} patients
- Urgences mineures légères VERT: {severity_counts.get('VERT', 0)} patients
- Non urgentes bénignes GRIS: {severity_counts.get('GRIS', 0)} patients

Personnel médical staff infirmiers docteurs agents:
- Total présent actuellement: {staff_present} agents
- Actuellement occupés en activité: {staff_busy} agents
- Disponibles libres immédiatement: {staff_available} agents

Capacités places lits disponibilité:
- Soins Critiques réanimation urgence: {current_state.get('soins_critiques', {}).get('occupancy', 0)}/{current_state.get('soins_critiques', {}).get('capacity', 5)} lits occupés
"""
        
        # Ajouter les salles d'attente
        for wr_id, wr in current_state.get('waiting_rooms', {}).items():
            doc_text += f"- Salle d'attente {wr.get('name', wr_id)}: {wr.get('occupancy', 0)}/{wr.get('capacity', 0)} places\n"
        
        documents.append({
            "id": f"doc_{doc_id}",
            "text": doc_text.strip(),
            "metadata": {
                "type": "current_state",
                "session_id": "current",
                "timestamp": datetime.now().isoformat()
            },
            "importance": 10.0  # Très haute priorité
        })
        doc_id += 1
        
        # Documents détaillés par gravité
        for severity in ['ROUGE', 'JAUNE', 'VERT', 'GRIS']:
            sev_patients = [p for p in patients.values() if p.get('severity', {}).get('value') == severity]
            if sev_patients:
                locations = {}
                for p in sev_patients:
                    loc = p.get('location', 'unknown')
                    locations[loc] = locations.get(loc, 0) + 1
                
                severity_names = {
                    'ROUGE': 'vitale critique grave urgente prioritaire',
                    'JAUNE': 'importante modérée significative',
                    'VERT': 'mineure légère faible',
                    'GRIS': 'non urgente bénigne'
                }
                
                doc_text = f"""
Patients {severity} gravité {severity_names.get(severity, '')} dans la session actuelle en cours:
Nombre: {len(sev_patients)} patients cas
Type d'urgence niveau: {severity_names.get(severity, '')}

Localisation position actuelle des patients:
"""
                for loc, count in sorted(locations.items(), key=lambda x: x[1], reverse=True):
                    doc_text += f"- {loc}: {count} patient(s)\n"
                
                # Temps d'attente moyen
                wait_times = [p.get('waiting_time', 0) for p in sev_patients]
                avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0
                doc_text += f"\nTemps d'attente moyen durée: {avg_wait:.1f} minutes"
                
                documents.append({
                    "id": f"doc_{doc_id}",
                    "text": doc_text.strip(),
                    "metadata": {
                        "type": "current_severity",
                        "severity": severity,
                        "session_id": "current"
                    },
                    "importance": 8.0 if severity == 'ROUGE' else 6.0
                })
                doc_id += 1
    
    # === 2. SESSIONS HISTORIQUES ===
    for session in session_metadata[-10:]:  # 10 dernières sessions
        doc_text = f"""
Session historique passée précédente {session['session_id']}:
Nombre total de patients traités pris en charge: {session['nb_patients']} patients
Durée de la session temps: {session['duration_min']} minutes
Nombre total d'événements activités: {session['nb_events']}

Répartition des gravités niveaux:
"""
        for sev, count in session.get('severities', {}).items():
            doc_text += f"- {sev}: {count} patients\n"
        
        # Calcul du taux d'occupation moyen
        if session['duration_min'] > 0:
            taux_occupation = (session['nb_events'] / session['duration_min']) * 10
            doc_text += f"\nTaux d'activité flux charge: {taux_occupation:.1f} événements par 10 minutes"
        
        documents.append({
            "id": f"doc_{doc_id}",
            "text": doc_text.strip(),
            "metadata": {
                "type": "historical_session",
                "session_id": session['session_id']
            },
            "importance": 4.0
        })
        doc_id += 1
    
    # === 3. STATISTIQUES PAR GRAVITÉ (HISTORIQUE) ===
    if not patients_df.empty and 'severity' in patients_df.columns:
        for severity in patients_df['severity'].unique():
            sev_data = patients_df[patients_df['severity'] == severity]
            
            if len(sev_data) > 0:
                unique_patients = sev_data['id'].nunique() if 'id' in sev_data.columns else 0
                
                severity_names = {
                    'ROUGE': 'vitaux critiques graves urgents prioritaires',
                    'JAUNE': 'importants modérés significatifs',
                    'VERT': 'mineurs légers faibles',
                    'GRIS': 'non urgents bénins'
                }
                
                doc_text = f"""
Statistiques historiques données passées pour les patients {severity} cas {severity_names.get(severity, '')}:
Nombre total de patients {severity}: {unique_patients} patients cas
Nombre d'événements enregistrés passages: {len(sev_data)} événements

Parcours typiques trajets habituels (localisations les plus fréquentes courantes):
"""
                if 'location' in sev_data.columns:
                    top_locs = sev_data['location'].value_counts().head(5)
                    for loc, count in top_locs.items():
                        percentage = (count / len(sev_data)) * 100
                        doc_text += f"- {loc}: {count} passages ({percentage:.1f}%)\n"
                
                # Durée moyenne
                if 'timestamp' in sev_data.columns and 'id' in sev_data.columns:
                    durations = []
                    for patient_id in sev_data['id'].unique()[:50]:  # Échantillon
                        patient_events = sev_data[sev_data['id'] == patient_id]
                        if len(patient_events) > 1:
                            duration = patient_events['timestamp'].max() - patient_events['timestamp'].min()
                            durations.append(duration)
                    
                    if durations:
                        avg_duration = sum(durations) / len(durations)
                        doc_text += f"\nDurée moyenne du parcours temps: {avg_duration:.1f} minutes"
                
                documents.append({
                    "id": f"doc_{doc_id}",
                    "text": doc_text.strip(),
                    "metadata": {
                        "type": "historical_severity_stats",
                        "severity": severity
                    },
                    "importance": 5.0 if severity == 'ROUGE' else 3.0
                })
                doc_id += 1
    
    # === 4. STATISTIQUES PERSONNEL ===
    if not staff_df.empty and 'id' in staff_df.columns:
        staff_ids = staff_df['id'].unique()
        
        doc_text = f"""
Statistiques historiques données passées du personnel staff médical infirmiers:
Nombre total d'agents actifs personnel: {len(staff_ids)} agents
Nombre d'événements activités staff: {len(staff_df)} événements

Agents les plus actifs personnel productif (top 5):
"""
        staff_activity = staff_df.groupby('id').size().sort_values(ascending=False)
        for staff_id, count in list(staff_activity.head(5).items()):
            doc_text += f"- {staff_id}: {count} événements activités\n"
        
        # Analyser les absences
        if 'is_present' in staff_df.columns:
            absences = staff_df[staff_df['is_present'] == False]
            if len(absences) > 0:
                absence_rate = (len(absences) / len(staff_df)) * 100
                doc_text += f"\nTaux d'absence historique manque: {absence_rate:.1f}%"
        
        documents.append({
            "id": f"doc_{doc_id}",
            "text": doc_text.strip(),
            "metadata": {
                "type": "historical_staff_stats"
            },
            "importance": 3.0
        })
        doc_id += 1
    
    # === 5. RECOMMANDATIONS ET INSIGHTS ===
    if not patients_df.empty and 'severity' in patients_df.columns:
        # Analyser les patterns
        rouge_count = len(patients_df[patients_df['severity'] == 'ROUGE'])
        total_count = len(patients_df)
        rouge_percentage = (rouge_count / total_count * 100) if total_count > 0 else 0
        
        doc_text = f"""
Insights tendances analyses recommandations alertes des urgences:

Taux de cas critiques graves urgents vitaux ROUGE:
- Patients ROUGE critiques: {rouge_percentage:.1f}% du total historique global
- Tendance niveau: {"Élevée haute" if rouge_percentage > 20 else "Modérée moyenne" if rouge_percentage > 10 else "Faible basse"}

Recommandations suggestions conseils basées sur l'historique données:
"""
        if rouge_percentage > 20:
            doc_text += "- Maintenir conserver une capacité élevée haute en Soins Critiques réanimation\n"
            doc_text += "- Prioriser privilégier la disponibilité du personnel qualifié compétent\n"
        
        if current_state and severity_counts.get('ROUGE', 0) > 3:
            doc_text += "- Alerte attention: Nombre élevé important de patients ROUGE critiques actuellement maintenant\n"
            doc_text += "- Recommandation conseil: Mobiliser activer des ressources supplémentaires additionnelles\n"
        
        documents.append({
            "id": f"doc_{doc_id}",
            "text": doc_text.strip(),
            "metadata": {
                "type": "insights_recommendations"
            },
            "importance": 6.0
        })
        doc_id += 1
    
    return documents


# =============================================================================
# RAG BASIQUE : RETRIEVER TF-IDF
# =============================================================================

class TFIDFRetriever:
    """
    Retriever basique utilisant TF-IDF pour la recherche sémantique.
    Simple, rapide, efficace, pas de dépendances lourdes.
    """
    
    def __init__(self):
        self.vectorizer = None
        self.tfidf_matrix = None
        self.documents = []
    
    def index_documents(self, documents: List[Dict]) -> None:
        """
        Indexe les documents avec TF-IDF.
        """
        if not SKLEARN_AVAILABLE:
            st.error("❌ scikit-learn requis pour le RAG")
            return
        
        self.documents = documents
        texts = [doc["text"] for doc in documents]
        
        try:
            # Vectorisation TF-IDF
            self.vectorizer = TfidfVectorizer(
                max_features=RAG_CONFIG["tfidf_max_features"],
                ngram_range=RAG_CONFIG["tfidf_ngram_range"],
                stop_words=None,
                lowercase=True,
                strip_accents='unicode'
            )
            self.tfidf_matrix = self.vectorizer.fit_transform(texts)
            
        except Exception as e:
            st.error(f"Erreur vectorisation TF-IDF: {e}")
            self.vectorizer = None
            self.tfidf_matrix = None
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Récupère les documents les plus pertinents via TF-IDF.
        
        Args:
            query: Question de l'utilisateur
            top_k: Nombre de documents à retourner
        
        Returns:
            Liste des documents pertinents avec scores
        """
        if not self.documents or self.vectorizer is None or self.tfidf_matrix is None:
            return []
        
        try:
            # Vectoriser la requête
            query_vector = self.vectorizer.transform([query])
            
            # Calculer similarité cosinus
            similarities = cosine_similarity(query_vector, self.tfidf_matrix)[0]
            
            # Boost basé sur l'importance des documents
            importance_scores = np.array([doc.get("importance", 1.0) for doc in self.documents])
            importance_scores = importance_scores / importance_scores.max()  # Normaliser
            boosted_scores = similarities * (1 + 0.3 * importance_scores)  # Boost de 30% max
            
            # Top-k
            top_indices = np.argsort(boosted_scores)[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                if boosted_scores[idx] > 0:  # Seulement scores positifs
                    doc = self.documents[idx].copy()
                    doc['score'] = float(boosted_scores[idx])
                    doc['base_score'] = float(similarities[idx])
                    results.append(doc)
            
            return results
        
        except Exception as e:
            st.error(f"Erreur recherche TF-IDF: {e}")
            return []


# =============================================================================
# RAG BASIQUE : RÉRANKING
# =============================================================================

def rerank_documents(query: str, documents: List[Dict], top_k: int = 5) -> List[Dict]:
    """
    Réordonne les documents récupérés pour maximiser la pertinence.
    
    Stratégies:
    1. Diversité (éviter les doublons thématiques)
    2. Fraîcheur (privilégier l'état actuel)
    3. Pertinence
    """
    if len(documents) <= top_k:
        return documents
    
    reranked = []
    remaining = documents.copy()
    
    # 1. Toujours inclure l'état actuel en premier
    current_docs = [d for d in remaining if d['metadata'].get('type') == 'current_state']
    if current_docs:
        reranked.append(current_docs[0])
        remaining = [d for d in remaining if d['id'] != current_docs[0]['id']]
    
    # 2. Sélectionner le reste par score et diversité
    types_included = {d['metadata'].get('type') for d in reranked}
    
    while len(reranked) < top_k and remaining:
        # Trouver le meilleur document non encore représenté
        best_doc = None
        best_score = -1
        
        for doc in remaining:
            doc_type = doc['metadata'].get('type')
            score = doc.get('score', 0)
            
            # Boost si type non représenté (diversité)
            if doc_type not in types_included:
                score *= 1.5
            
            if score > best_score:
                best_score = score
                best_doc = doc
        
        if best_doc:
            reranked.append(best_doc)
            types_included.add(best_doc['metadata'].get('type'))
            remaining = [d for d in remaining if d['id'] != best_doc['id']]
        else:
            break
    
    return reranked


# =============================================================================
# RAG BASIQUE : CONSTRUCTION DU CONTEXTE
# =============================================================================

def build_optimized_context(query: str, relevant_docs: List[Dict]) -> str:
    """
    Construit un contexte compact et structuré à partir des documents pertinents.
    """
    if not relevant_docs:
        return "Aucune information pertinente trouvée dans la base de connaissances."
    
    context_parts = ["=== INFORMATIONS PERTINENTES RÉCUPÉRÉES PAR LE RAG ===\n"]
    
    total_chars = 0
    max_chars = RAG_CONFIG["max_context_tokens"] * 4  # ~4 chars par token
    
    for i, doc in enumerate(relevant_docs, 1):
        doc_type = doc['metadata'].get('type', 'unknown')
        score = doc.get('score', 0)
        base_score = doc.get('base_score', 0)
        
        # En-tête du document
        header = f"\n[Document {i}/{len(relevant_docs)} - Type: {doc_type} - Score de pertinence: {score:.3f}]"
        doc_text = doc['text']
        
        # Vérifier la limite
        if total_chars + len(header) + len(doc_text) > max_chars:
            # Tronquer si nécessaire
            remaining_chars = max_chars - total_chars - len(header)
            if remaining_chars > 100:
                doc_text = doc_text[:remaining_chars] + "... [tronqué pour respecter la limite de contexte]"
            else:
                break
        
        context_parts.append(header)
        context_parts.append(doc_text)
        context_parts.append("\n" + "-" * 80)
        
        total_chars += len(header) + len(doc_text)
    
    return "\n".join(context_parts)


# =============================================================================
# INITIALISATION ET CACHE DU RAG
# =============================================================================

@st.cache_resource
def initialize_rag_system():
    """
    Initialise le système RAG avec cache.
    Cette fonction est appelée une seule fois et mise en cache.
    """
    retriever = TFIDFRetriever()
    return retriever


def update_rag_index(retriever: TFIDFRetriever, 
                    patients_df: pd.DataFrame,
                    staff_df: pd.DataFrame,
                    session_metadata: List[Dict],
                    current_state: Optional[Dict]) -> None:
    """
    Met à jour l'index RAG avec les données actuelles.
    Utilise un hash pour éviter les réindexations inutiles.
    """
    # Créer un hash des données pour détecter les changements
    data_hash = hashlib.md5(
        f"{len(patients_df)}{len(staff_df)}{len(session_metadata)}{current_state}".encode()
    ).hexdigest()
    
    # Vérifier si réindexation nécessaire
    if "last_data_hash" in st.session_state and st.session_state.last_data_hash == data_hash:
        return  # Données inchangées, pas de réindexation
    
    # Préparer et indexer les documents
    with st.spinner("🔄 Indexation des documents RAG (TF-IDF)..."):
        documents = prepare_rag_documents(patients_df, staff_df, session_metadata, current_state)
        retriever.index_documents(documents)
        
        # Sauvegarder le hash
        st.session_state.last_data_hash = data_hash
        st.session_state.rag_documents_count = len(documents)


# =============================================================================
# LLM : GÉNÉRATION DE RÉPONSE
# =============================================================================

def generate_response_with_rag(user_query: str, rag_context: str, 
                               retrieval_time: float, num_docs: int) -> str:
    """
    Génère une réponse en utilisant le LLM avec le contexte RAG optimisé.
    """
    if not MISTRAL_AVAILABLE or not MISTRAL_API_KEY or not MISTRAL_API_KEY.strip():
        return "❌ API Mistral non configurée. Vérifiez votre clé API dans le fichier .env"
    
    try:
        client = Mistral(api_key=MISTRAL_API_KEY)
        
        # Prompt système optimisé
        system_prompt = f"""Tu es un assistant médical expert en gestion des urgences hospitalières.

Tu as accès à un système RAG (Retrieval-Augmented Generation) basique mais efficace qui t'a fourni {num_docs} documents pertinents 
extraits de la session actuelle et de l'historique complet (récupérés en {retrieval_time:.3f}s via recherche TF-IDF).

Tes capacités:
- Analyser l'état actuel des urgences avec précision
- Identifier les tendances basées sur les données historiques
- Faire des recommandations data-driven
- Fournir des statistiques exactes

Règles strictes:
1. Base tes réponses UNIQUEMENT sur le contexte fourni ci-dessous
2. Si l'information n'est pas dans le contexte, dis "Je n'ai pas cette information dans les données disponibles"
3. Cite toujours les chiffres précis quand disponibles
4. Structure tes réponses clairement (utilise des sections si nécessaire)
5. Sois concis mais complet
6. Ne spécule jamais - reste factuel

Le contexte RAG contient:
- L'état en temps réel de la session actuelle
- Les statistiques historiques pertinentes
- Les tendances et patterns identifiés
"""

        # Prompt utilisateur avec contexte RAG
        user_prompt = f"""CONTEXTE RAG (Documents pertinents récupérés par recherche TF-IDF):

{rag_context}

================================================================================

QUESTION DE L'UTILISATEUR:
{user_query}

Réponds de manière précise, structurée et factuelle en te basant UNIQUEMENT sur le contexte ci-dessus."""

        # Appel API
        start_time = time.time()
        response = client.chat.complete(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,  # Très faible pour réponses factuelles
            max_tokens=1500
        )
        llm_time = time.time() - start_time
        
        answer = response.choices[0].message.content
        
        # Ajouter des métadonnées de performance
        performance_note = f"\n\n---\n📊 *Performance RAG: Récupération {retrieval_time:.2f}s | LLM {llm_time:.2f}s | {num_docs} docs | TF-IDF*"
        
        return answer + performance_note
    
    except Exception as e:
        return f"❌ Erreur lors de l'appel API: {str(e)}\n\nVérifiez votre clé API Mistral et votre quota."


# =============================================================================
# SUGGESTIONS DE QUESTIONS
# =============================================================================

SUGGESTED_QUESTIONS = [
    "📊 État actuel des urgences ?",
    "👥 Patients en attente ?",
    "🚨 Patients ROUGE ?",
    "📈 Comparaison à l'historique ?",
    "⏰ Temps d'attente moyen ?",
    "🏥 Capacités Soins Critiques ?",
    "👨‍⚕️ Personnel disponible ?",
    "📉 Tendance cas ROUGE ?",
    "💡 Recommandations ?",
    "📋 Parcours fréquents ?",
    "⚡ Pics d'activité ?",
    "🔍 Analyse cas critiques ?",
]


# =============================================================================
# INTERFACE STREAMLIT
# =============================================================================

def show_ai_assistant():
    """Page principale de l'AI Assistant avec RAG Basique."""
    
    st.title("🤖 AI Assistant - RAG Niveau 2 (Basique)")
    st.markdown("**Retrieval-Augmented Generation** avec TF-IDF - Simple, rapide, efficace")
    
    # Initialiser l'historique de chat
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # Charger les données
    with st.spinner("🔄 Chargement des données..."):
        patients_df, staff_df, session_metadata = load_historical_sessions()
        current_state = load_current_session_state()
    
    # Initialiser le système RAG
    retriever = initialize_rag_system()
    
    # Mettre à jour l'index RAG
    update_rag_index(retriever, patients_df, staff_df, session_metadata, current_state)
    
    # Indicateurs en haut
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "📚 Documents RAG",
            st.session_state.get('rag_documents_count', 0),
            "indexés (TF-IDF)"
        )
    
    with col2:
        st.metric(
            "👥 Patients Actuels",
            len(current_state.get('patients', {})) if current_state else 0,
            "en session active"
        )
    
    with col3:
        st.metric(
            "🧠 Type RAG",
            "TF-IDF",
            "Niveau 2"
        )
    
    with col4:
        st.metric(
            "💬 Conversations",
            len([m for m in st.session_state.chat_history if m["role"] == "user"]),
            "questions posées"
        )
    
    st.divider()
    
    # Layout principal : 2 colonnes
    col_chat, col_info = st.columns([2, 1])
    
    with col_chat:
        st.subheader("💬 Chat Intelligent")
        
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
            # Ajouter la question
            st.session_state.chat_history.append({
                "role": "user",
                "content": user_input
            })
            
            # Recherche RAG
            start_time = time.time()
            
            with st.spinner("🔍 Recherche TF-IDF dans la base de connaissances..."):
                # Récupération
                retrieved_docs = retriever.retrieve(
                    user_input,
                    top_k=RAG_CONFIG["top_k_retrieval"]
                )
                
                # Réranking
                reranked_docs = rerank_documents(
                    user_input,
                    retrieved_docs,
                    top_k=RAG_CONFIG["top_k_final"]
                )
                
                # Construction du contexte
                rag_context = build_optimized_context(user_input, reranked_docs)
                
                retrieval_time = time.time() - start_time
            
            # Génération LLM
            with st.spinner("🤖 Génération de la réponse..."):
                response = generate_response_with_rag(
                    user_input,
                    rag_context,
                    retrieval_time,
                    len(reranked_docs)
                )
            
            # Ajouter la réponse
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response
            })
            
            # Sauvegarder les docs utilisés pour inspection
            st.session_state.last_retrieved_docs = reranked_docs
            
            st.rerun()
    
    with col_info:
        st.subheader("💡 Suggestions")
        
        st.markdown("**Questions rapides :**")
        
        # Affichage des suggestions
        for i in range(0, len(SUGGESTED_QUESTIONS), 2):
            cols = st.columns(2)
            for j in range(2):
                if i + j < len(SUGGESTED_QUESTIONS):
                    question = SUGGESTED_QUESTIONS[i + j]
                    if cols[j].button(question, key=f"suggest_{i}_{j}", use_container_width=True):
                        # Simuler l'envoi
                        st.session_state.chat_history.append({
                            "role": "user",
                            "content": question
                        })
                        
                        # RAG retrieval
                        start_time = time.time()
                        retrieved_docs = retriever.retrieve(question, top_k=RAG_CONFIG["top_k_retrieval"])
                        reranked_docs = rerank_documents(question, retrieved_docs, top_k=RAG_CONFIG["top_k_final"])
                        rag_context = build_optimized_context(question, reranked_docs)
                        retrieval_time = time.time() - start_time
                        
                        response = generate_response_with_rag(question, rag_context, retrieval_time, len(reranked_docs))
                        
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response
                        })
                        
                        st.session_state.last_retrieved_docs = reranked_docs
                        st.rerun()
        
        st.divider()
        
        # Boutons d'action
        if st.button("🗑️ Nouvelle conversation", type="secondary", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
        
        # Inspection des documents récupérés
        if "last_retrieved_docs" in st.session_state:
            with st.expander("🔍 Documents RAG utilisés"):
                for i, doc in enumerate(st.session_state.last_retrieved_docs, 1):
                    st.markdown(f"**Document {i}** (score: {doc.get('score', 0):.3f})")
                    st.caption(f"Type: {doc['metadata'].get('type', 'unknown')}")
                    st.text(doc['text'][:200] + "...")
                    st.divider()
    
    # Section statistiques détaillées
    st.divider()
    
    with st.expander("📊 Statistiques & Configuration RAG"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("📁 Sources de données")
            st.write(f"- Sessions historiques: {len(session_metadata)}")
            st.write(f"- Événements patients: {len(patients_df)}")
            st.write(f"- Événements staff: {len(staff_df)}")
            st.write(f"- Documents indexés: {st.session_state.get('rag_documents_count', 0)}")
        
        with col2:
            st.subheader("🔧 Configuration RAG")
            st.write(f"- Top-K récupération: {RAG_CONFIG['top_k_retrieval']}")
            st.write(f"- Top-K final: {RAG_CONFIG['top_k_final']}")
            st.write(f"- Max tokens contexte: {RAG_CONFIG['max_context_tokens']}")
            st.write(f"- TF-IDF features: {RAG_CONFIG['tfidf_max_features']}")
            st.write(f"- N-grams: {RAG_CONFIG['tfidf_ngram_range']}")
        
        with col3:
            st.subheader("🧠 Capacités IA")
            st.write("✅ Recherche TF-IDF")
            st.write("✅ Réranking intelligent")
            st.write("✅ Cache vectoriel")
            st.write("✅ Boost par importance")
            st.write("🟡 RAG Niveau 2 (Basique)")
    
    # Footer
    st.divider()
    st.caption(f"🤖 AI Assistant RAG Niveau 2 | TF-IDF + {MODEL_NAME} | Simple, rapide, efficace")


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

def main():
    """Point d'entrée principal."""
    show_ai_assistant()


if __name__ == "__main__":
    show_ai_assistant()