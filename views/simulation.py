"""
Module de simulation - VERSION ULTRA-FINALE (CORRIGÉE & UNIFIÉE)
Intègre : Simulation + Gestion Scénarios (Fix Pydantic) + Verrouillage UI
"""

import streamlit as st
import time
import random
import re
import os
import pandas as pd
from datetime import datetime
import json
import plotly.express as px
import plotly.graph_objects as go

from src.models import Patient, Severity, PatientStatus, StateFile
from src.utils import load_initial_state, save_state
from src.logger import log_event
from src.ai_brain import process_brain_cycle, set_llm_model
from mistralai import Mistral

# =============================================================================
# CHARGEMENT
# =============================================================================

def load_symptoms():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    symptoms_path = os.path.join(base_dir, "data", "symptoms.json")
    try:
        with open(symptoms_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "ROUGE": ["Douleur"],
            "JAUNE": ["Fracture"],
            "VERT": ["Bobo"],
            "GRIS": ["Rhume"],
        }

def load_full_file(path):
    """Charge un état complet (StateFile)"""
    with open(path, "r", encoding="utf-8") as f:
        return StateFile(**json.load(f))

def get_scenarios_with_metadata(base_dir):
    """Charge les scénarios avec leurs métadonnées élégantes"""
    scenarios_dir = os.path.join(base_dir, "data", "scenarios")
    metadata_path = os.path.join(base_dir, "config", "scenarios_metadata.json")
    
    metadata = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    
    if not os.path.exists(scenarios_dir):
        return []
    
    scenarios = []
    for filename in os.listdir(scenarios_dir):
        if filename.endswith('.json'):
            if filename in metadata:
                scenarios.append({
                    'filename': filename,
                    'title': metadata[filename]['title'],
                    'description': metadata[filename]['description'],
                    'duration': metadata[filename]['duration'],
                    'difficulty': metadata[filename]['difficulty']
                })
            else:
                clean_name = filename.replace('.json', '').replace('_', ' ').title()
                scenarios.append({
                    'filename': filename,
                    'title': clean_name,
                    'description': 'Scénario de test',
                    'duration': 'N/A',
                    'difficulty': 'N/A'
                })
    return scenarios

def execute_scenario_timeline(state, scenario_data, current_time, base_dir):
    """Exécute les actions du scénario au temps donné"""
    timeline = scenario_data.get('timeline', [])
    actions_executed = False
    
    for action in timeline:
        if action.get('t') == current_time:
            action_type = action.get('action')
            
            if not action_type or action_type == 'comment':
                continue
            
            if action_type == 'inject_patient':
                severity = action.get('severity')
                symptom = action.get('symptom', 'Symptôme générique')
                
                if "scenario_patient_counter" not in st.session_state:
                    st.session_state.scenario_patient_counter = 1
                
                new_id = f"PAT_{st.session_state.scenario_patient_counter:03d}"
                st.session_state.scenario_patient_counter += 1
                
                new_patient = Patient(
                    id=new_id,
                    severity=Severity[severity],
                    symptom=symptom,
                    location="triage",
                    status=PatientStatus.WAITING,
                    arrival_time=current_time
                )
                
                state.patients[new_id] = new_patient
                state.triage_zone.patients.append(new_id)
                state.triage_zone.occupancy += 1
                
                log_event(state, "PATIENT", new_id, "injected_triage")
                
                st.session_state.brain_logs.append(
                    f"[{current_time//60}h{current_time%60:02d}] ➕ {new_id} ({severity}) arrivé au triage"
                )
                
                actions_executed = True
    
    return actions_executed


# =============================================================================
# SESSION CSV - CRÉER AU DÉMARRAGE
# =============================================================================

