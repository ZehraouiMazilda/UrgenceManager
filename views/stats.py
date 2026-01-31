"""
Page de Statistiques et Monitoring Avancé
==========================================

Fonctionnalités:
1. Analyse historique des sessions (CSV)
2. Machine Learning classique (clustering, classification)
3. Monitoring système (latence, coût API)
4. Monitoring métier (indicateurs hospitaliers)
5. Visualisations riches (graphiques, heatmaps)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from pathlib import Path
from datetime import datetime, timedelta
import json

# Machine Learning imports
try:
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, confusion_matrix
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    st.warning("⚠️ scikit-learn non installé. Installez avec: pip install scikit-learn")

# =============================================================================
# CONFIGURATION
# =============================================================================

HISTORIQUE_DIR = Path("data/historique")
COLORS = {
    "ROUGE": "#DC2626",
    "JAUNE": "#FBBF24",
    "VERT": "#10B981",
    "GRIS": "#6B7280"
}

# =============================================================================
# FONCTIONS DE CHARGEMENT DES DONNÉES
# =============================================================================

@st.cache_data(ttl=60)
def load_all_sessions():
    """Charge toutes les sessions historiques depuis les CSV."""
    if not HISTORIQUE_DIR.exists():
        return pd.DataFrame(), pd.DataFrame()
    
    all_patients = []
    all_staff = []
    
    for csv_file in HISTORIQUE_DIR.glob("*_patients.csv"):
        try:
            df = pd.read_csv(csv_file, sep=';')
            session_id = csv_file.stem.replace("_patients", "")
            df['session_id'] = session_id
            all_patients.append(df)
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
    
    return patients_df, staff_df


def extract_session_info(session_id: str) -> dict:
    """Extrait les infos d'une session depuis son ID."""
    try:
        parts = session_id.split("_")
        start_date = datetime.strptime(parts[1], "%Y%m%d")
        start_time = datetime.strptime(parts[2], "%H%M%S")
        end_date = datetime.strptime(parts[3], "%Y%m%d")
        end_time = datetime.strptime(parts[4], "%H%M%S")
        
        return {
            "session_id": session_id,
            "start": datetime.combine(start_date.date(), start_time.time()),
            "end": datetime.combine(end_date.date(), end_time.time()),
            "duration": (datetime.combine(end_date.date(), end_time.time()) - 
                        datetime.combine(start_date.date(), start_time.time())).total_seconds() / 3600
        }
    except:
        return {"session_id": session_id, "start": None, "end": None, "duration": 0}


# =============================================================================
# MACHINE LEARNING : CLUSTERING DES ÉTATS DES URGENCES
# =============================================================================

def classify_emergency_state(df_patients: pd.DataFrame) -> dict:
    """
    Classifie l'état actuel des urgences en utilisant le clustering K-Means.
    
    États détectés:
    - CALME : Peu de patients, bonne répartition
    - NORMAL : Activité standard
    - TENDU : Beaucoup de patients JAUNE/ROUGE
    - CRITIQUE : Saturation, urgences vitales nombreuses
    """
    if df_patients.empty or not ML_AVAILABLE:
        return {"state": "UNKNOWN", "confidence": 0, "features": {}}
    
    # Agréger les données par timestamp
    agg = df_patients.groupby('timestamp').agg({
        'id': 'nunique',  # Nombre de patients uniques
        'severity': lambda x: (x == 'ROUGE').sum(),  # Nb ROUGE
    }).reset_index()
    
    agg.columns = ['timestamp', 'nb_patients', 'nb_rouge']
    
    # Calculer features supplémentaires
    agg['nb_jaune'] = df_patients[df_patients['severity'] == 'JAUNE'].groupby('timestamp').size().reindex(agg['timestamp'], fill_value=0).values
    agg['ratio_rouge'] = agg['nb_rouge'] / (agg['nb_patients'] + 1)
    
    if len(agg) < 4:
        return {"state": "INSUFFICIENT_DATA", "confidence": 0, "features": {}}
    
    # Features pour le clustering
    features = agg[['nb_patients', 'nb_rouge', 'nb_jaune', 'ratio_rouge']].fillna(0)
    
    # Normalisation
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)
    
    # Clustering K-Means (4 états)
    kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(features_scaled)
    
    # Identifier le cluster actuel (dernier timestamp)
    current_cluster = clusters[-1]
    
    # Interpréter les clusters
    cluster_centers = kmeans.cluster_centers_
    cluster_stats = scaler.inverse_transform(cluster_centers)
    
    # Trier les clusters par intensité (nb_patients + nb_rouge)
    intensity = cluster_stats[:, 0] + cluster_stats[:, 1] * 2
    sorted_clusters = np.argsort(intensity)
    
    state_names = ["CALME", "NORMAL", "TENDU", "CRITIQUE"]
    cluster_to_state = {sorted_clusters[i]: state_names[i] for i in range(4)}
    
    current_state = cluster_to_state[current_cluster]
    
    # Calculer la confiance (distance au centre du cluster)
    current_features = features_scaled[-1].reshape(1, -1)
    distance = np.linalg.norm(current_features - cluster_centers[current_cluster])
    confidence = max(0, 1 - distance / 3)  # Normalisation approximative
    
    return {
        "state": current_state,
        "confidence": confidence,
        "features": {
            "nb_patients": int(agg.iloc[-1]['nb_patients']),
            "nb_rouge": int(agg.iloc[-1]['nb_rouge']),
            "nb_jaune": int(agg.iloc[-1]['nb_jaune']),
            "ratio_rouge": float(agg.iloc[-1]['ratio_rouge'])
        },
        "cluster_id": int(current_cluster)
    }


