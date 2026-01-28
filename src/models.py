"""
Module de modèles de données pour le système de gestion des urgences hospitalières.

Ce module définit les structures de données principales utilisées dans le système,
incluant les patients, le personnel, les salles, et l'état global de l'hôpital.
"""

from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


# =============================================================================
# 1. ENUMS (Énumérations)
# =============================================================================

class Severity(str, Enum):
    """
    Niveau de gravité d'un patient selon le système de triage.
    
    Attributes:
        GRIS: Patient non urgent, ne nécessite pas les urgences
        VERT: Pathologie non vitale et non urgente
        JAUNE: Pathologie non vitale mais urgente
        ROUGE: Pathologie potentiellement vitale et urgente
    """
    GRIS = "GRIS"
    VERT = "VERT"
    JAUNE = "JAUNE"
    ROUGE = "ROUGE"


class StaffRole(str, Enum):
    """
    Rôles du personnel hospitalier.
    
    Attributes:
        MEDECIN: Médecin en consultation
        INFIRMIER_TRIAGE: Infirmier au triage
        INFIRMIER_SALLES: Infirmier en salle d'attente
        AIDE_SOIGNANT: Aide-soignant pour transport
    """
    MEDECIN = "medecin_consultation"
    INFIRMIER_TRIAGE = "infirmier_triage"
    INFIRMIER_SALLES = "infirmier_salles"
    AIDE_SOIGNANT = "aide_soignant_transport"


class PatientStatus(str, Enum):
    """
    Statut du patient dans le parcours de soins.
    
    Attributes:
        WAITING: En attente de consultation
        IN_TRANSIT: En cours de transport
        IN_CONSULTATION: En consultation avec le médecin
        BOARDING: En attente de transfert vers une unité d'hospitalisation
        HOSPITALIZED: Hospitalisé dans une unité
        DISCHARGED: Sorti de l'hôpital
    """
    WAITING = "waiting"
    IN_TRANSIT = "in_transit"
    IN_CONSULTATION = "in_consultation"
    BOARDING = "boarding"
    HOSPITALIZED = "hospitalized"
    DISCHARGED = "discharged"


# =============================================================================
# 2. CONSTANTES DE CONFIGURATION
# =============================================================================

class TransportTimes(BaseModel):
    """
    Durées de transport en minutes.
    
    Attributes:
        to_unit: Temps pour transporter vers une unité d'hospitalisation (45 min)
        to_consultation: Temps pour transporter vers la consultation (5 min)
    """
    to_unit: int = Field(..., description="Temps de transport vers unité (min)")
    to_consultation: int = Field(..., description="Temps de transport vers consultation (min)")


class RoomCapacities(BaseModel):
    """
    Capacités maximales des différentes salles.
    
    Attributes:
        waiting_rooms: Capacités des salles d'attente
        consultation_room: Capacité de la salle de consultation
        soins_critiques: Capacité des soins critiques
        units: Capacités des unités d'hospitalisation
    """
    waiting_rooms: Dict[str, int] = Field(..., description="Capacités des salles d'attente")
    consultation_room: int = Field(..., description="Capacité de la consultation")
    soins_critiques: int = Field(..., description="Capacité des soins critiques")
    units: Dict[str, int] = Field(..., description="Capacités des unités")


class HospitalConstants(BaseModel):
    """
    Constantes de configuration de l'hôpital.
    
    Attributes:
        transport_times_min: Durées de transport
        capacities_max: Capacités maximales des salles
    """
    transport_times_min: TransportTimes
    capacities_max: RoomCapacities


# =============================================================================
# 3. ACTEURS PRINCIPAUX
# =============================================================================

class Patient(BaseModel):
    """
    Représente un patient dans le système.
    
    Attributes:
        id: Identifiant unique du patient (ex: PAT_001)
        severity: Niveau de gravité (ROUGE, JAUNE, VERT, GRIS)
        symptom: Symptôme principal du patient
        location: Localisation actuelle (ex: 'triage', 'wr_01', 'consultation')
        status: Statut du patient dans le parcours de soins
        arrival_time: Temps d'arrivée du patient (en minutes)
        treatment_end_time: Temps de fin de traitement prévu (0 si non défini)
        medical_decision: Décision médicale post-consultation (destination)
    """
    id: str = Field(..., description="Identifiant unique du patient")
    severity: Severity = Field(..., description="Niveau de gravité")
    symptom: str = Field(..., description="Symptôme principal")
    location: str = Field(..., description="Localisation actuelle")
    status: PatientStatus = Field(..., description="Statut du patient")
    arrival_time: int = Field(..., description="Temps d'arrivée (min)")
    treatment_end_time: int = Field(default=0, description="Temps de fin de traitement (min)")
    medical_decision: Optional[str] = Field(default=None, description="Décision médicale")


