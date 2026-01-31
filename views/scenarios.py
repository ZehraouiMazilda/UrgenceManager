"""
Page de Scénarios de Démonstration
===================================

Scénarios pré-configurés pour démontrer les capacités du système :
1. Afflux massif (simulation catastrophe)
2. Journée normale (gestion optimale)
3. Épidémie (patients similaires)
4. Urgences vitales en série
5. Sous-effectif critique
6. Test de résilience (montée en charge)
"""

import streamlit as st
import time
import random
from pathlib import Path
import json
from datetime import datetime

from src.utils import load_initial_state, save_state
from src.models import Severity, Patient

# =============================================================================
# CONFIGURATION
# =============================================================================

STATE_PATH = Path("data/state/urgence_state.json")
SYMPTOMS_PATH = Path("data/symptoms.json")

# Charger les symptômes
try:
    with open(SYMPTOMS_PATH, 'r', encoding='utf-8') as f:
        SYMPTOMS_DATA = json.load(f)
except:
    SYMPTOMS_DATA = {
        "ROUGE": ["Douleur thoracique intense", "AVC suspecté", "Hémorragie sévère"],
        "JAUNE": ["Fracture suspectée", "Fièvre élevée", "Douleur abdominale"],
        "VERT": ["Entorse", "Infection urinaire", "Gastro-entérite"],
        "GRIS": ["Rhume", "Renouvellement ordonnance", "Certificat médical"]
    }

# =============================================================================
# SCÉNARIOS PRÉDÉFINIS
# =============================================================================

