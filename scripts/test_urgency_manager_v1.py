import json
from pathlib import Path

from src.manager.urgency_manager_v1 import load_hospital_state, urgency_manager_v1
ROOT = Path(__file__).resolve().parents[1]
PATIENTS_PATH = ROOT / "data" / "patients" / "patients_seed.json"
HOSPITAL_PATH = ROOT / "data" / "hospital" / "hospital_state.json"


def main() -> None:
    patients = json.loads(PATIENTS_PATH.read_text(encoding="utf-8"))
    hospital = json.loads(HOSPITAL_PATH.read_text(encoding="utf-8"))

    decision = urgency_manager_v1(patients, hospital).to_dict()

    print("\n=== ACTIONS (ordered) ===")
    for a in decision["actions"]:
        print(
            f"{a['priority']:>2}. {a['patient_id']} [{a['severity']}] -> {a['target']} | {a['justification']}"
        )

    if decision["alerts"]:
        print("\n=== ALERTS ===")
        for al in decision["alerts"]:
            print(f"- {al}")

    print("\n=== METRICS ===")
    print(json.dumps(decision["metrics"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
