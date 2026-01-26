from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel

# --- 1. ENUMS ---
class Severity(str, Enum):
    GRIS = "GRIS"
    VERT = "VERT"
    JAUNE = "JAUNE"
    ROUGE = "ROUGE"

class StaffRole(str, Enum):
    MEDECIN = "medecin_consultation"
    INFIRMIER_TRIAGE = "infirmier_triage"
    INFIRMIER_SALLES = "infirmier_salles"
    AIDE_SOIGNANT = "aide_soignant_transport"

class PatientStatus(str, Enum):
    WAITING = "waiting"
    IN_TRANSIT = "in_transit"
    IN_CONSULTATION = "in_consultation"
    HOSPITALIZED = "hospitalized"
    DISCHARGED = "discharged"

# --- 2. CONSTANTES ---
class TransportTimes(BaseModel):
    to_unit: int
    to_consultation: int

class RoomCapacities(BaseModel):
    waiting_rooms: Dict[str, int]
    consultation_room: int
    soins_critiques: int
    units: Dict[str, int]

class HospitalConstants(BaseModel):
    transport_times_min: TransportTimes
    capacities_max: RoomCapacities

# --- 3. ACTEURS ---
class Patient(BaseModel):
    id: str
    severity: Severity
    symptom: str
    location: str
    status: PatientStatus
    arrival_time: int
    treatment_end_time: int = 0
    medical_decision: Optional[str] = None 

class Staff(BaseModel):
    id: str
    role: StaffRole
    location: str
    is_busy: bool = False
    busy_until: int = 0
    # NOUVEAU : Pour se souvenir du code de retour (ex: tran_consult_wr)
    return_transport_code: Optional[str] = None 

class Room(BaseModel):
    id: str
    name: str
    capacity: int
    occupancy: int = 0
    patients: List[str] = []
    staff: List[str] = []

# --- 4. LOGGING ---
class PatientLog(BaseModel):
    timestamp: int
    id: str
    location: str          # Code transport ou salle
    severity: str
    escort_id: Optional[str] = None

class StaffLog(BaseModel):
    timestamp: int
    id: str
    location: str          # Code transport
    patient_handling_id: Optional[str] = None
    patient_symptom: Optional[str] = None
    patient_color: Optional[str] = None

class SimulationSession(BaseModel):
    session_id: str
    logs_patients: List[PatientLog] = []
    logs_staff: List[StaffLog] = []

# --- 5. ÉTAT GLOBAL ---
class HospitalState(BaseModel):
    time: int = 0
    is_running: bool = False
    triage_zone: Room
    waiting_rooms: Dict[str, Room]
    consultation_room: Room
    soins_critiques: Room
    units: Dict[str, Room]
    patients: Dict[str, Patient] = {}
    staff: Dict[str, Staff] = {}
    transport_consultation_active: bool = False
    transport_hospital_active: bool = False

class StateFile(BaseModel):
    hospital_name: str
    constants: HospitalConstants
    state: HospitalState