import os
import time
import random
from src.utils import load_initial_state, save_state
from src.logger import log_event 

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(BASE_DIR, "data", "state", "urgence_state.json")

def _get_state(): return load_initial_state(JSON_PATH)
def _save_state(state): save_state(state, JSON_PATH)

# --- HELPERS ---
def _check_staff_in_room(room_obj, role_tag):
    if not room_obj.staff: return False
    return any(role_tag in s_id for s_id in room_obj.staff)

def _find_available_as(state):
    for s_id, agent in state.staff.items():
        if "aide_soignant" in agent.role and not agent.is_busy:
            return agent
    return None

def _get_severity_score(severity_enum):
    val = getattr(severity_enum, "value", str(severity_enum))
    mapping = {"ROUGE": 4, "JAUNE": 3, "VERT": 2, "GRIS": 1}
    return mapping.get(val, 1)

# =============================================================================
# TOOL 1 : TRANSFERT STAFF (NOUVEAU - Pour gérer les infirmiers)
# =============================================================================
def transfer_staff(staff_id: str, target_room_id: str):
    state = _get_state()
    
    if staff_id not in state.staff: return f"❌ Staff {staff_id} introuvable."
    agent = state.staff[staff_id]
    
    # Vérifier que c'est un infirmier (les AS et Docs sont gérés autrement)
    if "infirmier" not in agent.role:
        return f"⛔ Seuls les infirmiers peuvent être déplacés manuellement ici."

    current_loc_id = agent.location
    
    # Mapping des salles
    all_rooms = {"triage": state.triage_zone, **state.waiting_rooms, "consultation": state.consultation_room}
    target_room = all_rooms.get(target_room_id)
    start_room = all_rooms.get(current_loc_id)
    
    if not target_room: return f"❌ Salle destination {target_room_id} inconnue."
    if current_loc_id == target_room_id: return f"⚠️ {staff_id} est déjà en {target_room_id}."

    # Déplacement
    if start_room and staff_id in start_room.staff:
        start_room.staff.remove(staff_id)
    
    target_room.staff.append(staff_id)
    agent.location = target_room_id
    
    log_event(state, "STAFF", staff_id, f"moved_to_{target_room_id}")
    _save_state(state)
    return f"✅ {staff_id} déplacé vers {target_room.name}."

# =============================================================================
# TOOL 2 : TRANSFERT PATIENT BASIQUE
# =============================================================================
def transfer_patient_basic(patient_id: str, target_room_id: str):
    state = _get_state()
    if patient_id not in state.patients: return "❌ Patient introuvable (Fantôme)."
    patient = state.patients[patient_id]
    current_loc = patient.location
    
    if current_loc == target_room_id: return f"⚠️ Déjà fait."

    all_rooms = {"triage": state.triage_zone, "consultation": state.consultation_room, "soins_critiques": state.soins_critiques, **state.waiting_rooms, **state.units}
    target_room = all_rooms.get(target_room_id)
    start_room = all_rooms.get(current_loc)

    # Sortie
    if target_room_id == "exit":
        if patient.medical_decision == "exit":
            del state.patients[patient_id]
            if start_room:
                if patient_id in start_room.patients: start_room.patients.remove(patient_id)
                start_room.occupancy = max(0, start_room.occupancy - 1)
            if current_loc == "consultation" and "DOC_01" in state.staff: state.staff["DOC_01"].is_busy = False
            log_event(state, "PATIENT", patient_id, "exit", related_entity=None)
            _save_state(state)
            return f"✅ Patient {patient_id} SORTI."
        else: return "⛔ Sortie non validée par médecin."

    # Triage -> Ailleurs
    if current_loc == "triage":
        if _get_severity_score(patient.severity) >= 4 and target_room_id != "soins_critiques":
            return "⛔ ROUGE -> Soins Critiques OBLIGATOIRE !"

    if target_room and int(target_room.occupancy) >= int(target_room.capacity):
        return f"⛔ {target_room_id} PLEINE."

    if start_room:
        start_room.occupancy = max(0, int(start_room.occupancy) - 1)
        if patient_id in start_room.patients: start_room.patients.remove(patient_id)
    
    target_room.occupancy = int(target_room.occupancy) + 1
    target_room.patients.append(patient_id)
    patient.location = target_room_id
    
    log_event(state, "PATIENT", patient_id, target_room_id)
    _save_state(state)
    return f"✅ Succès : {patient_id} vers {target_room_id}."

