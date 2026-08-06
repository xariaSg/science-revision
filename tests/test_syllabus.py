"""Tests for the syllabus theme/topic mapping."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from syllabus import (  # noqa: E402
    SYLLABUS, THEME_OF_TOPIC, TOPIC_MAP, official_topics, out_of_scope_from_2026,
    theme_for, themes_for, unmapped,
)


def test_every_mapped_topic_is_a_real_syllabus_topic():
    """A typo in TOPIC_MAP would otherwise give a rubric a theme of None."""
    for tag, topic in TOPIC_MAP.items():
        assert topic in THEME_OF_TOPIC, f"{tag} -> {topic!r} is not in the syllabus"


def test_five_themes():
    assert set(SYLLABUS) == {"Diversity", "Cycles", "Systems", "Interactions", "Energy"}


def test_theme_is_derived_from_the_topic():
    assert theme_for("forces") == "Interactions"
    assert theme_for("photosynthesis") == "Energy"
    assert theme_for("plant_system") == "Systems"
    assert theme_for("fungi") == "Diversity"
    assert theme_for("reproduction_in_plants") == "Cycles"


def test_respiration_is_energy_not_systems():
    """Respiration is an Energy topic; the Human Respiratory System is a Systems one."""
    assert theme_for("respiration") == "Energy"
    assert theme_for("respiratory_system") == "Systems"


def test_states_of_matter_is_cycles():
    """Matter and Its Three States sits under Cycles, not Diversity."""
    assert theme_for("states_of_matter") == "Cycles"


def test_floating_is_a_material_property():
    assert official_topics(["floating_and_sinking"]) == ["Properties of Materials"]
    assert theme_for("floating_and_sinking") == "Diversity"


def test_skills_have_a_theme_but_no_syllabus_topic():
    assert theme_for("experimental_design") == "Skills"
    assert official_topics(["experimental_design", "measurement"]) == []


def test_themes_are_deduplicated_and_ordered():
    assert themes_for(["forces", "magnetism", "photosynthesis"]) == \
        ["Interactions", "Energy"]


def test_unknown_tag_is_reported():
    assert unmapped(["forces", "not_a_real_topic"]) == ["not_a_real_topic"]


def test_skills_are_not_reported_as_unmapped():
    assert unmapped(["experimental_design", "measurement"]) == []


def test_cells_is_out_of_scope_from_2026():
    assert out_of_scope_from_2026(["cells", "forces"]) == ["cells"]
    assert out_of_scope_from_2026(["forces"]) == []


def test_cells_is_not_reported_as_a_typo():
    """It is retired, not mistyped — reporting it as unmapped would be noise."""
    assert unmapped(["cells"]) == []
