import json
from src.agent.urgency_agent import run_agent_loop

def main():
    out = run_agent_loop(
        "Gère les urgences maintenant: "
        "1) décharge tous les GRIS vers sortie, "
        "2) affecte ROUGE en priorité (soins_critiques sinon fallback), "
        "3) gère JAUNE ensuite, "
        "4) si saturation, utilise tick et/ou move_staff. "
        "Rends un plan final en JSON."
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
