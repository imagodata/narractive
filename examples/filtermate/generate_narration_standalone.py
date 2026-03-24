#!/usr/bin/env python3
"""
Narration generator for FilterMate — creates TTS audio for all sequences.
Thin wrapper around narractive.core.narrator.

Uses edge-tts (free Microsoft Neural TTS voices).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from narractive.core.narrator import Narrator

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "narration")

NARRATOR_CONFIG = {
    "engine": "edge-tts",
    "voice": "fr-FR-HenriNeural",
    "rate": "+0%",
    "volume": "+0%",
    "output_dir": OUTPUT_DIR,
}

# All narration texts (FilterMate example)
NARRATIONS = {
    "seq00_intro": (
        "Vous avez 1 million de bâtiments dans votre PostGIS ? "
        "Vous cherchez juste ceux à 200 mètres d'une route spécifique ? "
        "Et vous voulez ça en moins de 2 secondes ? "
        "C'est exactement ce que fait FilterMate."
    ),
    "seq01_problem": (
        "En SIG, le filtrage est une tâche centrale. Mais les outils natifs ont leurs limites : "
        "expressions complexes, aucun historique, aucun système de favoris, "
        "performance dégradée sur les grosses sources. "
        "FilterMate résout tout ça."
    ),
    "seq02_install": (
        "Installation en 3 clics depuis le dépôt officiel. "
        "Pour les bases PostgreSQL, un simple pip install psycopg2-binary suffit. "
        "FilterMate fonctionne sur Windows, Linux et macOS."
    ),
    "seq03_interface": (
        "L'interface se présente sous forme d'un panneau ancré, "
        "organisé en 3 onglets principaux : Filtrage, Exploration des données, et Export. "
        "Support du thème sombre automatique, 22 langues disponibles."
    ),
    "seq04_filtering_part1": (
        "Voilà un jeu de données BDTopo. 1 million de bâtiments dans PostgreSQL. "
        "Je sélectionne ma couche source : les routes. Ma couche cible : les bâtiments."
    ),
    "seq04_filtering_part2": (
        "Je choisis le prédicat géométrique touches, j'ajoute un buffer de 50 mètres... "
        "et j'applique. FilterMate détecte automatiquement que c'est une couche PostgreSQL, "
        "crée une vue matérialisée optimisée et renvoie le résultat : 1 milliseconde."
    ),
    "seq04_filtering_part3": (
        "Je peux annuler avec l'undo, 100 états conservés. "
        "Ou rappeler un filtre favori enregistré précédemment. "
        "Tout ça sans jamais écrire une seule ligne de SQL."
    ),
    "seq05_exploration": (
        "L'onglet Exploration vous permet de parcourir vos entités une à une, "
        "avec centrage automatique sur la carte."
    ),
    "seq06_export": (
        "L'export GeoPackage est l'une des fonctionnalités les plus puissantes. "
        "FilterMate ne se contente pas d'exporter vos données, "
        "il embarque votre projet complet dans le fichier."
    ),
    "seq07_backends": (
        "Derrière l'interface simple, FilterMate embarque 4 backends optimisés. "
        "Il choisit automatiquement le meilleur selon le type de votre source de données."
    ),
    "seq08_architecture": (
        "FilterMate est construit sur une architecture hexagonale. "
        "Le domaine métier pur est au centre, totalement indépendant "
        "de l'interface graphique ou de la base de données."
    ),
    "seq09_advanced": (
        "FilterMate va plus loin : filtrage chaîné avec buffers dynamiques, "
        "détection automatique de la clé primaire PostgreSQL, "
        "100 états undo redo, et un système de favoris avec contexte spatial."
    ),
    "seq10_conclusion": (
        "FilterMate est disponible gratuitement. "
        "Le code source est sur GitHub, la documentation sur le site dédié. "
        "Installez-le, essayez-le, et si ça vous est utile, "
        "laissez une étoile sur GitHub. À bientôt !"
    ),
}


def main():
    narrator = Narrator(NARRATOR_CONFIG)

    print(f"\n{'='*50}")
    print(f"  FilterMate Narration Generator")
    print(f"  Voice: {NARRATOR_CONFIG['voice']}")
    print(f"  {len(NARRATIONS)} narrations to generate")
    print(f"{'='*50}\n")

    results = narrator.generate_all_narrations(NARRATIONS, OUTPUT_DIR)

    # Build manifest from results
    manifest = {}
    for name, path in results.items():
        manifest[name] = {
            "file": path.name,
            "text": NARRATIONS[name],
        }
        print(f"  ✓ {name}: {path}")

    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n  Done: {len(manifest)} narration files")
    print(f"  Manifest: {manifest_path}")
    print()


if __name__ == "__main__":
    main()
