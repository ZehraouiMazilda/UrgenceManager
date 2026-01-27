import os
import time
import random
from src.utils import load_initial_state, save_state
from src.logger import log_event 
from src.models import Severity

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(BASE_DIR, "data", "state", "urgence_state.json")

def _get_state(): return load_initial_state(JSON_PATH)
def _save_state(state): save_state(state, JSON_PATH)

# --- ANNUAIRES (FILTRE ABSENTS) ---
def get_staff_directory():
    """Liste les INFIRMIERS présents."""
    state = _get_state()
    lines = []
    for s_id, agent in state.staff.items():
        if "infirmier" in str(agent.role):
            # Si absent mais occupé, on le montre comme indisponible
            if not agent.is_present and not agent.is_busy:
                continue # On le cache totalement
            
            if not agent.is_present and agent.is_busy:
                status = "FIN DE SERVICE (Occupé)"
            else:
                status = "OCCUPÉ" if agent.is_busy else "DISPO"
                
            lines.append(f"- {s_id} ({agent.location}) [{status}]")
    random.shuffle(lines)
    return "\n".join(lines) if lines else "Aucun infirmier disponible."

def get_as_directory():
    """Liste les AIDES-SOIGNANTS présents."""
    state = _get_state()
    lines = []
    for s_id, agent in state.staff.items():
        if "aide" in str(agent.role):
            if not agent.is_present and not agent.is_busy:
                continue # Absent et libre -> Invisible
            
            if agent.is_busy:
                # On montre à l'IA quand il sera libre
                remaining = max(0, agent.busy_until - state.time)
                status = f"OCCUPÉ (Libre dans {remaining} min)"
                if not agent.is_present: status += " [FIN DE SERVICE]"
                lines.append(f"- {s_id} {status}")
            else:
                lines.append(f"- {s_id} (DISPO)")
    return "\n".join(lines) if lines else "Aucun AS disponible."

# --- HELPERS ---
def _check_staff_in_room(room_obj, role_partial_string):
    if not room_obj.staff: return False
    full_state = _get_state()
    for staff_id in room_obj.staff:
        agent = full_state.staff.get(staff_id)
        # On vérifie le rôle ET la présence
        if agent and role_partial_string in str(agent.role) and agent.is_present: 
            return True
    return False

def _find_available_as(state):
    """Cherche un AS libre et PRÉSENT."""
    for s_id, agent in state.staff.items():
        if "aide" in str(agent.role) and not agent.is_busy and agent.is_present:
            return agent
    return None

def _get_severity_score(severity_val):
    val = getattr(severity_val, "value", str(severity_val))
    mapping = {"ROUGE": 4, "JAUNE": 3, "VERT": 2, "GRIS": 1}
    return mapping.get(val, 1)

# =============================================================================
# TOOL 1 : TRANSFERT STAFF
# =============================================================================
def transfer_staff(staff_id: str, target_room_id: str):
    state = _get_state()
    
    if staff_id not in state.staff: return f"❌ Staff {staff_id} introuvable."
    agent = state.staff[staff_id]
    
    if "infirmier" not in str(agent.role): return f"⛔ Seuls les infirmiers peuvent être déplacés."
    if not agent.is_present: return f"⛔ {staff_id} est absent ou en fin de service."

    target_clean = target_room_id.lower().strip() if target_room_id else ""
    current_loc_id = agent.location
    all_rooms = {"triage": state.triage_zone, **state.waiting_rooms, "consultation": state.consultation_room}
    target_room = all_rooms.get(target_clean)
    start_room = all_rooms.get(current_loc_id)
    
    if not target_room: return f"❌ Destination '{target_room_id}' inconnue."
    if current_loc_id == target_clean: return f"⚠️ {staff_id} déjà en {target_room.name}."

    if start_room and staff_id in start_room.staff: start_room.staff.remove(staff_id)
    target_room.staff.append(staff_id)
    agent.location = target_clean
    
    log_event(state, "STAFF", staff_id, f"moved_to_{target_clean}")
    _save_state(state)
    return f"✅ {staff_id} déplacé vers {target_room.name}."

