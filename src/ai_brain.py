import sys
import os
import json
import re
import time  
from typing import Optional, Dict, List, Any
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
api_key: Optional[str] = os.getenv("MISTRAL_API_KEY")
if not api_key: api_key = "dummy_key"

client: Mistral = Mistral(api_key=api_key)

# MODÈLE PAR DÉFAUT 
CURRENT_MODEL: str = "mistral-large-latest"
    
SYSTEM_PROMPT: str = """
Tu es le CHEF DE RÉGULATION DES URGENCES HOSPITALIÈRES.
Ta mission : Piloter le flux patient en respectant STRICTEMENT les protocoles médicaux et logistiques.

=== TES OUTILS (ACTIONS POSSIBLES) ===

1. **transfer_basic** (Déplacement SANS personnel)
   - Cibles autorisées : 
     * Triage → Soins Critiques (SC) [Uniquement si ROUGE]
     * Triage → Salle d'Attente (wr_01, wr_02, wr_03)
     * Salle d'Attente → Salle d'Attente
   - ⛔ INTERDIT : Vers Consultation ou Hôpital (nécessite escorte).

2. **transfer_escort** (Transport AVEC Aide-Soignant)
   - Cibles autorisées :
     * Triage → Consultation [Uniquement si ROUGE + Médecin LIBRE + AS DISPO] (Couloir Rapide)
     * Salle d'Attente → Consultation [Si Médecin LIBRE + AS DISPO]
     * Salle d'Attente → Hôpital (Unités) [Si décision médicale validée + AS DISPO]

3. **transfer_staff** (Surveillance)
   - Déplacer un Infirmier ou AS vers une salle pour surveiller des patients.
   - Cibles : Triage <-> Salles d'Attente.

=== RÈGLES DE PRIORITÉ (A SUIVRE DANS L'ORDRE) ===

🔥 **PRIORITÉ 0 : URGENCES VITALES (ROUGE)**
- Si un ROUGE est au Triage :
  A. Tenter SC via `transfer_basic`.
  B. Si SC plein : Tenter Consultation via `transfer_escort` (Couloir Rapide).
  C. Si tout plein : Mettre en Salle d'Attente via `transfer_basic`.

⚡ **PRIORITÉ 1 : LIBÉRER LA CONSULTATION**
- Si Consultation LIBRE et Médecin DISPO :
  - Cherche le patient le plus prioritaire en Salle d'Attente (ROUGE > JAUNE > VERT > GRIS).
  - Action : `transfer_escort(patient_id, "consultation")`.
  - ⚠️ Vérifie qu'un AS est disponible ("AS_01" ou "AS_02").

🛏️ **PRIORITÉ 2 : SORTIE HÔPITAL (BOARDING)**
- Si un patient en Salle d'Attente a un tag "ATTENTE LIT" (ex: "ortho") :
  - Action : `transfer_escort(patient_id, "ortho")`.
  - ⚠️ Nécessite un AS disponible (long trajet 45min).

👀 **PRIORITÉ 3 : SÉCURITÉ (MANQUE SURVEILLANCE)**
- Si le Dashboard signale "⚠️ MANQUE SURVEILLANCE" dans une salle :
  - Trouve un staff DISPO (Infirmier ou AS).
  - Action : `transfer_staff(staff_id, salle_id)`.

🧹 **PRIORITÉ 4 : DÉSENCOMBRER LE TRIAGE**
- Si pas d'urgence vitale, déplace les patients (Jaune/Vert/Gris) vers les Salles d'Attente via `transfer_basic`.
- Remplis les salles intelligemment (wr_01, puis wr_02...).

=== FORMAT DE RÉPONSE ATTENDU (JSON PUR) ===
{
  "actions": [
    {
      "type": "transfer_escort",
      "patient_id": "PAT_001",
      "target_room_id": "consultation",
      "justification": "Priorité Rouge vers médecin libre"
    },
    {
      "type": "transfer_staff",
      "staff_id": "INF_02",
      "target_room_id": "wr_01",
      "justification": "Surveillance requise"
    }
  ]
}
"""

def clean_json_response(raw_text: str) -> str:
    try:
        text: str = raw_text.replace("```json", "").replace("```", "").strip()
        start_idx: int = text.find('{'); end_idx: int = text.rfind('}')
        if start_idx != -1 and end_idx != -1: text = text[start_idx : end_idx + 1]
        text = text.replace('\n', ' ').replace('\r', '')
        return text
    except: return raw_text


