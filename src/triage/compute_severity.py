from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_RULES_PATH = Path("data/rules/severity_rules.json")


def _normalize_text(text: str) -> str:
    """
    Normalize a French text for robust substring matching:
    - lowercasing
    - remove accents
    - remove extra spaces
    - keep apostrophes but simplify punctuation
    """
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s'<>°\-()]+", " ", text)  # keep basic useful chars
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_list(items: List[str]) -> List[str]:
    return [_normalize_text(x) for x in items if isinstance(x, str) and x.strip()]


@dataclass(frozen=True)
class SeverityResult:
    patient_id: str
    severity: str
    matched_triggers: List[str]
    reason: str
    rule_source: str
    version: str = "v1-symptoms-only"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "severity": self.severity,
            "matched_triggers": self.matched_triggers,
            "reason": self.reason,
            "rule_source": self.rule_source,
            "version": self.version,
        }


class RulesFormatError(ValueError):
    pass


def load_severity_rules(rules_path: Path = DEFAULT_RULES_PATH) -> Dict[str, Any]:
    """
    Load severity rules JSON and validate minimal expected structure.
    Expected structure:
    {
      "rules": [
        {"label": "...", "reasons": "...", "triggers": ["...", "..."]},
        ...
      ],
      "default_label": "VERT",
      "tie_breaker_order": ["ROUGE","JAUNE","VERT","GRIS"]
    }
    """
    if not rules_path.exists():
        raise FileNotFoundError(f"Rules file not found: {rules_path}")

    with rules_path.open("r", encoding="utf-8") as f:
        rules = json.load(f)

    if "rules" not in rules or not isinstance(rules["rules"], list):
        raise RulesFormatError("Invalid rules: missing 'rules' list.")

    if "default_label" not in rules or not isinstance(rules["default_label"], str):
        raise RulesFormatError("Invalid rules: missing 'default_label'.")

    if "tie_breaker_order" not in rules or not isinstance(rules["tie_breaker_order"], list):
        raise RulesFormatError("Invalid rules: missing 'tie_breaker_order' list.")

    # Validate each rule
    for i, r in enumerate(rules["rules"]):
        if not isinstance(r, dict):
            raise RulesFormatError(f"Invalid rule at index {i}: not a dict.")
        if "label" not in r or not isinstance(r["label"], str):
            raise RulesFormatError(f"Invalid rule at index {i}: missing 'label'.")
        if "triggers" not in r or not isinstance(r["triggers"], list):
            raise RulesFormatError(f"Invalid rule at index {i}: missing 'triggers' list.")
        if "reasons" not in r or not isinstance(r["reasons"], str):
            raise RulesFormatError(f"Invalid rule at index {i}: missing 'reasons' string.")

    return rules


def compute_severity(
    patient: Dict[str, Any],
    rules: Optional[Dict[str, Any]] = None,
    rules_path: Path = DEFAULT_RULES_PATH,
) -> SeverityResult:
    """
    Compute patient severity using symptom substring matching only (V1).
    - Looks at patient["symptomes_exprimes"] (list of strings)
    - Ignores patient["constantes"] entirely
    - Applies tie-breaker order (most severe first)
    """
    if rules is None:
        rules = load_severity_rules(rules_path)

    patient_id = str(patient.get("id", "")).strip() or "UNKNOWN"

    symptomes = patient.get("symptomes_exprimes", [])
    if not isinstance(symptomes, list):
        symptomes = []

    norm_symptoms = _normalize_list(symptomes)

    # Pre-normalize triggers for each rule
    label_to_rule: Dict[str, Dict[str, Any]] = {}
    for r in rules["rules"]:
        label_to_rule[r["label"]] = {
            "reasons": r["reasons"],
            "triggers_norm": _normalize_list(r["triggers"]),
            "triggers_raw": r["triggers"],
        }

    # Apply tie-breaker order strictly (e.g. ROUGE -> JAUNE -> VERT -> GRIS)
    for label in rules["tie_breaker_order"]:
        if label not in label_to_rule:
            continue

        triggers_norm = label_to_rule[label]["triggers_norm"]
        matched: List[str] = []

        # Match if any trigger is substring of any symptom OR symptom substring of trigger
        for trig_norm, trig_raw in zip(triggers_norm, label_to_rule[label]["triggers_raw"]):
            for s in norm_symptoms:
                if not s:
                    continue
                if trig_norm and (trig_norm in s or s in trig_norm):
                    matched.append(trig_raw)
                    break

        if matched:
            return SeverityResult(
                patient_id=patient_id,
                severity=label,
                matched_triggers=sorted(set(matched)),
                reason=label_to_rule[label]["reasons"],
                rule_source=str(rules_path),
            )

    # Default if nothing matched
    return SeverityResult(
        patient_id=patient_id,
        severity=rules["default_label"],
        matched_triggers=[],
        reason="Default label (no symptom matched)",
        rule_source=str(rules_path),
    )