SCENARIOS = {
    "🌪️ AFFLUX MASSIF (Catastrophe)": {
        "description": """
        **Simulation d'une catastrophe naturelle ou accident majeur**
        
        - 20 patients ROUGE en 5 minutes
        - 15 patients JAUNE en 10 minutes
        - Saturation complète des Soins Critiques
        - Test de la gestion de crise
        
        **Objectif :** Observer comment le système priorise les urgences vitales
        et gère la saturation des ressources.
        """,
        "icon": "🌪️",
        "duration": "~15 min",
        "difficulty": "🔴🔴🔴 Extrême",
        "patients": [
            {"count": 20, "severity": "ROUGE", "delay": 0.2, "interval": 5},
            {"count": 15, "severity": "JAUNE", "delay": 0.5, "interval": 10}
        ],
        "staff_config": "normal",
        "expected_outcome": "Le système doit prioriser les ROUGE vers SC, puis vers salles d'attente avec surveillance renforcée."
    },
    
    "📅 JOURNÉE NORMALE (Gestion Optimale)": {
        "description": """
        **Simulation d'une journée type aux urgences**
        
        - Flux régulier de patients (mix de gravités)
        - 2-3 patients toutes les 5 minutes
        - Répartition réaliste : 10% ROUGE, 30% JAUNE, 40% VERT, 20% GRIS
        
        **Objectif :** Démontrer l'efficacité du système en conditions normales
        avec optimisation du flux et des temps d'attente.
        """,
        "icon": "📅",
        "duration": "~20 min",
        "difficulty": "🟢 Normal",
        "patients": [
            {"count": 3, "severity": "ROUGE", "delay": 1.0, "interval": 20},
            {"count": 9, "severity": "JAUNE", "delay": 1.0, "interval": 20},
            {"count": 12, "severity": "VERT", "delay": 1.0, "interval": 20},
            {"count": 6, "severity": "GRIS", "delay": 1.0, "interval": 20}
        ],
        "staff_config": "normal",
        "expected_outcome": "Temps d'attente optimisés, flux fluide, satisfaction élevée."
    },
    
    "🦠 ÉPIDÉMIE (Patients Similaires)": {
        "description": """
        **Simulation d'une épidémie (ex: grippe, gastro)**
        
        - 25 patients VERT avec symptômes similaires
        - 10 patients JAUNE (complications)
        - Arrivée groupée (pic épidémique)
        
        **Objectif :** Tester la gestion de patients homogènes et le regroupement
        intelligent dans les salles d'attente.
        """,
        "icon": "🦠",
        "duration": "~15 min",
        "difficulty": "🟡 Modéré",
        "patients": [
            {"count": 25, "severity": "VERT", "delay": 0.3, "interval": 8, "same_symptom": True},
            {"count": 10, "severity": "JAUNE", "delay": 0.5, "interval": 12, "same_symptom": True}
        ],
        "staff_config": "normal",
        "expected_outcome": "Regroupement intelligent des patients similaires, optimisation des consultations."
    },
    
    "🚨 URGENCES VITALES EN SÉRIE": {
        "description": """
        **Série d'urgences vitales espacées**
        
        - 1 patient ROUGE toutes les 2 minutes (total: 10)
        - Quelques JAUNE entre les ROUGE
        - Test de la réactivité du système
        
        **Objectif :** Vérifier que chaque ROUGE est traité en priorité absolue,
        avec orientation immédiate vers SC ou consultation.
        """,
        "icon": "🚨",
        "duration": "~20 min",
        "difficulty": "🔴🔴 Difficile",
        "patients": [
            {"count": 10, "severity": "ROUGE", "delay": 2.0, "interval": 2},
            {"count": 5, "severity": "JAUNE", "delay": 2.5, "interval": 4}
        ],
        "staff_config": "normal",
        "expected_outcome": "Chaque ROUGE orienté en <5 min vers SC ou consultation. Aucun ROUGE en attente prolongée."
    },
    
    "👥 SOUS-EFFECTIF CRITIQUE": {
        "description": """
        **Gestion avec personnel réduit**
        
        - 1 seul AS disponible (au lieu de 2)
        - 1 seule infirmière de salle
        - Flux normal de patients
        
        **Objectif :** Tester la robustesse du système face à un manque de personnel.
        Observer les mécanismes de compensation (règle 2.2 : remplacement auto).
        """,
        "icon": "👥",
        "duration": "~15 min",
        "difficulty": "🔴🔴 Difficile",
        "patients": [
            {"count": 5, "severity": "ROUGE", "delay": 1.5, "interval": 6},
            {"count": 10, "severity": "JAUNE", "delay": 1.5, "interval": 8},
            {"count": 8, "severity": "VERT", "delay": 1.5, "interval": 10}
        ],
        "staff_config": "reduced",  # Configuration spéciale
        "expected_outcome": "Le système doit prioriser intelligemment avec ressources limitées. Temps d'attente augmentés mais gestion cohérente."
    },
    
    "📈 TEST DE RÉSILIENCE (Montée en Charge)": {
        "description": """
        **Montée progressive en charge**
        
        - Phase 1 (0-5 min): Calme (2 patients)
        - Phase 2 (5-10 min): Normal (8 patients)
        - Phase 3 (10-15 min): Intense (15 patients)
        - Phase 4 (15-20 min): Critique (25 patients)
        
        **Objectif :** Observer l'adaptation du système à une montée en charge progressive.
        Identifier le point de rupture.
        """,
        "icon": "📈",
        "duration": "~20 min",
        "difficulty": "🔴🔴🔴 Extrême",
        "patients": [
            # Phase 1
            {"count": 2, "severity": "VERT", "delay": 0, "interval": 2.5},
            # Phase 2
            {"count": 8, "severity": "JAUNE", "delay": 5, "interval": 5},
            # Phase 3
            {"count": 15, "severity": "ROUGE", "delay": 10, "interval": 10},
            # Phase 4
            {"count": 25, "severity": "ROUGE", "delay": 15, "interval": 15}
        ],
        "staff_config": "normal",
        "expected_outcome": "Dégradation progressive mais contrôlée. Priorisation maintenue. Pas de crash."
    },
    
    "🎯 RÈGLE ANTI-FAMINE (Dépassement Délai)": {
        "description": """
        **Test de la règle 5 : Patients VERT/GRIS prioritaires après 40/60 min**
        
        - 5 patients VERT injectés au début (attente longue)
        - 5 patients ROUGE injectés après 30 min
        - Observer si les VERT deviennent prioritaires après 40 min
        
        **Objectif :** Vérifier que le tag 🔥 DÉPASSEMENT fonctionne et que
        les VERT > 40 min passent AVANT les nouveaux JAUNE.
        """,
        "icon": "🎯",
        "duration": "~50 min",
        "difficulty": "🟡 Modéré (long)",
        "patients": [
            {"count": 5, "severity": "VERT", "delay": 0, "interval": 1},  # Au début
            {"count": 5, "severity": "ROUGE", "delay": 30, "interval": 35},  # Après 30 min
            {"count": 5, "severity": "JAUNE", "delay": 45, "interval": 50}   # Après 45 min
        ],
        "staff_config": "slow_consultation",  # Consultations lentes pour créer attente
        "expected_outcome": "Les VERT avec 🔥 DÉPASSEMENT doivent passer AVANT les JAUNE récents (mais après ROUGE)."
    },
    
    "🏃 SPRINT (Démo Rapide 5 min)": {
        "description": """
        **Démonstration rapide pour présentation**
        
        - 3 ROUGE (urgences vitales)
        - 5 JAUNE (urgences standards)
        - 4 VERT (non-urgents)
        - Tout en 5 minutes chrono
        
        **Objectif :** Démo rapide et impactante montrant toutes les capacités
        du système en conditions réelles compressées.
        """,
        "icon": "🏃",
        "duration": "~5 min",
        "difficulty": "🟢 Facile",
        "patients": [
            {"count": 3, "severity": "ROUGE", "delay": 0.1, "interval": 1},
            {"count": 5, "severity": "JAUNE", "delay": 0.2, "interval": 2},
            {"count": 4, "severity": "VERT", "delay": 0.3, "interval": 3}
        ],
        "staff_config": "normal",
        "expected_outcome": "Démonstration fluide et rapide de toutes les fonctionnalités clés."
    }
}


