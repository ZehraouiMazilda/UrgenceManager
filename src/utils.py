import json
import os
from typing import Dict, Any
from src.models import StateFile, HospitalState

def load_initial_state(json_path: str) -> HospitalState:
    """
    Charge le fichier JSON complet (avec constantes), le valide via Pydantic,
    et renvoie uniquement l'objet 'state' prêt à l'emploi.
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Fichier introuvable : {json_path}")
    
    with open(json_path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    
    # 1. Validation stricte avec le nouveau modèle StateFile
    try:
        full_file: StateFile = StateFile(**data)
        print("✅ État et Constantes chargés avec succès.")
        return full_file.state
    except Exception as e:
        print(f"❌ Erreur de validation Pydantic : {e}")
        raise e

def load_symptoms_config(json_path: str) -> Dict[str, Any]:
    """Charge le dictionnaire des symptômes (Ressources_Projet)"""
    if not os.path.exists(json_path):
        return {}
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)
    
    
def save_state(state: HospitalState, json_path: str) -> None:
    """
    Sauvegarde l'état actuel dans le fichier JSON.
    C'est ce que l'Agent utilisera pour appliquer ses décisions.
    """
    # 1. On charge les constantes depuis le fichier existant (pour ne pas les perdre)
    # car l'objet HospitalState ne contient que le 'state', pas les 'constants'
    constants: Dict[str, Any]
    hospital_name: str
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data: Dict[str, Any] = json.load(f)
            constants = raw_data.get("constants", {})
            hospital_name = raw_data.get("hospital_name", "Hopital")
    else:
        # Fallback si fichier perdu
        constants = {}
        hospital_name = "Hopital"

    # 2. On prépare le dictionnaire complet
    # On utilise model_dump() de Pydantic pour convertir l'objet en dict
    full_data: Dict[str, Any] = {
        "hospital_name": hospital_name,
        "constants": constants,
        "state": state.model_dump()
    }

    # 3. Ecriture atomique (pour éviter les conflits de lecture)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_data, f, indent=2, ensure_ascii=False)