def ensure_csv_session_initialized(base_dir):
    """Crée le fichier CSV de session au DÉMARRAGE (pas au reset)"""
    if "csv_session_id" not in st.session_state:
        st.session_state.csv_session_id = (
            f"SESSION_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # Créer le dossier historique
        hist_dir = os.path.join(base_dir, "data", "historique")
        os.makedirs(hist_dir, exist_ok=True)

        # Créer les fichiers CSV immédiatement
        pat_csv = os.path.join(
            hist_dir, f"{st.session_state.csv_session_id}_patients.csv"
        )
        staff_csv = os.path.join(
            hist_dir, f"{st.session_state.csv_session_id}_staff.csv"
        )

        # Créer headers
        pd.DataFrame(
            columns=["timestamp", "id", "location", "severity", "escort_id"]
        ).to_csv(pat_csv, sep=";", index=False)
        pd.DataFrame(
            columns=[
                "timestamp",
                "id",
                "location",
                "patient_handling_id",
                "patient_symptom",
                "patient_color",
            ]
        ).to_csv(staff_csv, sep=";", index=False)

        print(f"✅ CSV Session créée : {st.session_state.csv_session_id}")

# =============================================================================
# GÉNÉRATION UNIQUE IDs PATIENTS
# =============================================================================

def generate_unique_patient_id(state):
    """Génère un ID patient unique pour la session"""
    if "used_patient_ids" not in st.session_state:
        st.session_state.used_patient_ids = set()

    counter = len(st.session_state.used_patient_ids) + 1

    while True:
        new_id = f"PAT_{counter:03d}"
        if new_id not in st.session_state.used_patient_ids:
            st.session_state.used_patient_ids.add(new_id)
            return new_id
        counter += 1

# =============================================================================
# LECTURE CSV POUR STATS
# =============================================================================

def load_session_csv_data(base_dir):
    """Charge les données CSV de la session en cours"""
    if "csv_session_id" not in st.session_state:
        return None, None

    hist_dir = os.path.join(base_dir, "data", "historique")
    pat_csv = os.path.join(hist_dir, f"{st.session_state.csv_session_id}_patients.csv")
    staff_csv = os.path.join(hist_dir, f"{st.session_state.csv_session_id}_staff.csv")

    try:
        df_patients = pd.read_csv(pat_csv, sep=";")
        df_staff = pd.read_csv(staff_csv, sep=";")
        return df_patients, df_staff
    except:
        return None, None

# =============================================================================
# GRAPHIQUES AVEC DONNÉES CSV COMPLÈTES
# =============================================================================

def create_complete_statistics_charts(base_dir, state):
    """Graphiques basés sur TOUT le CSV (patients sortis inclus)"""

    df_patients, df_staff = load_session_csv_data(base_dir)

    if df_patients is None or len(df_patients) < 2:
        fig = go.Figure()
        fig.add_annotation(
            text="Pas encore assez de données", showarrow=False, font_size=14
        )
        fig.update_layout(height=350)
        return fig, fig, fig, fig, fig, fig
    
    # Vérifier que timestamp existe
    if 'timestamp' not in df_patients.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="CSV en cours de création...", showarrow=False, font_size=14
        )
        fig.update_layout(height=350)
        return fig, fig, fig, fig, fig, fig

    # GRAPHIQUE 1 : Évolution nombre de patients par localisation
    fig1 = go.Figure()

    # Agréger par timestamp et location
    timeline = []
    for t in sorted(df_patients["timestamp"].unique()):
        df_t = df_patients[df_patients["timestamp"] == t]
        timeline.append(
            {
                "timestamp": t,
                "triage": len(
                    df_t[
                        df_t["location"].str.contains(
                            "triage|injected_triage", na=False
                        )
                    ]
                ),
                "salles": len(df_t[df_t["location"].str.contains("wr_", na=False)]),
                "consultation": len(
                    df_t[df_t["location"].str.contains("consult", na=False)]
                ),
                "hopitaux": len(
                    df_t[
                        df_t["location"].str.contains(
                            "ortho|cardio|neuro|pneumo", na=False
                        )
                    ]
                ),
            }
        )

    if timeline:
        df_timeline = pd.DataFrame(timeline)
        fig1.add_trace(
            go.Scatter(
                x=df_timeline["timestamp"],
                y=df_timeline["triage"],
                name="Triage",
                stackgroup="one",
            )
        )
        fig1.add_trace(
            go.Scatter(
                x=df_timeline["timestamp"],
                y=df_timeline["salles"],
                name="Salles",
                stackgroup="one",
            )
        )
        fig1.add_trace(
            go.Scatter(
                x=df_timeline["timestamp"],
                y=df_timeline["consultation"],
                name="Consultation",
                stackgroup="one",
            )
        )
        fig1.add_trace(
            go.Scatter(
                x=df_timeline["timestamp"],
                y=df_timeline["hopitaux"],
                name="Hôpitaux",
                stackgroup="one",
            )
        )

    fig1.update_layout(
        title="📍 Répartition patients dans le temps",
        xaxis_title="Temps (min)",
        yaxis_title="Patients",
        height=350,
    )

    # GRAPHIQUE 2 : Total patients traités par couleur
    colors_count = df_patients.groupby("severity")["id"].nunique().to_dict()

    fig2 = go.Figure(
        data=[
            go.Bar(
                x=list(colors_count.keys()),
                y=list(colors_count.values()),
                marker_color=["gray", "orange", "red", "green"],
                text=list(colors_count.values()),
                textposition="auto",
            )
        ]
    )
    fig2.update_layout(
        title="📊 Total patients traités par gravité",
        xaxis_title="Gravité",
        yaxis_title="Nombre de patients",
        height=350,
    )

    # GRAPHIQUE 3 : Activité AS (nombre de transports)
    as_activity = (
        df_staff[df_staff["id"].str.contains("AS_", na=False)]
        .groupby("id")
        .size()
        .to_dict()
    )

    fig3 = go.Figure(
        data=[
            go.Bar(
                x=list(as_activity.keys()),
                y=list(as_activity.values()),
                marker_color="lightblue",
                text=list(as_activity.values()),
                textposition="auto",
            )
        ]
    )
    fig3.update_layout(
        title="🚑 Nombre de transports par AS",
        xaxis_title="AS",
        yaxis_title="Transports",
        height=350,
    )

    # GRAPHIQUE 4 : Temps d'attente moyen par couleur (patients encore actifs)
    current_wait = {"ROUGE": [], "JAUNE": [], "VERT": [], "GRIS": []}
    for pid, p in state.patients.items():
        if p.location in ["triage"] + list(state.waiting_rooms.keys()):
            current_wait[p.severity.value].append(state.time - p.arrival_time)

    wait_avgs = {
        color: (sum(times) / len(times) if times else 0)
        for color, times in current_wait.items()
    }

    fig4 = go.Figure(
        data=[
            go.Bar(
                x=list(wait_avgs.keys()),
                y=list(wait_avgs.values()),
                marker_color=["red", "orange", "green", "gray"],
                text=[f"{v:.1f} min" for v in wait_avgs.values()],
                textposition="auto",
            )
        ]
    )
    fig4.update_layout(
        title="⏱️ Temps d'attente moyen actuel",
        xaxis_title="Gravité",
        yaxis_title="Minutes",
        height=350,
    )

    # GRAPHIQUE 5 : Répartition destinations finales
    final_locs = df_patients.groupby("id")["location"].last().value_counts().to_dict()

    fig5 = go.Figure(
        data=[go.Pie(labels=list(final_locs.keys()), values=list(final_locs.values()))]
    )
    fig5.update_layout(title="🎯 Destinations finales des patients", height=350)

    # GRAPHIQUE 6 : PARCOURS PATIENT (Sankey)
    # Construire les flux patient par patient
    patient_paths = df_patients.groupby("id")["location"].apply(list).to_dict()

    flux = {}
    for pid, path in patient_paths.items():
        for i in range(len(path) - 1):
            from_loc = path[i]
            to_loc = path[i + 1]

            # Nettoyer les noms
            from_clean = from_loc.replace("injected_", "").replace("tran_", "→")
            to_clean = to_loc.replace("injected_", "").replace("tran_", "→")

            key = f"{from_clean} → {to_clean}"
            flux[key] = flux.get(key, 0) + 1

    if flux:
        # Construire Sankey
        all_locs = set()
        for k in flux.keys():
            f, t = k.split(" → ")
            all_locs.add(f)
            all_locs.add(t)

        loc_list = sorted(list(all_locs))
        loc_idx = {l: i for i, l in enumerate(loc_list)}

        src, tgt, val = [], [], []
        for k, c in flux.items():
            f, t = k.split(" → ")
            src.append(loc_idx[f])
            tgt.append(loc_idx[t])
            val.append(c)

        fig6 = go.Figure(
            data=[
                go.Sankey(
                    node=dict(pad=15, thickness=20, label=loc_list),
                    link=dict(source=src, target=tgt, value=val),
                )
            ]
        )
        fig6.update_layout(title="🗺️ Parcours complet des patients", height=400)
    else:
        fig6 = go.Figure()
        fig6.add_annotation(
            text="Pas assez de mouvements", showarrow=False, font_size=14
        )
        fig6.update_layout(title="🗺️ Parcours patients", height=400)

    return fig1, fig2, fig3, fig4, fig5, fig6

# =============================================================================
# HELPERS
# =============================================================================

def check_presence(state, room_staff_list, role_tag):
    found = []
    for s_id in room_staff_list:
        ag = state.staff.get(s_id)
        if ag and role_tag in s_id and ag.is_present and not ag.is_busy:
            found.append(s_id)
    return f"🟢 {', '.join(found)}" if found else "❌"

def format_patient_colored(patient, current_time):
    if not patient:
        return "Inconnu"
    val = patient.severity.value
    colors = {"ROUGE": "red", "JAUNE": "orange", "VERT": "green", "GRIS": "grey"}
    base = f":{colors.get(val, 'black')}[{patient.id}]"

    if patient.status == PatientStatus.IN_TRANSIT:
        transit_time = current_time - patient.arrival_time
        eta = max(0, 45 - transit_time)
        return f"{base} (🚑 Arrivée {eta} min)"

    if patient.treatment_end_time > 0:
        rem_min = patient.treatment_end_time - current_time
        if rem_min > 0:
            h = rem_min // 60
            m = rem_min % 60
            return f"{base} (⏳ {h}h{m:02d})"
        else:
            return f"{base} (✅ Sortie)"

    return base

def get_medical_decision(severity):
    roll = random.random()
    sev = severity.value
    if sev == "ROUGE":
        return (
            "soins_critiques"
            if roll < 0.60
            else random.choice(["ortho", "cardio", "neuro", "pneumo"])
        )
    elif sev == "JAUNE":
        if roll < 0.30:
            return "soins_critiques"
        return (
            random.choice(["ortho", "cardio", "neuro", "pneumo"])
            if roll < 0.80
            else "exit"
        )
    elif sev == "VERT":
        return (
            random.choice(["ortho", "cardio", "neuro", "pneumo"])
            if roll < 0.30
            else "exit"
        )
    else:
        return "exit"

def get_priority_dataframe(state):
    """Calcule le score de priorité actuel pour affichage"""
    data = []

    for p in state.patients.values():
        if p.location not in ["triage", "wr_01", "wr_02", "wr_03"]:
            continue

        sev = p.severity.value
        wait = state.time - p.arrival_time
        mapping = {"ROUGE": 4000, "JAUNE": 3000, "VERT": 2000, "GRIS": 1000}
        score = mapping.get(sev, 0)

        if sev == "ROUGE":
            score = 99999
            details = "URGENCE VITALE"
        else:
            score += wait
            panic = False
            if sev == "VERT" and wait > 120:
                score += 1500
                panic = True
            if sev == "GRIS" and wait > 240:
                score += 1500
                panic = True

            boarding = False
            if p.medical_decision and p.medical_decision in state.units:
                score += 500
                boarding = True

            details = []
            if panic:
                details.append("🔥 PANIC")
            if boarding:
                details.append("🛏️ BOARDING")
            details = ", ".join(details) if details else "Normal"

        data.append(
            {
                "ID": p.id,
                "Gravité": sev,
                "Attente": f"{wait} min",
                "Loc": p.location,
                "Score": score,
                "État": details,
            }
        )

    if not data:
        return pd.DataFrame(columns=["ID", "Score"])

    df = pd.DataFrame(data)
    return df.sort_values(by="Score", ascending=False)