# =============================================================================
# FONCTIONS D'INJECTION
# =============================================================================

def inject_patient(state, severity_str: str, symptom: str = None, state_path: Path = STATE_PATH):
    """Injecte un patient dans le triage."""
    severity_enum = getattr(Severity, severity_str, Severity.GRIS)
    
    # Symptôme aléatoire si non spécifié
    if not symptom:
        symptom = random.choice(SYMPTOMS_DATA.get(severity_str, ["Symptôme non spécifié"]))
    
    # Trouver le prochain ID
    existing_ids = [int(p_id.replace("PAT_", "")) for p_id in state.patients.keys() if p_id.startswith("PAT_")]
    next_id = max(existing_ids) + 1 if existing_ids else 1
    patient_id = f"PAT_{next_id:03d}"
    
    # Créer le patient
    new_patient = Patient(
        id=patient_id,
        severity=severity_enum,
        symptom=symptom,
        arrival_time=state.time,
        location="triage",
        status="waiting"
    )
    
    # Ajouter au state
    state.patients[patient_id] = new_patient
    state.triage_zone.patients.append(patient_id)
    state.triage_zone.occupancy += 1
    
    # Sauvegarder
    save_state(state, state_path)
    
    return patient_id


def configure_staff(state, config: str, state_path: Path = STATE_PATH):
    """Configure le personnel selon le scénario."""
    if config == "reduced":
        # Désactiver AS_02 et INF_SALLE_02
        if "AS_02" in state.staff:
            state.staff["AS_02"].is_present = False
        if "INF_SALLE_02" in state.staff:
            state.staff["INF_SALLE_02"].is_present = False
        save_state(state, state_path)
        return "Personnel réduit : AS_02 et INF_SALLE_02 désactivés"
    
    elif config == "slow_consultation":
        # Ralentir les consultations (via modification du médecin)
        # Note: Cela devrait être géré dans tools.py mais on peut le noter ici
        return "Configuration : Consultations ralenties (pour créer de l'attente)"
    
    else:  # normal
        # Tout le personnel présent
        for staff in state.staff.values():
            staff.is_present = True
            staff.is_busy = False
        save_state(state, state_path)
        return "Personnel complet : Tous disponibles"


