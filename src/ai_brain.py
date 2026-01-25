import sys
import os

# --- FIX DE CHEMIN ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ---------------------

import time
import json
import re
from dotenv import load_dotenv
from mistralai import Mistral

# Import des outils
from src.tools import get_hospital_dashboard, get_patient_list, transfer_patient_basic, transfer_patient_with_escort

# 1. CONFIG
load_dotenv()
api_key = os.getenv("MISTRAL_API_KEY")
if not api_key: api_key = "dummy_key"

# On garde le Large car il est plus logique, on va juste adapter le parser
MODEL_NAME = "mistral-large-latest" 
client = Mistral(api_key=api_key)

# =============================================================================
# 3. PROMPT SYSTEME
# =============================================================================

SYSTEM_PROMPT = """
Tu es le CHEF DE RÉGULATION des urgences.

TES OUTILS :
1. **"transfer_basic"** (Infirmier) : Triage -> Salle d'Attente ou Soins Critiques.
2. **"transfer_escort"** (Aide-Soignant) : Pour Consultation ou Hospitalisation.

RÈGLES STRICTES :
1. Si une salle est "[⛔ PLEIN]", tu DOIS choisir une autre salle (wr_01 -> wr_02 -> wr_03).
2. Triage -> Salle d'Attente = "transfer_basic".
3. Salle d'Attente -> Consultation = "transfer_escort".
4. Consultation -> Hôpital/Sortie = "transfer_escort" ou "transfer_basic" (si sortie).

FORMAT DE RÉPONSE ATTENDU (JSON PLAT) :
{
  "action": "transfer_basic",
  "patient_id": "PAT_XXX",
  "target_room_id": "wr_02"
}
"""

# =============================================================================
# 4. HELPERS
# =============================================================================

def clean_json_response(raw_text):
    match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
    if match: return match.group(0)
    return raw_text

def call_llm_api(context_text):
    print(f"📡 Analyse du contexte ({MODEL_NAME})...")
    try:
        chat_response = client.chat.complete(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context_text},
            ],
            temperature=0.0,
        )
        return clean_json_response(chat_response.choices[0].message.content)
    except Exception as e:
        print(f"🔥 Erreur API : {e}")
        return '{"action": "wait", "reason": "Erreur API"}'

# =============================================================================
# 5. BOUCLE PRINCIPALE (PARSER INTELLIGENT)
# =============================================================================

def run_brain_loop():
    print(f"🧠 Cerveau IA démarré. Prêt à réguler les flux.")
    
    while True:
        try:
            # A. OBSERVER
            dashboard = get_hospital_dashboard()
            detail_triage = get_patient_list("triage")
            detail_wr01 = get_patient_list("wr_01")
            detail_wr02 = get_patient_list("wr_02")
            detail_wr03 = get_patient_list("wr_03")
            
            # Veille si tout est vide
            all_empty = (
                "Aucun patient" in detail_triage and 
                "Aucun patient" in detail_wr01 and 
                "Aucun patient" in detail_wr02 and
                "Aucun patient" in detail_wr03
            )
            
            if all_empty and "ALARMES EN COURS" not in dashboard:
                print("💤 Veille (Hôpital Calme)...")
                time.sleep(5)
                continue

            full_prompt = (
                f"{dashboard}\n\n"
                f"DÉTAILS TRIAGE:\n{detail_triage}\n"
                f"DÉTAILS SALLE 1:\n{detail_wr01}\n"
                f"DÉTAILS SALLE 2:\n{detail_wr02}\n"
                f"DÉTAILS SALLE 3:\n{detail_wr03}"
            )

            # B. RÉFLÉCHIR
            llm_response_str = call_llm_api(full_prompt)
            print(f"🤖 Pensée : {llm_response_str}")

            # C. AGIR (PARSER ROBUSTE)
            try:
                decision = json.loads(llm_response_str)
                
                # --- DÉTECTION DU FORMAT (C'est ici la magie) ---
                raw_action = decision.get("action")
                
                real_action_name = "wait"
                pid = None
                dest = None
                
                # Cas 1 : L'IA fait du zèle (Format Niché : "action": {"method":...})
                if isinstance(raw_action, dict):
                    real_action_name = raw_action.get("method") or raw_action.get("type")
                    pid = raw_action.get("patient_id")
                    # L'IA utilise parfois "to" ou "target" au lieu de "target_room_id"
                    dest = raw_action.get("to") or raw_action.get("target") or raw_action.get("target_room_id")
                    
                # Cas 2 : L'IA obéit (Format Plat : "action": "transfer...")
                elif isinstance(raw_action, str):
                    real_action_name = raw_action
                    pid = decision.get("patient_id")
                    dest = decision.get("target_room_id")

                # --- EXÉCUTION ---
                result = "Pas d'action reconnue"
                
                if real_action_name == "transfer_basic":
                    print(f"⚡ ORDRE : Transfert Simple de {pid} vers {dest}")
                    result = transfer_patient_basic(pid, dest)
                    
                elif real_action_name == "transfer_escort":
                    print(f"⚡ ORDRE : Transfert ESCORTÉ de {pid} vers {dest}")
                    result = transfer_patient_with_escort(pid, dest)
                    
                elif real_action_name == "wait":
                    reason = decision.get("reason") or "Attente"
                    print(f"⏳ Standby : {reason}")
                    result = "Attente."
                
                print(f"   ↳ Résultat : {result}")

            except json.JSONDecodeError:
                print(f"❌ Erreur JSON : {llm_response_str}")

        except Exception as e:
            print(f"🚨 Crash Loop : {e}")

        print("⏳ ... (5s)")
        time.sleep(5)

if __name__ == "__main__":
    run_brain_loop()