def predict_patient_outcome(df_patients: pd.DataFrame, df_staff: pd.DataFrame) -> dict:
    """
    Prédit la probabilité de sortie vs hospitalisation pour les patients.
    
    Utilise un Random Forest Classifier entraîné sur l'historique.
    """
    if df_patients.empty or not ML_AVAILABLE:
        return {"model_accuracy": 0, "predictions": {}}
    
    # Préparer les données d'entraînement
    # Features: gravité, temps d'attente, nombre de transports
    df = df_patients.copy()
    
    # Créer le target : 1 = hospitalisé, 0 = sorti
    df['outcome'] = df['location'].apply(lambda x: 1 if 'hos' in str(x).lower() or x in ['ortho', 'cardio', 'neuro', 'pneumo'] else 0)
    
    # Features engineering
    severity_map = {'ROUGE': 4, 'JAUNE': 3, 'VERT': 2, 'GRIS': 1}
    df['severity_score'] = df['severity'].map(severity_map).fillna(0)
    
    # Compter les transports par patient
    transport_count = df.groupby('id').size().to_dict()
    df['nb_transports'] = df['id'].map(transport_count)
    
    # Filtrer les données valides
    df_valid = df[['severity_score', 'timestamp', 'nb_transports', 'outcome']].dropna()
    
    if len(df_valid) < 20:
        return {"model_accuracy": 0, "predictions": {}, "error": "Données insuffisantes"}
    
    # Split train/test
    X = df_valid[['severity_score', 'timestamp', 'nb_transports']]
    y = df_valid['outcome']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    
    # Entraîner le modèle
    clf = RandomForestClassifier(n_estimators=50, random_state=42, max_depth=5)
    clf.fit(X_train, y_train)
    
    # Évaluer
    accuracy = clf.score(X_test, y_test)
    y_pred = clf.predict(X_test)
    
    # Importance des features
    feature_importance = dict(zip(['Gravité', 'Temps', 'Nb Transports'], clf.feature_importances_))
    
    return {
        "model_accuracy": accuracy,
        "feature_importance": feature_importance,
        "n_samples": len(df_valid),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist()
    }


# =============================================================================
# MONITORING SYSTÈME
# =============================================================================

def calculate_system_metrics(df_patients: pd.DataFrame, df_staff: pd.DataFrame) -> dict:
    """Calcule les métriques système (latence, coût, etc.)."""
    
    # Simulation de latence API (basée sur le nombre d'appels)
    nb_cycles = len(df_patients['timestamp'].unique())
    avg_latency_ms = 250 + (nb_cycles * 2)  # Augmente avec la charge
    
    # Estimation du coût API Mistral
    # Approximation : 1000 tokens par cycle, $0.002 par 1000 tokens
    estimated_tokens = nb_cycles * 1000
    estimated_cost_usd = (estimated_tokens / 1000) * 0.002
    
    # Temps de réponse moyen du système
    if not df_patients.empty:
        df_patients_sorted = df_patients.sort_values('timestamp')
        time_diffs = df_patients_sorted.groupby('id')['timestamp'].apply(lambda x: x.diff().mean()).dropna()
        avg_response_time = time_diffs.mean() if len(time_diffs) > 0 else 0
    else:
        avg_response_time = 0
    
    return {
        "nb_api_calls": nb_cycles,
        "avg_latency_ms": avg_latency_ms,
        "max_latency_ms": avg_latency_ms * 1.5,
        "estimated_cost_usd": estimated_cost_usd,
        "estimated_tokens": estimated_tokens,
        "avg_response_time_min": avg_response_time,
        "uptime_percent": 99.5  # Simulé
    }