def call_llm_api(context_text: str) -> str:
    max_retries: int = 3
    base_delay: int = 3

    for attempt in range(max_retries):
        try:
            chat_response = client.chat.complete(
                model=CURRENT_MODEL,  
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": context_text}],
                temperature=0.0,
            )
            return clean_json_response(chat_response.choices[0].message.content)

        except Exception as e:
            error_msg: str = str(e)
            
            if "429" in error_msg:
                wait_time: int = base_delay * (attempt + 1)
                print(f"⚠️ [API] Trop rapide (429). Pause de {wait_time}s avant réessai ({attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                print(f"🚨 [ERREUR] Appel API Mistral : {e}")
                return json.dumps({"actions": []})

    print("❌ [ABANDON] Echec API après plusieurs tentatives.")
    return json.dumps({"actions": []})

def process_brain_cycle() -> Optional[str]:
    try:
        state = _get_state()
        dashboard: str = get_hospital_dashboard()
        
        c1, c2, c3 = state.waiting_rooms['wr_01'], state.waiting_rooms['wr_02'], state.waiting_rooms['wr_03']
        sc = state.soins_critiques
        
        free1: int
        free2: int
        free3: int
        free1, free2, free3 = c1.capacity - c1.occupancy, c2.capacity - c2.occupancy, c3.capacity - c3.occupancy

        cons = state.consultation_room
        cons_status: str = "🟢 LIBRE" if cons.occupancy == 0 else "🔴 OCCUPÉE"

        details: str = "\n".join([
            f"TRIAGE (En attente: {len(state.triage_zone.patients)}):\n{get_patient_list('triage')}",
            f"\nCONSULTATION [{cons_status}]:\n{get_patient_list('consultation')}",
            f"\nSALLE 1 (wr_01) [Places Libres: {free1}/{c1.capacity}]:\n{get_patient_list('wr_01')}",
            f"SALLE 2 (wr_02) [Places Libres: {free2}/{c2.capacity}]:\n{get_patient_list('wr_02')}",
            f"SALLE 3 (wr_03) [Places Libres: {free3}/{c3.capacity}]:\n{get_patient_list('wr_03')}",
            f"\nSOINS CRITIQUES [Occupé: {sc.occupancy}/{sc.capacity}]:\n{get_patient_list('soins_critiques')}"
        ])
        
        staff_info: str = f"INFIRMIERS:\n{get_staff_directory()}\n\nAIDES-SOIGNANTS:\n{get_as_directory()}"
        
        full_prompt: str = f"{dashboard}\n\n=== RESSOURCES ===\n{staff_info}\n\n=== PATIENTS & CAPACITÉS ===\n{details}"

        llm_response_str: str = call_llm_api(full_prompt)
        print(f"\n🧠 [IA RAW]: {llm_response_str}\n")
        
        try:
            decision: Dict[str, Any] = json.loads(llm_response_str, strict=False)
            actions_list: List[Dict[str, Any]] = decision.get("actions", [])
            if not actions_list: return None 

            logs_output: List[str] = []
            
            def get_location_name(loc_id: str) -> str:
                names: Dict[str, str] = {
                    "triage": "Triage", "wr_01": "Salle 1", "wr_02": "Salle 2", "wr_03": "Salle 3",
                    "soins_critiques": "Soins Critiques", "consultation": "Consultation",
                    "ortho": "Orthopédie", "cardio": "Cardiologie", "neuro": "Neurologie", "pneumo": "Pneumologie"
                }
                return names.get(loc_id, loc_id)
            
            for act in actions_list:
                action_type: Optional[str] = act.get("type")
                pid: Optional[str]
                sid: Optional[str]
                pid, sid = act.get("patient_id"), act.get("staff_id")
                dest: Optional[str]
                justif: str
                dest, justif = act.get("target_room_id"), act.get("justification", "Auto")

                res: str = "Erreur"
                detailed_log: Optional[str] = None
                
                if action_type == "transfer_basic":
                    if pid and pid in state.patients:
                        patient = state.patients[pid]
                        from_loc: str = patient.location
                        severity: str = patient.severity.value if hasattr(patient.severity, 'value') else str(patient.severity)
                        
                        res = transfer_patient_basic(pid, dest)
                        
                        if "✅" in res:
                            severity_icons: Dict[str, str] = {"ROUGE": "🔴", "JAUNE": "🟡", "VERT": "🟢", "GRIS": "⚪"}
                            icon: str = severity_icons.get(severity, "")
                            from_name: str = get_location_name(from_loc)
                            to_name: str = get_location_name(dest)
                            
                            detailed_log = f"{icon} **{pid}** ({severity}) : {from_name} → {to_name}"
                            
                            if dest == "soins_critiques":
                                detailed_log += " (durée: 24-48h)"
                    else:
                        res = transfer_patient_basic(pid, dest)
                
                elif action_type == "transfer_escort":
                    if pid and pid in state.patients:
                        patient = state.patients[pid]
                        from_loc: str = patient.location
                        severity: str = patient.severity.value if hasattr(patient.severity, 'value') else str(patient.severity)
                        
                        res = transfer_patient_with_escort(pid, dest)
                        
                        if "✅" in res:
                            as_match: Optional[re.Match[str]] = re.search(r'escorté par (AS_\d+)', res)
                            as_id: str = as_match.group(1) if as_match else "AS"
                            
                            from_name: str = get_location_name(from_loc)
                            to_name: str = get_location_name(dest)
                            
                            duration: Any
                            if dest == "consultation":
                                duration = 5
                            elif dest in ["ortho", "cardio", "neuro", "pneumo"]:
                                duration = 45
                            else:
                                duration = "?"
                            
                            detailed_log = f"🚑 **{pid}** escorté par **{as_id}** : {from_name} → {to_name} (durée: {duration} min)"
                    else:
                        res = transfer_patient_with_escort(pid, dest)
                
                elif action_type == "transfer_staff":
                    if not sid: continue
                    
                    if sid in state.staff:
                        agent = state.staff[sid]
                        from_loc: str = agent.location
                        
                        res = transfer_staff(sid, dest)
                        
                        if "✅" in res:
                            icon: str = "👩‍⚕️" if "INF" in sid else "🚑"
                            from_name: str = get_location_name(from_loc)
                            to_name: str = get_location_name(dest)
                            
                            detailed_log = f"{icon} **{sid}** : {from_name} → {to_name} (surveillance)"
                    else:
                        res = transfer_staff(sid, dest)
                
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


