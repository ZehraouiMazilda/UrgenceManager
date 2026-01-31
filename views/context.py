import streamlit as st


def show_context():
    st.title("🏠 Accueil & Contexte")

    # -------------------------------------------------------------------------
    # TL;DR
    # -------------------------------------------------------------------------
    st.info(
        "**TL;DR** — Projet académique **Master 2 SISE** (Université Lyon 2), module **NLP/LLM**. "
        "Objectif : contribuer à l’automatisation de la gestion des patients aux urgences via un système à base d’agents. "
        "L’application simule l’organisation des urgences de l’Hôpital X (flux, ressources, règles métier) et permet la prise en main via scénarios, simulateur et assistant en langage naturel."
    )
    st.divider()

    with st.container(border=True):
        st.subheader("📋 En bref")
        st.markdown(
            "**Urgence Manager** est une application de simulation et d’aide à la décision pour la gestion logistique "
            "d’un service d’accueil des urgences. Elle modélise les flux de patients, le personnel et les salles, "
            "et intègre un assistant interrogable en langage naturel (LLM)."
        )
        st.markdown(
            "Le projet s’inscrit dans le **Master 2 SISE**, module **NLP/LLM**. "
            "Il vise à automatiser ou assister la gestion des patients aux urgences dans un cadre académique (agents, RAG, machine learning)."
        )

    with st.container(border=True):
        st.subheader("🧭 Prise en main")
        st.success(
            "La **barre latérale** (à gauche) permet de naviguer entre les pages. Chaque page correspond à une fonctionnalité."
        )
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Par où commencer ?**")
            st.markdown(
                "- **🎬 Scénarios** : lancer un scénario préconfiguré (afflux massif, journée normale, etc.).\n"
                "- **🎮 Simulateur Live** : injecter des patients, piloter le temps et le personnel, observer le flux en direct."
            )
        with c2:
            st.markdown("**Analyse et interrogation**")
            st.markdown(
                "- **💬 Assistant IA** : interrogation en langage naturel (RAG sur les sessions).\n"
                "- **📊 Dashboard & KPIs** : statistiques, indicateurs et visualisations.\n"
                "- **ℹ️ À Propos** : crédits et version."
            )
        st.caption("→ Utilisez la liste « Navigation » dans la barre latérale pour accéder à une page.")

    st.divider()

    # =========================================================================
    # CONTEXTE — Cadre académique, objectifs, problématique, ressources
    # =========================================================================
    st.header("📚 Contexte")
    st.caption("Cadre académique, objectifs, problématique opérationnelle et ressources du système.")

    # -------------------------------------------------------------------------
    # Cadre académique
    # -------------------------------------------------------------------------
    with st.container(border=True):
        st.subheader("🎓 Cadre académique")
        st.info(
            "**Formation** : Master 2 SISE — Université Lyon 2. **Module** : NLP/LLM. "
            "**Objectif du projet** : contribuer à l’automatisation de la gestion des patients aux urgences (tri, orientation, suivi des flux) dans un cadre de recherche et d’enseignement."
        )

    # -------------------------------------------------------------------------
    # Objectifs du projet
    # -------------------------------------------------------------------------
    with st.container(border=True):
        st.subheader("🎯 Objectifs du projet")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Organisation**")
            st.markdown("Simuler et analyser la répartition des patients selon gravité et ressources.")
            st.markdown("**Décision**")
            st.markdown("Vue synthétique du système pour repérer les goulots d’étranglement.")
        with col2:
            st.markdown("**Interaction**")
            st.markdown("Interroger le système en langage naturel via un LLM.")
            st.markdown("**Évaluation**")
            st.markdown("Suivre les indicateurs métier et les variables du système.")
        with col3:
            st.markdown("**Architecture**")
            st.markdown("Architecture justifiable : agents, RAG, machine learning.")

    # -------------------------------------------------------------------------
    # Contexte opérationnel (problématique)
    # -------------------------------------------------------------------------
    with st.container(border=True):
        st.subheader("⚙️ Contexte opérationnel des urgences")
        st.warning(
            "La gestion des flux aux urgences consiste à **articuler** : nouvelles arrivées, patients en attente de résultats, "
            "surveillance continue, patients prêts pour hospitalisation ou sortie. Les **ressources sont limitées** (salles, médecins, équipements). "
            "L’organisation actuelle repose souvent sur tableaux manuels, communications verbales et mémoire du personnel, "
            "ce qui peut entraîner erreurs, temps d’attente prolongés et sous-utilisation de certaines capacités."
        )
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("**Flux à gérer**")
            st.markdown(
                "- Nouvelles arrivées (triage)\n"
                "- Patients en attente de résultats\n"
                "- Surveillance continue en salles\n"
                "- Patients prêts pour hospitalisation ou sortie"
            )
        with r2:
            st.markdown("**Limites actuelles**")
            st.markdown(
                "- Ressources limitées (salles, médecins, équipements)\n"
                "- Organisation manuelle → erreurs, attentes, sous-utilisation\n"
                "- Besoin de priorisation et de règles explicites"
            )

    # -------------------------------------------------------------------------
    # Organisation de l’Hôpital X — ressources et contraintes
    # -------------------------------------------------------------------------
    with st.container(border=True):
        st.subheader("🏥 Organisation de l’Hôpital X")
        st.info(
            "Le système modélise l’organisation des urgences d’un établissement type (« Hôpital X ») : agents, salles, personnel et règles métier."
        )
        # Agents
        st.markdown("**Agents**")
        st.markdown(
            "- **Triage** : prise en charge des arrivées et affectation d’une gravité (ROUGE, JAUNE, VERT, GRIS).\n"
            "- **Aide à la consultation** : coordination avec le médecin et les salles.\n"
            "- **Urgence Manager** : pilotage global des flux et des décisions (orientation, transferts)."
        )
        # Salles et spécialités
        st.markdown("**Salles et spécialités**")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.markdown(
                "- **Salles d’attente** : Salle 1, Salle 2, Salle 3\n"
                "- **Soins critiques** (urgences vitales)\n"
                "- **Salle de consultation** (médecin)"
            )
        with col_s2:
            st.markdown(
                "- **Unités d’hospitalisation** : cardiologie, pneumologie, neurologie, orthopédie"
            )
        # Règles métier
        st.markdown("**Règles métier**")
        st.markdown(
            "- Un patient doit avoir **vu un médecin** avant tout transfert vers une unité d’hospitalisation.\n"
            "- Une **unité doit valider** qu’elle a de la place avant d’accepter un patient."
        )
        # Personnel
        st.markdown("**Personnel modélisé**")
        st.markdown(
            "- **1 médecin** en salle de consultation.\n"
            "- **1 infirmier au triage** + **2 infirmiers** répartis entre les 3 salles d’attente (une salle ne doit pas rester **plus de 15 minutes** sans surveillance).\n"
            "- **2 aides-soignants** pour le transport (mission **max 1 heure** par trajet aller-retour)."
        )
        # Temps de transport
        st.markdown("**Temps de transport**")
        st.markdown(
            "- **Vers les unités d’hospitalisation** : 45 min (aller).\n"
            "- **Vers la consultation** : 5 min (aller)."
        )

    # -------------------------------------------------------------------------
    # Données et modèles
    # -------------------------------------------------------------------------
    with st.container(border=True):
        st.subheader("📊 Données et modèles utilisés")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Données d’entrée**")
            st.markdown(
                "- **Symptômes** : référentiel par gravité (`symptoms.json`).\n"
                "- **État** : configuration salles, personnel, constantes (JSON).\n"
                "- **Historique** : logs patients et personnel (CSV), pour statistiques, dashboard et RAG."
            )
        with col_b:
            st.markdown("**Modèles**")
            st.markdown(
                "- **Patient** : id, gravité, symptôme, localisation, statut, temps d’arrivée, décision médicale.\n"
                "- **Personnel** : rôles, disponibilité, occupation.\n"
                "- **Salles** : capacité et occupation (triage, attente, consultation, soins critiques, unités)."
            )

    st.divider()
    st.caption("Urgence Manager — Contexte et objectifs du projet.")
    st.caption("Master 2 SISE · Université Lyon 2 · Module NLP/LLM · v0.2 (Modular)")
