# Narractive - Agent Instructions

## Scope
Projet narratif interactif. Tu es l'agent dédié à ce projet.

## Conventions
- Vérifier la stack technique avant toute modification
- Documentation dans /docs/ si existant

## Permissions
- Lire/modifier tout le code du projet
- Proposer des améliorations d'architecture

## Mémoire
Maintiens .claude/memory.md avec les décisions importantes.

## Serena MCP - Auto-activation
At the start of each session, activate the project with activate_project using name "narractive".
This gives you LSP-powered code intelligence on /project.

## Outils CLI disponibles
- `gh` (GitHub CLI) est installe et authentifie. Utilise-le pour gerer les issues, PRs, releases.
  Exemples: `gh issue list`, `gh issue close 42`, `gh pr list`, `gh pr create`
- `git`, `make`, `python3`, `pip`, `curl` sont disponibles.
- REGLE: EXECUTE les commandes, ne les decris jamais. Utilise tes outils.