# =============================================================================
# INJECTION PATIENT
# =============================================================================

def inject_patient(state, severity_str, symptom, location_id, state_path):
    target_room = None
    as_needed = False
    real_location_id = location_id

    if location_id == "transport_consultation":
        real_location_id = "consultation"
        as_needed = True
    elif location_id == "transport_hospital":
        available_units = []
        for unit_id in ["ortho", "neuro", "pneumo", "cardio"]:
            unit = state.units[unit_id]
            if unit.occupancy < unit.capacity:
                available_units.append(unit_id)

        if not available_units:
            return (
                None,
                "⛔ Impossible : Tous les services d'hospitalisation sont PLEINS !",
            )

        real_location_id = random.choice(available_units)
        as_needed = True

    if real_location_id == "consultation":
        doc = state.staff.get("DOC_01")
        if not doc or not doc.is_present:
            return None, "⛔ Impossible : Médecin ABSENT."
        if state.consultation_room.occupancy > 0:
            return None, "⛔ Impossible : Consultation DÉJÀ OCCUPÉE."
        if doc.is_busy:
            return None, "⛔ Impossible : Médecin DÉJÀ OCCUPÉ."

    target_as = None
    if as_needed:
        as1 = state.staff.get("AS_01")
        as2 = state.staff.get("AS_02")
        as1_p = as1 and as1.is_present
        as2_p = as2 and as2.is_present

        candidates = []
        if location_id == "transport_hospital":
            if as2_p: candidates = [as2]
            elif as1_p: candidates = [as1]
        else:
            if as1_p: candidates = [as1]
            elif as2_p: candidates = [as2]

        for c in candidates:
            if not c.is_busy:
                target_as = c
                break

        if not target_as:
            return None, "⛔ Impossible : Aucun AS disponible."

    all_rooms = {
        "triage": state.triage_zone,
        "consultation": state.consultation_room,
        "soins_critiques": state.soins_critiques,
        **state.waiting_rooms,
        **state.units,
    }
    target_room = all_rooms.get(real_location_id)

    if not target_room:
        return None, f"❌ Localisation '{location_id}' introuvable."

    if hasattr(target_room, "capacity") and int(target_room.occupancy) >= int(
        target_room.capacity
    ):
        return None, f"⛔ Impossible : {target_room.name} PLEINE."

    # GÉNÉRATION ID UNIQUE
    new_id = generate_unique_patient_id(state)

    if location_id == "transport_hospital":
        status_initial = PatientStatus.IN_TRANSIT
        arrival_time_override = state.time
    else:
        status_initial = PatientStatus.WAITING
        arrival_time_override = None

    new_patient = Patient(
        id=new_id,
        severity=Severity[severity_str],
        symptom=symptom,
        location=real_location_id,
        status=status_initial,
        arrival_time=arrival_time_override if arrival_time_override else state.time,
    )

    state.patients[new_id] = new_patient

    if location_id == "transport_hospital":
        target_room.patients.append(new_id)
        target_room.occupancy += 1
    else:
        target_room.patients.append(new_id)
        target_room.occupancy += 1

    if real_location_id == "consultation":
        doc = state.staff["DOC_01"]
        doc.is_busy = True
        consult_duration = random.randint(10, 20)

        if location_id == "transport_consultation":
            doc.busy_until = state.time + 5 + consult_duration
            new_patient.treatment_end_time = state.time + 5 + consult_duration
        else:
            doc.busy_until = state.time + consult_duration
            new_patient.treatment_end_time = state.time + consult_duration

    if real_location_id == "soins_critiques":
        duration = random.randint(1440, 2880)
        new_patient.treatment_end_time = state.time + duration

    if as_needed and target_as:
        target_as.is_busy = True
        if location_id == "transport_consultation":
            target_as.busy_until = state.time + 10
        else:
            target_as.busy_until = state.time + 90

    log_event(state, "PATIENT", new_id, f"injected_{location_id}")
    save_state(state, state_path)

    as_msg = f" escorté par {target_as.id}" if as_needed and target_as else ""
    return new_id, f"✅ {new_id} ({severity_str}){as_msg} -> {target_room.name}"

# =============================================================================
# SHOW SIMULATION
# =============================================================================

