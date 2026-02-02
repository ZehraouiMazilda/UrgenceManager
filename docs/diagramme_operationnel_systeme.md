### Diagramme opérationnel du système

Ce diagramme représente :
- l’état global
- les entités principales
- les 3 types de transferts
- les contrôles critiques (sévérité, ressources, capacité)

Tout est relié à l’état JSON → aucune action n’est locale.

```mermaid
flowchart LR
    %% =========================
    %% GLOBAL STATE
    %% =========================
    STATE[(urgence_state.json)]

    %% =========================
    %% ROOMS
    %% =========================
    TRIAGE[Triage]
    WR1[Salle Attente 1]
    WR2[Salle Attente 2]
    WR3[Salle Attente 3]
    CONSULT[Consultation]
    SC[Soins Critiques]
    UNIT1[Unité Hôpital A]
    UNIT2[Unité Hôpital B]

    %% =========================
    %% STAFF
    %% =========================
    INF[Infirmiers]
    AS[Aides-soignants]
    DOC[Médecin]

    %% =========================
    %% PATIENT FLOW - BASIC
    %% =========================
    TRIAGE -->|Basic| WR1
    TRIAGE -->|Basic| WR2
    TRIAGE -->|Basic| WR3
    TRIAGE -->|ROUGE only| SC
    WR1 -->|Basic| WR2
    WR2 -->|Basic| WR3
    WR3 -->|Basic| WR1

    %% =========================
    %% PATIENT FLOW - ESCORTED
    %% =========================
    TRIAGE -->|Escort + AS\nROUGE| CONSULT
    WR1 -->|Escort + AS| CONSULT
    WR2 -->|Escort + AS| CONSULT
    WR3 -->|Escort + AS| CONSULT

    WR1 -->|Escort + AS\nDecision médicale| UNIT1
    WR2 -->|Escort + AS\nDecision médicale| UNIT1
    WR3 -->|Escort + AS\nDecision médicale| UNIT2

    %% =========================
    %% STAFF MOVEMENTS
    %% =========================
    INF -->|Surveillance| TRIAGE
    INF -->|Surveillance| WR1
    INF -->|Surveillance| WR2
    INF -->|Surveillance| WR3

    AS -->|Surveillance| TRIAGE
    AS -->|Surveillance| WR1
    AS -->|Surveillance| WR2
    AS -->|Surveillance| WR3

    %% =========================
    %% CONSTRAINTS (ANNOTATIONS)
    %% =========================
    CONSULT -.->|Médecin présent\net libre| DOC
    CONSULT -.->|Capacité = 1| CONSULT
    SC -.->|ROUGE uniquement| SC
    UNIT1 -.->|Capacité| UNIT1
    UNIT2 -.->|Capacité| UNIT2

    %% =========================
    %% STATE ACCESS
    %% =========================
    STATE --- TRIAGE
    STATE --- WR1
    STATE --- WR2
    STATE --- WR3
    STATE --- CONSULT
    STATE --- SC
    STATE --- UNIT1
    STATE --- UNIT2
    STATE --- INF
    STATE --- AS
    STATE --- DOC
```

##### Légende

<sup>**Flèches pleines** : flux patients</sup>  
<sup>**Flèches pointillées** : contraintes métier</sup>  
<sup>**Basic** : `transfer_patient_basic`</sup>  
<sup>**Escort + AS** : `transfer_patient_with_escort`</sup>  
<sup>**Surveillance** : `transfer_staff`</sup>  