# =============================================================================
# TOOL 2 : TRANSFERT PATIENT
# =============================================================================
def transfer_patient_basic(patient_id: str, target_room_id: str):
    state = _get_state()
    if patient_id not in state.patients: return "❌ Patient introuvable."
    patient = state.patients[patient_id]
    current_loc = patient.location
    target_clean = target_room_id.lower().strip() if target_room_id else ""
    
    if current_loc == target_clean: return f"⚠️ Déjà fait."

    all_rooms = {"triage": state.triage_zone, "consultation": state.consultation_room, "soins_critiques": state.soins_critiques, **state.waiting_rooms, **state.units}
    target_room = all_rooms.get(target_clean)
    start_room = all_rooms.get(current_loc)

    if target_clean == "exit":
        if patient.medical_decision == "exit":
            del state.patients[patient_id]
            if start_room:
                if patient_id in start_room.patients: start_room.patients.remove(patient_id)
                start_room.occupancy = max(0, start_room.occupancy - 1)
            if current_loc == "consultation":
                doc = state.staff.get("DOC_01")
                if doc: doc.is_busy = False
            log_event(state, "PATIENT", patient_id, "exit", related_entity=None)
            _save_state(state)
            return f"✅ Patient {patient_id} SORTI."
        else: return "⛔ Sortie non validée."

    if current_loc == "triage":
        score = _get_severity_score(patient.severity)
        if score >= 4: 
            if target_clean not in ["soins_critiques", "consultation"]: return "⛔ ROUGE -> SC ou Consult uniquement !"
            if target_clean == "consultation":
                doc = state.staff.get("DOC_01")
                if int(state.consultation_room.occupancy) > 0 or (doc and doc.is_busy): return "⛔ Consult OCCUPÉE."

    if target_room and int(target_room.occupancy) >= int(target_room.capacity): return f"⛔ {target_clean} PLEINE."

    if start_room:
        start_room.occupancy = max(0, int(start_room.occupancy) - 1)
        if patient_id in start_room.patients: start_room.patients.remove(patient_id)
    
    target_room.occupancy = int(target_room.occupancy) + 1
    target_room.patients.append(patient_id)
    patient.location = target_clean
    log_event(state, "PATIENT", patient_id, target_clean)
    _save_state(state)
    return f"✅ Succès : {patient_id} vers {target_room.name}."

# =============================================================================
# TOOL 3 : TRANSFERT ESCORTE
# =============================================================================
def transfer_patient_with_escort(patient_id: str, target_room_id: str):
    state = _get_state()
    current_time = state.time
    if patient_id not in state.patients: return "❌ Patient introuvable."
    patient = state.patients[patient_id]
    current_loc = patient.location
    target_clean = target_room_id.lower().strip() if target_room_id else ""

    if current_loc == target_clean: return f"⚠️ Déjà fait."
    
    as_agent = _find_available_as(state)
    if not as_agent: return "⛔ Pas d'AS disponible ou présent."

    all_rooms = {"consultation": state.consultation_room, **state.waiting_rooms, **state.units}
    target_room = all_rooms.get(target_clean)
    start_room = all_rooms.get(current_loc)
    
    if not target_room: return f"❌ Destination inconnue."

    transport_code, return_code = "unknown", "unknown"
    duration, allowed = 0, False

    if current_loc in state.waiting_rooms and target_clean == "consultation":
        allowed, duration = True, 5
        transport_code, return_code = "tran_wr_consult", "tran_consult_wr"
    elif current_loc in state.waiting_rooms and target_clean in state.units:
        if patient.medical_decision != target_clean: return "⛔ Erreur ordre médical."
        allowed, duration = True, 45
        transport_code, return_code = "tran_wr_hos", "tran_hos_hos"
        stay = random.randint(180, 2880)
        patient.treatment_end_time = current_time + stay + duration

    if not allowed: return "⛔ Trajet escort interdit."
    if int(target_room.occupancy) >= int(target_room.capacity): return f"⛔ {target_clean} PLEINE."

    log_event(state, "PATIENT", patient_id, transport_code, related_entity=as_agent.id)
    log_event(state, "STAFF", as_agent.id, transport_code, related_entity=patient)

    as_agent.is_busy = True
    as_agent.busy_until = current_time + duration
    as_agent.return_transport_code = return_code

    if target_clean == "consultation":
        doc = state.staff.get("DOC_01")
        if doc:
            # Si le médecin est absent mais libre (cas rare), on bloque quand même
            if not doc.is_present: return "⛔ Médecin absent."
            if doc.is_busy: return "⛔ Médecin occupé."
            doc.is_busy = True
            doc.busy_until = current_time + duration + random.randint(10, 20)

    if start_room:
        start_room.occupancy = max(0, int(start_room.occupancy) - 1)
        if patient_id in start_room.patients: start_room.patients.remove(patient_id)
        
    target_room.occupancy = int(target_room.occupancy) + 1
    target_room.patients.append(patient_id)
    patient.location = target_clean
    _save_state(state)
    return f"✅ Succès : {patient_id} escorté par {as_agent.id}."

