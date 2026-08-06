"""Map rubric topics onto the syllabus themes, and flag out-of-scope content.

Primary Science is organised into five themes. Topics authored on a rubric are
finer-grained than that on purpose -- "expansion_and_contraction" is more useful for
spotting a weak area than "Energy" -- so each topic is mapped to its theme rather
than replaced by it, and both are stored.

THE 2026 CHANGE. "Cells" leaves the syllabus from 2026: cytoplasm, nucleus and cell
terminology are no longer required. Papers up to 2025 still test it, so questions
tagged `cells` are marked out of scope rather than deleted -- they remain sound
reasoning practice, and a student should be able to choose. See CLAUDE.md section 5.

The five theme names are stable across the 2014 and 2023 syllabuses. The finer topic
names below are this project's own vocabulary, not quoted syllabus sub-topics; if
exact syllabus nomenclature is wanted, map these against the syllabus document.
"""

from __future__ import annotations

THEMES = ("Diversity", "Cycles", "Systems", "Interactions", "Energy")

# topic -> theme
THEME_OF: dict[str, str] = {
    # Diversity
    "diversity": "Diversity",
    "fungi": "Diversity",
    "bacteria": "Diversity",
    "materials": "Diversity",
    "floating_and_sinking": "Diversity",
    "states_of_matter": "Diversity",

    # Cycles
    "reproduction": "Cycles",
    "reproduction_in_plants": "Cycles",
    "life_cycles": "Cycles",
    "water_cycle": "Cycles",
    "matter": "Cycles",

    # Systems
    "plant_system": "Systems",
    "human_system": "Systems",
    "digestive_system": "Systems",
    "circulatory_system": "Systems",
    "respiration": "Systems",
    "electricity": "Systems",
    "cells": "Systems",

    # Interactions
    "forces": "Interactions",
    "magnetism": "Interactions",
    "interactions_within_environment": "Interactions",
    "food_chain": "Interactions",
    "adaptation": "Interactions",
    "survival_of_the_species": "Interactions",

    # Energy
    "energy": "Energy",
    "photosynthesis": "Energy",
    "heat": "Energy",
    "expansion_and_contraction": "Energy",
    "light": "Energy",
    "sound": "Energy",

    # Practices that run across every theme rather than sitting inside one.
    "experimental_design": "Skills",
    "measurement": "Skills",
}

# Official P6 topic names, read off the syllabus learning-outcomes table. Only the
# P6 table was available, so topics examined at lower levels (heat, electricity,
# matter, life cycles) carry a theme but no official topic name yet. PSLE examines
# the whole P3-P6 syllabus, so this map is incomplete by construction, not by error.
OFFICIAL_TOPIC: dict[str, str] = {
    "forces": "Interactions of Forces",
    "magnetism": "Interactions of Forces",
    "interactions_within_environment": "Interactions within the Environment",
    "food_chain": "Interactions within the Environment",
    "adaptation": "Interactions within the Environment",
    "survival_of_the_species": "Interactions within the Environment",
    "photosynthesis": "Energy Forms and Uses (Photosynthesis)",
    "respiration": "Energy Forms and Uses (Photosynthesis)",
    "energy": "Energy Conversion",
}

# Removed from the syllabus with effect from 2026.
RETIRED_FROM_2026 = frozenset({"cells"})


def theme_for(topic: str) -> str | None:
    return THEME_OF.get(topic)


def themes_for(topics: list[str]) -> list[str]:
    seen: list[str] = []
    for topic in topics:
        theme = theme_for(topic)
        if theme and theme not in seen:
            seen.append(theme)
    return seen


def official_topics(topics: list[str]) -> list[str]:
    """Syllabus topic names for the topics that have one."""
    seen: list[str] = []
    for topic in topics:
        name = OFFICIAL_TOPIC.get(topic)
        if name and name not in seen:
            seen.append(name)
    return seen


def unmapped(topics: list[str]) -> list[str]:
    """Topics with no theme — a tag typo, or vocabulary that needs adding here."""
    return sorted({t for t in topics if t not in THEME_OF})


def out_of_scope_from_2026(topics: list[str]) -> list[str]:
    return sorted(set(topics) & RETIRED_FROM_2026)
