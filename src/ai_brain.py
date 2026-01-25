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

from src.tools import get_hospital_status, get_patient_list, move_patient

# 1. CHARGEMENT CONFIG
load_dotenv()
api_key = os.getenv("MISTRAL_API_KEY")
if not api_key: api_key = "dummy_key"

# 2. CLIENT MISTRAL
MODEL_NAME = "mistral-tiny"
client = Mistral(api_key=api_key)

# =============================================================================
# 3. PROMPT SYSTEME (VERSION STRICTE)
# =============================================================================

SYSTEM_PROMPT = """
Tu es le CHEF RÉGULATEUR des urgences.
TA MISSION : VIDER LA ZONE DE TRIAGE. Si des patients attendent, tu DOIS les placer.

RÈGLES D'ACTION (IMPORTANT) :
1. Ne propose qu'UNE SEULE action JSON à la fois. Interdiction de faire des listes.
2. Si un patient est en Triage et qu'une salle (wr_01, wr_02, etc.) a de la place : DÉPLACE-LE IMMÉDIATEMENT.
3. Ne dis JAMAIS "attendre" si une salle est vide et qu'un patient attend.
4. Les ROUGES -> Priorité absolue pour "soins_critiques". Si plein -> Attente Triage.
5. Les JAUNES/VERTS -> Salles d'attente "wr_01", "wr_02", "wr_03".

FORMAT DE RÉPONSE OBLIGATOIRE :
Un seul objet JSON brut. Rien d'autre.
Exemple : {"action": "move_patient", "patient_id": "PAT_001", "target_room_id": "wr_01"}
"""

# =============================================================================
# 4. FONCTIONS HELPER (REGEX AMÉLIORÉE)
# =============================================================================

def clean_json_response(raw_text):
    """
    Nettoie la réponse.
    Si le LLM envoie plusieurs JSONs à la suite, on ne garde QUE LE PREMIER.
    """
    # L'astuce est dans le '?' après le '*' : ça veut dire "Non-Gourmand"
    # Il s'arrête dès qu'il trouve la première fermeture '}'
    match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
    if match:
        return match.group(0)
    return raw_text

def call_llm_api(context_text):
    print(f"📡 Envoi au Cerveau ({MODEL_NAME})...")
    try:
        chat_response = client.chat.complete(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context_text},
            ],
            temperature=0.1, # Encore plus froid pour être rigoureux
        )
        return clean_json_response(chat_response.choices[0].message.content)
    except Exception as e:
        print(f"🔥 Erreur API : {e}")
        return '{"action": "wait", "reason": "Erreur API"}'

# =============================================================================
# 5. BOUCLE D'INTELLIGENCE
# =============================================================================

def run_brain_loop():
    print(f"🧠 Cerveau IA démarré ({MODEL_NAME}). Ctrl+C pour stopper.")
    
    while True:
        try:
            # A. OBSERVER
            state_txt = get_hospital_status()
            triage_details = get_patient_list("triage")
            
            if "Aucun patient" in triage_details:
                print("💤 Veille (Triage vide)...")
                time.sleep(5)
                continue

            full_prompt = f"ÉTAT HÔPITAL :\n{state_txt}\n\nPATIENTS À PLACER (TRIAGE) :\n{triage_details}"

            # B. RÉFLÉCHIR
            llm_response_str = call_llm_api(full_prompt)
            print(f"🤖 Pensée brute : {llm_response_str}")

            # C. AGIR
            try:
                decision = json.loads(llm_response_str)
                action = decision.get("action")
                
                if action == "move_patient":
                    pid = decision.get("patient_id")
                    dest = decision.get("target_room_id")
                    print(f"⚡ ORDRE : Déplacer {pid} vers {dest}")
                    result = move_patient(pid, dest)
                    print(f"   ↳ Résultat : {result}")
                    
                elif action == "wait":
                    print(f"⏳ Standby : {decision.get('reason')}")
                
            except json.JSONDecodeError:
                print(f"❌ Erreur JSON (L'IA a bégayé) : {llm_response_str}")

        except Exception as e:
            print(f"🚨 Crash : {e}")

        print("⏳ ... (5s)")
        time.sleep(5)

if __name__ == "__main__":
    run_brain_loop()