# =============================================================================
# DASHBOARD
# =============================================================================
def get_hospital_dashboard():
    state = _get_state()
    alerts = []
    
    for p_id in state.triage_zone.patients:
        p = state.patients.get(p_id)
        if p and _get_severity_score(p.severity) >= 4:
            alerts.append(f"🚨 URGENCE : {p.id} (ROUGE) -> Soins Critiques OU Consult (si libre) !")

    for p in state.patients.values():
        if p.location in state.waiting_rooms and p.status == "waiting":
            wait_time = state.time - p.arrival_time
            sval = str(p.severity.value) if hasattr(p.severity, 'value') else str(p.severity)
            if sval == "VERT" and wait_time > 40: alerts.insert(0, f"🔥 PRIORITÉ DÉPASSEMENT : {p.id} (VERT) > 40min !")
            if sval == "GRIS" and wait_time > 60: alerts.insert(0, f"🔥 PRIORITÉ DÉPASSEMENT : {p.id} (GRIS) > 60min !")

    for rid, room in state.waiting_rooms.items():
        if int(room.occupancy) > 0 and not _check_staff_in_room(room, "infirmier"):
            alerts.append(f"⚠️ MANQUE STAFF : {room.name} sans infirmier !")

    for rid, room in state.waiting_rooms.items():
        for pid in room.patients:
            pat = state.patients.get(pid)
            if pat and pat.medical_decision and pat.medical_decision in state.units:
                alerts.append(f"🛏️ HOSPITALISATION : {pid} -> '{pat.medical_decision}' (Via AS).")

    cons = state.consultation_room
    doc = state.staff.get("DOC_01")
    # Gestion présence médecin
    if not doc or not doc.is_present:
        cons_status = "⚫ ABSENT"
    else:
        doc_free = "LIBRE" if not doc.is_busy else "OCCUPÉ"
        cons_status = "🟢 LIBRE" if int(cons.occupancy) == 0 and doc_free == "LIBRE" else "🔴 OCCUPÉ"
    
    if cons.occupancy > 0 and cons.patients:
        pid = cons.patients[0]
        pat = state.patients.get(pid)
        if pat:
            if pat.medical_decision == "exit": alerts.append(f"🏠 SORTIE : {pid} -> Exit.")
            elif pat.medical_decision == "soins_critiques": alerts.append(f"🚨 TRANSFERT SC : {pid} -> Soins Critiques.")

    report = f"\n=== DASHBOARD (H+{state.time // 60}) ===\n"
    report += f"CONSULTATION: {cons_status}\n"
    if alerts: report += "\n💥 ACTIONS 💥\n" + "\n".join([f"- {a}" for a in alerts]) + "\n"
    return report

def get_patient_list(loc):
    state = _get_state()
    pats = [p for p in state.patients.values() if p.location == loc]
    if not pats: return "Aucun."
    pats.sort(key=lambda x: _get_severity_score(x.severity), reverse=True)
    return "\n".join([f"- {p.id} ({p.severity.value}) [{state.time - p.arrival_time} min]" for p in pats])