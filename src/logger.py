import json
import os
import datetime
import streamlit as st
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def log_event(state, event_type, entity_id, location, related_entity=None):
    """
    Log un événement en TEMPS RÉEL dans les CSV de session
    
    Args:
        event_type: "PATIENT" ou "STAFF"
        entity_id: ID de l'entité
        location: Localisation ou code d'événement
        related_entity: 
            - Si event PATIENT : ID de l'AS (string ou None)
            - Si event STAFF : Objet Patient complet (ou None)
    """
    
    # Vérifier qu'on a une session CSV active
    if "csv_session_id" not in st.session_state:
        return
    
    hist_dir = os.path.join(BASE_DIR, "data", "historique")
    
    if event_type == "PATIENT":
        pat = state.patients.get(entity_id)
        sev = pat.severity.value if pat else "UNKNOWN"
        
        entry = {
            "timestamp": state.time,
            "id": entity_id,
            "location": location,
            "severity": sev,
            "escort_id": related_entity if isinstance(related_entity, str) else None
        }
        
        # Append au CSV patients
        pat_csv = os.path.join(hist_dir, f"{st.session_state.csv_session_id}_patients.csv")
        df = pd.DataFrame([entry])
        df.to_csv(pat_csv, sep=";", mode='a', header=False, index=False)

    elif event_type == "STAFF":
        # related_entity est l'objet Patient complet
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
        
        # Append au CSV staff
        staff_csv = os.path.join(hist_dir, f"{st.session_state.csv_session_id}_staff.csv")
        df = pd.DataFrame([entry])
        df.to_csv(staff_csv, sep=";", mode='a', header=False, index=False)