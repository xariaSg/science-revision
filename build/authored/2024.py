"""Authored rubric chains for the 2024 paper.

Kept as data here rather than edited into rubrics/2024.json by hand so that
re-scaffolding never loses the work and every chain is reviewable in one place.
Apply with:  python build/apply_authored.py --years 2024

Each entry is keyed (question, part). `mark_model` says how marks map onto the
rubric — see build/validate.py. Facets are variable / action / result.

These are authored from the EPH suggested answers, which are a publisher's
answers, not the official SEAB marking scheme. Every entry is reviewed: false
until a human confirms it.
"""

CHAINS: dict[tuple[int, str | None], dict] = {

    # "State two functions of roots." Two independent facts, not a cause-and-effect
    # chain, so each is its own route worth one mark. There is also no scenario here
    # to gate against — the question asks for general knowledge about roots, not
    # about a labelled plant — hence context_gate "general".
    (29, "a"): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "context_gate": "general",
        "topics": ["plant_system"],
        "chains": [
            {"chain_id": "absorb", "keypoints": [
                {"kp_id": "abs_1", "position": 1, "facet": "result",
                 "statement": "roots absorb water and mineral salts from the soil",
                 "accepts": ["roots take in water and minerals",
                             "roots absorb water and nutrients from the soil"]}]},
            {"chain_id": "anchor", "keypoints": [
                {"kp_id": "anc_1", "position": 1, "facet": "result",
                 "statement": "roots anchor the plant firmly to the ground",
                 "accepts": ["roots hold the plant in place",
                             "roots stop the plant being blown over"]}]},
        ],
        "traps": ["naming only one function when two are asked for",
                  "describing what roots are rather than what they do"],
    },

    (29, "b(i)"): {
        "mark_model": "per_keypoint",
        "topics": ["plant_system", "adaptation"],
        "chains": [{
            "chain_id": "compare",
            "keypoints": [
                {"kp_id": "cmp_1", "position": 1, "facet": "result",
                 "statement": "plant E has long roots growing deep into the ground "
                              "while plant H has shorter roots",
                 "accepts": ["plant E's roots are longer/deeper than plant H's",
                             "plant H has shorter roots than plant E"]},
            ],
        }],
        "traps": ["describing only one plant's roots without comparing",
                  "saying roots are 'different' without saying how"],
    },

    (29, "b(ii)"): {
        "mark_model": "per_keypoint",
        "topics": ["adaptation", "plant_system"],
        "chains": [{
            "chain_id": "water",
            "keypoints": [
                {"kp_id": "wat_1", "position": 1, "facet": "result",
                 "statement": "long roots reach deeper, moister layers of soil so "
                              "plant E can still obtain water where rain is scarce",
                 "accepts": ["its roots reach water deeper underground",
                             "it can absorb water from deeper soil which is still moist"]},
            ],
        }],
        "traps": ["stating the roots are long without saying what that lets the "
                  "plant obtain",
                  "saying it 'survives better' with no mechanism"],
    },

    (30, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["reproduction_in_plants"],
        "chains": [{
            "chain_id": "name",
            "keypoints": [
                {"kp_id": "nam_1", "position": 1, "facet": "result",
                 "statement": "pollination",
                 "accepts": []},
            ],
        }],
        "traps": ["answering 'fertilisation', which happens after pollination"],
    },

    (30, "b(i)"): {
        "mark_model": "per_keypoint",
        "topics": ["reproduction_in_plants"],
        "chains": [{
            "chain_id": "name",
            "keypoints": [
                {"kp_id": "nam_1", "position": 1, "facet": "result",
                 "statement": "germination",
                 "accepts": []},
            ],
        }],
        "traps": ["answering 'seed dispersal', which happens before germination"],
    },

    (30, "b(ii)"): {
        "mark_model": "per_chain",
        "chains_required": 1,
        "topics": ["reproduction_in_plants", "interactions_within_environment"],
        "chains": [{
            "chain_id": "competition",
            "keypoints": [
                {"kp_id": "comp_1", "position": 1, "facet": "variable",
                 "statement": "seed dispersal spreads the seeds away from the parent "
                              "plant, reducing competition for water, sunlight and space",
                 "accepts": ["the seeds land further apart so they compete less",
                             "there is less overcrowding"]},
                {"kp_id": "comp_2", "position": 2, "facet": "result",
                 "statement": "with enough water, sunlight and space young plant K can "
                              "grow well",
                 "accepts": ["young plant K gets enough sunlight and water to thrive"]},
            ],
        }],
        "traps": ["saying seeds are 'spread out' without naming what they would "
                  "otherwise compete for",
                  "naming the competition but never saying plant K grows better"],
    },

    (31, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["fungi", "interactions_within_environment"],
        "chains": [{
            "chain_id": "conditions",
            "keypoints": [
                {"kp_id": "con_1", "position": 1, "facet": "variable",
                 "statement": "the nest is dark, moist and warm",
                 "accepts": ["inside the nest it is humid and warm",
                             "the nest is damp and not exposed to sunlight"]},
                {"kp_id": "con_2", "position": 2, "facet": "result",
                 "statement": "these conditions favour the growth of fungus L on the "
                              "stored leaves",
                 "accepts": ["so fungus L grows well there",
                             "fungi grow well in warm humid places"]},
            ],
        }],
        "traps": ["reciting that fungi like warm damp places without tying it to the "
                  "nest — a textbook definition that does not answer the scenario"],
    },

    (31, "b"): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "topics": ["survival_of_the_species", "interactions_within_environment"],
        "chains": [
            {"chain_id": "food", "keypoints": [
                {"kp_id": "food_1", "position": 1, "facet": "result",
                 "statement": "when the eggs hatch the young of insect P have food "
                              "readily available",
                 "accepts": ["the young have food as soon as they hatch"]}]},
            {"chain_id": "shelter", "keypoints": [
                {"kp_id": "shl_1", "position": 1, "facet": "result",
                 "statement": "the young of insect P are hidden from predators that "
                              "enter the nest",
                 "accepts": ["the young are protected from predators"]}]},
        ],
        "traps": ["giving only food or only protection when two points are needed"],
    },

    (32, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["interactions_within_environment", "photosynthesis"],
        "chains": [{
            "chain_id": "light",
            "keypoints": [
                {"kp_id": "lig_1", "position": 1, "facet": "action",
                 "statement": "more plant F covered the pond surface so less light "
                              "reached plant G to photosynthesise, and plant G died",
                 "accepts": ["plant F blocked the sunlight from plant G so it could "
                             "not make food and died",
                             "less light reached plant G so it could not photosynthesise"]},
            ],
        }],
        "traps": ["saying plant G decreased without naming light as the cause",
                  "blaming competition for space rather than light"],
    },

    (32, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["interactions_within_environment", "food_chain"],
        "chains": [{
            "chain_id": "food",
            "keypoints": [
                {"kp_id": "food_1", "position": 1, "facet": "result",
                 "statement": "the population of bird A increases because more plant F "
                              "is available as food",
                 "accepts": ["bird A increases as it has more plant F to eat"]},
            ],
        }],
        "traps": ["stating the population changes without saying why",
                  "predicting a decrease"],
    },

    # Two parallel routes to the same conclusion, each worth one mark. A student who
    # completes one and omits the other has a different failure from one who states
    # both endpoints with no middle (CLAUDE.md 3.1).
    (32, "c"): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "topics": ["interactions_within_environment", "photosynthesis", "food_chain"],
        "chains": [
            {
                "chain_id": "food",
                "keypoints": [
                    {"kp_id": "food_1", "position": 1, "facet": "variable",
                     "statement": "fewer plant G means less food for bird B",
                     "accepts": ["bird B has less to eat"]},
                    {"kp_id": "food_2", "position": 2, "facet": "action",
                     "statement": "the same number of bird B eat more fish C instead",
                     "accepts": ["bird B turns to fish C", "bird B preys on fish C"]},
                    {"kp_id": "food_3", "position": 3, "facet": "result",
                     "statement": "the number of fish C decreases",
                     "accepts": ["fish C population drops"]},
                ],
            },
            {
                "chain_id": "oxygen",
                "keypoints": [
                    {"kp_id": "oxy_1", "position": 1, "facet": "variable",
                     "statement": "fewer plant G means less photosynthesis takes place",
                     "accepts": []},
                    {"kp_id": "oxy_2", "position": 2, "facet": "action",
                     "statement": "less oxygen is produced and dissolved in the pond water",
                     "accepts": ["less dissolved oxygen is available"]},
                    {"kp_id": "oxy_3", "position": 3, "facet": "result",
                     "statement": "the number of fish C decreases",
                     "accepts": ["fish C population drops"]},
                ],
            },
        ],
        "traps": ["stating that fish C decreases without naming a mechanism",
                  "answering only via food and omitting the oxygen route"],
    },

    (33, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["plant_system", "respiration"],
        "chains": [{"chain_id": "function", "keypoints": [
            {"kp_id": "fun_1", "position": 1, "facet": "result",
             "statement": "the tiny openings let gases be exchanged between the "
                          "plant and its surroundings",
             "accepts": ["they let carbon dioxide in and oxygen out",
                         "gases move in and out of the leaf through them"]}]}],
        "traps": ["naming the openings (stomata) without saying what they do"],
    },

    (33, "b"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["pollutant S"],
        "topics": ["interactions_within_environment", "plant_system"],
        "chains": [{"chain_id": "trend", "keypoints": [
            {"kp_id": "trd_1", "position": 1, "facet": "result",
             "statement": "the greater the percentage of pollutant S, the smaller "
                          "the tiny openings on the leaves",
             "accepts": ["more pollutant S means smaller openings",
                         "the openings get smaller as pollutant S increases"]}]}],
        "traps": ["saying the openings 'change' without giving the direction",
                  "stating a value without relating the two variables"],
    },

    # CLAUDE.md 3.3 uses this as the worked example of the contextual gate:
    # "it is a fair test" is a template answer and earns nothing. The mark needs
    # pollutant S named as the only changed variable AND another factor ruled out.
    (33, "c"): {
        "mark_model": "per_chain",
        "chains_required": 1,
        "scenario_anchors": ["pollutant S"],
        "topics": ["experimental_design"],
        "chains": [{"chain_id": "fair_test", "keypoints": [
            {"kp_id": "fair_1", "position": 1, "facet": "variable",
             "statement": "pollutant S must be the only thing changed between the "
                          "set-ups",
             "accepts": ["only the amount of pollutant S is different"]},
            {"kp_id": "fair_2", "position": 2, "facet": "result",
             "statement": "so any change in the size of the tiny openings is caused "
                          "by pollutant S and not by another factor such as heat "
                          "from the sun",
             "accepts": ["the openings changed because of pollutant S alone",
                         "no other factor such as sunlight caused the change"]}]}],
        "traps": ["answering 'it is a fair test' — a template answer that names no "
                  "variable and earns nothing",
                  "naming pollutant S but never ruling out any other factor"],
    },

    (34, "a"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["substance X"],
        "topics": ["interactions_within_environment"],
        "chains": [{"chain_id": "trend", "keypoints": [
            {"kp_id": "trd_1", "position": 1, "facet": "result",
             "statement": "as the mass of substance X added increased, the thickness "
                          "of the eggshell decreased",
             "accepts": ["more substance X gave thinner eggshells",
                         "the eggshells got thinner as more X was added"]}]}],
        "traps": ["describing one reading instead of the trend",
                  "saying the thickness 'changed' without the direction"],
    },

    (34, "b"): {
        "mark_model": "per_chain",
        "chains_required": 1,
        "scenario_anchors": ["animal Y", "substance X"],
        "topics": ["interactions_within_environment", "survival_of_the_species"],
        "chains": [{"chain_id": "decompose", "keypoints": [
            {"kp_id": "dec_1", "position": 1, "facet": "variable",
             "statement": "as the dead plants decompose further, more substance X is "
                          "produced",
             "accepts": ["decomposition releases more substance X"]},
            {"kp_id": "dec_2", "position": 2, "facet": "action",
             "statement": "more substance X makes the eggshells of animal Y thinner",
             "accepts": ["the eggshells become thinner"]},
            {"kp_id": "dec_3", "position": 3, "facet": "result",
             "statement": "the fully developed young of animal Y can break out of the "
                          "thin shells more easily",
             "accepts": ["the young hatch out more easily"]}]}],
        "traps": ["stating the eggshells get thinner without saying what that lets "
                  "the young do"],
    },

    (34, "c"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["animal Y", "32 °C"],
        "topics": ["survival_of_the_species", "reproduction"],
        "chains": [{"chain_id": "temperature", "keypoints": [
            {"kp_id": "tmp_1", "position": 1, "facet": "variable",
             "statement": "32 °C",
             "accepts": ["thirty-two degrees Celsius"]},
            {"kp_id": "tmp_2", "position": 2, "facet": "result",
             "statement": "at this temperature equal numbers of male and female "
                          "animal Y hatch, so they can mate and reproduce to continue "
                          "the species",
             "accepts": ["there are both males and females so they can reproduce",
                         "an equal number of each sex hatches so the species continues"]}]}],
        "traps": ["giving the temperature with no reason",
                  "saying 'more hatch' rather than an equal number of each sex"],
    },

    # Two trends either side of 45 degrees; the answer is incomplete with only one.
    (35, "a"): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "scenario_anchors": ["45 degrees"],
        "topics": ["forces", "energy"],
        "chains": [
            {"chain_id": "below_45", "keypoints": [
                {"kp_id": "bel_1", "position": 1, "facet": "result",
                 "statement": "as the launching angle increases up to 45 degrees, the "
                              "distance moved by the ball increases",
                 "accepts": ["the ball goes further as the angle rises towards 45"]}]},
            {"chain_id": "above_45", "keypoints": [
                {"kp_id": "abv_1", "position": 1, "facet": "result",
                 "statement": "beyond 45 degrees, the distance moved by the ball "
                              "decreases",
                 "accepts": ["past 45 degrees the ball does not go as far"]}]},
        ],
        "traps": ["describing only the rise and missing the fall after 45 degrees",
                  "saying the distance 'changes' without the direction"],
    },

    (35, "b"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["forces"],
        "chains": [{"chain_id": "name", "keypoints": [
            {"kp_id": "nam_1", "position": 1, "facet": "result",
             "statement": "gravitational force",
             "accepts": ["gravity"]}]}],
        "traps": ["answering 'frictional force' or 'air resistance'"],
    },

    (35, "c"): {
        "mark_model": "per_chain",
        "chains_required": 1,
        "topics": ["forces", "experimental_design"],
        "chains": [{"chain_id": "measurement", "keypoints": [
            {"kp_id": "mea_1", "position": 1, "facet": "action",
             "statement": "after hitting the water the ball sinks, and where it lands "
                          "may not be directly below the point where it entered",
             "accepts": ["the ball drifts as it sinks"]},
            {"kp_id": "mea_2", "position": 2, "facet": "result",
             "statement": "so the distance moved by the ball cannot be measured "
                          "accurately",
             "accepts": ["the measurement would not be accurate"]}]}],
        "traps": ["saying the ball sinks without saying why that matters"],
    },

    (35, "d"): {
        "mark_model": "per_keypoint",
        "topics": ["experimental_design", "forces"],
        "chains": [{"chain_id": "control", "keypoints": [
            {"kp_id": "ctl_1", "position": 1, "facet": "variable",
             "statement": "the spring must be compressed by the same amount each time",
             "accepts": ["the same compression of the spring",
                         "the elastic spring force used to launch the ball is kept "
                         "the same"]}]}],
        "traps": ["naming the launching angle, which is the variable being changed"],
    },

    (36, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["heat"],
        "chains": [{"chain_id": "read", "keypoints": [
            {"kp_id": "rd_1", "position": 1, "facet": "result",
             "statement": "50 mm", "accepts": ["50 millimetres"]}]}],
        "traps": [],
    },

    (36, "b"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["heat"],
        "chains": [{"chain_id": "read", "keypoints": [
            {"kp_id": "rd_1", "position": 1, "facet": "result",
             "statement": "6 mm", "accepts": ["6 millimetres"]}]}],
        "traps": [],
    },

    (36, "c"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["the wires"],
        "topics": ["heat", "expansion_and_contraction"],
        "chains": [{"chain_id": "contraction", "keypoints": [
            {"kp_id": "con_1", "position": 1, "facet": "action",
             "statement": "at night the surrounding temperature fell, so the wires "
                          "lost heat and contracted",
             "accepts": ["the wires got colder and contracted",
                         "the wires shrank as they lost heat"]},
            {"kp_id": "con_2", "position": 2, "facet": "result",
             "statement": "the wires had been pulled tight with no allowance for "
                          "contraction, so they snapped",
             "accepts": ["there was no slack, so they broke"]}]}],
        "traps": ["saying the wires contracted without saying why they broke",
                  "attributing the break to the wires expanding"],
    },

    (36, "d"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["the wires"],
        "topics": ["heat", "expansion_and_contraction"],
        "chains": [{"chain_id": "fix", "keypoints": [
            {"kp_id": "fix_1", "position": 1, "facet": "action",
             "statement": "secure the wires to the wooden support loosely, leaving "
                          "slack so they can contract without snapping",
             "accepts": ["let the wires hang loosely",
                         "do not pull the wires tight"]}]}],
        "traps": ["suggesting a change that does not allow for contraction"],
    },

    (37, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["states_of_matter", "heat"],
        "chains": [{"chain_id": "define", "keypoints": [
            {"kp_id": "def_1", "position": 1, "facet": "result",
             "statement": "freezing is when a liquid changes into a solid at its "
                          "freezing point",
             "accepts": ["a liquid turns into a solid",
                         "a liquid loses heat and becomes a solid"]}]}],
        "traps": ["describing melting instead", "omitting either state"],
    },

    (37, "b"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["substance P", "30 °C"],
        "topics": ["states_of_matter"],
        "chains": [{"chain_id": "identify", "keypoints": [
            {"kp_id": "id_1", "position": 1, "facet": "variable",
             "statement": "150 cm3 can only be stored in a 100 cm3 container if the "
                          "substance is a gas, because only a gas can be compressed",
             "accepts": ["only gases can be compressed into a smaller volume"]},
            {"kp_id": "id_2", "position": 2, "facet": "result",
             "statement": "substance P, because its boiling point is 15 °C so it is "
                          "a gas at 30 °C",
             "accepts": ["substance P is already a gas at 30 °C"]}]}],
        "traps": ["naming substance P with no reason",
                  "arguing from the freezing point rather than the boiling point"],
    },

    (37, "c"): {
        "mark_model": "per_chain",
        "chains_required": 1,
        "scenario_anchors": ["substance Q", "30 °C"],
        "topics": ["states_of_matter"],
        "chains": [{"chain_id": "liquid", "keypoints": [
            {"kp_id": "liq_1", "position": 1, "facet": "variable",
             "statement": "substance Q is a liquid at 30 °C",
             "accepts": ["Q is in the liquid state at that temperature"]},
            {"kp_id": "liq_2", "position": 2, "facet": "result",
             "statement": "the tray has gaps, so liquid Q would flow out instead of "
                          "being stored",
             "accepts": ["a liquid would run out of the open tray",
                         "the tray cannot hold a liquid because it is not sealed"]}]}],
        "traps": ["answering yes or no with no reason",
                  "saying Q is a liquid but never mentioning the gaps in the tray"],
    },

    (38, "a"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["contact B"],
        "topics": ["electricity", "magnetism"],
        "chains": [{"chain_id": "cycle", "keypoints": [
            {"kp_id": "cyc_1", "position": 1, "facet": "action",
             "statement": "with the switch closed, current makes the iron cylinder an "
                          "electromagnet that repels the magnet upwards, so metal "
                          "contact B is broken and the circuit opens",
             "accepts": ["the electromagnet pushes the magnet up and breaks the "
                         "contact, opening the circuit"]},
            {"kp_id": "cyc_2", "position": 2, "facet": "result",
             "statement": "with no current the cylinder loses its magnetism, the "
                          "magnet drops back, contact B is remade and the cycle "
                          "repeats",
             "accepts": ["the electromagnet switches off, the magnet falls back and "
                         "the circuit closes again, so it repeats"]}]}],
        "traps": ["describing only the upward push and never the circuit re-closing",
                  "saying the magnet moves without naming the electromagnet"],
    },

    (38, "b"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["contact B", "the batteries"],
        "topics": ["energy", "electricity", "magnetism"],
        "chains": [{"chain_id": "energy", "keypoints": [
            {"kp_id": "eng_1", "position": 1, "facet": "result",
             "statement": "the captain moved up to a lower height than before",
             "accepts": ["it did not go as high"]},
            {"kp_id": "eng_2", "position": 2, "facet": "variable",
             "statement": "hours of play converted much of the batteries' chemical "
                          "potential energy into electrical energy, so less remained, "
                          "giving a weaker electromagnet and weaker repulsion",
             "accepts": ["the batteries had less stored energy left, so the "
                         "electromagnet was weaker",
                         "less electrical energy meant a weaker push on the magnet"]}]}],
        "traps": ["saying the batteries are 'running out' with no energy conversion",
                  "stating the height changed without explaining why"],
    },

    (39, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["measurement"],
        "chains": [{"chain_id": "read", "keypoints": [
            {"kp_id": "rd_1", "position": 1, "facet": "result",
             "statement": "112.6 cm", "accepts": ["112.6 centimetres"]}]}],
        "traps": [],
    },

    (39, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["measurement", "experimental_design"],
        "chains": [{"chain_id": "method", "keypoints": [
            {"kp_id": "met_1", "position": 1, "facet": "action",
             "statement": "the zero end of the measuring tape should start at the "
                          "level the boy is standing on",
             "accepts": ["put the zero mark at his feet / at ground level",
                         "measure from the surface he stands on"]}]}],
        "traps": ["saying the measurement is wrong without saying how to fix it"],
    },

    (40, "a"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["block A", "block B"],
        "topics": ["floating_and_sinking", "forces"],
        "chains": [{"chain_id": "observe", "keypoints": [
            {"kp_id": "obs_1", "position": 1, "facet": "result",
             "statement": "block A floats and block B sinks",
             "accepts": ["A stays on the surface while B goes down"]}]}],
        "traps": ["describing only one of the two blocks"],
    },

    (40, "b"): {
        "mark_model": "per_chain",
        "chains_required": 1,
        "scenario_anchors": ["block A", "block B"],
        "topics": ["floating_and_sinking", "experimental_design"],
        "chains": [{"chain_id": "evidence", "keypoints": [
            {"kp_id": "evi_1", "position": 1, "facet": "variable",
             "statement": "many different materials can float on water, so floating "
                          "alone does not identify the material",
             "accepts": ["wood and polystyrene both float, so floating proves nothing "
                         "about which material it is"]},
            {"kp_id": "evi_2", "position": 2, "facet": "result",
             "statement": "so there is not enough evidence to conclude the two blocks "
                          "are made of the same material",
             "accepts": ["I do not agree — you cannot tell they are the same material"]}]}],
        "traps": ["agreeing with the conclusion",
                  "disagreeing with no reason given"],
    },
}
