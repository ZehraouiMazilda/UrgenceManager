import sys
import os
import json
import re
from dotenv import load_dotenv
from mistralai import Mistral
from src.tools import (
    get_hospital_dashboard, 
    get_patient_list, 
    transfer_patient_basic, 
    transfer_patient_with_escort, 
    transfer_staff, 
    get_staff_directory, 
    get_as_directory, 
    _get_state
)

load_dotenv()
api_key = os.getenv("MISTRAL_API_KEY")
if not api_key: api_key = "dummy_key"

MODEL_NAME = "mistral-large-latest" 
client = Mistral(api_key=api_key)

SYSTEM_PROMPT = """
Tu es le CHEF DE RÉGULATION DES URGENCES HOSPITALIÈRES.

=== CONTEXTE ===
Organisation : Service d'Urgences d'un hôpital public
Ton rôle : Gérer le flux de patients et le personnel
Objectif : Maximiser la fluidité, garantir la sécurité, optimiser les ressources
Unité de temps : 1 cycle = 5 minutes réelles

Tu gères : Triage → Salles → Consultation → Hôpital + Surveillance

=== TES CAPACITÉS ===

1. **transfer_basic** (Sans escorte)
   - Trajets : Triage → SC, Triage → Salle
   
2. **transfer_escort** (Avec AS)
   - Trajets : 
     * Triage → Consultation (ROUGE uniquement)
     * Salle → Consultation (toutes couleurs)
     * Salle → Hôpital (patients avec medical_decision)
   
3. **transfer_staff** (Déplacement personnel)
   - Pour surveillance des salles

=== RÈGLES MÉTIER ===

🔴 **ROUGE au Triage - Ordre strict :**
1. SC (si place) → transfer_basic
2. Consultation (si SC plein + AS dispo + Médecin dispo) → transfer_escort
3. Salle (fallback) → transfer_basic

🟡🟢⚪ **JAUNE/VERT/GRIS au Triage :**
- → Salle (transfer_basic)

🚑 **AS_01 :** Priorité Consultation > Hôpital (si AS_02 absente) > Surveillance
🚑 **AS_02 :** Priorité Hôpital > Consultation (si AS_01 absente) > Surveillance

👩‍⚕️ **INF_TRIAGE :** Reste au Triage (sauf si 2 autres absentes)
👩‍⚕️ **INF_SALLE :** Surveillance salles (15 min max sans staff)

=== ALGORITHME DE PRIORITÉS ===

🎯 **PRIORITÉ 1 : BOARDING (Évacuer vers hôpital)**
- Chercher : Patients en Salle avec tag 🛏️ [ATTENTE LIT]
- Vérifier : AS dispo + Service a place
- Action : transfer_escort(patient_id, service)

🎯 **PRIORITÉ 2 : SÉCURITÉ (Surveillance)**
- Chercher : Salle avec patients MAIS aucun staff > 15 min
- Action : transfer_staff(staff_dispo, salle_id)

🎯 **PRIORITÉ 3 : ÉVACUER TRIAGE**
- ROUGE : SC → Consultation → Salle
- JAUNE/VERT/GRIS : Salle (batch 3-5)

🎯 **PRIORITÉ 4 : OPTIMISATION**
- Équilibrage salles (optionnel)

=== FORMAT RÉPONSE (JSON) ===
{
  "actions": [
    {
      "type": "transfer_escort",
      "patient_id": "PAT_001",
      "target_room_id": "ortho",
      "justification": "Boarding → Orthopédie"
    }
  ]
}

Maximum 5 actions par cycle.
"""

def clean_json_response(raw_text):
    try:
        text = raw_text.replace("```json", "").replace("```", "").strip()
        start_idx = text.find('{'); end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1: text = text[start_idx : end_idx + 1]
        text = text.replace('\n', ' ').replace('\r', '')
        return text
    except: return raw_text

def call_llm_api(context_text):
    try:
        chat_response = client.chat.complete(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": context_text}],
            temperature=0.0,
        )
        return clean_json_response(chat_response.choices[0].message.content)
    except Exception as e:
        print(f"[ERREUR] Appel API Mistral : {e}")
        return json.dumps({"actions": []})

