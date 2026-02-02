# Moteur de gestion des urgences

Le module `tools.py` implément un **moteur de règles opérationnelles** pour la gestion d'un service d'urgences hospitalières simulé.

Il permet de :
- gérer les déplacements des patients entre zones
- géeer les déplacements et occupations du personnel
- appliquer des contraintes médicales et organisationnelles strictes
- produire un tableau de bord décisionnel.
 
Le moteur repose sur un **éta global persistant** stocké dans un fichier JSON.

## 1. Architecture générale

L'état global du système est stocké dans `data/stat/urgence_state.json`. Il contient notamment :
- le temps simulé `state.time`
- les patients `state.patients`
- le personnel `state/staff`
- les salles (triage, salles d'attente, consultation, soins critiques, unités)

Chaque action
1. charge l'état depuis le JSON,
2. applique des règles métier
3. journalise l'événement
4. sauvegarde l'état modifié

Aucune logique ne repose sur un état en mémoire longue.

## 2. Fonctions utilitaires

### 2.1. Chargement et sauvegarde de l'état

```python
_get_state()
_save_state(state)
```

- `_get_state()` charge l'état courant depuis le JSON
- `_save_state(state)` enregistre les modifications.

Ces fonctions garantissent que **toutes les opérations travaillent sur un état cohérent et traçable**.

### 2.2. Normalisation des identifiants de salle

```python
_normalize_room_id(rid)
```

Cette fonction permet d'accepter des entrées utilisateurs ou LLM non strictes :

| Entrée      | Normalisée        |
| ----------- | ----------------- |
| `"sc"`      | `soins_critiques` |
| `"consult"` | `consultation`    |
| `"salle 1"` | `wr_01`           |

Elle évite les erreurs dues à des varitions de langage naturel.

### 2.3. Sévérité et priorités

```python
_get_severity_score(severity)
```

Mappe une gravité médicale vers un score numérique :

| Gravité | Score |
| ------- | ----- |
| ROUGE   | 4     |
| JAUNE   | 3     |
| VERT    | 2     |
| GRIS    | 1     |

Ce score est utilisé pour :
- les règles d'accès aux zones
- le tri des patients
- les alertes du dashboard

## 3. Annuaire du personnel

### 3.1. Infirmiers

```python
get_staff_directory()
```
Affiche :
- les infirmiers présents ou occupés
- leur localisation
- leur état (`DISPO`, `OCCUPÉ`, `FIN DE SERVICE`)

L'ordre est volontairement aléatoire pour éviter un biais de sélection.

### 3.2. Aide-soignants

```python
get_as_directory()
```
Affiche :
- les aide-soignants disponibles ou occu^és
- le temps restant si occupés

## 4. Surveillance des salles

```python
_check_surveillance_in_room(room)
```
Vérifie qu'une salle contenant des patients est surveillée par un infirmier **ou** un aide-soignant physiquement présent.

Cette fonction est utilisée par le dashboard pour détecter les situations à risque.

## 5. Transfert de personnem (surveillance)

```python
transfer_staff(staff_id, target_room_id)
```

### Règles principales
- seuls les infirmiers et aide-soignants peuvent être déplacés
- le personnel doit être présent et non occupé
- les médecin ne peuvent pas être déplacés

### Zones autorisées
- Triage ↔ Salles d'attentes
- Salles d'attente ↔ Salles d'attente

les zones de soins critiques, consultation et hospitalisation sont exclues.

## 6. Transfert patients sans escorte

Déplacement simple sans mobilisation d'aide-soignant :

```python
transfer_patient_basic(patient_id, target_room_id)
```

### Règles géographiques

| Origine | Destination     |
| ------- | --------------- |
| Triage  | Salle d’attente |
| Triage  | Soins critiques |
| Salle   | Salle           |

### Règles médicales
- seuls les patients ROUGE peuvent entrer en soins critiques
- les capacités des salles sont strictement respectées

### Sécurité
Avant tout ajout, le patient est supprimé de toutes les salles existantes afin d'éviter toute duplication.

## 7. Transfert patient avec escorte

Fonction simulant un transprt réel mobilisant un aide-soignant :

```python
transfer_patient_with_escort(patient_id, target_room_id)
```

### Sélection de l'AS :
- consultation → priorité AS_01
- hospitalisation → priorité AS_02
- fallback si absent

### 7.1. Vers consultation

Conditions :
- depuis tirage : patients ROUGE uniquement
- depuis salle d'attente : tous les patients
- médecin présent, libre
- salle de consultation libre

Effets :
- AS bloqué pendant le transport
- médecinn bloqué pendant la consultation
- durée aléatoire de consultation

### 7.2. Vers hospitalisation (boarding)

Conditions :
- départ depuis salle d'attente
- décision médicale déjà prise
- capacité de l'unité disponible

Effets :
- AS bloqué plus longtemps
- patient hospitalisé
- durée de séjour simulée

## 8. Tableau de bord décisionnel

```python
get_hospital_dashboard()
```

Le dashboard génère des alertes en cas de :
- patient ROUGE non pris en charge
- dépassement de délais d'attente
- salle sans surveillance
- patients en attente d'hospitalisation (boarding)

Il affiche également l'état de la consultation :
- médecin absent / occupé / libre
- occupation de la salle

## 9. Liste priorisée des patients

```python
get_patient_list(location)
```

Les patients sont triés selon une priorité opérationnelle :
1. ROUGE
2. dépassement de délai
3. JAUNE
4. VERT
5. GRIS

Des tags visuels permettent d'identifier immédiatement :
- urgences vitales
- situations de dépassement
- boarding vers hospitalisation

## 10. Principes de conception

- règles explicites et strictes
- prévention systématique des incohérences d'état
- aucune dépendance à un état mémoire implicite
- moteur pilotable par interface ou LLM
- logique métier prioritaire sur l'optimisation algorithmique





