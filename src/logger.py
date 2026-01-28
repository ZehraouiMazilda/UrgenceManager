import json
import os
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(BASE_DIR, "data", "history_logs.json")

def log_event(state, event_type, entity_id, location, related_entity=None):
    """
    event_type: "PATIENT" ou "STAFF"
    related_entity: L'objet Patient (si event STAFF) ou l'ID Staff (si event PATIENT)
    """
    # 1. Charger l'historique
    try:
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "r", encoding='utf-8') as f:
                history = json.load(f)
        else:
            history = []
    except Exception:
        history = []

    # 2. Créer une session si vide
    if not history:
        history.append({
            "session_id": f"SESSION_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "logs_patients": [],
            "logs_staff": []
        })
    
    current_session = history[-1]

    # 3. Ajouter le log
    if event_type == "PATIENT":
        # On récupère l'objet patient du state pour avoir la gravité à jour
        pat = state.patients.get(entity_id)
        sev = pat.severity.value if pat else "UNKNOWN"
        
        entry = {
            "timestamp": state.time,
            "id": entity_id,
            "location": location,
            "severity": sev,
            "escort_id": related_entity # related_entity est l'ID de l'AS
        }
        current_session["logs_patients"].append(entry)

    elif event_type == "STAFF":
        # related_entity est l'objet Patient complet (s'il transporte quelqu'un)
        p_id = related_entity.id if related_entity else None
        p_symp = related_entity.symptom if related_entity else None
        p_col = related_entity.severity.value if related_entity else None
        
        entry = {
            "timestamp": state.time,
            "id": entity_id,
            "location": location,
            "patient_handling_id": p_id,
            "patient_symptom": p_symp,
            "patient_color": p_col
        }
        current_session["logs_staff"].append(entry)

    # 4. Sauvegarder
    with open(LOG_PATH, "w", encoding='utf-8') as f:
        json.dump(history, f, indent=2)