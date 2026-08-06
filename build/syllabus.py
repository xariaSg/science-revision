"""The Primary Science syllabus themes and topics, and the mapping onto them.

SYLLABUS below is the official structure: five themes, each with its topics, as
named by the syllabus. It is the single source of truth here -- a rubric's theme is
derived from its topic rather than stored separately, so the two cannot drift.

Rubric topics are this project's own finer vocabulary and stay that way on purpose.
"expansion_and_contraction" locates a weak area far better than "Heat Energy" does,
and "Interactions of Forces" is what a syllabus-shaped filter needs. Both are kept:
TOPIC_MAP relates one to the other.

THE 2026 CHANGE. "Cells" leaves the syllabus from 2026 -- cytoplasm, nucleus and
cell terminology are no longer required. Papers up to 2025 still test it, so
questions tagged `cells` are marked out of scope rather than deleted: they remain
sound reasoning practice and the student should be able to choose. CLAUDE.md §5.
"""

from __future__ import annotations

SYLLABUS: dict[str, tuple[str, ...]] = {
    "Diversity": (
        "Characteristics of Living Things",
        "Classification of Animals",
        "Classification of Plants",
        "Fungi",
        "Bacteria",
        "Properties of Materials",
        "Types of Materials",
    ),
    "Cycles": (
        "Life Cycle of Plants",
        "Life Cycle of Animals",
        "Matter and Its Three States",
        "Reproduction in Plants",
        "Reproduction in Humans",
        "Passing Down Characteristics from Parents to Young",
        "Water and Its States",
        "The Water Cycle",
        "Cooling Effects of Evaporation",
        "Examples of Condensation in Everyday Life",
    ),
    "Systems": (
        "The Human Body Systems",
        "Human Digestive System",
        "Plant System",
        "Plant Transport System",
        "Human Respiratory System",
        "Human Circulatory System",
        "The Electrical System",
    ),
    "Interactions": (
        "Magnets",
        "Forces",
        "The Environment",
        "Living Together",
        "What is a Community?",
        "Food Chains and Food Webs",
        "Man's Impact on the Environment",
        "Adaptations",
    ),
    "Energy": (
        "Light Energy",
        "Heat Energy",
        "Photosynthesis",
        "Respiration",
        "Energy Sources",
        "The Forms and Conversion of Energy",
    ),
}

THEME_OF_TOPIC: dict[str, str] = {
    topic: theme for theme, topics in SYLLABUS.items() for topic in topics
}

# Project topic tag -> syllabus topic.
TOPIC_MAP: dict[str, str] = {
    # Diversity
    "fungi": "Fungi",
    "bacteria": "Bacteria",
    "materials": "Types of Materials",
    # Whether an object floats is a property of its material, so this sits under
    # Diversity rather than with the forces it is usually taught alongside.
    "floating_and_sinking": "Properties of Materials",
    "characteristics_of_living_things": "Characteristics of Living Things",

    # Cycles
    "states_of_matter": "Matter and Its Three States",
    "matter": "Matter and Its Three States",
    "reproduction_in_plants": "Reproduction in Plants",
    "reproduction": "Reproduction in Plants",
    "life_cycles": "Life Cycle of Animals",
    "water_cycle": "The Water Cycle",
    "evaporation": "Cooling Effects of Evaporation",
    "condensation": "Examples of Condensation in Everyday Life",
    "heredity": "Passing Down Characteristics from Parents to Young",

    # Systems
    "plant_system": "Plant System",
    "plant_transport": "Plant Transport System",
    "human_system": "The Human Body Systems",
    "digestive_system": "Human Digestive System",
    "circulatory_system": "Human Circulatory System",
    "respiratory_system": "Human Respiratory System",
    "electricity": "The Electrical System",

    # Interactions
    "forces": "Forces",
    "magnetism": "Magnets",
    "interactions_within_environment": "The Environment",
    # The P6 outcomes put "factors that affect the survival of an organism" under
    # the Environment topic, not under Adaptations.
    "survival_of_the_species": "The Environment",
    "food_chain": "Food Chains and Food Webs",
    "adaptation": "Adaptations",
    "community": "What is a Community?",
    "human_impact": "Man's Impact on the Environment",
    "living_together": "Living Together",

    # Energy
    "photosynthesis": "Photosynthesis",
    # Respiration is an Energy topic; the Human Respiratory System is a Systems one.
    "respiration": "Respiration",
    "heat": "Heat Energy",
    "expansion_and_contraction": "Heat Energy",
    "light": "Light Energy",
    "energy": "The Forms and Conversion of Energy",
    "sound": "The Forms and Conversion of Energy",
    "energy_sources": "Energy Sources",
}

# Practices that run across every theme rather than sitting inside one. The 2026
# syllabus puts more weight on these, so they are tracked rather than discarded.
SKILL_TOPICS = frozenset({"experimental_design", "measurement"})

# Removed from the syllabus with effect from 2026.
RETIRED_FROM_2026 = frozenset({"cells"})


def syllabus_topic_for(topic: str) -> str | None:
    return TOPIC_MAP.get(topic)


def theme_for(topic: str) -> str | None:
    if topic in SKILL_TOPICS:
        return "Skills"
    mapped = TOPIC_MAP.get(topic)
    return THEME_OF_TOPIC.get(mapped) if mapped else None


def themes_for(topics: list[str]) -> list[str]:
    seen: list[str] = []
    for topic in topics:
        theme = theme_for(topic)
        if theme and theme not in seen:
            seen.append(theme)
    return seen


def official_topics(topics: list[str]) -> list[str]:
    seen: list[str] = []
    for topic in topics:
        name = syllabus_topic_for(topic)
        if name and name not in seen:
            seen.append(name)
    return seen


def unmapped(topics: list[str]) -> list[str]:
    """Tags with no syllabus topic and not a skill — a typo, or vocabulary to add."""
    return sorted({t for t in topics
                   if t not in TOPIC_MAP and t not in SKILL_TOPICS
                   and t not in RETIRED_FROM_2026})


def out_of_scope_from_2026(topics: list[str]) -> list[str]:
    return sorted(set(topics) & RETIRED_FROM_2026)
