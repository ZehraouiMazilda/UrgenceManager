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
        if "infirmier" in str(agent.role).lower():
            if not agent.is_present and not agent.is_busy: continue 
            status = "OCCUPÉ" if agent.is_busy else "[DISPO]"
            if not agent.is_present: status = "FIN DE SERVICE"
            lines.append(f"- {s_id} ({agent.location}) {status}")
    random.shuffle(lines)
    return "\n".join(lines) if lines else "Aucun infirmier disponible."

def get_as_directory():
    state = _get_state()
    lines = []
    for s_id, agent in state.staff.items():
        if "aide" in str(agent.role).lower():
            if not agent.is_present and not agent.is_busy: continue
            if agent.is_busy:
                remaining = max(0, agent.busy_until - state.time)
                status = f"OCCUPÉ (Libre dans {remaining} min)"
                if not agent.is_present: status += " [FIN DE SERVICE]"
                lines.append(f"- {s_id} {status}")
            else:
                lines.append(f"- {s_id} [DISPO]")
    return "\n".join(lines) if lines else "Aucun AS disponible."

# --- HELPERS ---
def _check_surveillance_in_room(room_obj):
    if not room_obj.staff: return False
    full_state = _get_state()
    for staff_id in room_obj.staff:
        agent = full_state.staff.get(staff_id)
        if agent and agent.is_present:
            if "infirmier" in str(agent.role).lower() or "aide" in str(agent.role).lower():
                return True
    return False

def _find_available_as(state, target_type="consultation"):
    """
    Cherche un AS selon la spécialisation et la présence.
    target_type: "consultation" ou "hospital"
    """
    as1 = state.staff.get("AS_01")
    as2 = state.staff.get("AS_02")
    
    # Définition des priorités
    priority_list = []
    if target_type == "consultation":
        # Prio AS1. Si AS1 absent -> AS2.
        if as1 and as1.is_present: priority_list.append(as1)
        if as2 and as2.is_present: priority_list.append(as2)
    else: # hospital
        # Prio AS2. Si AS2 absent -> AS1.
        if as2 and as2.is_present: priority_list.append(as2)
        if as1 and as1.is_present: priority_list.append(as1)
        
    # On prend le premier DISPONIBLE dans la liste de priorité
    for agent in priority_list:
        if not agent.is_busy:
            return agent
            
    return None

def _get_severity_score(severity_val):
    val = getattr(severity_val, "value", str(severity_val))
    mapping = {"ROUGE": 4, "JAUNE": 3, "VERT": 2, "GRIS": 1}
    return mapping.get(val, 1)

def _normalize_room_id(rid):
    if not rid: return ""
    clean = rid.lower().strip().strip("'").strip('"')
    mapping = {
        "soins critiques": "soins_critiques", "sc": "soins_critiques",
        "consult": "consultation", "box consultation": "consultation",
        "salle 1": "wr_01", "salle 2": "wr_02", "salle 3": "wr_03",
        "exit": "exit"
    }
    return mapping.get(clean, clean)