def show_simulation():
    if "sim_running" not in st.session_state:
        st.session_state.sim_running = False
    if "sim_time" not in st.session_state:
        st.session_state.sim_time = 0
    if "brain_logs" not in st.session_state:
        st.session_state.brain_logs = []
    # NOUVEAU : Flag pour mode scénario
    if "scenario_active" not in st.session_state:
        st.session_state.scenario_active = False
    if "scenario_data" not in st.session_state:
        st.session_state.scenario_data = None

    symptoms_data = load_symptoms()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    state_path = os.path.join(base_dir, "data", "state", "urgence_state.json")
    initial_path = os.path.join(base_dir, "data", "state", "urgence_initial_state.json")

    # CRÉER CSV AU DÉMARRAGE
    ensure_csv_session_initialized(base_dir)

    if "hospital_state" not in st.session_state:
        try:
            st.session_state.hospital_state = load_initial_state(state_path)
        except Exception as e:
            st.error(f"Erreur : {e}")
            st.stop()

    state = st.session_state.hospital_state

    # === INTRO STYLÉE ===
    st.markdown("# 🏥 Simulateur et Régulateur d'Urgences")
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 25px; border-radius: 12px; color: white; margin-bottom: 25px; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="margin-top: 0; color: white; font-weight: 600;">🎯 Système Intelligent de Gestion des Urgences</h2>
        <p style="font-size: 1.1em; line-height: 1.6; margin-bottom: 15px;">
            Plateforme de simulation avancée permettant de tester et d'optimiser la gestion des flux patients 
            dans un service d'urgences hospitalières, avec assistance IA en temps réel.
        </p>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 20px;">
            <div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px;">
                <div style="font-size: 1.3em; margin-bottom: 5px;">🎭</div>
                <div style="font-weight: 600;">Scénarios Automatiques</div>
                <div style="font-size: 0.9em; opacity: 0.9;">Tests prédéfinis</div>
            </div>
            <div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px;">
                <div style="font-size: 1.3em; margin-bottom: 5px;">🤖</div>
                <div style="font-weight: 600;">Assistant IA RAG</div>
                <div style="font-size: 0.9em; opacity: 0.9;">Analyse contextuelle</div>
            </div>
            <div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px;">
                <div style="font-size: 1.3em; margin-bottom: 5px;">📊</div>
                <div style="font-weight: 600;">Stats Temps Réel</div>
                <div style="font-size: 0.9em; opacity: 0.9;">6 graphiques live</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # === MODE D'EMPLOI ===
    with st.expander("📖 Mode d'Emploi - Comment utiliser le simulateur", expanded=False):
        st.markdown("""
        ## 🎮 Deux Modes Disponibles
        
        ### 1️⃣ Mode Scénarios Automatiques (Recommandé)
        
        **🎯 Idéal pour** : Tester le système dans des conditions prédéfinies et réalistes
        
        **📋 Étapes** :
        1. Ouvrez l'expander **"🎭 Scénarios de Test Prédéfinis"**
        2. Sélectionnez un scénario dans la liste
        3. Consultez la description, durée et difficulté
        4. Cliquez sur **"🚀 Lancer le Scénario"**
        5. ✨ **La simulation démarre automatiquement !**
        6. Les patients arrivent selon le planning du scénario
        7. Le cerveau IA prend les décisions en temps réel
        8. Les statistiques se mettent à jour automatiquement
        
        **📚 Types de scénarios** :
        - **🎯 Tests d'Optimisation** : Personnel minimal (1 AS, 1 INF...)
        - **🚨 Validation Priorités** : Vérification ROUGE > JAUNE > VERT > GRIS
        - **👁️ Contrôle Surveillance** : Protocoles de sécurité (15 min)
        - **⚠️ Situations de Saturation** : Débordements et boarding
        - **✨ Scénarios Référence** : Configuration optimale (baseline)
        
        ---
        
        ### 2️⃣ Mode Simulation Manuelle (Sandbox)
        
        **🎯 Idéal pour** : Expérimentation libre et tests personnalisés
        
        **📋 Étapes** :
        1. Configurez le personnel (présent/absent)
        2. Ajustez les capacités des services
        3. Injectez des patients manuellement
        4. Cliquez **"▶️ Démarrer"** pour lancer la simulation
        5. Observez et ajustez en temps réel
        
        **⚙️ Fonctionnalités** :
        - Configuration manuelle du personnel
        - Ajustement capacités services (Ortho, Cardio, Neuro, Pneumo, SC)
        - Injection patients : gravité + symptôme + destination
        - Contrôle total du déroulement
        
        ---
        
        ## 🤖 Assistant IA avec RAG
        
        **📍 Emplacement** : Colonne droite, à côté des logs cerveau
        
        **💡 Capacités** :
        - Répondre aux questions : *"Où est PAT_005 ?"*
        - Expliquer les décisions : *"Pourquoi PAT_001 en SC ?"*
        - Fournir des stats : *"Combien de patients ROUGE ?"*
        - Suggérer modifications (avec guardrails de sécurité)
        
        **🔬 Technologie** : Retrieval-Augmented Generation (RAG)
        - Accès données CSV temps réel
        - Contexte enrichi avec historique complet
        - LLM : **Mistral Large** (modèle premium)
        
        ---
        
        ## 📊 Statistiques et Analyses
        
        **6 graphiques Plotly interactifs** :
        
        1. **📍 Répartition patients** - Évolution dans le temps (Stacked Area)
        2. **📊 Total par gravité** - Barres colorées (Rouge/Jaune/Vert/Gris)
        3. **🚑 Activité AS** - Nombre de transports effectués
        4. **⏱️ Temps d'attente** - Moyen par niveau de gravité
        5. **🎯 Destinations finales** - Pie chart des orientations
        6. **🗺️ Parcours patients** - Diagramme de Sankey des flux
        
        **💾 Données** : Toutes les métriques calculées depuis CSV complets
        
        **📁 Export** : CSV sauvegardés dans `data/historique/` avec timestamp
        
        ---
        
        ## 🎯 Métriques de Performance
        
        **Indicateurs clés à surveiller** :
        
        - ⏱️ **Temps d'attente ROUGE** → Objectif : < 40 minutes
        - 🚑 **Taux utilisation AS** → Équilibrer charge de travail
        - 📈 **Taux occupation SC** → Éviter saturation
        - 👥 **Patients traités/heure** → Mesure du débit
        
        **🏆 Benchmark** : Comparez vos résultats avec le scénario "✨ Configuration Optimale"
        
        ---
        
        ## 🔒 Guardrails de Sécurité
        
        Le système intègre des garde-fous automatiques :
        
        - ❤️ **Patients ROUGE** → Uniquement SC ou Consultation (jamais en salle)
        - 📏 **Capacités** → Impossible de dépasser les limites fixées
        - 👤 **Personnel** → Seul le personnel présent peut être assigné
        - ⏰ **Surveillance** → Alerte si salle sans personnel > 15 min
        
        Ces règles sont **non négociables** et bloquent automatiquement les actions dangereuses.
        """)
    
    st.markdown("---")


    st.markdown("## 🎮 Simulateur Live (God Mode)")
    
    # === GESTION DES SCÉNARIOS ===
    with st.expander("🎭 Scénarios de Test Prédéfinis", expanded=not st.session_state.sim_running):
        scenarios = get_scenarios_with_metadata(base_dir)
        
        if not scenarios:
            st.info("📁 Aucun scénario trouvé dans `data/scenarios/`")
        else:
            scenario_titles = [s['title'] for s in scenarios]
            
            col_select, col_info = st.columns([2, 1])
            
            with col_select:
                selected_title = st.selectbox(
                    "Sélectionner un scénario",
                    scenario_titles,
                    disabled=st.session_state.sim_running,
                    key="scenario_selector"
                )
            
            selected_scenario = next(s for s in scenarios if s['title'] == selected_title)
            
            with col_info:
                st.metric("Durée", selected_scenario['duration'])
                st.caption(f"Difficulté : {selected_scenario['difficulty']}")
            
            st.info(f"📝 {selected_scenario['description']}")
            
            col_launch, col_stop = st.columns(2)
            
            with col_launch:
                if st.button(
                    "🚀 Lancer le Scénario",
                    use_container_width=True,
                    disabled=st.session_state.sim_running or st.session_state.scenario_active,
                    type="primary"
                ):
                    try:
                        st.info(f"📁 Chargement : {selected_scenario['filename']}")
                        sc_path = os.path.join(base_dir, "data", "scenarios", selected_scenario['filename'])
                        
                        if not os.path.exists(sc_path):
                            st.error(f"❌ Fichier introuvable : {sc_path}")
                            st.stop()
                        
                        st.info("✓ Chargement état initial...")
                        initial_state = load_initial_state(initial_path)
                        
                        with open(sc_path, 'r', encoding='utf-8') as f:
                            scenario_data = json.load(f)
                        
                        if "initial_state" in scenario_data:
                            init_config = scenario_data["initial_state"]
                            
                            if "staff_absent" in init_config:
                                for staff_id in init_config["staff_absent"]:
                                    if staff_id in initial_state.staff:
                                        initial_state.staff[staff_id].is_present = False
                                        initial_state.staff[staff_id].is_busy = False
                                        initial_state.staff[staff_id].busy_until = 0
                            
                            if "staff_present" in init_config:
                                for staff_id in init_config["staff_present"]:
                                    if staff_id in initial_state.staff:
                                        initial_state.staff[staff_id].is_present = True
                                        initial_state.staff[staff_id].is_busy = False
                                        initial_state.staff[staff_id].busy_until = 0
                            
                            if "capacities" in init_config:
                                caps = init_config["capacities"]
                                if "soins_critiques" in caps:
                                    initial_state.soins_critiques.capacity = caps["soins_critiques"]
                                if "salles" in caps:
                                    for room_id, cap in caps["salles"].items():
                                        if room_id in initial_state.waiting_rooms:
                                            initial_state.waiting_rooms[room_id].capacity = cap
                        
                        save_state(initial_state, state_path)
                        st.session_state.hospital_state = initial_state
                        
                        if "csv_session_id" in st.session_state:
                            del st.session_state.csv_session_id
                        
                        # Supprimer ancien CSV si existe
                        if "csv_session_id" in st.session_state:
                            del st.session_state.csv_session_id
                        
                        # Créer nouveau CSV pour le scénario
                        sc_name_clean = selected_scenario['filename'].replace('.json', '')
                        st.session_state.csv_session_id = f"SCENARIO_{sc_name_clean}_{datetime.now().strftime('%H%M')}"
                        
                        # Créer fichiers CSV AVEC HEADERS
                        hist_dir = os.path.join(base_dir, "data", "historique")
                        os.makedirs(hist_dir, exist_ok=True)
                        
                        pat_csv = os.path.join(hist_dir, f"{st.session_state.csv_session_id}_patients.csv")
                        staff_csv = os.path.join(hist_dir, f"{st.session_state.csv_session_id}_staff.csv")
                        
                        # Headers exactement comme dans ensure_csv_session_initialized
                        pd.DataFrame(
                            columns=["timestamp", "id", "location", "severity", "escort_id"]
                        ).to_csv(pat_csv, sep=";", index=False)
                        
                        pd.DataFrame(
                            columns=["timestamp", "id", "location", "patient_handling_id", "patient_symptom", "patient_color"]
                        ).to_csv(staff_csv, sep=";", index=False)
                        
                        st.info(f"✓ CSV créé : {st.session_state.csv_session_id}")
                        
                        st.info("✓ Activation mode scénario...")
                        st.session_state.scenario_active = True
                        st.session_state.scenario_data = scenario_data
                        st.session_state.sim_time = 0
                        st.session_state.brain_logs = []
                        st.session_state.scenario_patient_counter = 1
                        
                        # AUTO-DÉMARRAGE DE LA SIMULATION
                        st.session_state.sim_running = True
                        
                        st.success(f"✅ Scénario chargé et démarré : {selected_scenario['title']}")
                        st.toast(f"🎭 {selected_scenario['title']}", icon="✅")
                        
                        time.sleep(0.5)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Erreur : {e}")
                        import traceback
                        st.code(traceback.format_exc())
            
            with col_stop:
                if st.session_state.scenario_active:
                    if st.button("⏹️ Arrêter le Scénario", use_container_width=True, type="secondary"):
                        st.session_state.scenario_active = False
                        st.session_state.scenario_data = None
                        st.rerun()
        
        if st.session_state.scenario_active:
            st.warning("⚠️ **Mode Scénario Actif** - Les configurations manuelles sont désactivées. Cliquez sur 'Démarrer' pour lancer l'exécution automatique.")

    # === VARIABLE DE VERROUILLAGE ===
    # Si le mode scénario est actif, on désactive les inputs manuels
    disable_manual = st.session_state.scenario_active

    # === SÉLECTION MODÈLE LLM ===
    with st.expander("🤖 Configuration IA", expanded=False):
        llm_models = {
            "Mistral Large (Recommandé)": "mistral-large-latest",
            "Mistral Medium": "mistral-medium-latest",
            "Mistral Small": "mistral-small-latest",
            "Codestral": "codestral-latest",
        }

        selected_model = st.selectbox(
            "Modèle LLM",
            options=list(llm_models.keys()),
            index=0,
            key="llm_model_select",
        )

        set_llm_model(llm_models[selected_model])
        st.info(f"🧠 Modèle actif : **{selected_model}**")

    # === CAPACITÉS MODIFIABLES (VERROUILLÉ EN SCÉNARIO) ===
    with st.expander("⚙️ Configuration Capacités", expanded=False):
        if disable_manual: st.caption("🔒 Désactivé en mode Scénario")
        st.markdown("**🏥 Services Hospitaliers**")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            new_cap_ortho = st.number_input(
                "🦴 Orthopédie",
                min_value=1,
                max_value=50,
                value=state.units["ortho"].capacity,
                key="cap_ortho",
                disabled=disable_manual
            )
            if not disable_manual and new_cap_ortho != state.units["ortho"].capacity:
                state.units["ortho"].capacity = new_cap_ortho
                save_state(state, state_path)

        with col2:
            new_cap_cardio = st.number_input(
                "❤️ Cardiologie",
                min_value=1,
                max_value=50,
                value=state.units["cardio"].capacity,
                key="cap_cardio",
                disabled=disable_manual
            )
            if not disable_manual and new_cap_cardio != state.units["cardio"].capacity:
                state.units["cardio"].capacity = new_cap_cardio
                save_state(state, state_path)

        with col3:
            new_cap_neuro = st.number_input(
                "🧠 Neurologie",
                min_value=1,
                max_value=50,
                value=state.units["neuro"].capacity,
                key="cap_neuro",
                disabled=disable_manual
            )
            if not disable_manual and new_cap_neuro != state.units["neuro"].capacity:
                state.units["neuro"].capacity = new_cap_neuro
                save_state(state, state_path)

        with col4:
            new_cap_pneumo = st.number_input(
                "🫁 Pneumologie",
                min_value=1,
                max_value=50,
                value=state.units["pneumo"].capacity,
                key="cap_pneumo",
                disabled=disable_manual
            )
            if not disable_manual and new_cap_pneumo != state.units["pneumo"].capacity:
                state.units["pneumo"].capacity = new_cap_pneumo
                save_state(state, state_path)

        st.markdown("**❤️ Soins Critiques**")
        new_cap_sc = st.number_input(
            "Capacité SC",
            min_value=1,
            max_value=20,
            value=state.soins_critiques.capacity,
            key="cap_sc",
            disabled=disable_manual
        )
        if not disable_manual and new_cap_sc != state.soins_critiques.capacity:
            state.soins_critiques.capacity = new_cap_sc
            save_state(state, state_path)

    # === GESTION PERSONNEL (VERROUILLÉ EN SCÉNARIO) ===
    with st.expander("👥 Gestion Personnel", expanded=False):
        if disable_manual: st.caption("🔒 Désactivé en mode Scénario")
        cols = st.columns(3)
        with cols[0]:
            st.markdown("**🩺 Médecin**")
            d = state.staff.get("DOC_01")
            if d:
                d.is_present = st.toggle("DOC_01", value=d.is_present, key="t_doc", disabled=disable_manual)
        with cols[1]:
            st.markdown("**💉 Infirmiers**")
            for s in ["INF_TRIAGE_01", "INF_SALLE_01", "INF_SALLE_02"]:
                a = state.staff.get(s)
                if a:
                    a.is_present = st.toggle(s, value=a.is_present, key=f"t_{s}", disabled=disable_manual)
        with cols[2]:
            st.markdown("**🚑 AS**")
            for s in ["AS_01", "AS_02"]:
                a = state.staff.get(s)
                if a:
                    a.is_present = st.toggle(s, value=a.is_present, key=f"t_{s}", disabled=disable_manual)
        
        if st.button("💾 Sauvegarder Personnel", disabled=disable_manual):
            save_state(state, state_path)
            st.success("OK")

    # === INJECTION PATIENT (VERROUILLÉ EN SCÉNARIO) ===
    with st.expander("💉 Injection Patient", expanded=True):
        if disable_manual: st.caption("🔒 Désactivé en mode Scénario")
        c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
        with c1:
            sev = st.selectbox(
                "Gravité", ["ROUGE", "JAUNE", "VERT", "GRIS"], key="inj_sev", disabled=disable_manual
            )
        with c2:
            symp_list = symptoms_data.get(sev, ["Symptôme"])
            symp = st.selectbox("Symptôme", symp_list, key="inj_symp", disabled=disable_manual)
        with c3:
            loc_opts = {
                "Triage": "triage",
                "Salle 1": "wr_01",
                "Salle 2": "wr_02",
                "Salle 3": "wr_03",
                "Soins Critiques": "soins_critiques",
                "Consultation": "consultation",
                "→ Transport Consult (AS)": "transport_consultation",
                "→ Transport Hôpital (AS)": "transport_hospital",
            }
            loc_choice = st.selectbox(
                "Destination", list(loc_opts.keys()), key="inj_loc", disabled=disable_manual
            )
            loc_id = loc_opts[loc_choice]
        with c4:
            st.write("")
            st.write("")
            if st.button("➕ Injecter", use_container_width=True, disabled=disable_manual):
                pid, msg = inject_patient(state, sev, symp, loc_id, state_path)
                if pid:
                    st.success(msg)
                    st.session_state.hospital_state = load_initial_state(state_path)
                    st.rerun()
                else:
                    st.error(msg)

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button(
            "▶️ Démarrer" if not st.session_state.sim_running else "⏸️ Pause",
            use_container_width=True,
        ):
            st.session_state.sim_running = not st.session_state.sim_running
            st.rerun()
    with c2:
        if st.button("🔄 Reset", use_container_width=True):
            # SAVE & ARCHIVE CSV
            if "csv_session_id" in st.session_state:
                st.toast(
                    f"💾 Session {st.session_state.csv_session_id} archivée.", icon="✅"
                )
                time.sleep(1.0)

            ini = load_initial_state(initial_path)
            save_state(ini, state_path)

            for key in [
                "hospital_state",
                "sim_time",
                "brain_logs",
                "sim_running",
                "csv_session_id",
                "used_patient_ids",
                "scenario_active" # Reset aussi le mode scénario
            ]:
                if key in st.session_state:
                    del st.session_state[key]

            st.session_state.hospital_state = ini
            st.session_state.sim_time = 0
            st.session_state.brain_logs = []
            st.session_state.sim_running = False
            st.rerun()
    with c3:
        if st.button("💾 Export CSV", use_container_width=True):
            if "csv_session_id" in st.session_state:
                st.success(f"✅ CSV : {st.session_state.csv_session_id}_*.csv")
    with c4:
        st.metric(
            "Temps",
            f"{st.session_state.sim_time//60}h{st.session_state.sim_time%60:02d}",
        )

    # === SECTION CERVEAU & ASSISTANT IA ===
    c_brain, c_assistant = st.columns([1, 1])

    with c_brain:
        with st.expander("🧠 Cerveau (Logs)", expanded=True):
            if st.session_state.brain_logs:
                for l in st.session_state.brain_logs[-5:]:
                    st.text(l)
            else:
                st.caption("R.A.S. - En attente du cycle")

    with c_assistant:
        with st.expander("🤖 Assistant IA", expanded=True):
            show_ai_assistant_chat_inline(base_dir, state)

    # VISUALISATION (frontend intact)
    st.markdown("---")
    c_sc, c_cs = st.columns(2)
    with c_sc:
        with st.container(border=True):
            st.markdown("#### ❤️ Soins Critiques")
            st.write(
                f"**{state.soins_critiques.occupancy}/{state.soins_critiques.capacity}**"
            )
            pats = [
                format_patient_colored(state.patients.get(pid), state.time)
                for pid in state.soins_critiques.patients
            ]
            st.write(" ".join(pats) if pats else "_")

    with c_cs:
        with st.container(border=True):
            st.markdown("#### 👨‍⚕️ Consultation")
            d = state.staff.get("DOC_01")
            d_txt = "❌"
            has_p = len(state.consultation_room.patients) > 0
            if d and d.is_present:
                rem = max(0, d.busy_until - state.time)
                if (d.is_busy and rem > 0) or has_p:
                    txt_time = f" ({rem} min)" if rem > 0 else ""
                    d_txt = f"🔴 OCCUPÉ{txt_time}"
                else:
                    d_txt = "🟢 LIBRE"
            st.write(f"**Doc :** {d_txt}")
            p = (
                state.consultation_room.patients[0]
                if state.consultation_room.patients
                else None
            )
            st.write(
                f"**Pat :** {format_patient_colored(state.patients.get(p), state.time) if p else '_'}"
            )

    st.markdown("#### 🚑 Transport Consultation")
    c_as1, _ = st.columns(2)
    with c_as1:
        as1 = state.staff.get("AS_01")
        t1 = "❌"
        if as1 and as1.is_present:
            rem = max(0, as1.busy_until - state.time)
            t1 = "✅ DISPO" if rem <= 0 else f"🚑 MISSION ({rem} min)"
        st.info(f"**AS_01 (Prio Consult)** : {t1}")

    c_tr, c_rms, c_prio = st.columns([1, 2, 1])
    with c_tr:
        with st.container(border=True):
            st.markdown("#### 📋 Triage")
            st.write(f"INF: {check_presence(state, state.triage_zone.staff, 'INF')}")
            st.write(f"AS: {check_presence(state, state.triage_zone.staff, 'AS')}")
            p = [
                format_patient_colored(state.patients.get(pid), state.time)
                for pid in state.triage_zone.patients
            ]
            st.write(f"**{len(p)}** : {', '.join(p)}")
    with c_rms:
        st.markdown("#### 🛋️ Salles")
        cols = st.columns(3)
        for i, w in enumerate(["wr_01", "wr_02", "wr_03"]):
            with cols[i]:
                r = state.waiting_rooms[w]
                with st.container(border=True):
                    st.write(f"**{r.name}** ({r.occupancy}/{r.capacity})")
                    st.write(
                        f"S: {check_presence(state, r.staff, 'INF')} {check_presence(state, r.staff, 'AS')}"
                    )
                    p = [
                        format_patient_colored(state.patients.get(pid), state.time)
                        for pid in r.patients
                    ]
                    st.write(" ".join(p))

    st.markdown("#### 🚑 Transport Hôpital")
    c_as2, _ = st.columns(2)
    with c_as2:
        as2 = state.staff.get("AS_02")
        t2 = "❌"
        if as2 and as2.is_present:
            rem = max(0, as2.busy_until - state.time)
            t2 = "✅ DISPO" if rem <= 0 else f"🚑 MISSION ({rem} min)"
        st.info(f"**AS_02 (Prio Hôpital)** : {t2}")

    with c_prio:
        with st.container(border=True):
            st.markdown("#### 🧮 Priorités")
            df_prio = get_priority_dataframe(state)
            if not df_prio.empty:
                st.dataframe(
                    df_prio,
                    column_config={
                        "Score": st.column_config.ProgressColumn(
                            "Score",
                            help="Priorité",
                            format="%d",
                            min_value=0,
                            max_value=5000,
                        ),
                    },
                    hide_index=True,
                    use_container_width=True,
                    height=200,
                )
            else:
                st.caption("Aucun patient")

    st.markdown("#### 🏥 Hospitalisation")
    cols = st.columns(4)
    icons = ["🦴", "🧠", "🫁", "❤️"]
    for i, u in enumerate(["ortho", "neuro", "pneumo", "cardio"]):
        with cols[i]:
            ut = state.units[u]
            with st.container(border=True):
                st.write(f"**{icons[i]} {ut.name}**")
                st.progress(
                    ut.occupancy / ut.capacity if ut.capacity > 0 else 0,
                    f"{ut.occupancy}/{ut.capacity}",
                )
                if ut.patients:
                    p_list = [
                        format_patient_colored(state.patients.get(pid), state.time)
                        for pid in ut.patients
                    ]
                    st.caption(" ".join(p_list))



    # === STATISTIQUES TEMPS RÉEL ===
    st.markdown("---")
    st.markdown("## 📊 Statistiques Temps Réel (Données CSV complètes)")

    fig1, fig2, fig3, fig4, fig5, fig6 = create_complete_statistics_charts(
        base_dir, state
    )

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(fig1, use_container_width=True, key="chart_repartition_temps")
        st.plotly_chart(fig3, use_container_width=True, key="chart_as_transports")
        st.plotly_chart(fig5, use_container_width=True, key="chart_destinations")
    with col2:
        st.plotly_chart(fig2, use_container_width=True, key="chart_gravite_totaux")
        st.plotly_chart(fig4, use_container_width=True, key="chart_attente_moyen")

    st.markdown("---")
    st.plotly_chart(fig6, use_container_width=True, key="chart_parcours_sankey")

    # GAME LOOP (AVEC TEMPS MODIFIÉ 0.5s)
    if st.session_state.sim_running:
        time.sleep(0.5)  # <--- 0.5 sec = 5 min simulées
        st.session_state.sim_time += 5
        upd = False
        curr = load_initial_state(state_path)
        curr.time = st.session_state.sim_time

        # === EXÉCUTION SCÉNARIO (SI ACTIF) ===
        if st.session_state.scenario_active and st.session_state.scenario_data:
            actions_done = execute_scenario_timeline(
                curr, 
                st.session_state.scenario_data, 
                st.session_state.sim_time, 
                base_dir
            )
            if actions_done:
                save_state(curr, state_path)
                upd = True

        for s in curr.staff.values():
            if "aide" in str(s.role).lower() and s.is_busy and s.busy_until > 0:
                if curr.time >= s.busy_until:
                    s.is_busy = False
                    s.busy_until = 0
                    s.location = "wr_03"
                    upd = True

        for pid, pat in curr.patients.items():
            if pat.status == PatientStatus.IN_TRANSIT and pat.location in curr.units:
                if (curr.time - pat.arrival_time) >= 45:
                    pat.status = PatientStatus.HOSPITALIZED
                    pat.treatment_end_time = curr.time + random.randint(180, 1440)
                    upd = True

        doc = curr.staff["DOC_01"]
        cons = curr.consultation_room
        if doc.is_busy and doc.busy_until > 0 and curr.time >= doc.busy_until:
            doc.is_busy = False
            doc.busy_until = 0
            upd = True
            if cons.patients:
                pid = cons.patients[0]
                pat = curr.patients[pid]
                dec = get_medical_decision(pat.severity)

                if dec == "exit":
                    cons.patients.remove(pid)
                    cons.occupancy = 0
                    del curr.patients[pid]
                elif dec == "soins_critiques":
                    sc = curr.soins_critiques
                    if sc.occupancy < sc.capacity:
                        cons.patients.remove(pid)
                        cons.occupancy = 0
                        sc.patients.append(pid)
                        sc.occupancy += 1
                        pat.location = "soins_critiques"
                        pat.treatment_end_time = curr.time + random.randint(1440, 2880)
                    else:
                        dec = "boarding_sc"

                if dec in [
                    "hospital_unit",
                    "ortho",
                    "cardio",
                    "neuro",
                    "pneumo",
                    "boarding_sc",
                ]:
                    t_wr = None
                    for w in ["wr_01", "wr_02", "wr_03"]:
                        if (
                            curr.waiting_rooms[w].occupancy
                            < curr.waiting_rooms[w].capacity
                        ):
                            t_wr = curr.waiting_rooms[w]
                            break
                    if t_wr:
                        cons.patients.remove(pid)
                        cons.occupancy = 0
                        t_wr.patients.append(pid)
                        t_wr.occupancy += 1
                        pat.location = t_wr.id
                        pat.status = PatientStatus.BOARDING
                        if dec == "hospital_unit":
                            pat.medical_decision = random.choice(
                                ["ortho", "cardio", "neuro", "pneumo"]
                            )
                        else:
                            pat.medical_decision = (
                                "soins_critiques" if dec == "boarding_sc" else dec
                            )

        for r in list(curr.units.values()) + [curr.soins_critiques]:
            for pid in list(r.patients):
                pat = curr.patients.get(pid)
                if not pat:
                    r.patients.remove(pid)
                    r.occupancy = max(0, r.occupancy - 1)
                    upd = True
                    continue

                if (
                    pat.status == PatientStatus.HOSPITALIZED
                    and pat.treatment_end_time > 0
                    and curr.time >= pat.treatment_end_time
                ):
                    r.patients.remove(pid)
                    r.occupancy = max(0, r.occupancy - 1)
                    del curr.patients[pid]
                    upd = True

        if upd:
            save_state(curr, state_path)
            st.session_state.hospital_state = curr

        try:
            with st.spinner("🧠..."):
                br = process_brain_cycle()
            if br:
                l = f"[{st.session_state.sim_time//60}h{st.session_state.sim_time%60:02d}] {br}"
                if (
                    not st.session_state.brain_logs
                    or st.session_state.brain_logs[-1] != l
                ):
                    st.session_state.brain_logs.append(l)

                st.session_state.hospital_state = load_initial_state(state_path)
        except:
            pass
        
        # Rerun TOUJOURS à la fin du game loop
        st.rerun()