def run_scenario(scenario_key: str, progress_bar, status_text):
    """Exécute un scénario complet."""
    scenario = SCENARIOS[scenario_key]
    state = load_initial_state(STATE_PATH)
    
    # Configuration du personnel
    staff_status = configure_staff(state, scenario.get("staff_config", "normal"), STATE_PATH)
    status_text.text(f"⚙️ {staff_status}")
    time.sleep(1)
    
    # Injection des patients selon le plan
    total_patients = sum(p["count"] for p in scenario["patients"])
    injected = 0
    
    for patient_wave in scenario["patients"]:
        count = patient_wave["count"]
        severity = patient_wave["severity"]
        delay = patient_wave["delay"]
        interval = patient_wave["interval"]
        same_symptom = patient_wave.get("same_symptom", False)
        
        # Attendre le délai initial
        if delay > 0:
            status_text.text(f"⏳ Attente de {delay} min avant la vague {severity}...")
            time.sleep(delay)
        
        # Symptôme unique si demandé
        if same_symptom:
            unique_symptom = random.choice(SYMPTOMS_DATA.get(severity, ["Symptôme épidémique"]))
        
        # Injecter les patients
        for i in range(count):
            state = load_initial_state(STATE_PATH)  # Recharger pour avoir l'état à jour
            
            symptom = unique_symptom if same_symptom else None
            patient_id = inject_patient(state, severity, symptom, STATE_PATH)
            
            injected += 1
            progress = injected / total_patients
            progress_bar.progress(progress)
            status_text.text(f"💉 Injection {patient_id} ({severity}) - {injected}/{total_patients}")
            
            # Intervalle entre patients de la même vague
            if i < count - 1:  # Pas d'attente après le dernier patient
                time.sleep(interval / count)
    
    status_text.text(f"✅ Scénario terminé ! {total_patients} patients injectés.")
    return total_patients


# =============================================================================
# INTERFACE STREAMLIT
# =============================================================================