# =============================================================================
# TOOL 1 : TRANSFERT STAFF (SURVEILLANCE)
# =============================================================================
def transfer_staff(staff_id: str, target_room_id: str):
    """
    Déplace un membre du personnel (INF ou AS) pour surveillance.
    RÈGLES STRICTES DE MOUVEMENT :
    - Uniquement INF ou AS (pas Médecin).
    - Uniquement s'ils sont PRÉSENTS et LIBRES (pas occupés par un soin/transport).
    - Zones autorisées : Triage <-> Salles d'Attente (et entre Salles d'Attente).
    """
    state = _get_state()
    
    # 1. Vérification Identité
    if staff_id not in state.staff: return f"❌ Staff {staff_id} introuvable."
    agent = state.staff[staff_id]
    
    # 2. Vérification Rôle & Disponibilité
    is_inf = "infirmier" in str(agent.role).lower()
    is_as = "aide" in str(agent.role).lower()
    is_doc = "medecin" in str(agent.role).lower()

    if is_doc: return f"⛔ Le médecin ne bouge pas de la consultation."
    if not (is_inf or is_as): return f"⛔ Seuls INF ou AS peuvent être déplacés pour surveillance."
    if not agent.is_present: return f"⛔ {staff_id} est absent(e)."
    if agent.is_busy: return f"⛔ {staff_id} est occupé(e) (Transport ou Soin)."

    # 3. Vérification Destination
    target_clean = _normalize_room_id(target_room_id)
    current_loc = agent.location
    
    all_rooms = {"triage": state.triage_zone, **state.waiting_rooms, "consultation": state.consultation_room}
    target_room = all_rooms.get(target_clean)
    start_room = all_rooms.get(current_loc)
    
    if not target_room: return f"❌ Destination '{target_room_id}' inconnue."
    if current_loc == target_clean: return f"⚠️ Déjà sur place."

    # 4. MATRICE DE DÉPLACEMENTS AUTORISÉS
    # Règle : On ne surveille que les zones d'attente (Triage + Salles).
    # On n'envoie pas de staff surveiller les soins critiques ou les blocs opératoires ici.
    
    ZONE_TRIAGE = ["triage"]
    ZONE_ATTENTE = ["wr_01", "wr_02", "wr_03"]
    
    allowed = False
    
    # Cas 1 : Triage -> Salle Attente
    if current_loc in ZONE_TRIAGE and target_clean in ZONE_ATTENTE: allowed = True
    # Cas 2 : Salle Attente -> Triage
    elif current_loc in ZONE_ATTENTE and target_clean in ZONE_TRIAGE: allowed = True
    # Cas 3 : Salle Attente -> Salle Attente (Rééquilibrage)
    elif current_loc in ZONE_ATTENTE and target_clean in ZONE_ATTENTE: allowed = True
    
    if not allowed:
        return f"⛔ Mouvement interdit : {current_loc} -> {target_clean}. (Autorisé uniquement entre Triage et Salles d'Attente)."

    # 5. Exécution du Mouvement
    # a. Retirer de l'ancienne salle
    if start_room and staff_id in start_room.staff: 
        start_room.staff.remove(staff_id)
    
    # b. Ajouter dans la nouvelle salle
    target_room.staff.append(staff_id)
    
    # c. Mettre à jour le profil de l'agent
    agent.location = target_clean
    
    # d. Logger et Sauvegarder
    log_event(state, "STAFF", staff_id, f"moved_to_{target_clean}")
    _save_state(state)
    
    return f"✅ {staff_id} déplacé vers {target_room.name}."

# =============================================================================
# TOOL 2 : TRANSFERT BASIC (SANS ESCORTE)
# =============================================================================
def transfer_patient_basic(patient_id: str, target_room_id: str):
    """
    Déplacement simple (sans bloquer d'AS).
    
    RÈGLES STRICTES :
    1. Triage -> Soins Critiques (UNIQUEMENT POUR LES ROUGES).
    2. Triage -> Salle d'Attente (Tout le monde).
    3. Salle -> Salle (Tout le monde).
    """
    state = _get_state()
    if patient_id not in state.patients: return "❌ Patient introuvable."
    patient = state.patients[patient_id]
    current_loc = patient.location
    target_clean = _normalize_room_id(target_room_id)
    
    if current_loc == target_clean: return f"⚠️ Déjà fait."

    all_rooms = {"triage": state.triage_zone, "consultation": state.consultation_room, "soins_critiques": state.soins_critiques, **state.waiting_rooms, **state.units}
    target_room = all_rooms.get(target_clean)
    start_room = all_rooms.get(current_loc)

    if not target_room: return f"❌ Destination '{target_room_id}' inconnue."

    # --- 1. DÉFINITION DES ZONES ---
    ZONE_TRIAGE = ["triage"]
    ZONE_ATTENTE = ["wr_01", "wr_02", "wr_03"]
    ZONE_SC = ["soins_critiques"]
    
    # --- 2. WHITELIST GÉOGRAPHIQUE ---
    allowed_geo = False
    
    if current_loc in ZONE_TRIAGE and target_clean in ZONE_SC: allowed_geo = True      # Triage -> SC
    elif current_loc in ZONE_TRIAGE and target_clean in ZONE_ATTENTE: allowed_geo = True # Triage -> Salle
    elif current_loc in ZONE_ATTENTE and target_clean in ZONE_ATTENTE: allowed_geo = True # Salle -> Salle
    
    if not allowed_geo:
        return f"⛔ Trajet interdit via Basic : {current_loc} -> {target_clean}. (Autorisé : Triage->SC, Triage->Salle, Salle->Salle)."

    # --- 3. FILTRE SÉVÉRITÉ (Le point crucial) ---
    
    score = _get_severity_score(patient.severity)
    is_rouge = (score >= 4)
    is_target_sc = (target_clean in ZONE_SC)

    # Règle A : Seuls les Rouges entrent en SC
    if is_target_sc and not is_rouge:
        return f"⛔ INTERDIT : {patient_id} n'est pas ROUGE. Les Soins Critiques sont réservés aux urgences vitales."

    # Règle B : Les Rouges ne devraient pas aller ailleurs que SC ou Salle d'attente
    # (Déjà géré par la Whitelist géographique, mais on confirme la logique)
    if is_rouge and not is_target_sc and target_clean not in ZONE_ATTENTE:
         return "⛔ Un patient ROUGE doit aller en SC (priorité) ou Salle d'Attente (repli)."

    # --- 4. CAPACITÉ ---
    if hasattr(target_room, 'capacity') and int(target_room.occupancy) >= int(target_room.capacity):
        return f"⛔ {target_clean} PLEINE."

    # --- 5. EXÉCUTION ---
