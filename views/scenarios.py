"""
Module de scénarios de test - VERSION COMPLÈTE
Interface IDENTIQUE à simulation.py + Enregistrement CSV + Stats complètes
"""

import streamlit as st
import json
import os
import time
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.models import Patient, Severity, PatientStatus
from src.utils import load_initial_state, save_state
from src.logger import log_event
from src.ai_brain import process_brain_cycle, set_llm_model
import random


# =============================================================================
# SESSION CSV - CRÉER AU DÉMARRAGE
# =============================================================================

def ensure_csv_session_initialized(base_dir):
    """Crée le fichier CSV de session au DÉMARRAGE (pas au reset)"""
    if "csv_session_id" not in st.session_state:
        st.session_state.csv_session_id = f"SCENARIO_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Créer le dossier historique
        hist_dir = os.path.join(base_dir, "data", "historique")
        os.makedirs(hist_dir, exist_ok=True)
        
        # Créer les fichiers CSV immédiatement
        pat_csv = os.path.join(hist_dir, f"{st.session_state.csv_session_id}_patients.csv")
        staff_csv = os.path.join(hist_dir, f"{st.session_state.csv_session_id}_staff.csv")
        
        # Créer headers
        pd.DataFrame(columns=["timestamp", "id", "location", "severity", "escort_id"]).to_csv(pat_csv, sep=";", index=False)
        pd.DataFrame(columns=["timestamp", "id", "location", "patient_handling_id", "patient_symptom", "patient_color"]).to_csv(staff_csv, sep=";", index=False)
        
        print(f"✅ CSV Session Scénario créée : {st.session_state.csv_session_id}")


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
    """Génère 6 graphiques Plotly basés sur CSV complet"""
    df_patients, df_staff = load_session_csv_data(base_dir)
    
    if df_patients is None or df_patients.empty:
        # Graphiques vides si pas de données
        empty_fig = go.Figure()
        empty_fig.update_layout(title="Aucune donnée disponible", height=300)
        return empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, empty_fig
    
    # ===== GRAPHIQUE 1: Répartition patients dans le temps =====
    df_p = df_patients.copy()
    df_p['timestamp'] = pd.to_numeric(df_p['timestamp'], errors='coerce')
    
    # Agrégation par timestamp et location
    grouped = df_p.groupby(['timestamp', 'location']).size().reset_index(name='count')
    
    # Pivoter pour avoir les locations en colonnes
    pivot = grouped.pivot(index='timestamp', columns='location', values='count').fillna(0)
    
    fig1 = go.Figure()
    locations_of_interest = ['triage', 'wr_01', 'wr_02', 'wr_03', 'consultation', 'soins_critiques']
    
    for loc in locations_of_interest:
        if loc in pivot.columns:
            fig1.add_trace(go.Scatter(
                x=pivot.index, y=pivot[loc], mode='lines', name=loc.replace('_', ' ').title(),
                stackgroup='one', fill='tonexty'
            ))
    
    fig1.update_layout(title="📊 Répartition Patients dans le Temps", xaxis_title="Temps (min)", 
                       yaxis_title="Nombre de patients", height=350)
    
    # ===== GRAPHIQUE 2: Total patients traités par gravité =====
    severity_counts = df_patients.groupby('severity')['id'].nunique().reset_index()
    severity_counts.columns = ['Gravité', 'Total']
    
    color_map = {'ROUGE': '#e74c3c', 'JAUNE': '#f39c12', 'VERT': '#27ae60', 'GRIS': '#95a5a6'}
    
    fig2 = px.bar(severity_counts, x='Gravité', y='Total', 
                  title="🏥 Total Patients Traités par Gravité",
                  color='Gravité', color_discrete_map=color_map, height=350)
    
    # ===== GRAPHIQUE 3: Activité AS (transports) =====
    df_s = df_staff[df_staff['id'].str.contains('AS_', na=False)]
    as_activity = df_s.groupby('id').size().reset_index(name='Transports')
    
    fig3 = px.bar(as_activity, x='id', y='Transports',
                  title="🚑 Activité Aides-Soignants (Transports)",
                  labels={'id': 'AS', 'Transports': 'Nombre de transports'}, height=350)
    
    # ===== GRAPHIQUE 4: Temps d'attente moyen actuel =====
    # Calcul sur patients ACTIFS en attente
    active_waiting = []
    for pid, patient in state.patients.items():
        if patient.status == PatientStatus.WAITING and patient.location in ["triage"] + list(state.waiting_rooms.keys()):
            wait_time = state.time - patient.arrival_time
            active_waiting.append({'Couleur': patient.severity.value, 'Attente': wait_time})
    
    if active_waiting:
        df_wait = pd.DataFrame(active_waiting)
        avg_wait = df_wait.groupby('Couleur')['Attente'].mean().reset_index()
    else:
        avg_wait = pd.DataFrame({'Couleur': [], 'Attente': []})
    
    fig4 = px.bar(avg_wait, x='Couleur', y='Attente',
                  title="⏱️ Temps d'Attente Moyen Actuel (Patients en Attente)",
                  labels={'Attente': 'Temps moyen (min)'}, color='Couleur',
                  color_discrete_map=color_map, height=350)
    
    # ===== GRAPHIQUE 5: Destinations finales =====
    # Dernière location de chaque patient
    last_locations = df_patients.groupby('id')['location'].last().reset_index()
    dest_counts = last_locations['location'].value_counts().reset_index()
    dest_counts.columns = ['Destination', 'Nombre']
    
    fig5 = px.pie(dest_counts, names='Destination', values='Nombre',
                  title="🎯 Destinations Finales des Patients", height=350)
    
    # ===== GRAPHIQUE 6: Parcours patients (Sankey) =====
    patient_paths = df_patients.groupby('id')['location'].apply(list).to_dict()
    
    # Construire les flux
    flux = {}
    for pid, path in patient_paths.items():
        for i in range(len(path) - 1):
            from_loc = path[i]
            to_loc = path[i + 1]
            
            # Nettoyer les noms
            from_clean = from_loc.replace('injected_', '').replace('tran_', '→')
            to_clean = to_loc.replace('injected_', '').replace('tran_', '→')
            
            key = f"{from_clean} → {to_clean}"
            flux[key] = flux.get(key, 0) + 1
    
    # Construire Sankey
    if flux:
        all_locs = set()
        for k in flux.keys():
            f, t = k.split(' → ')
            all_locs.add(f)
            all_locs.add(t)
        
        loc_list = sorted(list(all_locs))
        loc_idx = {l: i for i, l in enumerate(loc_list)}
        
        src, tgt, val = [], [], []
        for k, c in flux.items():
            f, t = k.split(' → ')
            src.append(loc_idx[f])
            tgt.append(loc_idx[t])
            val.append(c)
        
        fig6 = go.Figure(data=[go.Sankey(
            node=dict(pad=15, thickness=20, label=loc_list),
            link=dict(source=src, target=tgt, value=val)
        )])
        fig6.update_layout(title="🔄 Parcours des Patients (Flux)", height=400)
    else:
        fig6 = go.Figure()
        fig6.update_layout(title="🔄 Parcours Patients (Aucune donnée)", height=400)
    
    return fig1, fig2, fig3, fig4, fig5, fig6


