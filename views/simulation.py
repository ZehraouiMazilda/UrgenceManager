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

# --- HELPERS ---
def verify_rules(state):
    violations = []
    
    # Règle 1: Rouge -> SC
    for p in state.patients.values():
        score = 0
        if p.severity == "ROUGE": score = 4
        if score >= 4 and p.location not in ["soins_critiques", "triage", "direct_transfer_sc"]:
            violations.append(f"🔴 VITALE : {p.id} (ROUGE) est en '{p.location}' au lieu de Soins Critiques !")

    # Règle 3: Salle Attente sans Infirmier > 15 min
    if "nurse_timers" not in st.session_state: st.session_state.nurse_timers = {}
    
    for rid, room in state.waiting_rooms.items():
        has_pats = int(room.occupancy) > 0
        has_nurse = any("infirmier" in state.staff[sid].role for sid in room.staff)
        
        if has_pats and not has_nurse:
            if rid not in st.session_state.nurse_timers:
                st.session_state.nurse_timers[rid] = state.time
            else:
                duration = state.time - st.session_state.nurse_timers[rid]
                if duration > 15:
                    violations.append(f"🚫 SÉCURITÉ : {room.name} sans infirmier depuis {duration} min !")
        else:
            if rid in st.session_state.nurse_timers:
                del st.session_state.nurse_timers[rid]

    return violations

def save_session_csv(base_dir):
    log_path = os.path.join(base_dir, "data", "history_logs.json")
    hist_dir = os.path.join(base_dir, "data", "historique")
    os.makedirs(hist_dir, exist_ok=True)
    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding='utf-8') as f: history = json.load(f)
            if history:
                last_session = history[-1]
                sess_id = last_session.get("session_id", "unknown")
                if last_session.get("logs_patients"):
                    pd.DataFrame(last_session["logs_patients"]).to_csv(os.path.join(hist_dir, f"{sess_id}_patients.csv"), index=False, sep=";")
                if last_session.get("logs_staff"):
                    pd.DataFrame(last_session["logs_staff"]).to_csv(os.path.join(hist_dir, f"{sess_id}_staff.csv"), index=False, sep=";")
                return True
    except Exception: return False
    return False

def check_presence(state, room_staff_list, role_tag):
    staff_id = next((s_id for s_id in room_staff_list if role_tag in s_id), None)
    if not staff_id: return "❌ Absent"
    return f"🟢 {staff_id}"

def load_full_file(path):
    with open(path, "r", encoding="utf-8") as f: data = json.load(f)
    return StateFile(**data)

