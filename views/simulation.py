"""
Module de simulation pour le système de gestion des urgences.
Version FINALE : Tous les détails corrigés
"""

import streamlit as st
import time
import random
import os
import pandas as pd
from datetime import datetime
import json

from src.models import Patient, Severity, PatientStatus, StateFile
from src.utils import load_initial_state, save_state
from src.logger import log_event
from src.ai_brain import process_brain_cycle


# =============================================================================
# CHARGEMENT DES DONNÉES
# =============================================================================

def load_symptoms():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    symptoms_path = os.path.join(base_dir, "data", "symptoms.json")
    try:
        with open(symptoms_path, "r", encoding="utf-8") as f: return json.load(f)
    except:
        return {"ROUGE": ["Douleur"], "JAUNE": ["Fracture"], "VERT": ["Bobo"], "GRIS": ["Rhume"]}

def load_full_file(path):
    with open(path, "r", encoding="utf-8") as f: return StateFile(**json.load(f))

# =============================================================================
# FONCTIONS D'AFFICHAGE ET HELPERS
# =============================================================================

def verify_rules(state):
    violations = []
    # Règle 1: Rouge -> SC
    for p in state.patients.values():
        score = 4 if p.severity.value == "ROUGE" else 0
        if score >= 4 and p.location not in ["soins_critiques", "triage", "consultation", "direct_transfer_sc"]:
            if p.status != PatientStatus.IN_TRANSIT:
                violations.append(f"🔴 VITALE : {p.id} (ROUGE) est en '{p.location}' au lieu de SC !")

    # Règle 3: Surveillance
    if "nurse_timers" not in st.session_state: st.session_state.nurse_timers = {}
    for rid, room in state.waiting_rooms.items():
        has_pats = int(room.occupancy) > 0
        has_surveillance = False
        for sid in room.staff:
            ag = state.staff.get(sid)
            if ag and ag.is_present and not ag.is_busy and ("infirmier" in str(ag.role) or "aide" in str(ag.role)):
                has_surveillance = True; break
        
        if has_pats and not has_surveillance:
            if rid not in st.session_state.nurse_timers: st.session_state.nurse_timers[rid] = state.time
            elif (state.time - st.session_state.nurse_timers[rid]) > 15:
                violations.append(f"🚫 SÉCURITÉ : {room.name} sans surveillance > 15 min !")
        else:
            if rid in st.session_state.nurse_timers: del st.session_state.nurse_timers[rid]
    return violations

def save_session_csv(base_dir):
    log_path = os.path.join(base_dir, "data", "history_logs.json")
    hist_dir = os.path.join(base_dir, "data", "historique")
    os.makedirs(hist_dir, exist_ok=True)
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding='utf-8') as f: history = json.load(f)
            if history:
                last = history[-1]; sid = last.get("session_id", "unk")
                if last.get("logs_patients"): pd.DataFrame(last["logs_patients"]).to_csv(os.path.join(hist_dir, f"{sid}_{ts_str}_pat.csv"), sep=";", index=False)
                if last.get("logs_staff"): pd.DataFrame(last["logs_staff"]).to_csv(os.path.join(hist_dir, f"{sid}_{ts_str}_stf.csv"), sep=";", index=False)
                return True
    except: return False
    return False

def check_presence(state, room_staff_list, role_tag):
    found = []
    for s_id in room_staff_list:
        ag = state.staff.get(s_id)
        if ag and role_tag in s_id and ag.is_present and not ag.is_busy: found.append(s_id)
    return f"🟢 {', '.join(found)}" if found else "❌"

def format_patient_colored(patient, current_time):
    """Affiche le patient avec timer décrémentiel."""
    if not patient: return "Inconnu"
    val = patient.severity.value
    colors = {"ROUGE": "red", "JAUNE": "orange", "VERT": "green", "GRIS": "grey"}
    base = f":{colors.get(val, 'black')}[{patient.id}]"
    
    # Cas Transit (Avant arrivée)
    if patient.status == PatientStatus.IN_TRANSIT:
        transit_time = current_time - patient.arrival_time
        eta = max(0, 45 - transit_time)
        return f"{base} (🚑 Arrivée {eta} min)"

    # Cas Hospitalisé / Consult (Timer restant)
    if patient.treatment_end_time > 0:
        rem_min = patient.treatment_end_time - current_time
        if rem_min > 0:
            h = rem_min // 60
            m = rem_min % 60
            return f"{base} (⏳ {h}h{m:02d})"
        else:
            return f"{base} (✅ Sortie)"
            
    return base

