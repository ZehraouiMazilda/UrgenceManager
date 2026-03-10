# Documentation technique - Système de régulation des urgences hospitalières

# 🏥 Système de régulation des urgences hospitalières

### Documentation technique - Architecture & Modules

---

## 1. Vue d'ensemble

Ce projet implémente un **simulateur temps réel des urgences hospitalières**, combinant :

* une **simulation déterministe** du parcours patient
* un **moteur de règles métier médicales**
* une **interface Streamlit interactive**
* une **IA de régulation (LLM Mistral)** capable de prendre des décisions opérationnelles
* un **système de scénarios de test**
* une **traçabilité complète via CSV temps réel**

Le système est conçu comme un **jeu de simulation sérieux**, où le temps avance par ticks discrets et où chaque décision impacte l'état global de l'hôpital.

---

## 2. Architecture globale

```
┌────────────────────┐
│  Interface Streamlit│
│  (simulation.py)   │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  État hôpital      │◄──── JSON persisté
│  (HospitalState)  │
└─────────┬──────────┘
          │
   ┌──────┴────────┐
   ▼               ▼
Simulation     IA / LLM
Déterministe   (Mistral)
   │               │
   └──────┬────────┘
          ▼
   CSV temps réel
 (patients / staff)
```

---

## 3. Modèles de données (`src/models.py`)

### 3.1 Enums métier

* **Severity** : `ROUGE`, `JAUNE`, `VERT`, `GRIS`
* **PatientStatus** :

  * `WAITING`
  * `IN_TRANSIT`
  * `IN_CONSULTATION`
  * `BOARDING`
  * `HOSPITALIZED`
  * `DISCHARGED`
* **StaffRole** :

  * médecin
  * infirmier triage
  * infirmier salles
  * aide-soignant transport

Ces enums garantissent une **cohérence stricte** entre la simulation, les règles métier et l'IA.

---

### 3.2 Entités principales

#### Patient

Représente un patient tout au long de son parcours :

* gravité
* symptôme
* localisation
* statut
* temps d'arrivée
* temps de fin de traitement
* décision médicale post-consultation

#### Staff

Représente un agent hospitalier :

* rôle
* présence
* disponibilité
* occupation temporelle (`busy_until`)

#### Room / Unit

Représente une salle ou unité :

* capacité
* occupation
* liste des patients
* personnel présent

#### HospitalState

État global **source de vérité** :

- patients
- personnel
- salles
- unités
- temps simulé

---

## 4. Simulation principale (`simulation.py`)

### 4.1 Rôle du module

Ce module est le **cœur interactif** du système :

- interface Streamlit
- injection manuelle de patients
- contrôle du temps
- affichage temps réel
- appels à l'IA
- génération de statistiques

---

### 4.2 Boucle de simulation (Game Loop)

Chaque tick :

1. Le temps avance (`+5 minutes`)
2. Les transports se terminent
3. Les consultations se terminent
4. Les décisions médicales sont appliquées
5. Les hospitalisations évoluent
6. L'IA peut intervenir
7. L'état est persisté

➡️ Le système fonctionne comme une **machine à états déterministe augmentée par IA**.

---

## 5. Injection et transport des patients

### `inject_patient(...)`

Fonction centrale pour :

- créer un patient
- vérifier les contraintes (capacités, staff disponible)
- déclencher transports avec AS si nécessaire
- initialiser les timers (consultation, soins critiques)

Elle applique des **règles de cohérence fortes** :

- pas de consultation sans médecin libre
- pas de transport sans AS disponible
- respect strict des capacités

---

## 6. Règles métier et sécurité

### `verify_rules(state)`

Détecte les violations critiques :

- patient **ROUGE hors soins critiques**
- salle avec patients **sans surveillance**
- temporisation des alertes (> 15 min)

Ces règles sont utilisées :

- en simulation libre
- en scénarios
- comme signal d'échec dans les objectifs

---

## 7. Statistiques temps réel (CSV)

### Principe

Chaque session génère **2 CSV indépendants** :

- `*_patients.csv`
- `*_staff.csv`

Les CSV sont :

- créés au démarrage
- enrichis en temps réel
- **jamais réinitialisés pendant la session**

### Usages

- graphiques temporels
- parcours patients (Sankey)
- métriques de performance
- audit post-simulation

---

## 8. Module Scénarios (`scenarios.py`)

### Objectif

Permettre des **tests reproductibles** du système :

- surcharge
- pénurie de personnel
- stress test ROUGE
- saturation soins critiques

### Fonctionnement

Un scénario contient :

- une durée
- un état initial
- une timeline d'actions horodatées
- des métriques attendues

Chaque scénario :

- avance par ticks
- injecte automatiquement des patients
- appelle l'IA
- mesure les performances

---

## 9. IA de régulation - Deux niveaux

### 9.1 IA Supervisor (JSON strict)

- analyse globale
- produit :

  - résumé
  - risques
  - recommandations
- **aucune action directe**

→ Utilisée pour **audit, explication, supervision**

---

### 9.2 IA Agent (Tool Calling)

- agit directement sur l'hôpital
- appelle des outils :

  - `assign_room`
  - `discharge_patient`
  - `move_staff`
  - `tick`
- fonctionne en **boucle multi-tours**
- respecte des règles strictes de priorité médicale

→ Utilisée pour **pilotage opérationnel**

---

## 10. Moteur (`hospital_server.py`)

Expose l'hôpital comme un **serveur d'outils** :

- état en mémoire
- outils atomiques
- aucune logique médicale lourde
- conçu pour être **LLM-safe**

➡️ Séparation claire :

- **LLM décide**
- **Agent exécute**

---

## 11. Triage médical (`compute_severity.py`) (out-of-scope)

### Version actuelle

- basé uniquement sur les symptômes textuels
- matching robuste (normalisation, accents, substrings)
- règles externalisées en JSON
- tie-breaker explicite (ROUGE > JAUNE > …)

Version extensible ultérieurement (constantes, âge, constantes vitales, etc.).

---

## 12. Philosophie générale

Ce projet respecte volontairement :

- **séparation stricte des responsabilités**
- **traçabilité totale**
- **déterminisme + IA contrôlée**
- **refus de la magie implicite**

L'IA n'est **ni omnisciente ni toute-puissante** :

- elle agit dans un cadre
- elle peut échouer
- elle est auditée

---

## 13. Extensions prévues (naturelles)

- multi-médecins
- urgences vitales concurrentes
- coûts humains / fatigue
- KPI hospitaliers
- apprentissage par scénario
- replay CSV → simulation

---
