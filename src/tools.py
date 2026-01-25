import os
from src.utils import load_initial_state, save_state

# Chemin vers le JSON (Le Cerveau Disque Dur)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(BASE_DIR, "data", "state", "urgence_state.json")

def _get_state():
    """Fonction helper pour charger l'état frais"""
    return load_initial_state(JSON_PATH)

def _save_state(state):
    """Fonction helper pour sauvegarder"""
    save_state(state, JSON_PATH)

# =============================================================================
# 🔧 OUTIL 1 : OBSERVATION (Les Yeux)
# =============================================================================

def get_hospital_status():
    """
    Renvoie un résumé textuel de l'hôpital pour le LLM.
    Il ne donne pas tout le JSON brut, mais l'essentiel pour décider.
    """
    state = _get_state()
    
    report = f"--- ETAT HOPITAL (Temps: {state.time // 60}h{state.time % 60}) ---\n"
    
    # 1. Triage
    nb_triage = len([p for p in state.patients.values() if p.location == "triage"])
    report += f"📍 Triage : {nb_triage} patients en attente.\n"
    
    # 2. Salles d'Attente
    for rid, room in state.waiting_rooms.items():
        report += f"📍 {room.name} ({rid}) : {room.occupancy}/{room.capacity} places.\n"
        
    # 3. Box Consultation
    doc_status = "Occupé" if state.staff["DOC_01"].is_busy else "Libre"
    report += f"📍 Consultation : Médecin {doc_status}. Attente: {state.consultation_room.occupancy}/{state.consultation_room.capacity}\n"
    
    # 4. Unités (Hospitalisation)
    report += "📍 UNITÉS SPÉCIALISÉES :\n"
    for uid, unit in state.units.items():
        report += f"   - {unit.name} ({uid}) : {unit.occupancy}/{unit.capacity}\n"
        
    return report

def get_patient_list(location="triage"):
    """
    Renvoie la liste des patients à un endroit précis.
    Le LLM l'utilisera pour savoir QUI déplacer.
    """
    state = _get_state()
    
    # On filtre les patients
    patients = [p for p in state.patients.values() if p.location == location]
    
    if not patients:
        return f"Aucun patient en zone '{location}'."
    
    # On formate une liste propre pour le LLM
    # Ex: "PAT_01 (ROUGE): Douleur thoracique"
    p_list_txt = ""
    for p in patients:
        p_list_txt += f"- ID: {p.id} | Gravité: {p.severity.value} | Symptôme: {p.symptom}\n"
        
    return p_list_txt

# =============================================================================
# 🔧 OUTIL 2 : ACTION (Les Mains)
# =============================================================================

def move_patient(patient_id: str, target_room_id: str):
    """
    Déplace un patient d'un point A vers un point B.
    ✅ Applique les règles de CAPACITÉ et de COHÉRENCE.
    """
    state = _get_state()
    
    # --- RÈGLE 1 : Le patient existe-t-il ? ---
    if patient_id not in state.patients:
        return f"❌ Erreur : Patient {patient_id} introuvable."
    
    patient = state.patients[patient_id]
    current_loc = patient.location
    
    # --- RÈGLE 2 : La salle de destination existe-t-elle ? ---
    # On doit chercher l'objet "Room" correspondant à l'ID (un peu complexe car structure imbriquée)
    target_room = None
    target_type = "" # Pour savoir dans quel dict chercher
    
    # Recherche dans les différentes catégories de salles
    if target_room_id == "triage":
        target_room = state.triage_zone
        target_type = "triage"
    elif target_room_id == "consultation":
        target_room = state.consultation_room
        target_type = "consultation"
    elif target_room_id == "soins_critiques":
        target_room = state.soins_critiques
        target_type = "critique"
    elif target_room_id in state.waiting_rooms:
        target_room = state.waiting_rooms[target_room_id]
        target_type = "waiting"
    elif target_room_id in state.units:
        target_room = state.units[target_room_id]
        target_type = "unit"
        
    if not target_room:
        return f"❌ Erreur : Salle de destination '{target_room_id}' inconnue."

    # --- RÈGLE 3 : Y a-t-il de la place ? (CAPACITÉ MAX) ---
    if target_room.occupancy >= target_room.capacity:
        return f"⛔ ACTION REFUSÉE : La salle {target_room.name} est PLEINE ({target_room.occupancy}/{target_room.capacity})."

    # --- EXÉCUTION DU MOUVEMENT (Si tout est OK) ---
    
    # 1. Retirer de l'ancienne salle (Logique inverse)
    # (Note : Pour faire simple ici, on ne décrémente pas l'ancienne salle car on n'a pas son ID direct, 
    # mais dans une V2 on fera ça proprement. Ici on suppose que le système s'auto-corrige ou on accepte l'imperfection pour le hackathon)
    # Pour bien faire, on va essayer de trouver l'ancienne salle
    old_room = None
    if current_loc == "triage": old_room = state.triage_zone
    elif current_loc in state.waiting_rooms: old_room = state.waiting_rooms[current_loc]
    elif current_loc == "consultation": old_room = state.consultation_room
    # ... etc
    
    if old_room and old_room.occupancy > 0:
        old_room.occupancy -= 1
        # On nettoie la liste des IDs si on l'utilise
        if patient_id in old_room.patients:
            old_room.patients.remove(patient_id)

    # 2. Ajouter dans la nouvelle salle
    target_room.occupancy += 1
    target_room.patients.append(patient_id)
    
    # 3. Mettre à jour le patient
    patient.location = target_room_id
    
    # 4. Règles Spéciales (Effets de bord)
    if target_type == "consultation":
        # Si on entre en consult, le médecin devient occupé
        if "DOC_01" in state.staff:
            state.staff["DOC_01"].is_busy = True
            
    if target_type == "waiting" and current_loc == "consultation":
        # Si on sort de consult, le médecin se libère
        if "DOC_01" in state.staff:
            state.staff["DOC_01"].is_busy = False

    # 5. SAUVEGARDE
    _save_state(state)
    
    return f"✅ Succès : Patient {patient_id} déplacé vers {target_room.name}."