def get_medical_decision(severity):
    roll = random.random()
    sev = severity.value
    if sev == "ROUGE": return "soins_critiques" if roll < 0.60 else random.choice(["ortho", "cardio", "neuro", "pneumo"])
    elif sev == "JAUNE":
        if roll < 0.30: return "soins_critiques"
        return random.choice(["ortho", "cardio", "neuro", "pneumo"]) if roll < 0.80 else "exit"
    elif sev == "VERT": return random.choice(["ortho", "cardio", "neuro", "pneumo"]) if roll < 0.30 else "exit"
    else: return "exit"

# =============================================================================
# LOGIQUE D'INJECTION (CORRIGÉE)
# =============================================================================

def inject_patient(state, severity_str, symptom, location_id, state_path):
    target_room = None
    as_needed = False
    
    # --- 1. Définition destination & besoins ---
    real_location_id = location_id
    
    if location_id == "transport_consultation":
        real_location_id = "consultation"
        as_needed = True
    elif location_id == "transport_hospital":
        # FIX 5 : Vérifier que au moins 1 service a de la place
        available_units = []
        for unit_id in ["ortho", "neuro", "pneumo", "cardio"]:
            unit = state.units[unit_id]
            if unit.occupancy < unit.capacity:
                available_units.append(unit_id)
        
        if not available_units:
            return None, "⛔ Impossible : Tous les services d'hospitalisation sont PLEINS !"
        
        real_location_id = random.choice(available_units)
        as_needed = True

    # FIX 1 : Vérification Consultation (directe ou transport)
    if real_location_id == "consultation":
        doc = state.staff.get("DOC_01")
        if not doc or not doc.is_present:
            return None, "⛔ Impossible : Médecin ABSENT."
        if state.consultation_room.occupancy > 0:
            return None, "⛔ Impossible : Consultation DÉJÀ OCCUPÉE."
        if doc.is_busy:
            return None, "⛔ Impossible : Médecin DÉJÀ OCCUPÉ."

    # --- 3. Sélection AS (PRIORITÉS) ---
    target_as = None
    if as_needed:
        as1 = state.staff.get("AS_01")
        as2 = state.staff.get("AS_02")
        as1_p = as1 and as1.is_present
        as2_p = as2 and as2.is_present
        
        candidates = []
        
        if location_id == "transport_hospital":
            if as2_p: candidates = [as2]
            elif as1_p: candidates = [as1]
        else:  # transport_consultation
            if as1_p: candidates = [as1]
            elif as2_p: candidates = [as2]
        
        # FIX 4 : Vérifier disponibilité
        for c in candidates:
            if not c.is_busy:
                target_as = c
                break
        
        if not target_as:
            return None, "⛔ Impossible : Aucun AS disponible."

    # --- 4. Détection destination ---
    all_rooms = {"triage": state.triage_zone, "consultation": state.consultation_room, "soins_critiques": state.soins_critiques, **state.waiting_rooms, **state.units}
    target_room = all_rooms.get(real_location_id)
    
    if not target_room: return None, f"❌ Localisation '{location_id}' introuvable."
    
    if hasattr(target_room, 'capacity') and int(target_room.occupancy) >= int(target_room.capacity):
        return None, f"⛔ Impossible : {target_room.name} PLEINE."

    # --- 5. Création Patient ---
    new_id = f"PAT_{len(state.patients)+1:03d}"
    
    if location_id == "transport_hospital":
        status_initial = PatientStatus.IN_TRANSIT
        arrival_time_override = state.time
    else:
        status_initial = PatientStatus.WAITING
        arrival_time_override = None

    new_patient = Patient(
        id=new_id,
        severity=Severity[severity_str],
        symptom=symptom,
        location=real_location_id,
        status=status_initial,
        arrival_time=arrival_time_override if arrival_time_override else state.time
    )

    state.patients[new_id] = new_patient
    
    if location_id == "transport_hospital":
        target_room.patients.append(new_id)
        target_room.occupancy += 1
    else:
        target_room.patients.append(new_id)
        target_room.occupancy += 1

    # Cas consultation (directe ou transport)
    if real_location_id == "consultation":
        doc = state.staff["DOC_01"]
        doc.is_busy = True
        consult_duration = random.randint(10, 20)
        
        # FIX 2 : Si transport consult, ajouter 5 min de trajet
        if location_id == "transport_consultation":
            doc.busy_until = state.time + 5 + consult_duration
            new_patient.treatment_end_time = state.time + 5 + consult_duration
        else:
            doc.busy_until = state.time + consult_duration
            new_patient.treatment_end_time = state.time + consult_duration
    
    # Soins critiques
    if real_location_id == "soins_critiques":
        duration = random.randint(1440, 2880)
        new_patient.treatment_end_time = state.time + duration

    # FIX 2 & 3 : Réserver l'AS avec durée aller-retour
    if as_needed and target_as:
        target_as.is_busy = True
        if location_id == "transport_consultation":
            # FIX 2 : Aller (5 min) + Retour (5 min) = 10 min total
            target_as.busy_until = state.time + 10
        else:  # transport_hospital
            # FIX 3 : Aller (45 min) + Retour (45 min) = 90 min total
            target_as.busy_until = state.time + 90
    
    log_event(state, "PATIENT", new_id, f"injected_{location_id}")
    save_state(state, state_path)
    
    as_msg = f" escorté par {target_as.id}" if as_needed and target_as else ""
    return new_id, f"✅ {new_id} ({severity_str}){as_msg} -> {target_room.name}"