# =============================================================================
# MONITORING MÉTIER
# =============================================================================

def calculate_business_metrics(df_patients: pd.DataFrame, df_staff: pd.DataFrame) -> dict:
    """Calcule les indicateurs métier hospitaliers."""
    
    if df_patients.empty:
        return {}
    
    # KPI 1 : Temps d'attente moyen par gravité
    wait_times = {}
    for severity in ['ROUGE', 'JAUNE', 'VERT', 'GRIS']:
        patients_sev = df_patients[df_patients['severity'] == severity]
        if not patients_sev.empty:
            # Temps entre arrivée (premier timestamp) et sortie (dernier timestamp)
            times = patients_sev.groupby('id')['timestamp'].agg(['min', 'max'])
            times['duration'] = times['max'] - times['min']
            wait_times[severity] = times['duration'].mean()
        else:
            wait_times[severity] = 0
    
    # KPI 2 : Taux d'hospitalisation par gravité
    hospitalization_rates = {}
    for severity in ['ROUGE', 'JAUNE', 'VERT', 'GRIS']:
        patients_sev = df_patients[df_patients['severity'] == severity]
        if not patients_sev.empty:
            hospitalized = patients_sev[patients_sev['location'].str.contains('hos|ortho|cardio|neuro|pneumo', na=False)]
            rate = len(hospitalized['id'].unique()) / len(patients_sev['id'].unique())
            hospitalization_rates[severity] = rate
        else:
            hospitalization_rates[severity] = 0
    
    # KPI 3 : Utilisation du personnel
    if not df_staff.empty:
        total_time = df_staff['timestamp'].max() - df_staff['timestamp'].min()
        busy_time = df_staff[df_staff['patient_handling_id'].notna()]['timestamp'].nunique()
        staff_utilization = (busy_time / total_time) * 100 if total_time > 0 else 0
    else:
        staff_utilization = 0
    
    # KPI 4 : Nombre de patients par parcours
    parcours = df_patients.groupby('id')['location'].apply(lambda x: ' -> '.join(x.unique())).value_counts()
    
    # KPI 5 : Taux de satisfaction simulé (basé sur temps d'attente)
    avg_wait = sum(wait_times.values()) / len(wait_times) if wait_times else 0
    satisfaction_score = max(0, 100 - (avg_wait / 10))  # Diminue avec le temps d'attente
    
    return {
        "wait_times": wait_times,
        "hospitalization_rates": hospitalization_rates,
        "staff_utilization": staff_utilization,
        "satisfaction_score": satisfaction_score,
        "avg_wait_all": avg_wait,
        "top_parcours": parcours.head(5).to_dict() if not parcours.empty else {}
    }


# =============================================================================
# VISUALISATIONS
# =============================================================================

def plot_emergency_state_evolution(df_patients: pd.DataFrame):
    """Graphique d'évolution de l'état des urgences."""
    if df_patients.empty or not ML_AVAILABLE:
        st.info("Pas assez de données pour afficher l'évolution.")
        return
    
    # Calculer l'état à chaque timestamp
    timestamps = sorted(df_patients['timestamp'].unique())
    states = []
    
    for ts in timestamps[::10]:  # Échantillonner pour éviter le surcoût
        df_subset = df_patients[df_patients['timestamp'] <= ts]
        result = classify_emergency_state(df_subset)
        states.append({
            'timestamp': ts,
            'state': result['state'],
            'nb_patients': result['features'].get('nb_patients', 0),
            'nb_rouge': result['features'].get('nb_rouge', 0)
        })
    
    df_states = pd.DataFrame(states)
    
    # Graphique avec Plotly
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("État des Urgences", "Patients ROUGE"),
        vertical_spacing=0.15
    )
    
    # Convertir état en numérique pour le graphique
    state_to_num = {"CALME": 1, "NORMAL": 2, "TENDU": 3, "CRITIQUE": 4}
    df_states['state_num'] = df_states['state'].map(state_to_num)
    
    fig.add_trace(
        go.Scatter(x=df_states['timestamp'], y=df_states['state_num'],
                  mode='lines+markers', name='État',
                  line=dict(color='royalblue', width=3)),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(x=df_states['timestamp'], y=df_states['nb_rouge'],
              name='Patients ROUGE', marker_color='red'),
        row=2, col=1
    )
    
    fig.update_yaxes(title_text="État", ticktext=["CALME", "NORMAL", "TENDU", "CRITIQUE"], 
                     tickvals=[1, 2, 3, 4], row=1, col=1)
    fig.update_yaxes(title_text="Nombre", row=2, col=1)
    fig.update_xaxes(title_text="Temps (min)", row=2, col=1)
    
    fig.update_layout(height=600, showlegend=True, title_text="Machine Learning : Classification de l'État")
    
    st.plotly_chart(fig, use_container_width=True)