# =============================================================================
# HELPERS VISUALISATION
# =============================================================================

def format_patient_colored(patient, current_time):
    """Formate l'affichage d'un patient avec couleur et timer"""
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


def check_presence(state, room_staff_list, role_tag):
    """Vérifie la présence d'un type de personnel dans une salle"""
    found = []
    for s_id in room_staff_list:
        ag = state.staff.get(s_id)
        if ag and role_tag in s_id and ag.is_present and not ag.is_busy:
            found.append(s_id)
    return f"🟢 {', '.join(found)}" if found else "❌"


def verify_rules(state):
    """Vérifie les violations des règles métier"""
    violations = []
    
    # Vérifier patients ROUGE mal placés
    for p in state.patients.values():
        score = 4 if p.severity.value == "ROUGE" else 0
        if score >= 4 and p.location not in ["soins_critiques", "triage", "consultation", "direct_transfer_sc"]:
            if p.status != PatientStatus.IN_TRANSIT:
                violations.append(f"🔴 VITALE : {p.id} (ROUGE) est en '{p.location}' au lieu de SC !")

    # Vérifier surveillance salles
    if "nurse_timers" not in st.session_state:
        st.session_state.nurse_timers = {}
    
    for rid, room in state.waiting_rooms.items():
        has_pats = int(room.occupancy) > 0
        has_surveillance = False
        
        for sid in room.staff:
            ag = state.staff.get(sid)
            if ag and ag.is_present and not ag.is_busy and ("infirmier" in str(ag.role) or "aide" in str(ag.role)):
                has_surveillance = True
                break
        
        if has_pats and not has_surveillance:
            if rid not in st.session_state.nurse_timers:
                st.session_state.nurse_timers[rid] = state.time
            elif (state.time - st.session_state.nurse_timers[rid]) > 15:
                violations.append(f"🚫 SÉCURITÉ : {room.name} sans surveillance > 15 min !")
        else:
            if rid in st.session_state.nurse_timers:
                del st.session_state.nurse_timers[rid]
    
    return violations