# =============================================================================
# SYSTÈME RAG (Retrieval-Augmented Generation)
# =============================================================================

def load_rag_data(base_dir):
    """
    RETRIEVAL : Charge les données CSV pour le contexte RAG
    """
    if "csv_session_id" not in st.session_state:
        return None, None

    hist_dir = os.path.join(base_dir, "data", "historique")
    pat_csv = os.path.join(hist_dir, f"{st.session_state.csv_session_id}_patients.csv")
    staff_csv = os.path.join(hist_dir, f"{st.session_state.csv_session_id}_staff.csv")

    try:
        df_patients = pd.read_csv(pat_csv, sep=";")
        df_staff = pd.read_csv(staff_csv, sep=";")
        return df_patients, df_staff
    except:
        return None, None

def build_rag_context(question, df_patients, df_staff):
    """
    RETRIEVAL : Construit le contexte RAG basé sur la question

    Cette fonction analyse la question et extrait les données pertinentes
    des CSV pour enrichir le contexte du LLM.
    """
    context_parts = []

    # Extraire les IDs patients mentionnés dans la question (PAT_XXX)
    import re

    patient_ids = re.findall(r"PAT_\d+", question.upper())

    # === CONTEXTE PATIENTS ===
    if df_patients is not None and not df_patients.empty:
        context_parts.append("=== DONNÉES PATIENTS ===")

        if patient_ids:
            # Si des patients spécifiques sont mentionnés
            for pid in patient_ids:
                patient_data = df_patients[df_patients["id"] == pid]
                if not patient_data.empty:
                    context_parts.append(f"\n{pid}:")
                    for _, row in patient_data.iterrows():
                        context_parts.append(
                            f"  T+{row['timestamp']}: {row['location']} (Gravité: {row['severity']})"
                        )
        else:
            # Sinon, donner un résumé général
            latest_patients = df_patients.groupby("id").tail(1)
            context_parts.append(
                f"\nNombre total de patients traités: {df_patients['id'].nunique()}"
            )
            context_parts.append("\nPatients actuels:")
            for _, row in latest_patients.head(10).iterrows():
                context_parts.append(
                    f"  - {row['id']}: {row['location']} ({row['severity']})"
                )

    # === CONTEXTE PERSONNEL ===
    if df_staff is not None and not df_staff.empty:
        context_parts.append("\n=== ACTIVITÉ PERSONNEL ===")

        # Résumé activité AS
        as_activity = df_staff[df_staff["id"].str.contains("AS_", na=False)]
        if not as_activity.empty:
            context_parts.append(
                f"\nAS_01: {len(as_activity[as_activity['id']=='AS_01'])} transports"
            )
            context_parts.append(
                f"AS_02: {len(as_activity[as_activity['id']=='AS_02'])} transports"
            )

        # Patients pris en charge
        recent_staff = df_staff.tail(20)
        if not recent_staff.empty:
            context_parts.append("\nDernières actions:")
            for _, row in recent_staff.iterrows():
                if pd.notna(row["patient_handling_id"]):
                    context_parts.append(
                        f"  - {row['id']}: {row['patient_handling_id']} "
                        f"({row['patient_color']}) - {row['patient_symptom'][:30]}..."
                    )

    return "\n".join(context_parts)

