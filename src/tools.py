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

# --- ANNUAIRES ---
def get_staff_directory():
    state = _get_state()
    lines = []
    for s_id, agent in state.staff.items():
        # FIX INCOHÉRENCE 6 : Ajouter .lower() pour détecter toutes les casses
        if "infirmier" in str(agent.role).lower():
            if not agent.is_present and not agent.is_busy: continue 
            status = "OCCUPÉ" if agent.is_busy else "[DISPO]"  # FIX INCOHÉRENCE 7 : Tag avec crochets
            if not agent.is_present: status = "FIN DE SERVICE"
            lines.append(f"- {s_id} ({agent.location}) {status}")
    random.shuffle(lines)
    return "\n".join(lines) if lines else "Aucun infirmier disponible."

def get_as_directory():
    state = _get_state()
    lines = []
    for s_id, agent in state.staff.items():
        # FIX INCOHÉRENCE 6 : Ajouter .lower()
        if "aide" in str(agent.role).lower():
            if not agent.is_present and not agent.is_busy: continue
            if agent.is_busy:
                remaining = max(0, agent.busy_until - state.time)
                status = f"OCCUPÉ (Libre dans {remaining} min)"
                if not agent.is_present: status += " [FIN DE SERVICE]"
                lines.append(f"- {s_id} {status}")
            else:
                # FIX INCOHÉRENCE 7 : Tag [DISPO] avec crochets
                lines.append(f"- {s_id} [DISPO]")
    return "\n".join(lines) if lines else "Aucun AS disponible."

# --- HELPERS ---
def _check_surveillance_in_room(room_obj):
    if not room_obj.staff: return False
    full_state = _get_state()
    for staff_id in room_obj.staff:
        agent = full_state.staff.get(staff_id)
        if agent and agent.is_present:
            # FIX INCOHÉRENCE 6 : Ajouter .lower()
            if "infirmier" in str(agent.role).lower() or "aide" in str(agent.role).lower():
                return True
    return False

def _find_available_as(state):
    for s_id, agent in state.staff.items():
        # FIX INCOHÉRENCE 6 : Ajouter .lower()
        if "aide" in str(agent.role).lower() and not agent.is_busy and agent.is_present:
            return agent
    return None

def _get_severity_score(severity_val):
    val = getattr(severity_val, "value", str(severity_val))
    mapping = {"ROUGE": 4, "JAUNE": 3, "VERT": 2, "GRIS": 1}
    return mapping.get(val, 1)

def _normalize_room_id(rid):
    """Nettoie et normalise les IDs de salle pour éviter les erreurs bêtes."""
    if not rid: return ""
    # Enlever espaces et guillemets parasites
    clean = rid.lower().strip().strip("'").strip('"')
    # Mapping des synonymes courants
    mapping = {
        "soins critiques": "soins_critiques",
        "sc": "soins_critiques",
        "consult": "consultation",
        "box consultation": "consultation",
        "salle 1": "wr_01",
        "salle 2": "wr_02",
        "salle 3": "wr_03",
        "exit": "exit"
    }
    return mapping.get(clean, clean)

# =============================================================================
# TOOL 1 : TRANSFERT STAFF
# =============================================================================
def transfer_staff(staff_id: str, target_room_id: str):
    state = _get_state()
    if staff_id not in state.staff: return f"❌ Staff {staff_id} introuvable."
    agent = state.staff[staff_id]
    
    # FIX INCOHÉRENCE 6 : Ajouter .lower()
    is_inf = "infirmier" in str(agent.role).lower()
    is_as = "aide" in str(agent.role).lower()
    
    if not (is_inf or is_as): return f"⛔ Seuls INF ou AS peuvent surveiller."
    if not agent.is_present: return f"⛔ {staff_id} absent."
    if agent.is_busy: return f"⛔ {staff_id} occupé."

    target_clean = _normalize_room_id(target_room_id)
    current_loc_id = agent.location
    
    all_rooms = {"triage": state.triage_zone, **state.waiting_rooms, "consultation": state.consultation_room}
    target_room = all_rooms.get(target_clean)
    start_room = all_rooms.get(current_loc_id)
    
    if not target_room: return f"❌ Destination '{target_room_id}' inconnue."
    if current_loc_id == target_clean: return f"⚠️ Déjà sur place."

    if start_room and staff_id in start_room.staff: start_room.staff.remove(staff_id)
    target_room.staff.append(staff_id)
    agent.location = target_clean
    
    log_event(state, "STAFF", staff_id, f"moved_to_{target_clean}")
    _save_state(state)
    return f"✅ {staff_id} -> {target_room.name}."

