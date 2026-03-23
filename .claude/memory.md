# Project Memory
_Auto-maintained by project agent_


## [2026-03-23 13:22]
Delegate task: brainstormer sur le projet narractive pour les prochaines améliorations/implémentations, créer les prochains issues des prohcains spritns dans ggithub
Result: 14 issues créés sur 5 sprints. Voici le récap complet :

---

## Issues créées — imagodata/narractive

### Sprint 1 — Foundation & CI (2 issues)
| # | Titre | Labels |
|---|-------|--------|
| [#1](https://github.com/imagodata/narractive/issues/1) | Bootstrap CI/CD pipeline (ruff + mypy + pytest) | `sprint:1` `ci/cd` `testing` |
| [#2](https://github.com/imagodata/narractive/issues/2) | Write unit tests for core modules | `sprint:1` `testing` `good first issue` |

### Sprint 2 — Developer Experi


## [2026-03-23 13:42]
Delegate task: Narractive : implémenter sprint 1 et 2
Result: Claude response timed out.

*(pas de changements de fichiers)*


## [2026-03-23 14:09]
Delegate task: Délégué à narractive le sprint 1
Result: Sprint 1 est implémenté et la PR est ouverte : **https://github.com/imagodata/narractive/pull/16**

## Ce qui a été fait

**Issue #1 — Bootstrap CI/CD pipeline**
- Nouveau `.github/workflows/ci.yml` avec 3 jobs séparés :
  - `lint` : `ruff check` + `ruff format --check`
  - `typecheck` : `mypy`
  - `test` : pytest sur Python 3.10, 3.11, 3.12, 3.13

**Issue #2 — Unit tests for core modules**
- Ajout de `test_text_preprocessor.py`, `test_subtitles.py`, `test_i18n.py`
- **92 tests passent**, 2 skip