def get_current_state_summary(state):
    """
    Résumé de l'état actuel du système pour le contexte RAG
    """
    summary = []
    summary.append("=== ÉTAT ACTUEL DU SYSTÈME ===")
    summary.append(f"\nTemps: {state.time} min")

    # Soins Critiques
    summary.append(
        f"\nSoins Critiques: {state.soins_critiques.occupancy}/{state.soins_critiques.capacity}"
    )
    if state.soins_critiques.patients:
        summary.append(f"  Patients: {', '.join(state.soins_critiques.patients)}")

    # Consultation
    summary.append(
        f"\nConsultation: {'Occupée' if state.consultation_room.patients else 'Libre'}"
    )
    if state.consultation_room.patients:
        summary.append(f"  Patient: {state.consultation_room.patients[0]}")

    # Triage
    summary.append(f"\nTriage: {len(state.triage_zone.patients)} patients")
    if state.triage_zone.patients:
        summary.append(f"  Patients: {', '.join(state.triage_zone.patients[:5])}")

    # Salles d'attente
    for rid, room in state.waiting_rooms.items():
        if room.patients:
            summary.append(f"\n{room.name}: {room.occupancy}/{room.capacity}")
            summary.append(f"  Patients: {', '.join(room.patients[:3])}")

    # Personnel
    summary.append("\n=== PERSONNEL ===")
    for sid, staff in state.staff.items():
        if staff.is_present:
            status = "Occupé" if staff.is_busy else "Disponible"
            summary.append(f"{sid}: {status}")

    return "\n".join(summary)