# =============================================================================
# TOOL 3 : TRANSFERT ESCORTE
# =============================================================================
def transfer_patient_with_escort(patient_id: str, target_room_id: str):
    state = _get_state()
    current_time = state.time
    
    if patient_id not in state.patients: return "❌ Patient introuvable."
    patient = state.patients[patient_id]
    current_loc = patient.location
    if current_loc == target_room_id: return f"⚠️ Déjà fait."

    as_agent = _find_available_as(state)
    if not as_agent: return "⛔ Pas d'AS libre."

    all_rooms = {"consultation": state.consultation_room, **state.waiting_rooms, **state.units}
    target_room = all_rooms.get(target_room_id)
    start_room = all_rooms.get(current_loc)
    if not target_room: return f"❌ Destination inconnue."

    transport_code, return_code = "unknown", "unknown"
    duration, allowed = 0, False

    # 1. WR -> Consult
    if current_loc in state.waiting_rooms and target_room_id == "consultation":
        allowed, duration = True, 5
        transport_code, return_code = "tran_wr_consult", "tran_consult_wr"

    # 2. WR -> Hôpital
    elif current_loc in state.waiting_rooms and target_room_id in state.units:
        if patient.medical_decision != target_room_id: return "⛔ Erreur ordre médical."
        allowed, duration = True, 45
        transport_code, return_code = "tran_wr_hos", "tran_hos_hos"
        stay = random.randint(180, 2880)
        patient.treatment_end_time = current_time + stay + duration

    if not allowed: return "⛔ Trajet escort interdit."
    if int(target_room.occupancy) >= int(target_room.capacity): return f"⛔ {target_room_id} PLEINE."

    log_event(state, "PATIENT", patient_id, transport_code, related_entity=as_agent.id)
    log_event(state, "STAFF", as_agent.id, transport_code, related_entity=patient)

    as_agent.is_busy = True
    as_agent.busy_until = current_time + duration
    as_agent.return_transport_code = return_code

    if target_room_id == "consultation":
        if state.staff["DOC_01"].is_busy: return "⛔ Médecin occupé."
        consult_duration = random.randint(10, 20)
        state.staff["DOC_01"].is_busy = True
        state.staff["DOC_01"].busy_until = current_time + duration + consult_duration

    if start_room:
        start_room.occupancy = max(0, int(start_room.occupancy) - 1)
        if patient_id in start_room.patients: start_room.patients.remove(patient_id)
        
    target_room.occupancy = int(target_room.occupancy) + 1
    target_room.patients.append(patient_id)
    patient.location = target_room_id
    
    _save_state(state)
    return f"✅ Succès : {patient_id} escorté ({transport_code})."

# =============================================================================
# DASHBOARD
# =============================================================================
def get_hospital_dashboard():
    state = _get_state()
    alerts = []
    
    # 1. Alertes Triage & Priorité
    triage_pats = []
    for p_id in state.triage_zone.patients:
        p = state.patients.get(p_id)
        if p:
            triage_pats.append(p)
            if _get_severity_score(p.severity) >= 4: 
                alerts.append(f"🚨 URGENCE : {p.id} (ROUGE) -> Soins Critiques.")

    # 2. Alertes Infirmières (Règle 3)
    for rid, room in state.waiting_rooms.items():
        has_patients = int(room.occupancy) > 0
        has_nurse = _check_staff_in_room(room, "INF")
        if has_patients and not has_nurse:
            alerts.append(f"⚠️ MANQUE STAFF : {room.name} a des patients mais PAS d'infirmier ! (Utilise 'transfer_staff')")

    # 3. Alertes Médicales
    for rid, room in state.waiting_rooms.items():
        for pid in room.patients:
            pat = state.patients.get(pid)
            if pat and pat.medical_decision and pat.medical_decision in state.units:
                alerts.append(f"🛏️ HOSPITALISATION : {pid} -> '{pat.medical_decision}' (Via AS).")

    # 4. Sortie Consult
    cons = state.consultation_room
    if cons.occupancy > 0 and cons.patients:
        pid = cons.patients[0]
        pat = state.patients.get(pid)
        if pat:
            if pat.medical_decision == "exit": alerts.append(f"🏠 SORTIE : {pid} -> Exit.")
            elif pat.medical_decision == "soins_critiques": alerts.append(f"🚨 TRANSFERT SC : {pid} -> Soins Critiques.")

    # STAFF LOCATIONS (Pour aider le LLM)
    inf_locs = [f"{s.id}@{s.location}" for s in state.staff.values() if "infirmier" in s.role]

    report = f"\n=== DASHBOARD (H+{state.time // 60}) ===\n"
    if alerts: report += "\n💥 ACTIONS 💥\n" + "\n".join([f"- {a}" for a in alerts]) + "\n"
    
    report += f"\nINFIRMIERS : {', '.join(inf_locs)}"
    
    return report

def get_patient_list(loc):
    state = _get_state()
    pats = [p for p in state.patients.values() if p.location == loc]
    if not pats: return "Aucun."
    # Tri par gravité pour aider le LLM à respecter la priorité
    pats.sort(key=lambda x: _get_severity_score(x.severity), reverse=True)
    return "\n".join([f"- {p.id} ({p.severity.value}) {f'-> {p.medical_decision}' if p.medical_decision else ''}" for p in pats])