# =============================================================================
# SHOW SIMULATION
# =============================================================================

def show_simulation():
    if "sim_running" not in st.session_state: st.session_state.sim_running = False
    if "sim_time" not in st.session_state: st.session_state.sim_time = 0
    if "brain_logs" not in st.session_state: st.session_state.brain_logs = []
    
    symptoms_data = load_symptoms()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    state_path = os.path.join(base_dir, "data", "state", "urgence_state.json")
    initial_path = os.path.join(base_dir, "data", "state", "urgence_initial_state.json")
    
    if "hospital_state" not in st.session_state:
        try: st.session_state.hospital_state = load_initial_state(state_path)
        except Exception as e: st.error(f"Erreur : {e}"); st.stop()
    
    state = st.session_state.hospital_state

    st.markdown("## 🎮 Simulateur Live (God Mode)")
    
    with st.expander("👥 Gestion Personnel", expanded=False):
        cols = st.columns(3)
        with cols[0]:
            st.markdown("**🩺 Médecin**")
            d = state.staff.get("DOC_01")
            if d: d.is_present = st.toggle("DOC_01", value=d.is_present, key="t_doc")
        with cols[1]:
            st.markdown("**💉 Infirmiers**")
            for s in ["INF_TRIAGE_01", "INF_SALLE_01", "INF_SALLE_02"]:
                a = state.staff.get(s)
                if a: a.is_present = st.toggle(s, value=a.is_present, key=f"t_{s}")
        with cols[2]:
            st.markdown("**🚑 AS**")
            for s in ["AS_01", "AS_02"]:
                a = state.staff.get(s)
                if a: a.is_present = st.toggle(s, value=a.is_present, key=f"t_{s}")
        if st.button("💾 Sauvegarder Personnel"): save_state(state, state_path); st.success("OK")

    with st.expander("💉 Injection Patient", expanded=True):
        c1, c2, c3, c4 = st.columns([2,2,2,1])
        with c1:
            sev = st.selectbox("Gravité", ["ROUGE", "JAUNE", "VERT", "GRIS"], key="inj_sev")
        with c2:
            symp_list = symptoms_data.get(sev, ["Symptôme"])
            symp = st.selectbox("Symptôme", symp_list, key="inj_symp")
        with c3:
            loc_opts = {
                "Triage": "triage",
                "Salle 1": "wr_01",
                "Salle 2": "wr_02",
                "Salle 3": "wr_03",
                "Soins Critiques": "soins_critiques",
                "Consultation": "consultation",  # FIX 1 : Injection directe possible
                "→ Transport Consult (AS)": "transport_consultation",
                "→ Transport Hôpital (AS)": "transport_hospital"
            }
            loc_choice = st.selectbox("Destination", list(loc_opts.keys()), key="inj_loc")
            loc_id = loc_opts[loc_choice]
        with c4:
            st.write(""); st.write("")
            if st.button("➕ Injecter", use_container_width=True):
                pid, msg = inject_patient(state, sev, symp, loc_id, state_path)
                if pid: st.success(msg); st.session_state.hospital_state = load_initial_state(state_path); st.rerun()
                else: st.error(msg)

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("▶️ Démarrer" if not st.session_state.sim_running else "⏸️ Pause", use_container_width=True):
            st.session_state.sim_running = not st.session_state.sim_running; st.rerun()
    with c2:
        if st.button("🔄 Reset", use_container_width=True):
            ini = load_initial_state(initial_path)
            save_state(ini, state_path)
            st.session_state.hospital_state = ini
            st.session_state.sim_time = 0
            st.session_state.brain_logs = []
            st.session_state.sim_running = False
            st.success("OK"); st.rerun()
    with c3:
        if st.button("💾 CSV", use_container_width=True):
            if save_session_csv(base_dir): st.success("OK")
    with c4:
        st.metric("Temps", f"{st.session_state.sim_time//60}h{st.session_state.sim_time%60:02d}")

    with st.expander("🧠 Cerveau", expanded=True):
        if st.session_state.brain_logs:
            for l in st.session_state.brain_logs[-5:]: st.text(l)
        else: st.caption("R.A.S.")

    # FIX 6 : ORDRE ESTHÉTIQUE DES BLOCS
    st.markdown("---")
    
    # === BLOC 1 : SOINS CRITIQUES + CONSULTATION ===
    c_sc, c_cs = st.columns(2)
    with c_sc:
        with st.container(border=True):
            st.markdown("#### ❤️ Soins Critiques")
            st.write(f"**{state.soins_critiques.occupancy}/{state.soins_critiques.capacity}**")
            pats = [format_patient_colored(state.patients.get(pid), state.time) for pid in state.soins_critiques.patients]
            st.write(" ".join(pats) if pats else "_")
            
    with c_cs:
        with st.container(border=True):
            st.markdown("#### 👨‍⚕️ Consultation")
            d = state.staff.get("DOC_01")
            d_txt = "❌"
            has_p = len(state.consultation_room.patients) > 0
            if d and d.is_present:
                rem = max(0, d.busy_until - state.time)
                if (d.is_busy and rem > 0) or has_p:
                    txt_time = f" ({rem} min)" if rem > 0 else ""
                    d_txt = f"🔴 OCCUPÉ{txt_time}"
                else: d_txt = "🟢 LIBRE"
            st.write(f"**Doc :** {d_txt}")
            p = state.consultation_room.patients[0] if state.consultation_room.patients else None
            st.write(f"**Pat :** {format_patient_colored(state.patients.get(p), state.time) if p else '_'}")

    # === BLOC 2 : TRANSPORT CONSULTATION (FIX 6) ===
    st.markdown("#### 🚑 Transport Consultation")
    c_as1, _ = st.columns(2)
    with c_as1:
        as1 = state.staff.get("AS_01")
        t1 = "❌"
        if as1 and as1.is_present:
            rem = max(0, as1.busy_until - state.time)
            t1 = "✅ DISPO" if rem <= 0 else f"🚑 MISSION ({rem} min)"
        st.info(f"**AS_01 (Prio Consult)** : {t1}")

    # === BLOC 3 : TRIAGE + SALLES D'ATTENTE ===
    c_tr, c_rms = st.columns([1, 3])
    with c_tr:
        with st.container(border=True):
            st.markdown("#### 📋 Triage")
            st.write(f"INF: {check_presence(state, state.triage_zone.staff, 'INF')}")
            st.write(f"AS: {check_presence(state, state.triage_zone.staff, 'AS')}")
            p = [format_patient_colored(state.patients.get(pid), state.time) for pid in state.triage_zone.patients]
            st.write(f"**{len(p)}** : {', '.join(p)}")
    with c_rms:
        st.markdown("#### 🛋️ Salles")
        cols = st.columns(3)
        for i, w in enumerate(["wr_01", "wr_02", "wr_03"]):
            with cols[i]:
                r = state.waiting_rooms[w]
                with st.container(border=True):
                    st.write(f"**{r.name}** {r.occupancy}/{r.capacity})")
                    st.write(f"S: {check_presence(state, r.staff, 'INF')} {check_presence(state, r.staff, 'AS')}")
                    p = [format_patient_colored(state.patients.get(pid), state.time) for pid in r.patients]
                    st.write(" ".join(p))

    # === BLOC 4 : TRANSPORT HÔPITAL (FIX 6) ===
    st.markdown("#### 🚑 Transport Hôpital")
    c_as2, _ = st.columns(2)
    with c_as2:
        as2 = state.staff.get("AS_02")
        t2 = "❌"
        if as2 and as2.is_present:
            rem = max(0, as2.busy_until - state.time)
            t2 = "✅ DISPO" if rem <= 0 else f"🚑 MISSION ({rem} min)"
        st.info(f"**AS_02 (Prio Hôpital)** : {t2}")

    # === BLOC 5 : HOSPITALISATION ===
    st.markdown("#### 🏥 Hospitalisation")
    cols = st.columns(4)
    icons = ["🦴", "🧠", "🫁", "❤️"]
    for i, u in enumerate(["ortho", "neuro", "pneumo", "cardio"]):
        with cols[i]:
            ut = state.units[u]
            with st.container(border=True):
                st.write(f"**{icons[i]} {ut.name}**")
                st.progress(ut.occupancy/ut.capacity if ut.capacity>0 else 0, f"{ut.occupancy}/{ut.capacity}")
                if ut.patients:
                    p_list = [format_patient_colored(state.patients.get(pid), state.time) for pid in ut.patients]
                    st.caption(" ".join(p_list))

    # === VÉRIFICATIONS ===
    viol = verify_rules(state)
    if viol: 
        for v in viol: st.error(v)
    else: st.success("✅ Règles respectées")

    # =========================================================================
    # GAME LOOP
    # =========================================================================
    if st.session_state.sim_running:
        time.sleep(2.0)
        st.session_state.sim_time += 5
        upd = False
        curr = load_initial_state(state_path); curr.time = st.session_state.sim_time
        
        # 1. Libération Staff
        for s in curr.staff.values():
            if "aide" in str(s.role).lower() and s.is_busy and s.busy_until>0:
                if curr.time >= s.busy_until:
                    s.is_busy=False
                    s.busy_until=0
                    s.location = "wr_03"
                    upd=True

        # 2. Gestion des Arrivées Hôpital (Transit -> Hospitalisé)
        for pid, pat in curr.patients.items():
            if pat.status == PatientStatus.IN_TRANSIT and pat.location in curr.units:
                if (curr.time - pat.arrival_time) >= 45:
                    pat.status = PatientStatus.HOSPITALIZED
                    pat.treatment_end_time = curr.time + random.randint(180, 1440)
                    upd = True

        # 3. Medecin
        doc = curr.staff["DOC_01"]; cons = curr.consultation_room
        if doc.is_busy and doc.busy_until>0 and curr.time>=doc.busy_until:
            doc.is_busy=False; doc.busy_until=0; upd=True
            if cons.patients:
                pid = cons.patients[0]; pat = curr.patients[pid]
                dec = get_medical_decision(pat.severity)
                if dec == "exit":
                    cons.patients.remove(pid); cons.occupancy=0; del curr.patients[pid]
                elif dec == "soins_critiques":
                    sc = curr.soins_critiques
                    if sc.occupancy < sc.capacity:
                        cons.patients.remove(pid); cons.occupancy=0; sc.patients.append(pid); sc.occupancy+=1
                        pat.location="soins_critiques"; pat.treatment_end_time = curr.time + random.randint(1440, 2880)
                    else: dec = "boarding_sc"
                
                if dec in ["hospital_unit", "ortho", "cardio", "neuro", "pneumo", "boarding_sc"]:
                    t_wr = None
                    for w in ["wr_01", "wr_02", "wr_03"]:
                        if curr.waiting_rooms[w].occupancy < curr.waiting_rooms[w].capacity: t_wr=curr.waiting_rooms[w]; break
                    if t_wr:
                        cons.patients.remove(pid); cons.occupancy=0; t_wr.patients.append(pid); t_wr.occupancy+=1
                        pat.location=t_wr.id; pat.status=PatientStatus.BOARDING
                        if dec == "hospital_unit": pat.medical_decision = random.choice(["ortho", "cardio", "neuro", "pneumo"])
                        else: pat.medical_decision = "soins_critiques" if dec=="boarding_sc" else dec

        # 4. Libération Lits
        for r in list(curr.units.values()) + [curr.soins_critiques]:
            for pid in list(r.patients):
                pat = curr.patients.get(pid)
                if not pat: r.patients.remove(pid); r.occupancy=max(0,r.occupancy-1); upd=True; continue
                
                if pat.status == PatientStatus.HOSPITALIZED and pat.treatment_end_time > 0 and curr.time >= pat.treatment_end_time:
                    r.patients.remove(pid); r.occupancy=max(0, r.occupancy-1); del curr.patients[pid]; upd=True

        if upd: save_state(curr, state_path); st.session_state.hospital_state = curr

        # 5. Brain
        try:
            with st.spinner("🧠..."):
                br = process_brain_cycle()
            if br:
                l = f"[{st.session_state.sim_time//60}h{st.session_state.sim_time%60:02d}] {br}"
                if not st.session_state.brain_logs or st.session_state.brain_logs[-1]!=l: st.session_state.brain_logs.append(l)
                st.session_state.hospital_state = load_initial_state(state_path)
        except: pass
        st.rerun()