# =============================================================================
# TOOL 2 : TRANSFERT BASIC
# =============================================================================
def transfer_patient_basic(patient_id: str, target_room_id: str):
    state = _get_state()
    if patient_id not in state.patients: return "❌ Patient introuvable."
    patient = state.patients[patient_id]
    current_loc = patient.location
    target_clean = _normalize_room_id(target_room_id)
    
    if current_loc == target_clean: return f"⚠️ Déjà fait."

    all_rooms = {"triage": state.triage_zone, "consultation": state.consultation_room, "soins_critiques": state.soins_critiques, **state.waiting_rooms, **state.units}
    target_room = all_rooms.get(target_clean)
    start_room = all_rooms.get(current_loc)

    # Sécurité absolue : si la salle n'existe pas
    if not target_room: return f"❌ Destination '{target_room_id}' inconnue."

    # Règle Rouge
    if current_loc == "triage":
        score = _get_severity_score(patient.severity)
        if score >= 4: # Rouge
            if target_clean not in ["soins_critiques", "consultation"] and target_clean not in state.waiting_rooms:
                return "⛔ ROUGE -> SC, Consult ou Salle d'Attente uniquement."
    
    # Capacité
    if hasattr(target_room, 'capacity') and int(target_room.occupancy) >= int(target_room.capacity):
        return f"⛔ {target_clean} PLEINE."

    if start_room:
        start_room.occupancy = max(0, int(start_room.occupancy) - 1)
        if patient_id in start_room.patients: start_room.patients.remove(patient_id)
    
    target_room.occupancy = int(target_room.occupancy) + 1
    target_room.patients.append(patient_id)
    patient.location = target_clean
    
    # FIX INCOHÉRENCE 8 : Durée SC 24-48h (1440-2880 min) au lieu de 12-24h
    if target_clean == "soins_critiques":
        patient.treatment_end_time = state.time + random.randint(1440, 2880)

    log_event(state, "PATIENT", patient_id, target_clean)
    _save_state(state)
    return f"✅ {patient_id} -> {target_room.name}."

# =============================================================================
# TOOL 3 : TRANSFERT ESCORTE (TIMINGS CORRIGÉS)
# =============================================================================
def transfer_patient_with_escort(patient_id: str, target_room_id: str):
    state = _get_state()
    current_time = state.time
    if not patient_id or patient_id not in state.patients: return "❌ Patient introuvable."
    patient = state.patients[patient_id]
    current_loc = patient.location
    target_clean = _normalize_room_id(target_room_id)
    
    as_agent = _find_available_as(state)
    if not as_agent: return "⛔ Pas d'AS disponible."

    all_rooms = {"consultation": state.consultation_room, **state.waiting_rooms, **state.units}
    target_room = all_rooms.get(target_clean)
    start_room = all_rooms.get(current_loc)
    
    if not target_room: return f"❌ Destination '{target_room_id}' inconnue."

    transport_code, return_code = "unknown", "unknown"
    duration = 0
    allowed = False

    # CAS A : Vers Consultation
    if current_loc in state.waiting_rooms and target_clean == "consultation":
        doc = state.staff.get("DOC_01")
        if not doc or not doc.is_present: return "⛔ Médecin absent."
        if doc.is_busy: return "⛔ Médecin occupé."
        if int(state.consultation_room.occupancy) > 0: return "⛔ Consultation occupée."
        
        allowed = True
        # FIX INCOHÉRENCE 9 : 5 min (1 tick = visible 1 sec en mode accéléré)
        duration = 5
        transport_code, return_code = "tran_wr_consult", "tran_consult_wr"
        
        doc.is_busy = True
        consult_time = random.randint(10, 20)
        doc.busy_until = current_time + duration + consult_time

    # CAS B : Vers Hôpital (Boarding)
    elif current_loc in state.waiting_rooms and target_clean in state.units:
        allowed = True
        # FIX INCOHÉRENCE 10 : 45 min (9 ticks = visible ~9 sec)
        duration = 45
        transport_code, return_code = "tran_wr_hos", "tran_hos_hos"
        stay = random.randint(180, 1440)
        patient.treatment_end_time = current_time + stay + duration

    if not allowed: return "⛔ Trajet escort invalide (uniquement Salle->Consult ou Salle->Hôpital)."
    if int(target_room.occupancy) >= int(target_room.capacity): return f"⛔ {target_clean} PLEINE."

    # Execution
    log_event(state, "PATIENT", patient_id, transport_code, related_entity=as_agent.id)
    log_event(state, "STAFF", as_agent.id, transport_code, related_entity=patient)

    as_agent.is_busy = True
    as_agent.busy_until = current_time + duration
    as_agent.return_transport_code = return_code

    if start_room:
        start_room.occupancy = max(0, int(start_room.occupancy) - 1)
        if patient_id in start_room.patients: start_room.patients.remove(patient_id)
        
    target_room.occupancy = int(target_room.occupancy) + 1
    target_room.patients.append(patient_id)
    patient.location = target_clean
    if target_clean in state.units: patient.status = "hospitalized"
    
    _save_state(state)
    return f"✅ {patient_id} escorté par {as_agent.id} vers {target_room.name}."