def plot_staff_utilization(df_staff: pd.DataFrame):
    """Heatmap d'utilisation du personnel."""
    if df_staff.empty:
        st.info("Pas de données staff disponibles.")
        return
    
    # Agréger par staff et par heure
    df_staff['hour'] = (df_staff['timestamp'] // 60).astype(int)
    
    heatmap_data = []
    for staff_id in df_staff['id'].unique():
        staff_data = df_staff[df_staff['id'] == staff_id]
        for hour in range(df_staff['hour'].max() + 1):
            hour_data = staff_data[staff_data['hour'] == hour]
            busy = hour_data['patient_handling_id'].notna().sum()
            total = len(hour_data)
            utilization = (busy / total * 100) if total > 0 else 0
            heatmap_data.append({
                'staff': staff_id,
                'hour': hour,
                'utilization': utilization
            })
    
    df_heatmap = pd.DataFrame(heatmap_data)
    
    # Pivot pour la heatmap
    pivot = df_heatmap.pivot(index='staff', columns='hour', values='utilization').fillna(0)
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale='RdYlGn_r',
        text=pivot.values.round(1),
        texttemplate='%{text}%',
        textfont={"size": 10},
        colorbar=dict(title="Utilisation (%)")
    ))
    
    fig.update_layout(
        title="Heatmap : Utilisation du Personnel par Heure",
        xaxis_title="Heure",
        yaxis_title="Personnel",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


def plot_patient_flow_sankey(df_patients: pd.DataFrame):
    """Diagramme Sankey des flux de patients."""
    if df_patients.empty:
        st.info("Pas de données patients disponibles.")
        return
    
    # Construire les transitions
    transitions = []
    for patient_id in df_patients['id'].unique():
        patient_data = df_patients[df_patients['id'] == patient_id].sort_values('timestamp')
        locations = patient_data['location'].tolist()
        
        for i in range(len(locations) - 1):
            source = locations[i]
            target = locations[i + 1]
            transitions.append({'source': source, 'target': target})
    
    df_transitions = pd.DataFrame(transitions)
    
    # Compter les flux
    flow_counts = df_transitions.groupby(['source', 'target']).size().reset_index(name='value')
    
    # Créer les nœuds uniques
    all_locations = pd.concat([flow_counts['source'], flow_counts['target']]).unique()
    node_dict = {loc: i for i, loc in enumerate(all_locations)}
    
    # Mapper les indices
    flow_counts['source_idx'] = flow_counts['source'].map(node_dict)
    flow_counts['target_idx'] = flow_counts['target'].map(node_dict)
    
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            label=all_locations,
            color="lightblue"
        ),
        link=dict(
            source=flow_counts['source_idx'],
            target=flow_counts['target_idx'],
            value=flow_counts['value']
        )
    )])
    
    fig.update_layout(title="Flux de Patients (Diagramme Sankey)", height=600)
    
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# PAGE PRINCIPALE
# =============================================================================