# --- NETTOYAGE PRÉVENTIF (Anti-Duplication) ---
    # On parcourt TOUTES les salles pour retirer le patient d'où qu'il soit
    for r_id, room_obj in all_rooms.items():
        if patient_id in room_obj.patients:
            room_obj.patients.remove(patient_id)
            # On recalcule l'occupancy proprement
            room_obj.occupancy = len(room_obj.patients)
    
    target_room.occupancy = int(target_room.occupancy) + 1
    target_room.patients.append(patient_id)
    patient.location = target_clean
    
    # Timer SC
    if target_clean == "soins_critiques":
        patient.treatment_end_time = state.time + random.randint(1440, 2880)

    log_event(state, "PATIENT", patient_id, target_clean)
    _save_state(state)
    return f"✅ {patient_id} -> {target_room.name}."

# =============================================================================
# TOOL 3 : TRANSFERT ESCORTE (TRANSPORT AS)
# =============================================================================
def transfer_patient_with_escort(patient_id: str, target_room_id: str):
    """
    Transport de patient par AS.
    Origine : Triage (ROUGE SEULEMENT) ou Salle d'Attente (Tout le monde).
    Destinations : Consultation OU Hôpital.
    """
    state = _get_state()
    current_time = state.time
    
    # 1. Vérifications de base
    if not patient_id or patient_id not in state.patients: return "❌ Patient introuvable."
    patient = state.patients[patient_id]
    current_loc = patient.location
    target_clean = _normalize_room_id(target_room_id)
    
    # 2. Recherche AS (Le Chauffeur)
    transport_type = "consultation"
    if target_clean in state.units: transport_type = "hospital"
    
    as_agent = _find_available_as(state, transport_type)
    if not as_agent: return "⛔ Pas d'AS disponible pour ce trajet."

    # --- CORRECTION DU BUG DE DOUBLON ICI ---
    # On ajoute "triage": state.triage_zone dans la liste pour pouvoir le nettoyer
    all_rooms = {
        "triage": state.triage_zone, 
        "consultation": state.consultation_room, 
        **state.waiting_rooms, 
        **state.units
    }
    
    target_room = all_rooms.get(target_clean)
    
    if not target_room: return f"❌ Destination '{target_room_id}' inconnue."

    transport_code, return_code = "unknown", "unknown"
    duration = 0
    allowed = False
    
    # Zones
    VALID_WAITING = ["wr_01", "wr_02", "wr_03"]

    # --- BRANCHE A : Vers Consultation ---
    if target_clean == "consultation":
        # A1. Contrôle Origine & Sévérité
        if current_loc == "triage":
            # RÈGLE DU COULOIR RAPIDE
            score = _get_severity_score(patient.severity)
            if score < 4: # Si pas ROUGE
                return "⛔ Triage -> Consult interdit pour non-ROUGE. Passez par une Salle d'Attente."
            allowed = True
            
        elif current_loc in VALID_WAITING:
            allowed = True # OK pour tout le monde depuis la salle d'attente
            
        else:
            return f"⛔ Origine invalide ({current_loc}). Départ autorisé depuis Triage (Rouge) ou Salles d'Attente."

        # A2. Contrôle Médecin & Salle (Si trajet autorisé)
        if allowed:
            doc = state.staff.get("DOC_01")
            if not doc or not doc.is_present: return "⛔ Médecin absent."
            if doc.is_busy: return "⛔ Médecin occupé."
            if int(state.consultation_room.occupancy) > 0: return "⛔ Consultation occupée."
            
            duration = 10 
            transport_code, return_code = "tran_wr_consult", "tran_consult_wr"
            
            # Bloque le médecin
            doc.is_busy = True
            consult_time = random.randint(10, 20)
            doc.busy_until = current_time + duration + consult_time

    # --- BRANCHE B : Vers Hôpital (Boarding) ---
    elif target_clean in state.units:
        # B1. Contrôle Origine (Boarding uniquement)
        if current_loc not in VALID_WAITING:
            return "⛔ Le départ vers l'hôpital se fait depuis une Salle d'Attente (Boarding)."

        # B2. Contrôle Médical
        if patient.medical_decision != target_clean: 
            return f"⛔ Erreur: Décision médicale est '{patient.medical_decision}', pas '{target_clean}'."
            
        allowed = True
        duration = 45 
        transport_code, return_code = "tran_wr_hos", "tran_hos_hos"
        stay = random.randint(180, 1440)
        patient.treatment_end_time = current_time + stay + duration

    # --- BRANCHE C : Rejet ---
    if not allowed: 
        return "⛔ Trajet invalide."
        
    # 4. Vérification Capacité Finale
    if int(target_room.occupancy) >= int(target_room.capacity): return f"⛔ {target_clean} PLEINE."

    # 5. Exécution
    log_event(state, "PATIENT", patient_id, transport_code, related_entity=as_agent.id)
    log_event(state, "STAFF", as_agent.id, transport_code, related_entity=patient)

    # Blocage de l'AS
    as_agent.is_busy = True
    as_agent.busy_until = current_time + duration
    as_agent.return_transport_code = return_code

    # --- NETTOYAGE TOTAL (ANTI-DOUBLON) ---
    # On scanne TOUTES les salles (y compris Triage maintenant) et on supprime le patient
    for r_name, room_obj in all_rooms.items():
        if patient_id in room_obj.patients:
            room_obj.patients.remove(patient_id)
            # On force la mise à jour de l'occupancy
            room_obj.occupancy = len(room_obj.patients)
        
    # Ajout dans la nouvelle salle
    target_room.occupancy = int(target_room.occupancy) + 1
    target_room.patients.append(patient_id)
    patient.location = target_clean
    
    if target_clean in state.units: patient.status = "hospitalized"
    
    _save_state(state)
    return f"✅ {patient_id} escorté par {as_agent.id} vers {target_room.name}."
