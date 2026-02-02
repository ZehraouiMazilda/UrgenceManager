from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Callable

from dotenv import load_dotenv
from mistralai import Mistral

from src.mcp.hospital_server import (
    init_state,
    get_hospital_state,
    list_patients,
    get_patient,
    compute_severity_tool,
    assign_room,
    discharge_patient,
    move_staff,
    tick,
)

TOOLS: Dict[str, Callable[..., Any]] = {
    "init_state": init_state,
    "get_hospital_state": get_hospital_state,
    "list_patients": list_patients,
    "get_patient": get_patient,
    "compute_severity_tool": compute_severity_tool,
    "assign_room": assign_room,
    "discharge_patient": discharge_patient,
    "move_staff": move_staff,
    "tick": tick,
}


def _must_json(text: str) -> Dict[str, Any]:
    """
    Extract first valid JSON object from text.
    Raise ValueError if none found.
    """
    if not text:
        raise ValueError("Empty LLM response")

    text = text.strip()

    # Fast path
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)

    # Fallback: extract JSON block
    start: int = text.find("{")
    end: int = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate: str = text[start : end + 1]
        return json.loads(candidate)

    raise ValueError("No JSON object found in LLM output")



SYSTEM_PROMPT: str = """
Tu es un agent de gestion des urgences. Tu dois AGIR en appelant des outils.

Tu ne dois produire QUE du JSON valide.

Format de réponse attendu à chaque tour (si tu n'as pas fini) :
{
  "tool_calls": [
    {"tool": "nom_outil", "args": { ... }},
    ...
  ],
  "final": false
}

Quand tu as fini :
{
  "summary_fr": "...",
  "alerts": [...],
  "final": true
}

Règles:
- Priorité: ROUGE > JAUNE > VERT > GRIS.
- Ne pose pas de diagnostic (pas "AVC", "infarctus"). Décris symptômes/sevérité.
- Respecte les capacités: si assign_room échoue, trouve une alternative.
- Max 12 tool_calls par tour.
- Tu peux faire plusieurs tours (max_rounds).
"""


def run_agent_loop(query: str, model: str = "mistral-large-latest", max_rounds: int = 6) -> Dict[str, Any]:
    load_dotenv()
    api_key: str | None = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY manquante dans .env")

    client: Mistral = Mistral(api_key=api_key)

    # init state once
    init_state()

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    executed: List[Dict[str, Any]] = []
    alerts: List[str] = []

    for _ in range(max_rounds):
        resp = client.chat.complete(model=model, messages=messages, temperature=0.2)
        content: Any = resp.choices[0].message.content
        if not isinstance(content, str):
            content = str(content)

        data: Dict[str, Any] = _must_json(content)

        if data.get("final") is True:
            # return final snapshot
            final_state: Dict[str, Any] = {
                "hospital_state": get_hospital_state(),
                "patients_overview": [
                    {
                        "id": p["id"],
                        "loc": p.get("localisation"),
                        "status": p.get("statut"),
                        "severity": compute_severity_tool(p["id"])["severity"],
                    }
                    for p in list_patients()
                ],
            }
            return {
                "summary_fr": data.get("summary_fr", ""),
                "actions_executed": executed,
                "final_state": final_state,
                "alerts": alerts + data.get("alerts", []),
            }

        tool_calls: Any = data.get("tool_calls", [])
        if not isinstance(tool_calls, list) or not tool_calls:
            messages.append(
                {"role": "user", "content": "Erreur: tu dois fournir tool_calls (JSON). Réessaie."}
            )
            continue

        tool_results: List[Dict[str, Any]] = []
        for call in tool_calls[:12]:
            tool: Any = call.get("tool")
            args: Any = call.get("args", {})
            if tool not in TOOLS:
                tool_results.append({"tool": tool, "ok": False, "error": "Unknown tool"})
                continue

            try:
                res: Any = TOOLS[tool](**args) if isinstance(args, dict) else TOOLS[tool]()
                executed.append({"tool": tool, "args": args, "result": res})
                tool_results.append({"tool": tool, "ok": True, "result": res})
            except Exception as e:
                alerts.append(f"Outil {tool} a échoué: {e}")
                tool_results.append({"tool": tool, "ok": False, "error": str(e)})

        snapshot: Dict[str, Any] = {
            "hospital_state": get_hospital_state(),
            "patients": list_patients(),
            "tool_results": tool_results,
        }

        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": json.dumps(snapshot, ensure_ascii=False)})

    return {
        "summary_fr": "Arrêt: max_rounds atteint sans finalisation.",
        "actions_executed": executed,
        "final_state": {
            "hospital_state": get_hospital_state(),
            "patients_overview": [
                {
                    "id": p["id"],
                    "loc": p.get("localisation"),
                    "status": p.get("statut"),
                    "severity": compute_severity_tool(p["id"])["severity"],
                }
                for p in list_patients()
            ],
        },
        "alerts": alerts + ["max_rounds atteint"],
    }