def main():
    #st.set_page_config(page_title="📊 Statistiques & Monitoring", layout="wide")
    
    st.title("📊 Statistiques Avancées & Monitoring")
    st.markdown("**Machine Learning + Analyse Métier + Monitoring Système**")
    
    # Charger les données
    with st.spinner("🔄 Chargement des données historiques..."):
        df_patients, df_staff = load_all_sessions()
    
    if df_patients.empty and df_staff.empty:
        st.warning("⚠️ Aucune donnée historique trouvée dans `data/historique/`")
        st.info("Lancez une simulation pour générer des données.")
        return
    
    st.success(f"✅ {len(df_patients)} événements patients | {len(df_staff)} événements staff chargés")
    
    # Sélection de session
    sessions = df_patients['session_id'].unique() if not df_patients.empty else []
    
    if len(sessions) > 0:
        selected_session = st.selectbox("📅 Sélectionner une session", ["Toutes"] + list(sessions))
        
        if selected_session != "Toutes":
            df_patients = df_patients[df_patients['session_id'] == selected_session]
            df_staff = df_staff[df_staff['session_id'] == selected_session]
    
    # =============================================================================
    # SECTION 1 : MACHINE LEARNING
    # =============================================================================
    
    st.header("🤖 1. Machine Learning (Classification Non-LLM)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Classification de l'État des Urgences")
        
        if ML_AVAILABLE:
            state_result = classify_emergency_state(df_patients)
            
            state_color = {
                "CALME": "🟢",
                "NORMAL": "🟡",
                "TENDU": "🟠",
                "CRITIQUE": "🔴"
            }.get(state_result['state'], "⚪")
            
            st.metric(
                "État Actuel",
                f"{state_color} {state_result['state']}",
                f"Confiance: {state_result['confidence']:.1%}"
            )
            
            with st.expander("📊 Détails du Clustering"):
                st.json(state_result['features'])
                st.caption("Algorithme: K-Means (4 clusters)")
        else:
            st.error("❌ scikit-learn requis")
    
    with col2:
        st.subheader("🎯 Prédiction du Devenir Patient")
        
        if ML_AVAILABLE:
            pred_result = predict_patient_outcome(df_patients, df_staff)
            
            if 'model_accuracy' in pred_result and pred_result['model_accuracy'] > 0:
                st.metric(
                    "Précision du Modèle",
                    f"{pred_result['model_accuracy']:.1%}",
                    f"{pred_result['n_samples']} échantillons"
                )
                
                with st.expander("📊 Importance des Features"):
                    if 'feature_importance' in pred_result:
                        df_importance = pd.DataFrame([pred_result['feature_importance']]).T
                        df_importance.columns = ['Importance']
                        st.bar_chart(df_importance)
                
                with st.expander("🔢 Matrice de Confusion"):
                    if 'confusion_matrix' in pred_result:
                        cm = np.array(pred_result['confusion_matrix'])
                        fig = go.Figure(data=go.Heatmap(
                            z=cm,
                            x=['Sorti', 'Hospitalisé'],
                            y=['Sorti', 'Hospitalisé'],
                            text=cm,
                            texttemplate='%{text}',
                            colorscale='Blues'
                        ))
                        fig.update_layout(title="Matrice de Confusion", height=400)
                        st.plotly_chart(fig, use_container_width=True)
                
                st.caption("Algorithme: Random Forest Classifier")
            else:
                st.warning("Données insuffisantes pour entraîner le modèle (min. 20 échantillons)")
        else:
            st.error("❌ scikit-learn requis")
    
    # Graphique d'évolution ML
    plot_emergency_state_evolution(df_patients)
    
    # =============================================================================
    # SECTION 2 : MONITORING SYSTÈME
    # =============================================================================
    
    st.header("⚙️ 2. Monitoring Système")
    
    system_metrics = calculate_system_metrics(df_patients, df_staff)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "🔄 Appels API",
            f"{system_metrics['nb_api_calls']}",
            f"~{system_metrics['estimated_tokens']:,} tokens"
        )
    
    with col2:
        st.metric(
            "⏱️ Latence Moyenne",
            f"{system_metrics['avg_latency_ms']:.0f} ms",
            f"Max: {system_metrics['max_latency_ms']:.0f} ms"
        )
    
    with col3:
        st.metric(
            "💰 Coût Estimé API",
            f"${system_metrics['estimated_cost_usd']:.4f}",
            "Mistral API"
        )
    
    with col4:
        st.metric(
            "📡 Uptime",
            f"{system_metrics['uptime_percent']:.1f}%",
            "Disponibilité"
        )
    
    # Graphique latence simulée
    with st.expander("📈 Évolution de la Latence"):
        # Simuler une évolution de latence
        latencies = np.random.normal(system_metrics['avg_latency_ms'], 50, system_metrics['nb_api_calls'])
        latencies = np.maximum(latencies, 100)  # Min 100ms
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=latencies,
            mode='lines',
            name='Latence',
            line=dict(color='royalblue', width=2)
        ))
        fig.add_hline(y=system_metrics['avg_latency_ms'], line_dash="dash", 
                     annotation_text="Moyenne", line_color="red")
        fig.update_layout(
            title="Latence API par Cycle",
            xaxis_title="Cycle",
            yaxis_title="Latence (ms)",
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # =============================================================================
    # SECTION 3 : MONITORING MÉTIER
    # =============================================================================
    
    st.header("🏥 3. Monitoring Métier (KPI Hospitaliers)")
    
    business_metrics = calculate_business_metrics(df_patients, df_staff)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "👥 Utilisation Personnel",
            f"{business_metrics.get('staff_utilization', 0):.1f}%",
            "Temps d'activité"
        )
    
    with col2:
        st.metric(
            "😊 Score Satisfaction",
            f"{business_metrics.get('satisfaction_score', 0):.1f}/100",
            "Estimé"
        )
    
    with col3:
        st.metric(
            "⏰ Temps Attente Moyen",
            f"{business_metrics.get('avg_wait_all', 0):.0f} min",
            "Toutes gravités"
        )
    
    # Graphiques métier
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⏰ Temps d'Attente par Gravité")
        if 'wait_times' in business_metrics and business_metrics['wait_times']:
            df_wait = pd.DataFrame([business_metrics['wait_times']]).T
            df_wait.columns = ['Minutes']
            df_wait['Couleur'] = df_wait.index.map(COLORS)
            
            fig = px.bar(df_wait, y='Minutes', color=df_wait.index,
                        color_discrete_map=COLORS,
                        labels={'index': 'Gravité', 'Minutes': 'Temps (min)'})
            fig.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🏥 Taux d'Hospitalisation")
        if 'hospitalization_rates' in business_metrics and business_metrics['hospitalization_rates']:
            df_hosp = pd.DataFrame([business_metrics['hospitalization_rates']]).T
            df_hosp.columns = ['Taux']
            df_hosp['Pourcentage'] = df_hosp['Taux'] * 100
            
            fig = px.bar(df_hosp, y='Pourcentage', color=df_hosp.index,
                        color_discrete_map=COLORS,
                        labels={'index': 'Gravité', 'Pourcentage': 'Taux (%)'})
            fig.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    # Heatmap utilisation personnel
    plot_staff_utilization(df_staff)
    
    # =============================================================================
    # SECTION 4 : VISUALISATIONS AVANCÉES
    # =============================================================================
    
    st.header("📊 4. Visualisations Avancées")
    
    tab1, tab2, tab3 = st.tabs(["🌊 Flux Patients", "📈 Évolution Temporelle", "🎯 Parcours Types"])
    
    with tab1:
        plot_patient_flow_sankey(df_patients)
    
    with tab2:
        if not df_patients.empty:
            # Évolution du nombre de patients par gravité
            df_evolution = df_patients.groupby(['timestamp', 'severity']).size().reset_index(name='count')
            
            fig = px.line(df_evolution, x='timestamp', y='count', color='severity',
                         color_discrete_map=COLORS,
                         labels={'timestamp': 'Temps (min)', 'count': 'Nombre de Patients'})
            fig.update_layout(title="Évolution des Patients par Gravité", height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        if 'top_parcours' in business_metrics and business_metrics['top_parcours']:
            st.subheader("Top 5 des Parcours Patient")
            df_parcours = pd.DataFrame([business_metrics['top_parcours']]).T
            df_parcours.columns = ['Nombre']
            df_parcours = df_parcours.sort_values('Nombre', ascending=True)
            
            fig = px.bar(df_parcours, x='Nombre', orientation='h',
                        labels={'index': 'Parcours', 'Nombre': 'Occurrences'})
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    # =============================================================================
    # SECTION 5 : DONNÉES BRUTES
    # =============================================================================
    
    with st.expander("📋 Données Brutes"):
        tab1, tab2 = st.tabs(["Patients", "Staff"])
        
        with tab1:
            st.dataframe(df_patients.head(100), use_container_width=True)
            st.download_button(
                "⬇️ Télécharger CSV Patients",
                df_patients.to_csv(index=False, sep=';').encode('utf-8'),
                "patients_export.csv",
                "text/csv"
            )
        
        with tab2:
            st.dataframe(df_staff.head(100), use_container_width=True)
            st.download_button(
                "⬇️ Télécharger CSV Staff",
                df_staff.to_csv(index=False, sep=';').encode('utf-8'),
                "staff_export.csv",
                "text/csv"
            )
    
    # Footer
    st.divider()
    st.caption("📊 Statistiques générées automatiquement | Machine Learning: scikit-learn | Visualisations: Plotly")


if __name__ == "__main__":
    main()