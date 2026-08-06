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
}