# =============================================================================
# DASHBOARD ET LISTES
# =============================================================================
def get_hospital_dashboard():
    state = _get_state()
    alerts = []
    for p in state.patients.values():
        if p.location in state.waiting_rooms or p.location == "triage":
            wait_time = state.time - p.arrival_time
            sev = p.severity.value if hasattr(p.severity, 'value') else str(p.severity)
            if sev == "ROUGE":
                alerts.append(f"🚨 URGENCE VITALE : {p.id} (ROUGE) -> Consult/SC !")
            elif p.status == "waiting":
                is_timeout = (sev == "VERT" and wait_time > 40) or (sev == "GRIS" and wait_time > 60)
                if is_timeout:
                    alerts.insert(0, f"🔥 DÉPASSEMENT DÉLAI : {p.id} ({sev}) > {wait_time}min -> CONSULT PRIORITAIRE !")
    for rid, room in state.waiting_rooms.items():
        if int(room.occupancy) > 0 and not _check_surveillance_in_room(room):
            alerts.append(f"⚠️ MANQUE SURVEILLANCE : {room.name} sans INF ni AS !")
    for rid, room in state.waiting_rooms.items():
        for pid in room.patients:
            pat = state.patients.get(pid)
            if pat and pat.medical_decision and pat.medical_decision in state.units:
                alerts.append(f"🛏️ BOARDING : {pid} attend transport vers '{pat.medical_decision}'.")
    cons = state.consultation_room
    doc = state.staff.get("DOC_01")
    if not doc or not doc.is_present: cons_status = "⚫ ABSENT"
    else:
        doc_free = "LIBRE" if not doc.is_busy else "OCCUPÉ"
        cons_status = "🟢 LIBRE" if int(cons.occupancy) == 0 and doc_free == "LIBRE" else "🔴 OCCUPÉ"
    report = f"\n=== DASHBOARD (H+{state.time // 60}) ===\n"
    report += f"CONSULTATION: {cons_status}\n"
    if alerts: report += "\n💥 ACTIONS REQUISES 💥\n" + "\n".join([f"- {a}" for a in alerts]) + "\n"
    return report

def get_patient_list(loc):
    state = _get_state()
    pats = [p for p in state.patients.values() if p.location == loc]
    if not pats: return "Aucun."
    def sort_key(p):
        sev = p.severity.value
        wait = state.time - p.arrival_time
        score = _get_severity_score(p.severity) * 100
        if (sev == "VERT" and wait > 40) or (sev == "GRIS" and wait > 60): score += 350 
        if sev == "ROUGE": score = 1000
        return score
    pats.sort(key=sort_key, reverse=True)
    lines = []
    for p in pats:
        sev = p.severity.value
        wait = state.time - p.arrival_time
        tag = ""
        if sev == "ROUGE": tag = "🚨 [URGENCE VITALE]"
        elif (sev == "VERT" and wait > 40) or (sev == "GRIS" and wait > 60): tag = "🔥 [DÉPASSEMENT]"
        if p.medical_decision and p.medical_decision in state.units: tag = f"🛏️ [ATTENTE LIT: {p.medical_decision}]"
        lines.append(f"- {p.id} ({sev}) {tag}")
    return "\n".join(lines)