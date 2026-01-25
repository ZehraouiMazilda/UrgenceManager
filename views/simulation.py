import streamlit as st
import time
from src.utils import load_initial_state, save_state  # <--- AJOUT CRITIQUE ICI
import os
from src.models import Patient, Severity, PatientStatus

def check_presence(state, room_staff_list, role_tag):
    """
    Vérifie la présence et le statut (is_busy) d'un membre du staff dans une salle.
    """
    # 1. On cherche si un ID contenant le role (ex: "INF") est assigné à cette salle
    staff_id = next((s_id for s_id in room_staff_list if role_tag in s_id), None)
    
    if not staff_id:
        return "❌ Absent" # Pas assigné à cette salle
    
    # 2. On récupère la fiche réelle de l'agent dans le dictionnaire global
    agent = state.staff.get(staff_id)
    
    if not agent:
        return "❌ Introuvable" # ID dans la salle mais pas dans la liste staff (Erreur JSON)
        
    # 3. On vérifie le booléen is_busy
    if agent.is_busy:
        return "🔴 Occupé" # is_busy = true
    else:
        return "🟢 Présent" # is_busy = false

def show_simulation():
    # --- 1. INIT SESSION STATE ---
    if "sim_running" not in st.session_state:
        st.session_state.sim_running = False
    if "sim_time" not in st.session_state:
        st.session_state.sim_time = 0
    
    # Chargement initial
    if "hospital_state" not in st.session_state:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        state_path = os.path.join(base_dir, "data", "state", "urgence_state.json")
        try:
            st.session_state.hospital_state = load_initial_state(state_path)
        except Exception as e:
            st.error(f"Erreur chargement State : {e}")
            st.stop()
            
    state = st.session_state.hospital_state

    # --- 2. ENTÊTE & CONTRÔLES ---
    st.markdown("## 🎮 Simulateur Live (God Mode)")
    st.caption("Supervision temps réel : Flux, Ressources et Personnels.")

    col_controls, col_timer = st.columns([1, 2], gap="large")
    with col_controls:
        c_start, c_stop = st.columns(2)
        with c_start:
            if not st.session_state.sim_running:
                if st.button("▶️ Démarrer", use_container_width=True, type="primary"):
                    st.session_state.sim_running = True
                    st.rerun()
            else:
                if st.button("⏸️ Pause", use_container_width=True):
                    st.session_state.sim_running = False
                    st.rerun()

        with c_stop:
            # RESET COMPLET qui vide aussi la mémoire pour forcer la relecture du JSON
            if st.button("⏹️ Reset", use_container_width=True):
                st.session_state.sim_running = False
                st.session_state.sim_time = 0
                if "hospital_state" in st.session_state:
                    del st.session_state["hospital_state"] # On vide la mémoire
                st.rerun()

    with col_timer:
        hours = st.session_state.sim_time // 60
        minutes = st.session_state.sim_time % 60
        st.metric("Temps Simulé", f"{hours:02d}h{minutes:02d}", delta="En cours" if st.session_state.sim_running else "Pause")

    st.divider()

    # --- 3. RESSOURCES GLOBALES ---
    c_pat, c_doc, c_inf, c_aid = st.columns(4)

    # Box 1 : Patients & Injection
    with c_pat:
        with st.container(border=True):
            st.markdown(f"**🤒 Total Patients : {len(state.patients)}**")
            with st.popover("➕ Nouvelle Admission"):
                st.markdown("### Triage Rapide")
                from src.utils import load_symptoms_config
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                symptoms_path = os.path.join(base_dir, "data", "symptoms.json")
                symptoms_map = load_symptoms_config(symptoms_path)

                if symptoms_map:
                    gravite = st.selectbox("Gravité", list(symptoms_map.keys()))
                    symptome = st.selectbox("Symptôme", symptoms_map[gravite])
                    
                    if st.button("Injecter Patient"):
                        # 1. Création en mémoire
                        new_id = f"PAT_{len(state.patients)+1:03d}"
                        new_p = Patient(
                            id=new_id, severity=Severity(gravite), symptom=symptome,
                            location="triage", status=PatientStatus.WAITING, arrival_time=st.session_state.sim_time
                        )
                        state.patients[new_id] = new_p
                        
                        # 2. SAUVEGARDE SUR DISQUE (POUR LE LLM)
                        # C'est ici que l'interface parle au JSON
                        save_state(state, os.path.join(base_dir, "data", "state", "urgence_state.json"))

                        st.success(f"Ajouté : {new_id}")
                        time.sleep(0.5)
                        st.rerun()
                else:
                    st.error("Symptomes introuvables")

    # Calcul dynamique du total Staff
    nb_medecins = len([s for s in state.staff.values() if "medecin" in s.role])
    nb_infirmiers = len([s for s in state.staff.values() if "infirmier" in s.role])
    nb_as = len([s for s in state.staff.values() if "aide_soignant" in s.role])

    with c_doc: st.info(f"**Médecins : {nb_medecins}** (Total)")
    with c_inf: st.info(f"**Infirmiers : {nb_infirmiers}** (Total)")
    with c_aid: st.info(f"**Aides-Soignants : {nb_as}** (Total)")

    st.divider()

    # =========================================================================
    # BLOC 04 : LA CARTE DÉTAILLÉE (Connectée au JSON)
    # =========================================================================
    st.subheader("🗺️ Carte de l'Hôpital")

    # --- ÉTAGE 1 : CRITIQUE & CONSULTATION ---
    col_critique, col_gap, col_consult = st.columns([1.2, 0.2, 1.2])

    # 1. SOINS CRITIQUES
    with col_critique:
        sc = state.soins_critiques
        with st.container(border=True):
            st.markdown("#### ❤️ Soins Critiques")
            c1, c2 = st.columns(2)
            c1.write(f"**Patients : {sc.occupancy}**") 
            c1.caption(f"Capacité : {sc.capacity}")
            c2.error("🔴 ROUGE ONLY")
            st.write(f"Lits : {sc.patients}")

    # 2. CONSULTATION
    with col_consult:
        cons = state.consultation_room
        with st.container(border=True):
            st.markdown("#### 👨‍⚕️ Consultation")
            c1, c2 = st.columns(2)
            
            status_med = check_presence(state, cons.staff, "DOC")
            c1.write(f"**Médecin :** {status_med}")
            
            p_in = cons.patients[0] if cons.patients else "_Aucun_"
            c1.write(f"**Patient :** {p_in}")
            c2.warning("Zone stérile")

    # --- TRANSPORT 1 ---
    st.markdown("")
    as1_state = state.staff.get("AS_01")
    if as1_state and as1_state.is_busy:
        status_transport = "🚑 EN COURS"
    else:
        status_transport = "⛔ NON"
    st.info(f"⬇️ Transport vers Consultation (AS_01) : **{status_transport}**")
    st.markdown("")

    # --- ÉTAGE 2 : TRIAGE & SALLES D'ATTENTE ---
    col_triage, col_salles = st.columns([1, 3])

    # 3. TRIAGE
    with col_triage:
        tr = state.triage_zone
        with st.container(border=True):
            st.markdown("#### 📋 Triage (IOA)")
            nb_p_triage = len([p for p in state.patients.values() if p.location == "triage"])
            
            status_inf = check_presence(state, tr.staff, "INF")
            status_as = check_presence(state, tr.staff, "AS")
            
            st.write(f"**Infirmier :** {status_inf}") 
            st.write(f"**Aide Soignant :** {status_as}")
            st.divider()
            st.write(f"**Patients : {nb_p_triage}**")

    # 4. SALLES D'ATTENTE
    with col_salles:
        st.markdown("#### 🛋️ Salles d'Attente")
        c_s1, c_s2, c_s3 = st.columns([1, 1.5, 1])

        # Salle 1
        w1 = state.waiting_rooms["wr_01"]
        with c_s1:
            with st.container(border=True):
                st.write(f"**{w1.name}** ({w1.capacity}p)")
                st.write(f"Infirmier : {check_presence(state, w1.staff, 'INF')}")
                st.write(f"Patients: **{w1.occupancy}**")

        # Salle 2
        w2 = state.waiting_rooms["wr_02"]
        with c_s2:
            with st.container(border=True):
                st.write(f"**{w2.name}** ({w2.capacity}p)")
                st.write(f"Infirmier : {check_presence(state, w2.staff, 'INF')}")
                st.write(f"Patients: **{w2.occupancy}**")

        # Salle 3
        w3 = state.waiting_rooms["wr_03"]
        with c_s3:
            with st.container(border=True):
                st.write(f"**{w3.name}** ({w3.capacity}p)")
                st.write(f"Infirmier : {check_presence(state, w3.staff, 'INF')}") 
                st.write(f"Patients: **{w3.occupancy}**")

    # --- TRANSPORT 2 ---
    st.markdown("")
    as2_state = state.staff.get("AS_02")
    if as2_state and as2_state.is_busy:
        status_transport_hop = "🚑 EN COURS"
    else:
        status_transport_hop = "⛔ NON"
    st.info(f"⬇️ Transport vers Hôpital (AS_02) : **{status_transport_hop}**")
    st.markdown("")

    # --- ÉTAGE 3 : HÔPITAL (UNITÉS) ---
    st.markdown("#### 🏥 Hospitalisation (Unités)")
    u1, u2, u3, u4 = st.columns(4)

    units_data = [
        (state.units["ortho"], "🦴"),
        (state.units["neuro"], "🧠"),
        (state.units["pneumo"], "🫁"),
        (state.units["cardio"], "❤️"),
    ]

    for i, (unit_obj, icon) in enumerate(units_data):
        with [u1, u2, u3, u4][i]:
            with st.container(border=True):
                st.write(f"**{icon} {unit_obj.name}**")
                st.write(f"Patients : **{unit_obj.occupancy}**")
                ratio = unit_obj.occupancy / unit_obj.capacity if unit_obj.capacity > 0 else 0
                st.progress(ratio, text=f"{unit_obj.occupancy}/{unit_obj.capacity}")

    # =========================================================================
    # ⚡ BOUCLE DE JEU (GAME LOOP) - SYNCHRONISATION LIVE
    # =========================================================================
    if st.session_state.sim_running:
        # 1. On attend 0.5 seconde
        time.sleep(0.5)
        
        # 2. AVANCÉE DU TEMPS
        st.session_state.sim_time += 5
        
        # 3. [IMPORTANT] SYNCHRO FICHIER -> MÉMOIRE
        # On force la relecture du fichier JSON pour voir si l'Agent a modifié quelque chose
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            state_path = os.path.join(base_dir, "data", "state", "urgence_state.json")
            
            # On recharge l'état frais depuis le disque
            new_state = load_initial_state(state_path)
            
            # On préserve le temps simulé (pour l'interface)
            new_state.time = st.session_state.sim_time
            new_state.is_running = True 
            
            # On met à jour la mémoire
            st.session_state.hospital_state = new_state
            
        except Exception as e:
            # Si le LLM est en train d'écrire, on ignore ce tick
            # print(f"Sync skip: {e}") 
            pass
        
        # 4. On recharge l'interface
        st.rerun()