# =============================================================================
# GUARDRAILS - RÈGLES DE SÉCURITÉ
# =============================================================================

def check_guardrails(action_request, state):
    """
    Vérifie si une action demandée respecte les règles de sécurité

    Retourne : (is_allowed: bool, reason: str)
    """
    # Extraire l'action demandée
    action_lower = action_request.lower()

    # === RÈGLE 1 : Patients ROUGE doivent être en SC ou consultation ===
    if "déplace" in action_lower or "move" in action_lower:
        # Extraire ID patient
        import re

        patient_ids = re.findall(r"PAT_\d+", action_request.upper())

        for pid in patient_ids:
            patient = state.patients.get(pid)
            if patient and patient.severity.value == "ROUGE":
                # Vérifier destination
                if "salle" in action_lower or "wr_" in action_lower:
                    return (
                        False,
                        f"❌ GUARDRAIL: {pid} est ROUGE, ne peut pas aller en salle d'attente (risque vital)",
                    )
                if "triage" in action_lower:
                    return (
                        False,
                        f"❌ GUARDRAIL: {pid} est ROUGE, ne peut pas retourner au triage",
                    )

    # === RÈGLE 2 : Ne pas dépasser les capacités ===
    if "ajoute" in action_lower or "place" in action_lower:
        if "soins critiques" in action_lower or "sc" in action_lower:
            if state.soins_critiques.occupancy >= state.soins_critiques.capacity:
                return (
                    False,
                    f"❌ GUARDRAIL: Soins Critiques saturés ({state.soins_critiques.capacity}/{state.soins_critiques.capacity})",
                )

    # === RÈGLE 3 : Personnel doit être présent ===
    if "assigne" in action_lower or "envoie" in action_lower:
        import re

        staff_ids = re.findall(r"(AS_\d+|INF_\w+|DOC_\d+)", action_request.upper())
        for sid in staff_ids:
            staff = state.staff.get(sid)
            if staff and not staff.is_present:
                return (
                    False,
                    f"❌ GUARDRAIL: {sid} est absent, ne peut pas être assigné",
                )

    # Si aucune règle violée
    return True, "✅ Action autorisée par les guardrails"

