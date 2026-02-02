from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from src.triage.compute_severity import compute_severity


# -------------------------
# Persistent file locations
# -------------------------
ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_PATIENTS_PATH: Path = ROOT / "data" / "patients" / "patients_seed.json"
DEFAULT_HOSPITAL_PATH: Path = ROOT / "data" / "hospital" / "hospital_state.json"


# -------------------------
# In-memory state (single source of truth during a run)
# -------------------------
_STATE: Dict[str, Any] = {
    "hospital": None,   # dict
    "patients": None,   # list[dict]
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_loaded() -> None:
    if _STATE["hospital"] is None or _STATE["patients"] is None:
        raise RuntimeError("State not initialized. Call init_state() first.")


def _room_has_space(hospital: Dict[str, Any], room: str) -> bool:
    r: Optional[Dict[str, Any]] = hospital["rooms"].get(room)
    if not r:
        return False
    return int(r.get("occupied", 0)) < int(r.get("capacity", 0))


def _occupy_room(hospital: Dict[str, Any], room: str, delta: int) -> None:
    if room not in hospital["rooms"]:
        return
    hospital["rooms"][room]["occupied"] = max(0, int(hospital["rooms"][room].get("occupied", 0)) + delta)


def _find_patient(pid: str) -> Dict[str, Any]:
    _ensure_loaded()
    for p in _STATE["patients"]:
        if p.get("id") == pid:
            return p
    raise KeyError(f"Patient not found: {pid}")


def _normalize_room(room: str) -> str:
    return str(room).strip()


mcp: FastMCP = FastMCP("hospital_tools")


# -------------------------
# Tools
# -------------------------
@mcp.tool()
def init_state(
    patients_path: str = str(DEFAULT_PATIENTS_PATH),
    hospital_path: str = str(DEFAULT_HOSPITAL_PATH),
) -> Dict[str, Any]:
    """
    Load patients + hospital state into memory for this run.
    Must be called before other tools.
    """
    p_path: Path = Path(patients_path)
    h_path: Path = Path(hospital_path)

    patients: List[Dict[str, Any]] = json.loads(p_path.read_text(encoding="utf-8"))
    hospital: Dict[str, Any] = json.loads(h_path.read_text(encoding="utf-8"))

    # Ensure baseline fields
    if "timestamp" not in hospital:
        hospital["timestamp"] = _now_iso()

    _STATE["patients"] = patients
    _STATE["hospital"] = hospital

    return {
        "ok": True,
        "patients_loaded": len(patients),
        "hospital_timestamp": hospital["timestamp"],
        "rooms": list(hospital.get("rooms", {}).keys()),
    }


@mcp.tool()
def get_hospital_state() -> Dict[str, Any]:
    """Return current hospital state (in memory)."""
    _ensure_loaded()
    return deepcopy(_STATE["hospital"])


@mcp.tool()
def list_patients(
    severity: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List patients with optional filters.
    Note: severity filter uses V1 compute_severity (symptoms-only).
    """
    _ensure_loaded()
    out: List[Dict[str, Any]] = []
    for p in _STATE["patients"]:
        if location and p.get("localisation") != location:
            continue
        if status and p.get("statut") != status:
            continue
        if severity:
            sev: str = compute_severity(p).severity
            if sev != severity:
                continue

        out.append(
            {
                "id": p.get("id"),
                "prenom": p.get("prenom"),
                "nom": p.get("nom"),
                "heure_arrivee": p.get("heure_arrivee"),
                "localisation": p.get("localisation"),
                "statut": p.get("statut"),
                "triage_v1": compute_severity(p).to_dict(),
            }
        )
    return out


@mcp.tool()
def get_patient(patient_id: str) -> Dict[str, Any]:
    """Get full patient record + triage result."""
    p: Dict[str, Any] = _find_patient(patient_id)
    out: Dict[str, Any] = deepcopy(p)
    out["triage_v1"] = compute_severity(p).to_dict()
    return out


@mcp.tool()
def compute_severity_tool(patient_id: str) -> Dict[str, Any]:
    """Compute severity for one patient (symptoms-only V1)."""
    p: Dict[str, Any] = _find_patient(patient_id)
    return compute_severity(p).to_dict()


@mcp.tool()
def move_patient(patient_id: str, target_location: str) -> Dict[str, Any]:
    """
    Move patient location only (no capacity accounting).
    Use assign_room for room moves with capacity.
    """
    _ensure_loaded()
    p: Dict[str, Any] = _find_patient(patient_id)
    old: Optional[str] = p.get("localisation")
    p["localisation"] = target_location
    return {"patient_id": patient_id, "from": old, "to": target_location, "ok": True}


@mcp.tool()
def assign_room(patient_id: str, room: str) -> Dict[str, Any]:
    """
    Assign patient to a room with capacity tracking.
    If patient was in another tracked room, we free it.
    """
    _ensure_loaded()
    hospital: Dict[str, Any] = _STATE["hospital"]
    p: Dict[str, Any] = _find_patient(patient_id)

    room = _normalize_room(room)
    if room not in hospital["rooms"]:
        return {"ok": False, "error": f"Unknown room '{room}'", "patient_id": patient_id}

    # Check space (except 'attente' which is huge but still tracked)
    if room != "attente" and not _room_has_space(hospital, room):
        return {"ok": False, "error": f"Room '{room}' is full", "patient_id": patient_id, "room": room}

    old_loc: Optional[str] = p.get("localisation")

    # Free old room occupancy if it was a tracked room
    if old_loc in hospital["rooms"]:
        _occupy_room(hospital, old_loc, delta=-1)

    # Occupy new room
    _occupy_room(hospital, room, delta=+1)

    p["localisation"] = room

    # Status heuristic
    if room in ("consultation", "soins_critiques", "salle_1", "salle_2", "salle_3"):
        p["statut"] = "en_consultation"
    elif room == "attente":
        p["statut"] = "en_attente"
    elif room == "sortie":
        p["statut"] = "sortie"

    return {
        "ok": True,
        "patient_id": patient_id,
        "from": old_loc,
        "to": room,
        "rooms_after": deepcopy(hospital["rooms"]),
    }


@mcp.tool()
def discharge_patient(patient_id: str, reason: str = "") -> Dict[str, Any]:
    """Discharge patient (free room if needed)."""
    _ensure_loaded()
    hospital: Dict[str, Any] = _STATE["hospital"]
    p: Dict[str, Any] = _find_patient(patient_id)
    old_loc: Optional[str] = p.get("localisation")
    if old_loc in hospital["rooms"]:
        _occupy_room(hospital, old_loc, delta=-1)
    p["localisation"] = "sortie"
    p["statut"] = "sortie"
    return {"ok": True, "patient_id": patient_id, "from": old_loc, "to": "sortie", "reason": reason}


@mcp.tool()
def move_staff(role: str, from_area: str, to_area: str, count: int = 1) -> Dict[str, Any]:
    """
    Simple staff tool (role-based).
    V1: we only log; we do not enforce complex constraints.
    """
    _ensure_loaded()
    hospital: Dict[str, Any] = _STATE["hospital"]
    staff: Dict[str, Any] = hospital.setdefault("staff", {})
    key: str = str(role).strip()

    # This tool doesn't track per-area staff in V1; it records an ops log.
    log: List[Dict[str, Any]] = hospital.setdefault("ops_log", [])
    log.append(
        {
            "time": hospital.get("timestamp", _now_iso()),
            "type": "move_staff",
            "role": key,
            "count": int(count),
            "from": from_area,
            "to": to_area,
        }
    )
    return {"ok": True, "role": key, "count": int(count), "from": from_area, "to": to_area}


@mcp.tool()
def tick(minutes: int = 5) -> Dict[str, Any]:
    """
    Advance simulated time; optionally free capacity in consultation (simple simulation).
    V1 simulation: each tick frees 1 slot in consultation if occupied > 0.
    """
    _ensure_loaded()
    hospital: Dict[str, Any] = _STATE["hospital"]
    t: datetime = datetime.fromisoformat(hospital.get("timestamp", _now_iso()))
    t2: datetime = t + timedelta(minutes=int(minutes))
    hospital["timestamp"] = t2.isoformat(timespec="seconds")

    # Simple simulation rule: consultation frees 1 spot per tick (if occupied > 0)
    if "consultation" in hospital["rooms"] and int(hospital["rooms"]["consultation"].get("occupied", 0)) > 0:
        _occupy_room(hospital, "consultation", delta=-1)

    return {"ok": True, "timestamp": hospital["timestamp"], "rooms": deepcopy(hospital["rooms"])}