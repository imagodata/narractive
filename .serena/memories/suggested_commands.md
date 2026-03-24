# Video Automation — Suggested Commands

## Development
- `pip install -e .` — Install in editable mode
- `pip install -e ".[all]"` — With all optional deps

## CLI
- `narractive --help`
- `narractive --list --sequences-package examples.filtermate.sequences`
- `narractive --narration --narrations-file examples/filtermate/narrations.yaml`
- `narractive --diagrams --diagrams-module examples.filtermate.diagrams.mermaid_definitions`
- `narractive --calibrate --config config.yaml`
- `narractive --all --sequences-package examples.filtermate.sequences --config config.yaml`
- `narractive --assemble --video v01`
- `narractive --dry-run --all --sequences-package examples.filtermate.sequences`

## Docker
- `docker compose build`
- `docker compose run --rm video --all --sequences-package examples.filtermate.sequences`

## Git
- `git status && git log --oneline -10`

## Note
- No test suite configured yet
- No linter/formatter configured