def process_brain_cycle():
    try:
        state = _get_state()
        dashboard = get_hospital_dashboard()
        
        c1, c2, c3 = state.waiting_rooms['wr_01'], state.waiting_rooms['wr_02'], state.waiting_rooms['wr_03']
        sc = state.soins_critiques
        
        free1, free2, free3 = c1.capacity - c1.occupancy, c2.capacity - c2.occupancy, c3.capacity - c3.occupancy

        # État de la consultation
        cons = state.consultation_room
        cons_status = "🟢 LIBRE" if cons.occupancy == 0 else "🔴 OCCUPÉE"

        details = "\n".join([
            f"TRIAGE (En attente: {len(state.triage_zone.patients)}):\n{get_patient_list('triage')}",
            f"\nCONSULTATION [{cons_status}]:\n{get_patient_list('consultation')}",
            f"\nSALLE 1 (wr_01) [Places Libres: {free1}/{c1.capacity}]:\n{get_patient_list('wr_01')}",
            f"SALLE 2 (wr_02) [Places Libres: {free2}/{c2.capacity}]:\n{get_patient_list('wr_02')}",
            f"SALLE 3 (wr_03) [Places Libres: {free3}/{c3.capacity}]:\n{get_patient_list('wr_03')}",
            f"\nSOINS CRITIQUES [Occupé: {sc.occupancy}/{sc.capacity}]:\n{get_patient_list('soins_critiques')}"
        ])
        
        staff_info = f"INFIRMIERS:\n{get_staff_directory()}\n\nAIDES-SOIGNANTS:\n{get_as_directory()}"
        
        full_prompt = f"{dashboard}\n\n=== RESSOURCES ===\n{staff_info}\n\n=== PATIENTS & CAPACITÉS ===\n{details}"

        llm_response_str = call_llm_api(full_prompt)
        print(f"\n🧠 [IA RAW]: {llm_response_str}\n")
        
        try:
            decision = json.loads(llm_response_str, strict=False)
            actions_list = decision.get("actions", [])
            if not actions_list: return None 

            logs_output = []
            
            # Helper pour formater les noms de lieux
            def get_location_name(loc_id):
                names = {
                    "triage": "Triage",
                    "wr_01": "Salle 1",
                    "wr_02": "Salle 2",
                    "wr_03": "Salle 3",
                    "soins_critiques": "Soins Critiques",
                    "consultation": "Consultation",
                    "ortho": "Orthopédie",
                    "cardio": "Cardiologie",
                    "neuro": "Neurologie",
                    "pneumo": "Pneumologie"
                }
                return names.get(loc_id, loc_id)
            
            for act in actions_list:
                action_type = act.get("type")
                pid, sid = act.get("patient_id"), act.get("staff_id")
                dest, justif = act.get("target_room_id"), act.get("justification", "Auto")

                res = "Erreur"
                detailed_log = None
                
                # Transfer Basic
                if action_type == "transfer_basic":
                    if pid and pid in state.patients:
                        patient = state.patients[pid]
                        from_loc = patient.location
                        severity = patient.severity.value if hasattr(patient.severity, 'value') else str(patient.severity)
                        
                        res = transfer_patient_basic(pid, dest)
                        
                        if "✅" in res:
                            severity_icons = {"ROUGE": "🔴", "JAUNE": "🟡", "VERT": "🟢", "GRIS": "⚪"}
                            icon = severity_icons.get(severity, "")
                            from_name = get_location_name(from_loc)
                            to_name = get_location_name(dest)
                            
                            detailed_log = f"{icon} **{pid}** ({severity}) : {from_name} → {to_name}"
                            
                            if dest == "soins_critiques":
                                detailed_log += " (durée: 24-48h)"
                    else:
                        res = transfer_patient_basic(pid, dest)
                
                # Transfer Escort
                elif action_type == "transfer_escort":
                    if pid and pid in state.patients:
                        patient = state.patients[pid]
                        from_loc = patient.location
                        severity = patient.severity.value if hasattr(patient.severity, 'value') else str(patient.severity)
                        
                        res = transfer_patient_with_escort(pid, dest)
                        
                        if "✅" in res:
                            # Extraire l'AS du message de résultat
                            as_match = re.search(r'escorté par (AS_\d+)', res)
                            as_id = as_match.group(1) if as_match else "AS"
                            
                            from_name = get_location_name(from_loc)
                            to_name = get_location_name(dest)
                            
                            # Déterminer la durée selon la destination
                            if dest == "consultation":
                                duration = 5
                            elif dest in ["ortho", "cardio", "neuro", "pneumo"]:
                                duration = 45
                            else:
                                duration = "?"
                            
                            detailed_log = f"🚑 **{pid}** escorté par **{as_id}** : {from_name} → {to_name} (durée: {duration} min)"
                    else:
                        res = transfer_patient_with_escort(pid, dest)
                
                # Transfer Staff
                elif action_type == "transfer_staff":
                    if not sid: continue
                    
                    if sid in state.staff:
                        agent = state.staff[sid]
                        from_loc = agent.location
                        
                        res = transfer_staff(sid, dest)
                        
                        if "✅" in res:
                            icon = "👩‍⚕️" if "INF" in sid else "🚑"
                            from_name = get_location_name(from_loc)
                            to_name = get_location_name(dest)
                            
                            detailed_log = f"{icon} **{sid}** : {from_name} → {to_name} (surveillance)"
                    else:
                        res = transfer_staff(sid, dest)
                
                # Ajouter le log (enrichi si disponible, sinon standard)
                if detailed_log and "✅" in res:
                    logs_output.append(detailed_log)
                elif "⚠️ Déjà" not in res and "introuvable" not in res:
                    logs_output.append(f"👉 {justif} : {res}")

            if not logs_output: return None
            return "\n".join(logs_output)

        except json.JSONDecodeError as e:
            print(f"[ERREUR] JSON invalide : {llm_response_str}")
            return f"❌ Erreur JSON"

    except Exception as e:
        print(f"[ERREUR] Brain cycle : {e}")
        import traceback
        traceback.print_exc()
        return f"🚨 Erreur Brain"