# =============================================================================
# CHARGEMENT SCÉNARIOS
# =============================================================================

def load_scenarios():
    """Charge tous les scénarios disponibles"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scenarios_dir = os.path.join(base_dir, "data", "scenarios")
    
    scenarios = []
    
    if not os.path.exists(scenarios_dir):
        st.error(f"❌ Dossier scenarios introuvable : {scenarios_dir}")
        return []
    
    for filename in os.listdir(scenarios_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(scenarios_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    scenario = json.load(f)
                    scenarios.append(scenario)
            except Exception as e:
                st.warning(f"⚠️ Erreur chargement {filename}: {e}")
    
    return sorted(scenarios, key=lambda x: x['id'])


# =============================================================================
# MOTEUR D'EXÉCUTION
# =============================================================================

def execute_scenario_action(state, action, state_path):
    """Exécute une action du scénario"""
    
    action_type = action.get("action")
    
    # IGNORER les commentaires
    if not action_type or action_type == "comment":
        return None
    
    if action_type == "inject_patient":
        severity = action.get("severity")
        symptom = action.get("symptom", "Symptôme générique")
        location = action.get("location", "triage")
        
        # Générer ID unique
        if "scenario_patient_counter" not in st.session_state:
            st.session_state.scenario_patient_counter = 1
        
        new_id = f"PAT_{st.session_state.scenario_patient_counter:03d}"
        st.session_state.scenario_patient_counter += 1
        
        # Créer patient
        new_patient = Patient(
            id=new_id,
            severity=Severity[severity],
            symptom=symptom,
            location=location,
            status=PatientStatus.WAITING,
            arrival_time=state.time
        )
        
        # Ajouter au triage
        state.patients[new_id] = new_patient
        state.triage_zone.patients.append(new_id)
        state.triage_zone.occupancy += 1
        
        # Logger
        log_event(state, "PATIENT", new_id, f"injected_{location}")
        
        # IMPORTANT : Sauvegarder l'état immédiatement
        save_state(state, state_path)
        
        return f"✅ {new_id} ({severity}) injecté au triage"
    
    elif action_type == "set_staff_absent":
        staff_id = action.get("staff_id")
        if staff_id in state.staff:
            state.staff[staff_id].is_present = False
            save_state(state, state_path)
            return f"⚠️ {staff_id} est parti (fin de service)"
        return f"❌ {staff_id} introuvable"
    
    return "❌ Action inconnue"


def run_scenario_cycle(scenario_data, base_dir):
    """Exécute UN cycle du scénario"""
    
    if "scenario_running" not in st.session_state:
        st.session_state.scenario_running = False
    
    if "scenario_time" not in st.session_state:
        st.session_state.scenario_time = 0
    
    if "scenario_logs" not in st.session_state:
        st.session_state.scenario_logs = []
    
    if "scenario_metrics" not in st.session_state:
        st.session_state.scenario_metrics = {
            "patients_injected": 0,
            "patients_treated": 0,
            "violations": 0,
            "max_wait_rouge": 0,
            "total_wait_rouge": []
        }
    
    # Rate limiter : mémoriser le dernier appel LLM
    if "last_llm_call_time" not in st.session_state:
        st.session_state.last_llm_call_time = 0
    
    if not st.session_state.scenario_running:
        return
    
    # Charger état
    state_path = os.path.join(base_dir, "data", "state", "urgence_state.json")
    state = load_initial_state(state_path)
    current_time = st.session_state.scenario_time
    state.time = current_time
    
    # Exécuter actions du timeline
    timeline = scenario_data.get("timeline", [])
    for action in timeline:
        if action.get("t") == current_time:
            result = execute_scenario_action(state, action, state_path)
            
            # Ne logger que si c'est une vraie action (pas un commentaire)
            if result:
                st.session_state.scenario_logs.append(f"[T+{current_time}] {result}")
                
                if action.get("action") == "inject_patient":
                    st.session_state.scenario_metrics["patients_injected"] += 1
    
    # Calculer métriques
    for p in state.patients.values():
        if p.severity.value == "ROUGE" and p.location in ["triage"] + list(state.waiting_rooms.keys()):
            wait_time = state.time - p.arrival_time
            st.session_state.scenario_metrics["total_wait_rouge"].append(wait_time)
            if wait_time > st.session_state.scenario_metrics["max_wait_rouge"]:
                st.session_state.scenario_metrics["max_wait_rouge"] = wait_time
    
    # Sauvegarder état
    save_state(state, state_path)
    
    # Appeler le cerveau LLM comme dans simulation.py (ignore les erreurs 429)
    llm_enabled = st.session_state.get("llm_enabled", True)
    
    if llm_enabled:
        try:
            brain_result = process_brain_cycle()
            if brain_result:
                log_entry = f"[T+{current_time}] 🧠 {brain_result}"
                # Éviter doublons
                if not st.session_state.scenario_logs or st.session_state.scenario_logs[-1] != log_entry:
                    st.session_state.scenario_logs.append(log_entry)
                # Recharger l'état après le LLM
                state = load_initial_state(state_path)
                state.time = current_time
        except:
            # IGNORE les erreurs (comme simulation.py) - le LLM réessaiera au prochain cycle
            pass
    
    # Vérifier fin
    duration = scenario_data.get("duration_minutes", 30)
    if current_time >= duration:
        st.session_state.scenario_running = False
        st.session_state.scenario_logs.append(f"✅ Scénario terminé ({duration} min)")


# =============================================================================
# INTERFACE STREAMLIT
# =============================================================================

def show_scenarios():
    """Interface principale des scénarios"""
    
    st.markdown("## 📚 Scénarios de Test")
    st.caption("Testez le système de régulation avec des scénarios prédéfinis")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Initialiser CSV session
    ensure_csv_session_initialized(base_dir)
    
    # Charger scénarios
    scenarios = load_scenarios()
    
    if not scenarios:
        st.error("❌ Aucun scénario disponible. Vérifiez le dossier data/scenarios/")
        return
    
    # === SÉLECTION MODÈLE LLM ===
    with st.expander("🤖 Configuration IA", expanded=False):
        # Option pour désactiver le LLM (tests rapides)
        enable_llm = st.checkbox("Activer le LLM (décocher pour tests rapides)", value=True, key="enable_llm_scenario")
        
        if enable_llm:
            llm_models = {
                "Mistral Large (Recommandé)": "mistral-large-latest",
                "Mistral Medium": "mistral-medium-latest",
                "Mistral Small": "mistral-small-latest",
                "Codestral": "codestral-latest"
            }
            
            selected_model = st.selectbox(
                "Modèle LLM",
                options=list(llm_models.keys()),
                index=0,
                key="llm_model_selector"
            )
            
            set_llm_model(llm_models[selected_model])
            st.caption(f"Modèle actif : {llm_models[selected_model]}")
        else:
            st.warning("⚠️ LLM désactivé - Mode test rapide (pas de gestion automatique)")
        
        # Sauver l'état dans session_state
        st.session_state.llm_enabled = enable_llm
    
    # Sélection scénario
    st.markdown("### 🎯 Choisir un scénario")
    
    scenario_options = {f"{s['name']} ({s['duration_minutes']} min)": s for s in scenarios}
    selected_name = st.selectbox(
        "Scénario",
        options=list(scenario_options.keys()),
        key="scenario_selector"
    )
    
    selected_scenario = scenario_options[selected_name]
    
    # Afficher détails
    with st.expander("📋 Détails du scénario", expanded=True):
        st.markdown(f"**Description :** {selected_scenario.get('description', 'N/A')}")
        st.markdown(f"**Durée :** {selected_scenario.get('duration_minutes')} minutes")
        st.markdown(f"**Objectif :** {selected_scenario.get('objective', 'N/A')}")
        
        # Résumé timeline
        timeline = selected_scenario.get("timeline", [])
        st.markdown(f"**Événements :** {len(timeline)} actions programmées")
        
        # Compter par type
        severities = {}
        for event in timeline:
            if event.get("action") == "inject_patient":
                sev = event.get("severity", "UNKNOWN")
                severities[sev] = severities.get(sev, 0) + 1
        
        if severities:
            st.markdown("**Patients injectés :**")
            cols = st.columns(len(severities))
            for i, (sev, count) in enumerate(severities.items()):
                color_map = {"ROUGE": "🔴", "JAUNE": "🟡", "VERT": "🟢", "GRIS": "⚪"}
                cols[i].metric(f"{color_map.get(sev, '')} {sev}", count)
    
    # Contrôles
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("▶️ Lancer Scénario", use_container_width=True, type="primary"):
            # Reset état
            initial_path = os.path.join(base_dir, "data", "state", "urgence_initial_state.json")
            state_path = os.path.join(base_dir, "data", "state", "urgence_state.json")
            
            initial_state = load_initial_state(initial_path)
            
            # Appliquer initial_state du scénario si présent
            if "initial_state" in selected_scenario:
                init_config = selected_scenario["initial_state"]
                
                # Gérer staff_absent
                if "staff_absent" in init_config:
                    for staff_id in init_config["staff_absent"]:
                        if staff_id in initial_state.staff:
                            initial_state.staff[staff_id].is_present = False
                            initial_state.staff[staff_id].is_busy = False
                            initial_state.staff[staff_id].busy_until = 0
                
                # Gérer staff_present (s'assurer qu'ils sont bien présents)
                if "staff_present" in init_config:
                    for staff_id in init_config["staff_present"]:
                        if staff_id in initial_state.staff:
                            initial_state.staff[staff_id].is_present = True
                            initial_state.staff[staff_id].is_busy = False
                            initial_state.staff[staff_id].busy_until = 0
                
                # Gérer capacités
                if "capacities" in init_config:
                    caps = init_config["capacities"]
                    if "soins_critiques" in caps:
                        initial_state.soins_critiques.capacity = caps["soins_critiques"]
                    if "salles" in caps:
                        for room_id, cap in caps["salles"].items():
                            if room_id in initial_state.waiting_rooms:
                                initial_state.waiting_rooms[room_id].capacity = cap
            
            save_state(initial_state, state_path)
            
            # Reset session state
            st.session_state.scenario_running = True
            st.session_state.scenario_time = 0
            st.session_state.scenario_logs = []
            st.session_state.scenario_patient_counter = 1
            st.session_state.scenario_metrics = {
                "patients_injected": 0,
                "patients_treated": 0,
                "violations": 0,
                "max_wait_rouge": 0,
                "total_wait_rouge": []
            }
            st.session_state.scenario_violations_list = []
            st.session_state.selected_scenario = selected_scenario
            
            st.rerun()
    
    with col2:
        if st.button("⏸️ Pause", use_container_width=True):
            st.session_state.scenario_running = False
            st.rerun()
    
    with col3:
        if st.button("⏹️ Stop", use_container_width=True):
            st.session_state.scenario_running = False
            st.session_state.scenario_time = 0
            st.session_state.scenario_logs = []
            st.rerun()
    
    # Affichage état scénario
    if "selected_scenario" in st.session_state:
        st.markdown("---")
        st.markdown("### 📊 Exécution en cours")
        
        current_scenario = st.session_state.selected_scenario
        duration = current_scenario.get("duration_minutes", 30)
        current_time = st.session_state.get("scenario_time", 0)
        
        # Barre de progression
        progress = min(current_time / duration, 1.0)
        st.progress(progress, text=f"⏱️ Temps : {current_time}/{duration} min")
        
        # Métriques temps réel
        metrics = st.session_state.get("scenario_metrics", {})
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Patients injectés", metrics.get("patients_injected", 0))
        with col2:
            avg_wait = sum(metrics.get("total_wait_rouge", [0])) / len(metrics.get("total_wait_rouge", [1])) if metrics.get("total_wait_rouge") else 0
            st.metric("Attente moy. ROUGE", f"{avg_wait:.1f} min")
        with col3:
            st.metric("Max attente ROUGE", f"{metrics.get('max_wait_rouge', 0)} min")
        with col4:
            violations_count = metrics.get("violations", 0)
            # Afficher en rouge si violations
            if violations_count > 0:
                st.metric("⚠️ Violations", violations_count, delta=f"+{violations_count}", delta_color="inverse")
            else:
                st.metric("✅ Violations", violations_count)
        
        # Logs
        with st.expander("📝 Journal d'événements", expanded=False):
            logs = st.session_state.get("scenario_logs", [])
            if logs:
                for log in logs[-20:]:  # 20 derniers logs
                    st.text(log)
            else:
                st.caption("Aucun événement pour le moment")
        
        # Liste des violations actives
        if "scenario_violations_list" not in st.session_state:
            st.session_state.scenario_violations_list = []
        
        if st.session_state.scenario_violations_list:
            with st.expander(f"⚠️ Détail des Violations ({len(st.session_state.scenario_violations_list)})", expanded=True):
                for v in st.session_state.scenario_violations_list:
                    st.error(v)
        
        # =====================================================================
        # VISUALISATION COMPLÈTE (COMME SIMULATION.PY)
        # =====================================================================
        
        st.markdown("---")
        st.markdown("### 🏥 État des Services")
        
        # Charger état actuel
        state_path = os.path.join(base_dir, "data", "state", "urgence_state.json")
        state = load_initial_state(state_path)
        state.time = current_time
        
        # Soins Critiques + Consultation
        c_sc, c_cs = st.columns(2)
        with c_sc:
            with st.container(border=True):
                st.markdown("#### ❤️ Soins Critiques")
                st.write(f"**{state.soins_critiques.occupancy}/{state.soins_critiques.capacity}**")
                pats = [format_patient_colored(state.patients.get(pid), state.time) for pid in state.soins_critiques.patients]
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
                p = state.consultation_room.patients[0] if state.consultation_room.patients else None
                st.write(f"**Pat :** {format_patient_colored(state.patients.get(p), state.time) if p else '_'}")
        
        # Transport Consultation
        st.markdown("#### 🚑 Transport Consultation")
        c_as1, _ = st.columns(2)
        with c_as1:
            as1 = state.staff.get("AS_01")
            t1 = "❌"
            if as1 and as1.is_present:
                rem = max(0, as1.busy_until - state.time)
                t1 = "✅ DISPO" if rem <= 0 else f"🚑 MISSION ({rem} min)"
            st.info(f"**AS_01 (Prio Consult)** : {t1}")
        
        # Triage + Salles
        c_tr, c_rms = st.columns([1, 3])
        with c_tr:
            with st.container(border=True):
                st.markdown("#### 📋 Triage")
                st.write(f"INF: {check_presence(state, state.triage_zone.staff, 'INF')}")
                st.write(f"AS: {check_presence(state, state.triage_zone.staff, 'AS')}")
                p = [format_patient_colored(state.patients.get(pid), state.time) for pid in state.triage_zone.patients]
                st.write(f"**{len(p)}** : {', '.join(p) if p else '_'}")
        
        with c_rms:
            st.markdown("#### 🛋️ Salles d'Attente")
            cols = st.columns(3)
            for i, w in enumerate(["wr_01", "wr_02", "wr_03"]):
                with cols[i]:
                    r = state.waiting_rooms[w]
                    with st.container(border=True):
                        st.write(f"**{r.name}** ({r.occupancy}/{r.capacity})")
                        st.write(f"S: {check_presence(state, r.staff, 'INF')} {check_presence(state, r.staff, 'AS')}")
                        p = [format_patient_colored(state.patients.get(pid), state.time) for pid in r.patients]
                        st.write(" ".join(p) if p else "_")
        
        # Transport Hôpital
        st.markdown("#### 🚑 Transport Hôpital")
        c_as2, _ = st.columns(2)
        with c_as2:
            as2 = state.staff.get("AS_02")
            t2 = "❌"
            if as2 and as2.is_present:
                rem = max(0, as2.busy_until - state.time)
                t2 = "✅ DISPO" if rem <= 0 else f"🚑 MISSION ({rem} min)"
            st.info(f"**AS_02 (Prio Hôpital)** : {t2}")
        
        # Hospitalisation
        st.markdown("#### 🏥 Hospitalisation")
        cols = st.columns(4)
        icons = ["🦴", "🧠", "🫁", "❤️"]
        for i, u in enumerate(["ortho", "neuro", "pneumo", "cardio"]):
            with cols[i]:
                ut = state.units[u]
                with st.container(border=True):
                    st.write(f"**{icons[i]} {ut.name}**")
                    st.progress(ut.occupancy/ut.capacity if ut.capacity>0 else 0, f"{ut.occupancy}/{ut.capacity}")
                    if ut.patients:
                        p_list = [format_patient_colored(state.patients.get(pid), state.time) for pid in ut.patients]
                        st.caption(" ".join(p_list))
        
        # Violations
        viol = verify_rules(state)
        
        # Mettre à jour métriques violations
        if "scenario_violations_list" not in st.session_state:
            st.session_state.scenario_violations_list = []
        
        if viol:
            # Ajouter nouvelles violations (éviter doublons)
            for v in viol:
                if v not in st.session_state.scenario_violations_list:
                    st.session_state.scenario_violations_list.append(v)
            
            if "scenario_metrics" in st.session_state:
                st.session_state.scenario_metrics["violations"] = len(st.session_state.scenario_violations_list)
        
        if viol:
            for v in viol:
                st.error(v)
        else:
            st.success("✅ Règles respectées")
        
        # Expected metrics
        if "expected_metrics" in current_scenario:
            st.markdown("---")
            st.markdown("### 🎯 Objectifs du scénario")
            expected = current_scenario["expected_metrics"]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                target = expected.get("max_wait_time_rouge_minutes", "N/A")
                actual = metrics.get("max_wait_rouge", 0)
                status = "✅" if actual <= target else "❌"
                st.metric(f"Attente ROUGE max {status}", f"Cible: ≤{target} min", f"Actuel: {actual} min")
            
            with col2:
                target = expected.get("max_violations", "N/A")
                actual = metrics.get("violations", 0)
                status = "✅" if actual <= target else "❌"
                st.metric(f"Violations max {status}", f"Cible: ≤{target}", f"Actuel: {actual}")
            
            with col3:
                target = expected.get("min_patients_treated", "N/A")
                actual = metrics.get("patients_treated", 0)
                status = "✅" if actual >= target else "⏳"
                st.metric(f"Patients traités {status}", f"Cible: ≥{target}", f"Actuel: {actual}")
        
        # =====================================================================
        # STATISTIQUES TEMPS RÉEL (COMME SIMULATION.PY)
        # =====================================================================
        
        st.markdown("---")
        st.markdown("## 📊 Statistiques Temps Réel (Données CSV complètes)")
        
        fig1, fig2, fig3, fig4, fig5, fig6 = create_complete_statistics_charts(base_dir, state)
        
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(fig1, use_container_width=True, key="scenario_chart_repartition_temps")
            st.plotly_chart(fig3, use_container_width=True, key="scenario_chart_as_transports")
            st.plotly_chart(fig5, use_container_width=True, key="scenario_chart_destinations")
        with col2:
            st.plotly_chart(fig2, use_container_width=True, key="scenario_chart_gravite_totaux")
            st.plotly_chart(fig4, use_container_width=True, key="scenario_chart_attente_moyen")
        
        st.markdown("---")
        st.plotly_chart(fig6, use_container_width=True, key="scenario_chart_parcours_sankey")
    
    # GAME LOOP - EXACTEMENT comme simulation.py
    if st.session_state.get("scenario_running", False) and "selected_scenario" in st.session_state:
        time.sleep(1.0)
        st.session_state.scenario_time = st.session_state.get("scenario_time", 0) + 5
        
        scenario_data = st.session_state.selected_scenario
        current_time = st.session_state.scenario_time
        
        # Charger état
        state_path = os.path.join(base_dir, "data", "state", "urgence_state.json")
        state = load_initial_state(state_path)
        state.time = current_time
        
        # Exécuter actions timeline
        timeline = scenario_data.get("timeline", [])
        for action in timeline:
            if action.get("t") == current_time:
                result = execute_scenario_action(state, action, state_path)
                if result:
                    st.session_state.scenario_logs.append(f"[T+{current_time}] {result}")
                    if action.get("action") == "inject_patient":
                        st.session_state.scenario_metrics["patients_injected"] += 1
        
        # Calculer métriques
        for p in state.patients.values():
            if p.severity.value == "ROUGE" and p.location in ["triage"] + list(state.waiting_rooms.keys()):
                wait_time = state.time - p.arrival_time
                st.session_state.scenario_metrics["total_wait_rouge"].append(wait_time)
                if wait_time > st.session_state.scenario_metrics["max_wait_rouge"]:
                    st.session_state.scenario_metrics["max_wait_rouge"] = wait_time
        
        save_state(state, state_path)
        
        # === LOGIQUE MÉTIER (comme simulation.py) ===
        # Gérer le médecin et les patients en consultation
        doc = state.staff.get("DOC_01")
        cons = state.consultation_room
        
        if doc and doc.is_busy and doc.busy_until > 0 and current_time >= doc.busy_until:
            doc.is_busy = False
            doc.busy_until = 0
            
            if cons.patients:
                pid = cons.patients[0]
                pat = state.patients.get(pid)
                
                if pat:
                    # Décision médicale simple basée sur gravité
                    if pat.severity.value == "ROUGE":
                        dec = "soins_critiques"
                    elif pat.severity.value == "JAUNE":
                        dec = random.choice(["ortho", "cardio", "neuro", "pneumo"])
                    elif pat.severity.value == "VERT":
                        dec = "exit"
                    else:  # GRIS
                        dec = "exit"
                    
                    # Appliquer la décision
                    if dec == "exit":
                        cons.patients.remove(pid)
                        cons.occupancy = 0
                        del state.patients[pid]
                    
                    elif dec == "soins_critiques":
                        sc = state.soins_critiques
                        if sc.occupancy < sc.capacity:
                            cons.patients.remove(pid)
                            cons.occupancy = 0
                            sc.patients.append(pid)
                            sc.occupancy += 1
                            pat.location = "soins_critiques"
                            pat.treatment_end_time = current_time + random.randint(1440, 2880)
                        else:
                            # SC saturé → boarding
                            t_wr = None
                            for w in ["wr_01", "wr_02", "wr_03"]:
                                if state.waiting_rooms[w].occupancy < state.waiting_rooms[w].capacity:
                                    t_wr = state.waiting_rooms[w]
                                    break
                            if t_wr:
                                cons.patients.remove(pid)
                                cons.occupancy = 0
                                t_wr.patients.append(pid)
                                t_wr.occupancy += 1
                                pat.location = t_wr.id
                                pat.status = PatientStatus.BOARDING
                                pat.medical_decision = "soins_critiques"
                    
                    elif dec in ["ortho", "cardio", "neuro", "pneumo"]:
                        # Hospitalisation
                        t_wr = None
                        for w in ["wr_01", "wr_02", "wr_03"]:
                            if state.waiting_rooms[w].occupancy < state.waiting_rooms[w].capacity:
                                t_wr = state.waiting_rooms[w]
                                break
                        if t_wr:
                            cons.patients.remove(pid)
                            cons.occupancy = 0
                            t_wr.patients.append(pid)
                            t_wr.occupancy += 1
                            pat.location = t_wr.id
                            pat.status = PatientStatus.BOARDING
                            pat.medical_decision = dec
                    
                    save_state(state, state_path)
        
        # Gérer les patients hospitalisés (sortie)
        for r in list(state.units.values()) + [state.soins_critiques]:
            for pid in list(r.patients):
                pat = state.patients.get(pid)
                if not pat:
                    r.patients.remove(pid)
                    r.occupancy = max(0, r.occupancy - 1)
                    continue
                
                if pat.status == PatientStatus.HOSPITALIZED and pat.treatment_end_time > 0 and current_time >= pat.treatment_end_time:
                    r.patients.remove(pid)
                    r.occupancy = max(0, r.occupancy - 1)
                    del state.patients[pid]
                    save_state(state, state_path)
        
        # Appeler LLM (comme simulation.py - ignore erreurs)
        if st.session_state.get("llm_enabled", True):
            try:
                with st.spinner("🧠..."):
                    br = process_brain_cycle()
                if br:
                    l = f"[T+{current_time}] 🧠 {br}"
                    if not st.session_state.scenario_logs or st.session_state.scenario_logs[-1] != l:
                        st.session_state.scenario_logs.append(l)
                    state = load_initial_state(state_path)
                    state.time = current_time
            except: 
                pass
        
        # Vérifier fin
        duration = scenario_data.get("duration_minutes", 30)
        if current_time >= duration:
            st.session_state.scenario_running = False
            st.session_state.scenario_logs.append(f"✅ Scénario terminé ({duration} min)")
        
        st.rerun()
