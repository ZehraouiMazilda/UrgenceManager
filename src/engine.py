import datetime
from typing import List, Optional
from src.models import HospitalState, Patient, Severity, PatientStatus, Room

class HospitalManager:
    """
    Le 'Moteur de Jeu'. Il contient toute la logique de déplacement et de règles.
    """
    def __init__(self, state: HospitalState):
        self.state = state

    # --- 1. AJOUTER UN PATIENT (Injection Manuelle) ---
    def add_patient(self, severity: str, symptoms: str):
        """Crée un patient et l'oriente selon sa gravité (Règle V1)."""
        
        # Création de l'ID unique
        new_id = f"PAT_{len(self.state.patients) + 1:03d}"
        
        # Création de l'objet Patient
        new_patient = Patient(
            patient_id=new_id,
            severity=severity,
            symptoms=[symptoms],
            location="outside",
            status=PatientStatus.ARRIVED
        )
        
        self.state.patients.append(new_patient)
        
        # --- RÈGLE 1 : LES ROUGES (Vital) ---
        # "Les rouges : directement en soins intensif"
        if severity == "ROUGE":
            target_room = self.state.resources.soins_critiques
            if target_room.occupancy < target_room.capacity_max:
                new_patient.location = "soins_critiques"
                new_patient.status = PatientStatus.IN_CONSULTATION # ou traitement
                target_room.patients.append(new_patient.patient_id)
                target_room.occupancy += 1
                return f"🚨 Patient {severity} envoyé direct en SOINS CRITIQUES !"
            else:
                # Fallback si Soins critiques pleins (Cas limite)
                self.state.resources.waiting_rooms["waiting_room_01"].patients.append(new_patient.patient_id)
                new_patient.location = "waiting_room_01"
                new_patient.status = PatientStatus.WAITING_ROOM
                return f"⚠️ Soins Critiques COMPLETS ! Patient {severity} en Attente (Prio Max)."

        # --- RÈGLE 2 : LES AUTRES (Jaune, Vert, Gris) ---
        # "Il l'envoi dans une salle d'attente"
        else:
            # On choisit la salle 1 par défaut pour l'instant
            target_room = self.state.resources.waiting_rooms["waiting_room_01"]
            target_room.patients.append(new_patient.patient_id)
            target_room.occupancy += 1
            new_patient.location = "waiting_room_01"
            new_patient.status = PatientStatus.WAITING_CONSULTATION
            return f"Patient {severity} placé en Salle d'Attente."

    # --- 2. LA BOUCLE DE GESTION (Le 'Tick' du jeu) ---
    def process_queue(self):
        """
        Regarde qui attend et attribue les ressources (Médecins/Salles).
        Appelé à chaque clic sur 'Actualiser'.
        """
        logs = []
        
        # A. Récupérer tous les patients en attente de consultation
        waiting_patients = [p for p in self.state.patients if p.status == PatientStatus.WAITING_CONSULTATION]
        
        # B. TRIER PAR PRIORITÉ (Ta règle : Jaune > Vert > Gris)
        # On donne un score : ROUGE=4, JAUNE=3, VERT=2, GRIS=1
        severity_score = {"ROUGE": 4, "JAUNE": 3, "VERT": 2, "GRIS": 1}
        
        # On trie la liste : les plus gros scores en premier
        waiting_patients.sort(key=lambda p: severity_score.get(p.severity.value, 0), reverse=True)
        
        # C. ATTRIBUER UN MÉDECIN
        # On vérifie si la salle de consult est libre
        consult_room = self.state.resources.consultation_room
        
        if consult_room.occupancy == 0 and waiting_patients:
            # On prend le premier patient prioritaire
            patient_to_move = waiting_patients[0]
            
            # On le déplace (Téléportation V1 - On fera les infirmiers/transport après)
            # 1. Sortir de la salle d'attente
            old_room_id = patient_to_move.location
            if old_room_id in self.state.resources.waiting_rooms:
                self.state.resources.waiting_rooms[old_room_id].patients.remove(patient_to_move.patient_id)
                self.state.resources.waiting_rooms[old_room_id].occupancy -= 1
            
            # 2. Entrer en consultation
            consult_room.patients = [patient_to_move.patient_id]
            consult_room.occupancy = 1
            patient_to_move.location = "consultation_room"
            patient_to_move.status = PatientStatus.IN_CONSULTATION
            
            logs.append(f"✅ Patient {patient_to_move.patient_id} ({patient_to_move.severity.value}) est entré en CONSULTATION.")
            
        return logs