import sys
import os
import json
import re
from dotenv import load_dotenv
from mistralai import Mistral
from src.tools import get_hospital_dashboard, get_patient_list, transfer_patient_basic, transfer_patient_with_escort, transfer_staff, get_staff_directory, get_as_directory

load_dotenv()
api_key = os.getenv("MISTRAL_API_KEY")
if not api_key: api_key = "dummy_key"

MODEL_NAME = "mistral-large-latest" 
client = Mistral(api_key=api_key)

SYSTEM_PROMPT = """
Tu es le CHEF DE RÉGULATION des urgences. Tu dois agir vite et traiter PLUSIEURS patients à la fois.

TES OUTILS :
1. "transfer_basic" : Triage -> Salle d'Attente / Soins Critiques / Sortie.
2. "transfer_escort" : Salle d'Attente -> Consultation -> Hospitalisation. (Nécessite AS dispo !)
3. "transfer_staff" : Déplace un INFIRMIER pour la sécurité.

🚨 RÈGLES DE PRIORITÉ (ORDRE D'EXÉCUTION) 🚨

1. **URGENCES VITALES (ROUGE & DÉPASSEMENTS)**
   - Priorité absolue. Destination : Consultation (si libre) ou Soins Critiques.

2. **ALIMENTATION CONSULTATION (GOULOT)**
   - Si Consult "🟢 LIBRE" + AS dispo : Envoie IMMÉDIATEMENT un patient via "transfer_escort".

3. **FLUX DE MASSE**
   - Vide le Triage. Remplis wr_01 -> wr_02 -> wr_03.

4. **SÉCURITÉ**
   - Si une salle a des patients, assure-toi qu'il y a un infirmier.

FORMAT DE RÉPONSE OBLIGATOIRE (STRICT JSON ONLY, NO MARKDOWN, NO TEXT) :
{
  "actions": [
    {
      "type": "transfer_basic",
      "patient_id": "PAT_001",
      "target_room_id": "wr_01",
      "justification": "Patient Vert vers salle 1"
    },
    {
      "type": "transfer_escort",
      "patient_id": "PAT_005",
      "target_room_id": "consultation",
      "justification": "Consult libre"
    }
  ]
}
Si rien à faire : { "actions": [] }
"""

def clean_json_response(raw_text):
    """Nettoie brutalement la réponse pour ne garder que le bloc JSON { ... }"""
    try:
        # Enlever les balises markdown code
        text = raw_text.replace("```json", "").replace("```", "").strip()
        
        # Trouver la première accolade ouvrante et la dernière fermante
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            return text[start_idx : end_idx + 1]
        
        return text
    except Exception:
        return raw_text

def call_llm_api(context_text):
    try:
        chat_response = client.chat.complete(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": context_text}],
            temperature=0.0,
        )
        return clean_json_response(chat_response.choices[0].message.content)
    except Exception as e:
        # En cas d'erreur API, on renvoie un JSON vide valide
        print(f"🚨 ERREUR API MISTRAL : {e}")
        return json.dumps({"actions": []})

def process_brain_cycle():
    try:
        # 1. Récupération du contexte
        dashboard = get_hospital_dashboard()
        detail_triage = get_patient_list("triage")
        detail_wr01 = get_patient_list("wr_01")
        detail_wr02 = get_patient_list("wr_02")
        detail_wr03 = get_patient_list("wr_03")
        
        staff_list = get_staff_directory()
        as_list = get_as_directory()
        
        full_prompt = f"""{dashboard}
        
INFIRMIERS:
{staff_list}

AIDES-SOIGNANTS:
{as_list}

TRIAGE:
{detail_triage}

SALLE 1:
{detail_wr01}

SALLE 2:
{detail_wr02}

SALLE 3:
{detail_wr03}
"""

        # 2. Appel IA
        llm_response_str = call_llm_api(full_prompt)
        
        # DEBUG : Affiche ce que le LLM envoie vraiment dans ta console
        print(f"\n🧠 [DEBUG LLM RAW]: {llm_response_str}\n")
        
        try:
            decision = json.loads(llm_response_str)
            actions_list = decision.get("actions", [])
            
            if not actions_list:
                return None 

            # 3. Exécution de la liste
            logs_output = []
            
            for act in actions_list:
                action_type = act.get("type")
                pid = act.get("patient_id")
                sid = act.get("staff_id")
                dest = act.get("target_room_id")
                justif = act.get("justification", "Auto")

                res = "Erreur"
                
                if action_type == "transfer_basic":
                    res = transfer_patient_basic(pid, dest)
                elif action_type == "transfer_escort":
                    res = transfer_patient_with_escort(pid, dest)
                elif action_type == "transfer_staff":
                    res = transfer_staff(sid, dest)
                elif action_type == "wait":
                    continue 
                else:
                    res = f"⚠️ Type inconnu : {action_type}"
                
                if "⚠️ Déjà" not in res:
                    logs_output.append(f"👉 {justif} : {res}")

            if not logs_output: return None
            return "\n".join(logs_output)

        except json.JSONDecodeError as e:
            # On affiche l'erreur exacte pour débugger
            return f"❌ Erreur JSON : {e}. Voir console pour le RAW."

    except Exception as e:
        return f"🚨 Erreur Cerveau : {e}"