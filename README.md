# UrgenceManager (Logistics Agent)

## Description
This academic project is developed as part of the *Data for Good* module and aims to design an agent-based assistant for emergency department logistics management.

The objective is to propose an application capable of simulating the organization of an emergency department (patient flows, severity levels, waiting queues, available resources) and to provide an interactive interface that helps analyze and understand the system state using a language model.

At this stage, the repository serves as a working base for the design, structuring, and progressive iteration of the project.

---

## Project Objectives

| Objective | Description |
|---------|-------------|
| Patient organization | Simulate and analyze patient organization based on severity levels and resource availability |
| Decision support | Provide a synthetic view of the system state to identify bottlenecks |
| Natural language interaction | Allow system interrogation through a language model |
| System evaluation | Track business metrics and system variables |
| Sobriety and justification | Design a reasoned and justifiable architecture |

---

## Requirements Specification

### Expected Functional Components

| Component | Description |
|----------|-------------|
| LLM | Use of a language model with a central role in the application |
| RAG | Integration of at least one Retrieval-Augmented Generation component |
| Agent-based logic | Implementation of an agent-based mechanism (workflow or MCP) |
| Machine Learning | Integration of at least one machine learning component (classification, clustering, regression, etc.) |

---

### Interface & Interaction

| Requirement | Description |
|------------|-------------|
| User interface | Interactive application (e.g., Streamlit, Gradio) |
| Hosting | Online access (HuggingFace Space or equivalent platform) |
| Simulation | Simulated cases (automatically generated patients based on a context) |
| Interaction | Manual patient addition and free interaction with the system |

---

### Dashboard & Monitoring

| Tracked Element | Description |
|----------------|-------------|
| Business metrics | Waiting time, room saturation, patient distribution |
| Latency | System response time |
| Cost | Estimated costs related to model usage |
| Environmental impact | Estimated ecological footprint |

---

### Software Quality & Best Practices

| Aspect | Expectation |
|------|-------------|
| Typing | Variable and function typing |
| Documentation | Documented functions and modules |
| Formatting | Use of `black` |
| Static analysis | Use of `pylint` |
| Architecture | Object-oriented programming |
| Design principles | Compliance with SOLID principles |
| Deployment | Dockerization if relevant |

---

### Expected Deliverables

| Deliverable | Description |
|------------|-------------|
| Source code | Public GitHub repository |
| Application | Online hosted interface |
| Presentation | Oral project presentation |

---

## Project Status
🟡 **Design and scoping phase**  
The project is currently in the design and structuring phase. Technical and architectural choices will be refined progressively as the project advances.

---

## Authors
Group project developed in an academic context.