# =============================================================================
# DASHBOARD
# =============================================================================
def get_hospital_dashboard():
    state = _get_state()
    alerts = []
    
    # 1. ROUGE & Dépassement
    for p in state.patients.values():
        if p.location in state.waiting_rooms or p.location == "triage":
            wait_time = state.time - p.arrival_time
            sev = p.severity.value if hasattr(p.severity, 'value') else str(p.severity)
            
            # Rouge
            if sev == "ROUGE":
                alerts.append(f"🚨 URGENCE VITALE : {p.id} (ROUGE) -> Consult/SC !")
            
            # Anti-Famine
            elif p.status == "waiting":
                is_timeout = (sev == "VERT" and wait_time > 40) or (sev == "GRIS" and wait_time > 60)
                if is_timeout:
                    alerts.insert(0, f"🔥 DÉPASSEMENT DÉLAI : {p.id} ({sev}) > {wait_time}min -> CONSULT PRIORITAIRE !")

    # 2. Sécurité Salles (Nurse OR AS)
    for rid, room in state.waiting_rooms.items():
        if int(room.occupancy) > 0 and not _check_surveillance_in_room(room):
            alerts.append(f"⚠️ MANQUE SURVEILLANCE : {room.name} sans INF ni AS !")

    # 3. Boarding (Attente Hôpital)
    for rid, room in state.waiting_rooms.items():
        for pid in room.patients:
            pat = state.patients.get(pid)
            if pat and pat.medical_decision and pat.medical_decision in state.units:
                alerts.append(f"🛏️ BOARDING : {pid} attend transport vers '{pat.medical_decision}'.")

    # 4. Consult Status
    cons = state.consultation_room
    doc = state.staff.get("DOC_01")
    if not doc or not doc.is_present:
        cons_status = "⚫ ABSENT"
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
    
    # Tri intelligent : Rouge > Timeout > Jaune > Vert > Gris
    def sort_key(p):
        sev = p.severity.value
        wait = state.time - p.arrival_time
        score = _get_severity_score(p.severity) * 100 # Base score (400, 300, 200, 100)
        
        # Bonus Timeout
        if (sev == "VERT" and wait > 40) or (sev == "GRIS" and wait > 60):
            score += 250
        if sev == "ROUGE": score = 1000
        
        return score

    pats.sort(key=sort_key, reverse=True)
    
    lines = []
    for p in pats:
        sev = p.severity.value
        wait = state.time - p.arrival_time
        tag = ""
        
        # Tags visuels pour le LLM
        if sev == "ROUGE": tag = "🚨 [URGENCE VITALE]"
        elif (sev == "VERT" and wait > 40) or (sev == "GRIS" and wait > 60): tag = "🔥 [DÉPASSEMENT]"
        
        # Tag Boarding
        if p.medical_decision and p.medical_decision in state.units:
            tag = f"🛏️ [ATTENTE LIT: {p.medical_decision}]"
        
        lines.append(f"- {p.id} ({sev}) {tag}")
        
    return "\n".join(lines)