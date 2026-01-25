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

# --- 2. LES CONSTANTES (NOUVEAU : C'est ici qu'on stocke les règles) ---

class TransportTimes(BaseModel):
    to_unit: int
    to_consultation: int

class RoomCapacities(BaseModel):
    waiting_rooms: Dict[str, int]
    consultation_room: int
    soins_critiques: int
    units: Dict[str, int]

class HospitalConstants(BaseModel):
    """Les règles du jeu chargées depuis le JSON"""
    transport_times_min: TransportTimes
    capacities_max: RoomCapacities

# --- 3. LES ACTEURS ---

class Patient(BaseModel):
    id: str
    severity: Severity
    symptom: str
    location: str
    status: PatientStatus
    arrival_time: int

class Staff(BaseModel):
    id: str
    role: StaffRole
    location: str
    is_busy: bool = False

class Room(BaseModel):
    id: str
    name: str
    capacity: int
    occupancy: int = 0
    patients: List[str] = []
    staff: List[str] = []

# --- 4. L'ÉTAT GLOBAL ---

class HospitalState(BaseModel):
    time: int = 0
    is_running: bool = False
    
    # Lieux
    triage_zone: Room
    waiting_rooms: Dict[str, Room]
    consultation_room: Room
    soins_critiques: Room
    units: Dict[str, Room]
    
    # Acteurs
    patients: Dict[str, Patient] = {}
    staff: Dict[str, Staff] = {}
    
    # Transport flags
    transport_consultation_active: bool = False
    transport_hospital_active: bool = False

class StateFile(BaseModel):
    hospital_name: str
    constants: HospitalConstants  # <--- On ajoute les constantes ici
    state: HospitalState