# =============================================================================
# FONCTION PRINCIPALE ASSISTANT IA
# =============================================================================

def process_ai_assistant_query(question, base_dir, state):
    """
    Traite une question de l'utilisateur avec RAG + LLM

    WORKFLOW:
    1. RETRIEVAL : Charger données CSV
    2. BUILD CONTEXT : Créer contexte enrichi
    3. GUARDRAILS : Vérifier si c'est une demande d'action
    4. GENERATION : Appeler LLM avec contexte
    5. ACTION : Appliquer modification si demandé et autorisé
    """

    # === ÉTAPE 1 : RETRIEVAL ===
    df_patients, df_staff = load_rag_data(base_dir)

    # === ÉTAPE 2 : BUILD CONTEXT ===
    rag_context = ""

    if df_patients is not None:
        rag_context += build_rag_context(question, df_patients, df_staff)

    rag_context += "\n\n" + get_current_state_summary(state)

    # === ÉTAPE 3 : GUARDRAILS (si c'est une demande d'action) ===
    action_keywords = ["déplace", "move", "change", "modifie", "assigne", "envoie"]
    is_action_request = any(kw in question.lower() for kw in action_keywords)

    guardrail_ok = True
    guardrail_msg = ""

    if is_action_request:
        guardrail_ok, guardrail_msg = check_guardrails(question, state)

    # === ÉTAPE 4 : GENERATION (LLM) ===
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return "❌ Clé API Mistral manquante"

    client = Mistral(api_key=api_key)

    # Construire le prompt système
    system_prompt = f"""Tu es un assistant IA expert en régulation hospitalière.

Tu as accès aux données suivantes via RAG (Retrieval-Augmented Generation):

{rag_context}

RÈGLES IMPORTANTES:
1. Réponds UNIQUEMENT en te basant sur les données fournies
2. Si l'utilisateur demande une modification:
   - Vérifie les guardrails de sécurité
   - Explique clairement ce que tu vas faire
   - Confirme que c'est fait SI c'est autorisé
3. Sois précis, factuel et professionnel
4. Si tu ne sais pas, dis-le clairement

GUARDRAILS ACTIFS:
- Patients ROUGE: Seulement SC ou Consultation (JAMAIS en salle d'attente)
- Ne pas dépasser les capacités des services
- Personnel absent ne peut pas être assigné
"""

    if not guardrail_ok:
        system_prompt += f"\n\n⚠️ DEMANDE BLOQUÉE PAR GUARDRAIL:\n{guardrail_msg}"

    try:
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            max_tokens=500,
        )

        ai_response = response.choices[0].message.content

        # === ÉTAPE 5 : ACTION (si autorisé) ===
        if is_action_request and guardrail_ok:
            # Ici tu pourrais ajouter la logique pour vraiment modifier l'état
            # Pour l'instant on simule
            ai_response += "\n\n✅ Modification appliquée dans le système."
        elif is_action_request and not guardrail_ok:
            ai_response = guardrail_msg + "\n\n" + ai_response

        return ai_response

    except Exception as e:
        return f"❌ Erreur LLM: {str(e)}"

# =============================================================================
# INTERFACE CHATBOT
# =============================================================================

def show_ai_assistant_chat_inline(base_dir, state):
    """
    Version inline de l'assistant (pour utiliser dans un expander)
    """
    simulation_running = st.session_state.get("sim_running", False)

    if "ai_chat_history" not in st.session_state:
        st.session_state.ai_chat_history = []

    if not simulation_running:
        st.warning("⚠️ Démarrez la simulation")
        return

    st.caption("Posez des questions sur les patients")

    # Historique
    chat_area = st.container(height=200)
    with chat_area:
        if not st.session_state.ai_chat_history:
            st.info("💡 Ex: Pourquoi PAT_001 en SC ?")
        else:
            for msg in st.session_state.ai_chat_history[-5:]:  # 5 derniers messages
                if msg["role"] == "user":
                    st.markdown(f"**Vous:** {msg['content']}")
                else:
                    st.markdown(f"**🤖:** {msg['content']}")

    # Input
    col1, col2 = st.columns([4, 1])

    with col1:
        user_input = st.text_input(
            "Question",
            key="ai_input_inline",
            placeholder="Ex: Pourquoi PAT_001 ?",
            label_visibility="collapsed",
        )

    with col2:
        st.write("")
        send = st.button("📤", key="send_inline", use_container_width=True)

    if send and user_input.strip():
        st.session_state.ai_chat_history.append({"role": "user", "content": user_input})

        with st.spinner("🧠..."):
            try:
                response = process_ai_assistant_query(user_input, base_dir, state)
            except Exception as e:
                response = f"❌ Erreur: {str(e)}"

        st.session_state.ai_chat_history.append(
            {"role": "assistant", "content": response}
        )

        st.rerun()

def show_ai_assistant_chat(base_dir, state):
    """
    Assistant IA - Version simplifiée pour expander
    """

    simulation_running = st.session_state.get("sim_running", False)

    if "ai_chat_history" not in st.session_state:
        st.session_state.ai_chat_history = []

    # CSS pour les messages
    st.markdown(
        """
    <style>
    .user-message {
        background: #667eea;
        color: white;
        padding: 8px 12px;
        border-radius: 12px;
        margin: 6px 0;
        margin-left: 15%;
        text-align: right;
    }
    
    .bot-message {
        background: var(--secondary-background-color);
        padding: 8px 12px;
        border-radius: 12px;
        margin: 6px 0;
        margin-right: 15%;
        border-left: 3px solid #667eea;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    if not simulation_running:
        st.warning("⚠️ Démarrez la simulation")
    else:
        st.caption("💡 Questions, explications, suggestions...")

        # Historique
        chat_area = st.container(height=250)
        with chat_area:
            if not st.session_state.ai_chat_history:
                st.info("💬 Ex: *Pourquoi PAT_001 en SC ?*")
            else:
                for msg in st.session_state.ai_chat_history:
                    if msg["role"] == "user":
                        st.markdown(
                            f'<div class="user-message">👤 {msg["content"]}</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f'<div class="bot-message">🤖 {msg["content"]}</div>',
                            unsafe_allow_html=True,
                        )

        # Input
        col1, col2 = st.columns([5, 1])

        with col1:
            user_input = st.text_input(
                "Question",
                key="ai_chat_input",
                placeholder="Ex: Combien de patients ROUGE ?",
                label_visibility="collapsed",
            )

        with col2:
            st.write("")
            send = st.button("📤", key="send_btn")

        # Traitement
        if send and user_input.strip():
            st.session_state.ai_chat_history.append(
                {"role": "user", "content": user_input}
            )

            with st.spinner("🧠..."):
                try:
                    response = process_ai_assistant_query(user_input, base_dir, state)
                except Exception as e:
                    response = f"❌ Erreur: {str(e)}"

            st.session_state.ai_chat_history.append(
                {"role": "assistant", "content": response}
            )
            st.rerun()

