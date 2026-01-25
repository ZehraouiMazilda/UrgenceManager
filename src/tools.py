import os
import time
import random
from src.utils import load_initial_state, save_state

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(BASE_DIR, "data", "state", "urgence_state.json")

def _get_state():
    return load_initial_state(JSON_PATH)

def _save_state(state):
    save_state(state, JSON_PATH)

# --- HELPERS (Fonctions internes) ---

def _check_staff_in_room(room_obj, role_tag):
    """Vérifie si un staff (INF, AS, DOC) est physiquement dans la salle."""
    if not room_obj.staff: return False
    return any(role_tag in s_id for s_id in room_obj.staff)

def _find_available_as(state):
    """Cherche un Aide-Soignant (AS) qui n'est PAS occupé."""
    for s_id, agent in state.staff.items():
        if "aide_soignant" in agent.role and not agent.is_busy:
            return agent
    return None

def _get_severity_score(severity_enum):
    """Convertit l'Enum (ROUGE, VERT...) en chiffre pour les comparaisons."""
    # On gère le cas où c'est l'objet Enum ou juste la string
    val = getattr(severity_enum, "value", str(severity_enum))
    mapping = {
        "ROUGE": 4,
        "JAUNE": 3,
        "VERT": 2,
        "GRIS": 1
    }
    return mapping.get(val, 1)

# =============================================================================
# 🔧 TOOL 1 : DEPLACEMENT BASIQUE (Infirmier / Autonome)
# =============================================================================

def transfer_patient_basic(patient_id: str, target_room_id: str):
    state = _get_state()
    
    if patient_id not in state.patients: return "❌ Patient introuvable."
    patient = state.patients[patient_id]
    current_loc = patient.location
    
    all_rooms = {
        "triage": state.triage_zone, "consultation": state.consultation_room,
        "soins_critiques": state.soins_critiques, **state.waiting_rooms, **state.units
    }
    
    target_room = all_rooms.get(target_room_id)
    start_room = all_rooms.get(current_loc)

    # --- RÈGLE 1 : Triage nécessite INF ou AS ---
    if current_loc == "triage":
        has_inf = _check_staff_in_room(state.triage_zone, "INF")
        has_as = _check_staff_in_room(state.triage_zone, "AS")
        if not (has_inf or has_as):
            return "⛔ ACTION REFUSÉE (Règle 1) : Pas d'Infirmier ou d'AS au Triage."

    # --- RÈGLE 2 : Patient ROUGE -> Soins Critiques ---
    severity_val = _get_severity_score(patient.severity)
    is_red = severity_val >= 4 

    if is_red and current_loc == "triage" and target_room_id != "soins_critiques":
        return "⛔ SÉCURITÉ (Règle 2) : Patient ROUGE doit aller en Soins Critiques !"

    # --- TRAJETS AUTORISÉS ---
    allowed = False
    if current_loc == "triage":
        if target_room_id == "soins_critiques": allowed = True
        elif target_room_id in state.waiting_rooms: allowed = True
        
    elif current_loc == "consultation":
        if target_room_id == "soins_critiques": allowed = True
        elif target_room_id == "exit": 
            # SORTIE DÉFINITIVE
            del state.patients[patient_id]
            state.consultation_room.occupancy = 0
            state.consultation_room.patients = []
            if "DOC_01" in state.staff: 
                state.staff["DOC_01"].is_busy = False
                state.staff["DOC_01"].busy_until = 0
            _save_state(state)
            return f"✅ Patient {patient_id} est SORTI de l'hôpital (Retour Domicile)."

    if not allowed:
        return f"⛔ Trajet interdit pour 'transfer_basic'."

    # --- CAPACITÉ ---
    if target_room and int(target_room.occupancy) >= int(target_room.capacity):
        return f"⛔ Salle {target_room_id} PLEINE ({target_room.occupancy}/{target_room.capacity})."

    # --- EXÉCUTION ---
    if start_room: 
        start_room.occupancy = max(0, int(start_room.occupancy) - 1)
        if patient_id in start_room.patients: start_room.patients.remove(patient_id)
    
    target_room.occupancy = int(target_room.occupancy) + 1
    target_room.patients.append(patient_id)
    patient.location = target_room_id
    
    _save_state(state)
    return f"✅ Succès : {patient_id} déplacé vers {target_room_id}."

# =============================================================================
# 🔧 TOOL 2 : DEPLACEMENT AVEC ESCORTE AS (Gestion Temps & Hasard)
# =============================================================================

