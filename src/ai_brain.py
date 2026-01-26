import sys
import os
import json
import re
from dotenv import load_dotenv
from mistralai import Mistral
from src.tools import get_hospital_dashboard, get_patient_list, transfer_patient_basic, transfer_patient_with_escort, transfer_staff

load_dotenv()
api_key = os.getenv("MISTRAL_API_KEY")
if not api_key: api_key = "dummy_key"

MODEL_NAME = "mistral-large-latest" 
client = Mistral(api_key=api_key)

SYSTEM_PROMPT = """
Tu es le CHEF DE RÉGULATION des urgences.

TES OUTILS :
1. **"transfer_basic"** (Pour Patient) : Triage -> Salle d'Attente / Soins Critiques / Sortie.
2. **"transfer_escort"** (Pour Patient + AS) : Salle d'Attente -> Consultation -> Hospitalisation.
3. **"transfer_staff"** (Pour Infirmier) : Déplace un infirmier d'une salle à l'autre.

🚨 RÈGLES DE DÉCISION (PRIORITÉ ABSOLUE) 🚨

1. **URGENCE VITALE (ROUGE)** : Tout patient ROUGE au triage doit aller en Soins Critiques IMMÉDIATEMENT.
2. **SÉCURITÉ SALLES (Règle 3)** : Si une salle d'attente a des patients mais PAS d'infirmier, envoie un infirmier disponible (depuis une salle vide ou le triage s'il y a du monde).
3. **PRIORITÉ MÉDICALE** : Traite TOUJOURS les patients JAUNES avant les VERTS/GRIS.
4. **FLUX** : Vide le triage dès que possible.

FORMAT DE RÉPONSE OBLIGATOIRE (JSON) :
{
  "action": "transfer_basic" | "transfer_escort" | "transfer_staff" | "wait",
  "patient_id": "PAT_XXX" (ou null si staff),
  "staff_id": "INF_XXX" (seulement si transfer_staff),
  "target_room_id": "wr_01",
  "justification": "Courte phrase expliquant pourquoi (ex: 'Patient Rouge prioritaire', 'Salle 1 sans surveillance')"
}
"""

def clean_json_response(raw_text):
    match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
    if match: return match.group(0)
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
        return json.dumps({"action": "wait", "justification": f"Erreur API: {e}"})

def process_brain_cycle():
    try:
        dashboard = get_hospital_dashboard()
        detail_triage = get_patient_list("triage")
        detail_wr01 = get_patient_list("wr_01")
        detail_wr02 = get_patient_list("wr_02")
        
        # Veille si calme plat
        if "Aucun" in detail_triage and "ACTIONS" not in dashboard:
             if ("Aucun" in detail_wr01) and ("Aucun" in detail_wr02):
                 return None # Pas de log si rien à faire

        full_prompt = f"{dashboard}\n\nPATIENTS TRIAGE:\n{detail_triage}\n\nPATIENTS SALLE 1:\n{detail_wr01}\n\nPATIENTS SALLE 2:\n{detail_wr02}"

        llm_response_str = call_llm_api(full_prompt)
        
        try:
            decision = json.loads(llm_response_str)
            action_type = decision.get("action")
            pid = decision.get("patient_id")
            sid = decision.get("staff_id")
            dest = decision.get("target_room_id")
            justif = decision.get("justification", "Pas de justification")

            res = "Erreur"
            if action_type == "transfer_basic": res = transfer_patient_basic(pid, dest)
            elif action_type == "transfer_escort": res = transfer_patient_with_escort(pid, dest)
            elif action_type == "transfer_staff": res = transfer_staff(sid, dest)
            elif action_type == "wait": return None # On ne loggue pas les attentes silencieuses
            else: return f"⚠️ Action inconnue : {action_type}"
            
            return f"🤖 **{justif}**\n👉 {res}"

        except json.JSONDecodeError:
            return f"❌ Erreur JSON LLM"

    except Exception as e:
        return f"🚨 Erreur Cerveau : {e}"