def show_simulation():
    if "sim_running" not in st.session_state: st.session_state.sim_running = False
    if "sim_time" not in st.session_state: st.session_state.sim_time = 0
    if "brain_logs" not in st.session_state: st.session_state.brain_logs = []
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    state_path = os.path.join(base_dir, "data", "state", "urgence_state.json")

    if "hospital_state" not in st.session_state:
        try: st.session_state.hospital_state = load_initial_state(state_path)
        except Exception as e: st.stop()
    state = st.session_state.hospital_state

    # 1. CONFIG
    st.markdown("## 🎮 Simulateur Live (God Mode)")
    with st.expander("⚙️ Configuration Capacités", expanded=not st.session_state.sim_running):
        disable_config = st.session_state.sim_running
        full_file = load_full_file(state_path)
        c1, c2 = st.columns(2)
        cap_sc = c1.number_input("Lits Soins Critiques", value=full_file.constants.capacities_max.soins_critiques, disabled=disable_config)
        cols = st.columns(4)
        updated = False
        if cap_sc != full_file.constants.capacities_max.soins_critiques:
            full_file.constants.capacities_max.soins_critiques = cap_sc
            full_file.state.soins_critiques.capacity = cap_sc; updated = True
        
        for i, uid in enumerate(["ortho", "neuro", "pneumo", "cardio"]):
            u_conf = full_file.constants.capacities_max.units[uid]
            new_cap = cols[i].number_input(f"{uid.capitalize()}", value=u_conf, min_value=1, key=f"c_{uid}", disabled=disable_config)
            if new_cap != u_conf:
                full_file.constants.capacities_max.units[uid] = new_cap
                full_file.state.units[uid].capacity = new_cap; updated = True
        
        if updated:
            try: jd = full_file.model_dump()
            except: jd = full_file.dict()
            with open(state_path, "w", encoding="utf-8") as f: json.dump(jd, f, indent=2)
            st.session_state.hospital_state = full_file.state; st.rerun()

    # 2. CONTROLES
    col_controls, col_timer = st.columns([1, 2], gap="large")
    with col_controls:
        c1, c2 = st.columns(2)
        with c1:
            if not st.session_state.sim_running:
                if st.button("▶️ Démarrer", use_container_width=True, type="primary"):
                    st.session_state.sim_running = True; st.rerun()
            else:
                if st.button("⏸️ Pause", use_container_width=True):
                    st.session_state.sim_running = False; st.rerun()
        with c2:
            if st.button("⏹️ Reset & Save", use_container_width=True):
                if save_session_csv(base_dir): st.toast("✅ Sauvegardé !", icon="💾")
                st.session_state.sim_running = False
                st.session_state.sim_time = 0
                st.session_state.brain_logs = []
                st.session_state.nurse_timers = {} 
                
                full = load_full_file(state_path)
                full.state.time = 0
                full.state.patients = {}
                for r in [full.state.triage_zone, full.state.consultation_room, full.state.soins_critiques] + list(full.state.waiting_rooms.values()) + list(full.state.units.values()):
                    r.occupancy = 0; r.patients = []
                for s in full.state.staff.values(): s.is_busy = False; s.busy_until = 0; s.return_transport_code = None
                
                try: jd = full.model_dump()
                except: jd = full.dict()
                with open(state_path, "w", encoding="utf-8") as f: json.dump(jd, f, indent=2)
                st.session_state.hospital_state = full.state; st.rerun()

    with col_timer:
        hours = st.session_state.sim_time // 60
        minutes = st.session_state.sim_time % 60
        st.metric("Temps Simulé", f"{hours:02d}h{minutes:02d}", delta="En cours" if st.session_state.sim_running else "Pause")

    st.divider()

    # 3. INJECTION
    c_pat, c_doc, c_inf, c_aid = st.columns(4)
    with c_pat:
        with st.container(border=True):
            st.markdown(f"**🤒 Patients : {len(state.patients)}**")
            with st.popover("➕ Injection"): 
                from src.utils import load_symptoms_config
                smap = load_symptoms_config(os.path.join(base_dir, "data", "symptoms.json"))
                if smap:
                    grav = st.selectbox("Gravité", list(smap.keys()))
                    symp = st.selectbox("Symptôme", smap[grav])
                    loc_ops = {"Triage": "triage", "Salle 1": "wr_01", "Salle 2": "wr_02", "Salle 3": "wr_03"}
                    target = loc_ops[st.selectbox("Vers :", list(loc_ops.keys()))]
                    qty = st.number_input("Qté", 1, 50, 1)
                    if st.button(f"Injecter {qty}"):
                        cnt = len(state.patients)
                        for i in range(qty):
                            nid = f"PAT_{cnt+i+1:03d}"
                            np = Patient(id=nid, severity=Severity(grav), symptom=symp, location=target, status=PatientStatus.WAITING, arrival_time=st.session_state.sim_time)
                            state.patients[nid] = np
                            if target == "triage": state.triage_zone.patients.append(nid)
                            elif target in state.waiting_rooms:
                                wr = state.waiting_rooms[target]
                                wr.patients.append(nid); wr.occupancy += 1
                        save_state(state, state_path); st.success(f"Ajouté {qty} en {target}"); time.sleep(0.5); st.rerun()

    nb_med = len([s for s in state.staff.values() if "medecin" in s.role])
    nb_inf = len([s for s in state.staff.values() if "infirmier" in s.role])
    nb_as = len([s for s in state.staff.values() if "aide" in s.role])
    with c_doc: st.info(f"**Médecins : {nb_med}**")
    with c_inf: st.info(f"**Infirmiers : {nb_inf}**")
    with c_aid: st.info(f"**Aides-Soignants : {nb_as}**")

    # 4. LOGS
    st.divider()
    st.markdown("### 🧠 Cerveau IA (Journal de Bord)")
    with st.container(height=300):
        if not st.session_state.brain_logs: st.caption("En attente...")
        else:
            for log in reversed(st.session_state.brain_logs): st.markdown(log)
    st.divider()

    # 5. CARTE
    st.subheader("🗺️ Carte")
    c_crit, _, c_cons = st.columns([1.2, 0.2, 1.2])
    with c_crit:
        with st.container(border=True):
            st.markdown("#### ❤️ Soins Critiques")
            st.write(f"**{state.soins_critiques.occupancy}/{state.soins_critiques.capacity}**")
            st.error("🔴 ROUGE ONLY")
    with c_cons:
        with st.container(border=True):
            st.markdown("#### 👨‍⚕️ Consultation")
            st.write(f"**Doc :** {check_presence(state, state.consultation_room.staff, 'DOC')}")
            st.write(f"**Patient :** {state.consultation_room.patients[0] if state.consultation_room.patients else '_'}")

    as1 = state.staff.get("AS_01")
    st.info(f"⬇️ Transport Consult : **{'🚑 OUI ('+as1.id+')' if as1 and as1.is_busy else '⛔ NON'}**")

    c_tri, c_salles = st.columns([1, 3])
    with c_tri:
        with st.container(border=True):
            st.markdown("#### 📋 Triage")
            st.write(f"**INF:** {check_presence(state, state.triage_zone.staff, 'INF')}")
            st.write(f"**AS:** {check_presence(state, state.triage_zone.staff, 'AS')}")
            st.write(f"**P:** {len([p for p in state.patients.values() if p.location == 'triage'])}")

    with c_salles:
        st.markdown("#### 🛋️ Attente")
        c1, c2, c3 = st.columns([1, 1.5, 1])
        w1, w2, w3 = state.waiting_rooms["wr_01"], state.waiting_rooms["wr_02"], state.waiting_rooms["wr_03"]
        with c1: st.container(border=True).write(f"**{w1.name}**\n\nStaff: {check_presence(state, w1.staff, 'INF')}\n\nPat: {w1.occupancy}/{w1.capacity}")
        with c2: st.container(border=True).write(f"**{w2.name}**\n\nStaff: {check_presence(state, w2.staff, 'INF')}\n\nPat: {w2.occupancy}/{w2.capacity}")
        with c3: st.container(border=True).write(f"**{w3.name}**\n\nStaff: {check_presence(state, w3.staff, 'INF')}\n\nPat: {w3.occupancy}/{w3.capacity}")

    as2 = state.staff.get("AS_02")
    st.info(f"⬇️ Transport Hôpital : **{'🚑 OUI ('+as2.id+')' if as2 and as2.is_busy else '⛔ NON'}**")

    st.markdown("#### 🏥 Hospitalisation")
    u1, u2, u3, u4 = st.columns(4)
    units_data = [state.units["ortho"], state.units["neuro"], state.units["pneumo"], state.units["cardio"]]
    icons = ["🦴", "🧠", "🫁", "❤️"]
    for i, u in enumerate(units_data):
        with [u1, u2, u3, u4][i]:
            with st.container(border=True):
                st.write(f"**{icons[i]} {u.name}**")
                st.progress(u.occupancy / u.capacity if u.capacity > 0 else 0, text=f"{u.occupancy}/{u.capacity}")

    # 6. VERIFICATION REGLES
    st.divider()
    st.markdown("### 🛡️ Conformité & Règles (Temps Réel)")
    violations = verify_rules(state)
    if violations:
        for v in violations: st.error(v)
    else:
        st.success("✅ Aucune violation détectée. Le protocole est respecté.")

    # 7. GAME LOOP
    if st.session_state.sim_running:
        time.sleep(0.1)
        st.session_state.sim_time += 5
        try:
            brain_result = process_brain_cycle()
            if brain_result:
                ts = f"[{st.session_state.sim_time // 60}h{st.session_state.sim_time % 60:02d}]"
                st.session_state.brain_logs.append(f"{ts} {brain_result}")
            
            new_state = load_initial_state(state_path)
            new_state.time = st.session_state.sim_time
            new_state.is_running = True 
            updated = False
            
            doc = new_state.staff["DOC_01"]
            cons = new_state.consultation_room
            if doc.is_busy and doc.busy_until > 0 and new_state.time >= doc.busy_until:
                doc.is_busy = False; doc.busy_until = 0; updated = True
                if cons.patients:
                    pid = cons.patients[0]; pat = new_state.patients[pid]; roll = random.random()
                    if roll < 0.30:
                        cons.patients.remove(pid); cons.occupancy=0; del new_state.patients[pid]
                        log_event(new_state, "PATIENT", pid, "exit_from_consult")
                    elif roll < 0.40:
                        cons.patients.remove(pid); cons.occupancy=0
                        new_state.soins_critiques.patients.append(pid); new_state.soins_critiques.occupancy+=1
                        pat.location="soins_critiques"; pat.treatment_end_time=new_state.time+random.randint(360,2880)
                        log_event(new_state, "PATIENT", pid, "direct_transfer_sc")
                    else:
                        unit = random.choice(["ortho", "cardio", "neuro", "pneumo"]); pat.medical_decision = unit
                        target = None
                        for wid in ["wr_01", "wr_02", "wr_03"]:
                            if new_state.waiting_rooms[wid].occupancy < new_state.waiting_rooms[wid].capacity:
                                target = new_state.waiting_rooms[wid]; break
                        if target:
                            cons.patients.remove(pid); cons.occupancy=0
                            target.patients.append(pid); target.occupancy+=1; pat.location=target.id
                            log_event(new_state, "PATIENT", pid, "return_to_wr_for_hos")

            for s_id, agent in new_state.staff.items():
                if "aide" in agent.role and agent.is_busy and agent.busy_until > 0 and new_state.time >= agent.busy_until:
                    code = agent.return_transport_code if agent.return_transport_code else "unknown"
                    log_event(new_state, "STAFF", agent.id, code)
                    agent.is_busy=False; agent.busy_until=0; agent.return_transport_code=None; updated=True

            all_beds = {**new_state.units, "sc": new_state.soins_critiques}
            for uid, room in all_beds.items():
                for pid in list(room.patients):
                    pat = new_state.patients.get(pid)
                    if not pat: room.patients.remove(pid); room.occupancy=max(0,room.occupancy-1); updated=True; continue
                    if pat.treatment_end_time > 0 and new_state.time >= pat.treatment_end_time:
                        room.patients.remove(pid); room.occupancy=max(0,room.occupancy-1)
                        del new_state.patients[pid]; log_event(new_state, "PATIENT", pid, f"discharged_from_{uid}"); updated=True

            if updated: save_state(new_state, state_path)
            st.session_state.hospital_state = new_state
        except Exception: pass
        st.rerun()