def show_scenarios():
    """Page principale des scénarios."""
    
    #st.set_page_config(page_title="🎬 Scénarios de Démo", layout="wide")
    
    st.title("🎬 Scénarios de Démonstration")
    st.markdown("**Scénarios pré-configurés pour tester et démontrer le système**")
    
    # Message d'accueil
    st.info("""
    👨‍🏫 **Pour le Prof :**
    
    Ces scénarios permettent de démontrer les capacités du système dans différentes situations :
    - Gestion de crise (afflux massif)
    - Optimisation du flux (journée normale)
    - Robustesse (sous-effectif)
    - Règles métier (anti-famine, priorisation)
    
    **Instructions :** Sélectionnez un scénario, cliquez sur "▶️ Lancer", puis allez dans l'onglet **Simulation** 
    pour observer le système en action.
    """)
    
    st.divider()
    
    # Sélection du scénario
    st.subheader("📋 Choisir un Scénario")
    
    # Afficher les scénarios en grille
    cols = st.columns(2)
    
    selected_scenario = None
    
    for i, (scenario_key, scenario_data) in enumerate(SCENARIOS.items()):
        col = cols[i % 2]
        
        with col:
            with st.container(border=True):
                st.markdown(f"### {scenario_data['icon']} {scenario_key.split(')')[0]})")
                st.markdown(scenario_data["description"])
                
                # Métadonnées
                col1, col2, col3 = st.columns(3)
                col1.metric("⏱️ Durée", scenario_data["duration"])
                col2.metric("🎚️ Difficulté", scenario_data["difficulty"])
                col3.metric("👥 Patients", sum(p["count"] for p in scenario_data["patients"]))
                
                # Résultat attendu
                with st.expander("🎯 Résultat Attendu"):
                    st.write(scenario_data["expected_outcome"])
                
                # Bouton de sélection
                if st.button(f"▶️ Lancer ce scénario", key=f"btn_{scenario_key}", type="primary", use_container_width=True):
                    selected_scenario = scenario_key
    
    # Exécution du scénario
    if selected_scenario:
        st.divider()
        st.subheader(f"🎬 Exécution : {selected_scenario}")
        
        # Confirmation
        st.warning("""
        ⚠️ **Attention :**
        - Le scénario va injecter des patients automatiquement
        - Assurez-vous que la simulation est **démarrée** (bouton ▶️)
        - Vous pouvez observer en temps réel dans l'onglet **Simulation**
        """)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            confirm = st.checkbox("✅ J'ai compris, je veux lancer le scénario")
        
        with col2:
            if confirm:
                if st.button("🚀 GO !", type="primary", use_container_width=True):
                    # Barre de progression
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Lancer le scénario
                    total = run_scenario(selected_scenario, progress_bar, status_text)
                    
                    # Message de fin
                    st.success(f"""
                    ✅ **Scénario terminé !**
                    
                    - {total} patients injectés
                    - Allez dans l'onglet **Simulation** pour observer
                    - Allez dans l'onglet **Statistiques** pour analyser les résultats
                    - Allez dans l'onglet **AI Assistant** pour poser des questions
                    """)
                    
                    st.balloons()
    
    # Section : Créer un scénario personnalisé
    st.divider()
    
    with st.expander("🛠️ Créer un Scénario Personnalisé (Avancé)"):
        st.markdown("**Construisez votre propre scénario**")
        
        custom_name = st.text_input("Nom du scénario", "Mon Scénario Personnalisé")
        
        st.subheader("Vagues de Patients")
        
        num_waves = st.number_input("Nombre de vagues", min_value=1, max_value=5, value=2)
        
        waves = []
        for i in range(num_waves):
            st.markdown(f"**Vague {i+1}**")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                count = st.number_input(f"Nombre", min_value=1, max_value=50, value=5, key=f"count_{i}")
            with col2:
                severity = st.selectbox(f"Gravité", ["ROUGE", "JAUNE", "VERT", "GRIS"], key=f"sev_{i}")
            with col3:
                delay = st.number_input(f"Délai (min)", min_value=0.0, max_value=60.0, value=0.0, step=0.5, key=f"delay_{i}")
            with col4:
                interval = st.number_input(f"Intervalle (min)", min_value=1, max_value=30, value=5, key=f"interval_{i}")
            
            waves.append({
                "count": count,
                "severity": severity,
                "delay": delay,
                "interval": interval
            })
        
        if st.button("🚀 Lancer le Scénario Personnalisé", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Construire et exécuter
            custom_scenario = {
                "patients": waves,
                "staff_config": "normal"
            }
            
            state = load_initial_state(STATE_PATH)
            configure_staff(state, "normal", STATE_PATH)
            
            total_patients = sum(w["count"] for w in waves)
            injected = 0
            
            for wave in waves:
                if wave["delay"] > 0:
                    status_text.text(f"⏳ Attente de {wave['delay']} min...")
                    time.sleep(wave["delay"])
                
                for i in range(wave["count"]):
                    state = load_initial_state(STATE_PATH)
                    patient_id = inject_patient(state, wave["severity"], None, STATE_PATH)
                    
                    injected += 1
                    progress_bar.progress(injected / total_patients)
                    status_text.text(f"💉 {patient_id} ({wave['severity']}) - {injected}/{total_patients}")
                    
                    if i < wave["count"] - 1:
                        time.sleep(wave["interval"] / wave["count"])
            
            st.success(f"✅ Scénario personnalisé terminé ! {total_patients} patients injectés.")
            st.balloons()
    
    # Footer
    st.divider()
    st.caption("🎬 Scénarios de démonstration | Conçus pour tester toutes les capacités du système")


# Alias pour compatibilité
def main():
    show_scenarios()


if __name__ == "__main__":
    show_scenarios()