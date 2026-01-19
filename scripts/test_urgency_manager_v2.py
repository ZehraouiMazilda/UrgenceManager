import json
from pathlib import Path

from src.manager.urgency_manager_v1 import urgency_manager_v1
from src.agent.llm_supervisor_mistral import run_llm_supervisor

ROOT = Path(__file__).resolve().parents[1]
PATIENTS_PATH = ROOT / "data" / "patients" / "patients_seed.json"
HOSPITAL_PATH = ROOT / "data" / "hospital" / "hospital_state.json"


def main() -> None:
    patients = json.loads(PATIENTS_PATH.read_text(encoding="utf-8"))
    hospital = json.loads(HOSPITAL_PATH.read_text(encoding="utf-8"))

    decision_v1 = urgency_manager_v1(patients, hospital).to_dict()

    payload = {
        "hospital_state": hospital,
        "patients": patients,
        "decision_v1": decision_v1,
    }

    supervisor = run_llm_supervisor(payload)

    print("\n=== DECISION V1 (short) ===")
    for a in decision_v1["actions"][:5]:
        print(f"{a['priority']:>2}. {a['patient_id']} [{a['severity']}] -> {a['target']}")

    print("\n=== LLM SUPERVISOR (V2) ===")
    print(json.dumps(supervisor, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