class Staff(BaseModel):
    """
    Représente un membre du personnel.
    
    Attributes:
        id: Identifiant unique (ex: DOC_01, INF_TRIAGE_01, AS_01)
        role: Rôle du personnel
        location: Localisation actuelle
        is_busy: Indique si le personnel est occupé
        busy_until: Temps jusqu'à la fin de l'occupation (en minutes)
        return_transport_code: Code de retour pour le transport
        is_present: Indique si le personnel est présent (ou en fin de service)
    """
    id: str = Field(..., description="Identifiant unique du personnel")
    role: StaffRole = Field(..., description="Rôle du personnel")
    location: str = Field(..., description="Localisation actuelle")
    is_busy: bool = Field(default=False, description="Personnel occupé?")
    busy_until: int = Field(default=0, description="Occupé jusqu'à (min)")
    return_transport_code: Optional[str] = Field(default=None, description="Code de retour transport")
    is_present: bool = Field(default=True, description="Personnel présent?")


class Room(BaseModel):
    """
    Représente une salle de l'hôpital.
    
    Attributes:
        id: Identifiant de la salle (ex: 'wr_01', 'consultation', 'ortho')
        name: Nom lisible de la salle
        capacity: Capacité maximale de la salle
        occupancy: Nombre actuel de patients
        patients: Liste des IDs des patients dans la salle
        staff: Liste des IDs du personnel dans la salle
    """
    id: str = Field(..., description="Identifiant de la salle")
    name: str = Field(..., description="Nom de la salle")
    capacity: int = Field(..., description="Capacité maximale")
    occupancy: int = Field(default=0, description="Occupation actuelle")
    patients: List[str] = Field(default_factory=list, description="IDs des patients")
    staff: List[str] = Field(default_factory=list, description="IDs du personnel")


# =============================================================================
# 4. LOGGING ET HISTORIQUE
# =============================================================================

class PatientLog(BaseModel):
    """
    Log d'un événement patient.
    
    Attributes:
        timestamp: Moment de l'événement (en minutes)
        id: ID du patient
        location: Localisation lors de l'événement
        severity: Gravité du patient
        escort_id: ID de l'escorte (si applicable)
    """
    timestamp: int = Field(..., description="Temps de l'événement (min)")
    id: str = Field(..., description="ID du patient")
    location: str = Field(..., description="Localisation")
    severity: str = Field(..., description="Gravité")
    escort_id: Optional[str] = Field(default=None, description="ID de l'escorte")


class StaffLog(BaseModel):
    """
    Log d'un événement personnel.
    
    Attributes:
        timestamp: Moment de l'événement (en minutes)
        id: ID du personnel
        location: Localisation lors de l'événement
        patient_handling_id: ID du patient pris en charge
        patient_symptom: Symptôme du patient
        patient_color: Couleur/gravité du patient
    """
    timestamp: int = Field(..., description="Temps de l'événement (min)")
    id: str = Field(..., description="ID du personnel")
    location: str = Field(..., description="Localisation")
    patient_handling_id: Optional[str] = Field(default=None, description="ID du patient")
    patient_symptom: Optional[str] = Field(default=None, description="Symptôme du patient")
    patient_color: Optional[str] = Field(default=None, description="Gravité du patient")


class SimulationSession(BaseModel):
    """
    Session de simulation avec historique des logs.
    
    Attributes:
        session_id: Identifiant unique de la session
        logs_patients: Historique des événements patients
        logs_staff: Historique des événements personnel
    """
    session_id: str = Field(..., description="ID de la session")
    logs_patients: List[PatientLog] = Field(default_factory=list, description="Logs patients")
    logs_staff: List[StaffLog] = Field(default_factory=list, description="Logs personnel")


# =============================================================================
# 5. ÉTAT GLOBAL DU SYSTÈME
# =============================================================================

class HospitalState(BaseModel):
    """
    État complet du système hospitalier à un instant T.
    
    Attributes:
        time: Temps actuel de la simulation (en minutes)
        is_running: Indique si la simulation est en cours
        triage_zone: Zone de triage
        waiting_rooms: Salles d'attente (wr_01, wr_02, wr_03)
        consultation_room: Salle de consultation
        soins_critiques: Salle de soins critiques
        units: Unités d'hospitalisation (ortho, cardio, neuro, pneumo)
        patients: Dictionnaire de tous les patients actifs
        staff: Dictionnaire de tout le personnel
        transport_consultation_active: Transport vers consultation actif?
        transport_hospital_active: Transport vers hôpital actif?
    """
    time: int = Field(default=0, description="Temps de simulation (min)")
    is_running: bool = Field(default=False, description="Simulation en cours?")
    triage_zone: Room = Field(..., description="Zone de triage")
    waiting_rooms: Dict[str, Room] = Field(..., description="Salles d'attente")
    consultation_room: Room = Field(..., description="Salle de consultation")
    soins_critiques: Room = Field(..., description="Soins critiques")
    units: Dict[str, Room] = Field(..., description="Unités d'hospitalisation")
    patients: Dict[str, Patient] = Field(default_factory=dict, description="Patients actifs")
    staff: Dict[str, Staff] = Field(default_factory=dict, description="Personnel")
    transport_consultation_active: bool = Field(default=False, description="Transport consult actif?")
    transport_hospital_active: bool = Field(default=False, description="Transport hôpital actif?")


class StateFile(BaseModel):
    """
    Structure du fichier d'état complet.
    
    Attributes:
        hospital_name: Nom de l'hôpital
        constants: Constantes de configuration
        state: État actuel du système
    """
    hospital_name: str = Field(..., description="Nom de l'hôpital")
    constants: HospitalConstants = Field(..., description="Constantes")
    state: HospitalState = Field(..., description="État du système")