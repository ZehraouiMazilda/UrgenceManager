from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.triage.compute_severity import compute_severity


DEFAULT_HOSPITAL_PATH: Path = Path("data/hospital/hospital_state.json")


SEVERITY_RANK: Dict[str, int] = {"ROUGE": 0, "JAUNE": 1, "VERT": 2, "GRIS": 3}


def _parse_dt(dt_str: str) -> datetime:
    # Your seed uses ISO8601; this is enough for V1
    return datetime.fromisoformat(dt_str)


def _room_has_space(room: Dict[str, Any]) -> bool:
    return int(room.get("occupied", 0)) < int(room.get("capacity", 0))


def _occupy_room(state: Dict[str, Any], room_name: str) -> None:
    state["rooms"][room_name]["occupied"] = int(state["rooms"][room_name].get("occupied", 0)) + 1


def _choose_target_room(severity: str, patient: Dict[str, Any], hospital: Dict[str, Any]) -> Tuple[str, str]:
    """
    Deterministic room assignment logic V1:
    - GRIS -> sortie
    - VERT -> consultation if available else attente
    - JAUNE -> salle_2 (pneumo/urgent) if space else attente (+ alert)
    - ROUGE -> soins_critiques if space else consultation if available else attente (+ alert)
    Additionally, uses type_maladie as a hint for ROUGE routing:
      cardio -> salle_1 fallback, neuro -> salle_3 fallback, resp -> salle_2 fallback
    """
    rooms: Dict[str, Any] = hospital["rooms"]

    if severity == "GRIS":
        return "sortie", "GRIS: ne nécessite pas les urgences (orientation hors urgences)"

    if severity == "VERT":
        if _room_has_space(rooms["consultation"]):
            return "consultation", "VERT: consultation si disponible"
        return "attente", "VERT: consultation saturée -> attente"

    if severity == "JAUNE":
        if _room_has_space(rooms["salle_2"]):
            return "salle_2", "JAUNE: urgent non vital -> salle_2"
        return "attente", "JAUNE: salle_2 saturée -> attente + alerte saturation"

    # ROUGE
    if _room_has_space(rooms["soins_critiques"]):
        return "soins_critiques", "ROUGE: vital -> soins critiques"

    # Fallbacks for ROUGE
    type_maladie: Any = patient.get("type_maladie", [])
    type_maladie_str: str = " ".join(type_maladie).lower() if isinstance(type_maladie, list) else str(type_maladie).lower()

    # specialty fallback
    if "cardio" in type_maladie_str and _room_has_space(rooms["salle_1"]):
        return "salle_1", "ROUGE: soins critiques saturés -> fallback cardiologie (salle_1)"
    if "neuro" in type_maladie_str and _room_has_space(rooms["salle_3"]):
        return "salle_3", "ROUGE: soins critiques saturés -> fallback neurologie (salle_3)"
    if "resp" in type_maladie_str and _room_has_space(rooms["salle_2"]):
        return "salle_2", "ROUGE: soins critiques saturés -> fallback pneumologie (salle_2)"

    # general fallback
    if _room_has_space(rooms["consultation"]):
        return "consultation", "ROUGE: soins critiques saturés -> consultation en priorité"
    return "attente", "ROUGE: saturation totale -> attente + alerte critique"


@dataclass
class ManagerDecision:
    timestamp: str
    actions: List[Dict[str, Any]]
    queue: List[Dict[str, Any]]
    alerts: List[str]
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "actions": self.actions,
            "queue": self.queue,
            "alerts": self.alerts,
            "metrics": self.metrics,
        }


def urgency_manager_v1(
    patients: List[Dict[str, Any]],
    hospital_state: Dict[str, Any],
) -> ManagerDecision:
    """
    Manager V1:
    - computes severity for each patient (symptoms-only)
    - sorts patients by severity rank then arrival time
    - assigns rooms deterministically with capacity tracking
    - produces actions + queue + alerts + metrics
    """
    # Copy hospital state shallowly to update occupancy safely
    hospital: Dict[str, Any] = json.loads(json.dumps(hospital_state))

    # Enrich patients with severity results
    enriched: List[Dict[str, Any]] = []
    by_sev: Dict[str, int] = {"GRIS": 0, "VERT": 0, "JAUNE": 0, "ROUGE": 0}

    for p in patients:
        sev_res: Dict[str, Any] = compute_severity(p).to_dict()
        sev: str = sev_res["severity"]
        by_sev[sev] = by_sev.get(sev, 0) + 1

        enriched.append(
            {
                "patient": p,
                "severity": sev,
                "arrival": _parse_dt(p["heure_arrivee"]) if "heure_arrivee" in p else datetime.min,
                "matched_triggers": sev_res["matched_triggers"],
                "reason": sev_res["reason"],
            }
        )

    # Sort: ROUGE first, then JAUNE, then VERT, then GRIS; ties by arrival
    enriched.sort(key=lambda x: (SEVERITY_RANK.get(x["severity"], 99), x["arrival"]))

    actions: List[Dict[str, Any]] = []
    alerts: List[str] = []
    queue: List[Dict[str, Any]] = []

    # Decide for each patient in priority order
    for idx, item in enumerate(enriched, start=1):
        p: Dict[str, Any] = item["patient"]
        sev: str = item["severity"]

        target: str
        justification: str
        target, justification = _choose_target_room(sev, p, hospital)

        # Update patient location & status for action output (V1: simplistic)
        action: Dict[str, Any] = {
            "type": "assign_room",
            "patient_id": p["id"],
            "severity": sev,
            "target": target,
            "priority": idx,
            "matched_triggers": item["matched_triggers"],
            "justification": justification,
        }

        if target == "sortie":
            action["type"] = "discharge_or_redirect"
            action["target"] = "sortie"
        elif target in hospital["rooms"]:
            # occupy room (except 'attente' which we can still count)
            _occupy_room(hospital, target)
        else:
            # unknown target
            alerts.append(f"Target room unknown: {target} for patient {p['id']}")

        # Saturation alerts
        if sev == "ROUGE" and target == "attente":
            alerts.append(f"CRITIQUE: patient ROUGE {p['id']} en attente (saturation).")
        if sev == "JAUNE" and target == "attente":
            alerts.append(f"ALERTE: patient JAUNE {p['id']} en attente (salle_2 saturée).")

        actions.append(action)

        # Queue representation = patients that are not directly in a treatment room
        if target in ("attente", "consultation"):
            queue.append({"patient_id": p["id"], "severity": sev, "rank": idx, "target": target})

    metrics: Dict[str, Any] = {
        "patients_total": len(patients),
        "by_severity": by_sev,
        "rooms_after": hospital["rooms"],
    }

    timestamp: str = hospital_state.get("timestamp", datetime.now().isoformat(timespec="seconds"))

    return ManagerDecision(
        timestamp=timestamp,
        actions=actions,
        queue=queue,
        alerts=alerts,
        metrics=metrics,
    )


def load_hospital_state(path: Path = DEFAULT_HOSPITAL_PATH) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))