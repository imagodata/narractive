# Video Automation — Suggested Commands

## Development
- `pip install -e .` — Install in editable mode
- `pip install -e ".[all]"` — With all optional deps

## CLI
- `video-automation --help`
- `video-automation --list --sequences-package examples.filtermate.sequences`
- `video-automation --narration --narrations-file examples/filtermate/narrations.yaml`
- `video-automation --diagrams --diagrams-module examples.filtermate.diagrams.mermaid_definitions`
- `video-automation --calibrate --config config.yaml`
- `video-automation --all --sequences-package examples.filtermate.sequences --config config.yaml`
- `video-automation --assemble --video v01`
- `video-automation --dry-run --all --sequences-package examples.filtermate.sequences`

## Docker
- `docker compose build`
- `docker compose run --rm video --all --sequences-package examples.filtermate.sequences`

## Git
- `git status && git log --oneline -10`

## Note
- No test suite configured yet
- No linter/formatter configured