def transfer_patient_with_escort(patient_id: str, target_room_id: str):
    state = _get_state()
    current_time = state.time
    
    if patient_id not in state.patients: return "❌ Patient introuvable."
    patient = state.patients[patient_id]
    current_loc = patient.location
    
    as_agent = _find_available_as(state)
    if not as_agent:
        return "⛔ RESSOURCE MANQUANTE : Aucun Aide-Soignant libre."

    all_rooms = {
        "consultation": state.consultation_room,
        **state.waiting_rooms, **state.units
    }
    target_room = all_rooms.get(target_room_id)
    start_room = all_rooms.get(current_loc)
    
    if not target_room: return f"❌ Destination {target_room_id} inconnue."

    allowed = False
    duration_transport = 0 
    duration_task = 0 # Temps d'occupation du médecin ou autre
    
    # 1. VERS CONSULTATION
    if current_loc in state.waiting_rooms and target_room_id == "consultation":
        allowed = True
        duration_transport = 5
        duration_task = 15 # La consultation dure 15 min
        
    # 2. VERS SALLE D'ATTENTE (Retour Consult)
    elif current_loc == "consultation" and target_room_id in state.waiting_rooms:
        allowed = True
        duration_transport = 5 
        # On libère le médecin immédiatement
        if "DOC_01" in state.staff: 
            state.staff["DOC_01"].is_busy = False
            state.staff["DOC_01"].busy_until = 0

    # 3. VERS UNITÉS (HOSPITALISATION)
    elif current_loc in state.waiting_rooms and target_room_id in state.units:
        # Note: Normalement on vient de consult, mais si le LLM fait Consult->Attente->Unité, c'est ok.
        allowed = True
        duration_transport = 45
        # DUREE DE SEJOUR ALEATOIRE (12h - 24h)
        # 12h = 720 min, 24h = 1440 min
        stay_duration = random.randint(720, 1440)
        patient.treatment_end_time = current_time + stay_duration

    if not allowed:
        return f"⛔ Trajet interdit pour 'transfer_escort'."

    # --- CAPACITÉ ---
    if int(target_room.occupancy) >= int(target_room.capacity):
        return f"⛔ Salle {target_room_id} PLEINE."

    # --- EXÉCUTION & BLOCAGE TEMPOREL ---
    
    # Bloquer AS
    as_agent.is_busy = True 
    as_agent.busy_until = current_time + duration_transport

    # Bloquer Médecin (Si consult)
    if target_room_id == "consultation":
        if state.staff["DOC_01"].is_busy:
            return "⛔ Le Médecin est déjà OCCUPÉ."
        state.staff["DOC_01"].is_busy = True
        state.staff["DOC_01"].busy_until = current_time + duration_task

    # Mouvement
    if start_room:
        start_room.occupancy = max(0, int(start_room.occupancy) - 1)
        if patient_id in start_room.patients: start_room.patients.remove(patient_id)
        
    target_room.occupancy = int(target_room.occupancy) + 1
    target_room.patients.append(patient_id)
    patient.location = target_room_id
    
    _save_state(state)
    return f"✅ Succès : {patient_id} vers {target_room_id} (AS occupé {duration_transport}min)."

# =============================================================================
# 🔧 TOOL 3 : DASHBOARD & ALARMES (Avec Aide à la Décision)
# =============================================================================

def get_hospital_dashboard():
    state = _get_state()
    alerts = []
    
    # Alarme Règle 5
    for rid, room in state.waiting_rooms.items():
        has_inf = _check_staff_in_room(room, "INF")
        if int(room.occupancy) > 0 and not has_inf:
            alerts.append(f"🔥 ALERTE SÉCURITÉ : {room.name} contient des patients mais AUCUNE Infirmière !")
            
    # Alarme Règle 3
    if int(state.waiting_rooms["wr_02"].occupancy) > 0 and int(state.waiting_rooms["wr_01"].occupancy) == 0:
        alerts.append("⚠️ OPTIMISATION : Remplissez Salle 1 avant Salle 2.")

    # Alarme Règle 2
    triage_pats = [p for p in state.patients.values() if p.location == "triage"]
    for p in triage_pats:
        score = _get_severity_score(p.severity)
        if score >= 4:
            alerts.append(f"🚨 URGENCE VITALE : Patient {p.id} (ROUGE) attend au Triage !")

    # --- AIDE A LA DECISION (POST-CONSULTATION) ---
    # Si un patient est en consult ET que le médecin n'est PLUS occupé (donc temps écoulé)
    if state.consultation_room.occupancy > 0:
        if not state.staff["DOC_01"].is_busy:
            p_id = state.consultation_room.patients[0]
            
            # HASARD : 50% Maison / 50% Hôpital
            # On utilise le hash de l'ID + le temps pour que la décision soit stable mais pseudo-aléatoire
            seed = hash(p_id) + state.time
            random.seed(seed)
            choice = random.choice(["MAISON", "HOPITAL"])
            
            if choice == "MAISON":
                alerts.append(f"✅ FIN CONSULTATION ({p_id}) : Patient stable -> RECOMMANDATION : SORTIE (Maison).")
            else:
                unit = random.choice(["ortho", "cardio", "neuro", "pneumo"])
                alerts.append(f"⚠️ FIN CONSULTATION ({p_id}) : Cas complexe -> RECOMMANDATION : HOSPITALISATION ({unit}).")

    busy_staff = [s.id for s in state.staff.values() if s.is_busy]
    
    report = f"\n=== 📟 DASHBOARD HÔPITAL (H+{state.time // 60}) ===\n"
    
    if alerts:
        report += "\n💥💥 ALARMES / AVIS MÉDICAL 💥💥\n"
        for a in alerts: report += f"- {a}\n"
        report += "\n"
    else:
        report += "✅ Aucune alerte active.\n"
        
    report += f"🚑 STAFF OCCUPÉ : {', '.join(busy_staff) if busy_staff else 'Aucun'}\n"
    report += f"📍 Triage : {len(triage_pats)} patients.\n"
    
    for rid, room in state.waiting_rooms.items():
        staff_icon = "✅INF" if _check_staff_in_room(room, "INF") else "❌VIDE"
        report += f"📍 {room.name} ({rid}) [{staff_icon}] : {room.occupancy}/{room.capacity}\n"
        
    report += f"📍 Consultation : {state.consultation_room.occupancy}/1\n"
    
    return report

def get_patient_list(location="triage"):
    state = _get_state()
    patients = [p for p in state.patients.values() if p.location == location]
    if not patients: return f"Aucun patient en '{location}'."
    
    txt = ""
    for p in patients:
        val = _get_severity_score(p.severity)
        severity_icon = "🔴" if val >= 4 else "🟢" if val <= 2 else "🟡"
        # On affiche le nom de l'Enum (ex: ROUGE)
        severity_str = getattr(p.severity, "value", str(p.severity))
        txt += f"- ID: {p.id} | {severity_icon} {severity_str} | Symp: {p.symptom}\n"
    return txt