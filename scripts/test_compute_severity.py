import json
from pathlib import Path

from src.triage.compute_severity import compute_severity


PATIENTS_PATH = Path("data/patients/patients_seed.json")


def main() -> None:
    patients = json.loads(PATIENTS_PATH.read_text(encoding="utf-8"))
    results = [compute_severity(p).to_dict() for p in patients]

    # Print per patient
    for r in results:
        print(f"{r['patient_id']} -> {r['severity']} | triggers={r['matched_triggers']}")

    # Summary counts
    counts = {}
    for r in results:
        counts[r["severity"]] = counts.get(r["severity"], 0) + 1

    print("\nSummary:")
    for k in sorted(counts.keys()):
        print(f"  {k}: {counts[k]}")


if __name__ == "__main__":
    main()
