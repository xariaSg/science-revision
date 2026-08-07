"""Authored rubric chains for the 2023 paper.

Kept as data here rather than edited into rubrics/2023.json by hand so that
re-scaffolding never loses the work and every chain is reviewable in one place.
Apply with:  python build/apply_authored.py --years 2023

Each entry is keyed (question, part). `mark_model` says how marks map onto the
rubric — see build/validate.py. Facets are variable / action / result.

The first paper on the current syllabus, so the scaffold tags it era "2023".

Two sub-parts are marked response_mode "drawn": Q32(a) asks for a food web and
Q39 for a corrected circuit. Q29(a) is deliberately *not* — it says "use a pencil
to draw the life cycle using only words and arrows", and a spoken "egg, larva,
pupa, adult" is the whole of the science being tested. Drawing is the medium
there, not the answer.

Q36(b)'s model answer reached the rubric only because the "(b)" glyph was
recovered geometrically by build/extract_answers.py; it and Q29(a) were both
checked against the page scan.

These are authored from the EPH suggested answers, which are a publisher's
answers, not the official SEAB marking scheme.
"""

CHAINS: dict[tuple[int, str | None], dict] = {

    (29, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["life_cycles"],
        "chains": [{
            "chain_id": "cycle",
            "keypoints": [
                {"kp_id": "cyc_1", "position": 1, "facet": "result",
                 "statement": "egg, then larva, then pupa, then adult, and the adult "
                              "lays eggs again",
                 "accepts": ["egg to larva to pupa to adult",
                             "it goes egg, larva, pupa, adult and back round"]},
            ],
        }],
        "traps": ["leaving out the pupa stage, which mosquitoes do have",
                  "giving the stages out of order"],
    },

    (29, "b"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["characteristics_of_living_things"],
        "chains": [{
            "chain_id": "insect",
            "keypoints": [
                {"kp_id": "ins_1", "position": 1, "facet": "result",
                 "statement": "it has three pairs of legs",
                 "accepts": ["six legs", "it has three body parts",
                             "it has a pair of feelers / antennae"]},
            ],
        }],
        "traps": ["naming wings, which many non-insects also have",
                  "naming a characteristic of living things in general rather than "
                  "one that makes it an insect"],
    },

    (29, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["life_cycles", "human_impact",
                   "interactions_within_environment"],
        "scenario_anchors": ["global warming", "temperature"],
        "chains": [{
            "chain_id": "warming",
            "keypoints": [
                {"kp_id": "war_1", "position": 1, "facet": "variable",
                 "statement": "global warming raises the temperature of the "
                              "surroundings, and the graph shows a life cycle then "
                              "takes fewer days to complete",
                 "accepts": ["it gets hotter, and the hotter it is the fewer days the "
                             "life cycle takes"]},
                {"kp_id": "war_2", "position": 2, "facet": "result",
                 "statement": "so mosquitoes become adults sooner and the number of "
                              "adult mosquitoes increases",
                 "accepts": ["they grow up faster, so there are more adult mosquitoes"]},
            ],
        }],
        "traps": ["saying there will be more mosquitoes without using the graph",
                  "stopping at 'the life cycle is shorter' and never reaching the "
                  "number of adults"],
    },

    (30, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["circulatory_system", "respiration", "human_system"],
        "chains": [{
            "chain_id": "supply",
            "keypoints": [
                {"kp_id": "sup_1", "position": 1, "facet": "action",
                 "statement": "the legs need more energy when jogging, so the heart "
                              "pumps more blood carrying more oxygen and digested food "
                              "to them",
                 "accepts": ["the heart beats faster to send more oxygen and food to "
                             "the leg muscles"]},
                {"kp_id": "sup_2", "position": 2, "facet": "result",
                 "statement": "more respiration can take place in the legs to release "
                              "more energy, and more carbon dioxide is carried away to "
                              "the lungs to be breathed out",
                 "accepts": ["more respiration happens so more energy is released, and "
                             "the carbon dioxide made is taken to the lungs"]},
            ],
        }],
        "traps": ["saying the heart beats faster without saying what the blood delivers",
                  "naming oxygen but never naming respiration as what uses it"],
    },

    (30, "b"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["digestive_system", "circulatory_system"],
        "chains": [{
            "chain_id": "diverted",
            "keypoints": [
                {"kp_id": "div_1", "position": 1, "facet": "action",
                 "statement": "during jogging more blood is sent to the leg muscles and "
                              "less to the small intestine",
                 "accepts": ["the blood goes to the legs instead of the digestive "
                             "system"]},
                {"kp_id": "div_2", "position": 2, "facet": "result",
                 "statement": "so less digested food is absorbed into the bloodstream "
                              "at the small intestine",
                 "accepts": ["less digested food gets absorbed",
                             "absorption of digested food goes down"]},
            ],
        }],
        "traps": ["saying digestion 'stops' rather than that absorption falls",
                  "naming the change without saying where the blood went instead"],
    },

    (31, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["experimental_design"],
        "scenario_anchors": ["lake"],
        "chains": [{
            "chain_id": "variable",
            "keypoints": [
                {"kp_id": "var_1", "position": 1, "facet": "variable",
                 "statement": "the lake used, each of which holds a different amount "
                              "of dirt",
                 "accepts": ["the different lakes", "how much dirt is in the water"]},
            ],
        }],
        "traps": ["naming the depth, which is what is measured rather than changed",
                  "naming the disc, which is kept the same throughout"],
    },

    (31, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["experimental_design"],
        "scenario_anchors": ["lake"],
        "chains": [{
            "chain_id": "repeat",
            "keypoints": [
                {"kp_id": "rep_1", "position": 1, "facet": "action",
                 "statement": "the experiment was repeated three times for each lake",
                 "accepts": ["he did it three times at every lake and averaged them",
                             "there were three readings per lake"]},
            ],
        }],
        "traps": ["naming a variable kept constant rather than what makes the result "
                  "reliable"],
    },

    (31, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["experimental_design", "light"],
        "scenario_anchors": ["lake S", "750 cm"],
        "chains": [{
            "chain_id": "clearest",
            "keypoints": [
                {"kp_id": "clr_1", "position": 1, "facet": "variable",
                 "statement": "lake S, where the disc could still be seen at an average "
                              "depth of 750 cm — the deepest of the three",
                 "accepts": ["lake S, because the disc stayed visible deepest there"]},
                {"kp_id": "clr_2", "position": 2, "facet": "result",
                 "statement": "so lake S has the least dirt blocking light from passing "
                              "through the water",
                 "accepts": ["there is least dirt in it to stop the light",
                             "its water is the clearest, so light travels furthest"]},
            ],
        }],
        "traps": ["naming the lake with no reading to support it",
                  "quoting the depth without saying what it shows about the dirt"],
    },

    # "Draw a food web to show the relationships among all the organisms." [2]
    (32, "a"): {
        "response_mode": "drawn",
        "topics": ["food_chain", "interactions_within_environment"],
        "scenario_anchors": ["organism B", "organism C", "organism E", "organism F",
                             "organism G"],
        "traps": [],
    },

    (32, "b"): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "topics": ["adaptation", "survival_of_the_species", "food_chain"],
        "scenario_anchors": ["organism E", "organism G", "organism B", "organism C",
                             "nest"],
        "chains": [
            {"chain_id": "shelter", "keypoints": [
                {"kp_id": "shl_1", "position": 1, "facet": "result",
                 "statement": "building the nest in water lets organism E hide from "
                              "predator G, which lives on land",
                 "accepts": ["G lives on land so it cannot reach E in the water",
                             "E is safe from being eaten by G"]}]},
            {"chain_id": "food", "keypoints": [
                {"kp_id": "fd_1", "position": 1, "facet": "result",
                 "statement": "the nest is among organisms B and C, which live in "
                              "water, so organism E has food close by",
                 "accepts": ["E can eat B and C, which live in the water",
                             "its food is right there in the water"]}]},
        ],
        "traps": ["giving only one advantage when two are asked for",
                  "saying the nest gives 'shelter' without saying from what, or "
                  "'food' without naming B and C"],
    },

    (33, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["photosynthesis", "plant_system"],
        "chains": [{
            "chain_id": "name",
            "keypoints": [
                {"kp_id": "nam_1", "position": 1, "facet": "result",
                 "statement": "the chloroplast",
                 "accepts": ["chloroplasts", "chlorophyll in the chloroplasts"]},
            ],
        }],
        "traps": ["naming the cell wall or the nucleus, which are not where food is "
                  "made"],
    },

    (33, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["characteristics_of_living_things"],
        "scenario_anchors": ["organism P"],
        "chains": [{
            "chain_id": "respond",
            "keypoints": [
                {"kp_id": "res_1", "position": 1, "facet": "result",
                 "statement": "living things respond to changes in their surroundings",
                 "accepts": ["it shows that living things react to changes around them"]},
            ],
        }],
        "traps": ["naming growth or reproduction, which the observation does not show"],
    },

    (33, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["photosynthesis", "adaptation"],
        "scenario_anchors": ["organism P"],
        "chains": [{
            "chain_id": "light",
            "keypoints": [
                {"kp_id": "lgt_1", "position": 1, "facet": "result",
                 "statement": "organism P needs light in order to make its own food",
                 "accepts": ["it moves towards light because it photosynthesises",
                             "it needs light for photosynthesis to make food"]},
            ],
        }],
        "traps": ["saying it 'likes' light without saying what the light is for",
                  "saying it needs light to see"],
    },

    (34, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["reproduction_in_plants"],
        "chains": [{
            "chain_id": "name",
            "keypoints": [
                {"kp_id": "nam_1", "position": 1, "facet": "result",
                 "statement": "the ovary", "accepts": ["ovary of the flower"]},
            ],
        }],
        "traps": ["naming the stigma, where pollen lands, rather than where the fruit "
                  "develops"],
    },

    (34, "b"): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "topics": ["reproduction_in_plants", "interactions_within_environment"],
        "scenario_anchors": ["plant Y", "insect M"],
        "chains": [
            {"chain_id": "plant", "keypoints": [
                {"kp_id": "pl_1", "position": 1, "facet": "result",
                 "statement": "carrying pollen to the stigma pollinates plant Y, and "
                              "after fertilisation fruits and seeds develop from the "
                              "ovary, so plant Y can continue to reproduce",
                 "accepts": ["insect M pollinates plant Y so it can make seeds and "
                             "keep going",
                             "pollination then fertilisation lets plant Y produce "
                             "fruits and seeds"]}]},
            {"chain_id": "insect", "keypoints": [
                {"kp_id": "in_1", "position": 1, "facet": "result",
                 "statement": "the young of insect M feed on the seeds of plant Y, so "
                              "insect M gains a food supply",
                 "accepts": ["insect M's young get food from plant Y's seeds",
                             "the plant feeds insect M's offspring"]}]},
        ],
        "traps": ["describing the benefit to only one of the two organisms",
                  "saying insect M 'helps' plant Y without naming pollination"],
    },

    (35, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["evaporation", "heat"],
        "scenario_anchors": ["hand sanitiser", "Ali's hand"],
        "chains": [{
            "chain_id": "evaporate",
            "keypoints": [
                {"kp_id": "evp_1", "position": 1, "facet": "result",
                 "statement": "the liquid sanitiser gains heat from Ali's hand and "
                              "evaporates into a vapour",
                 "accepts": ["it takes heat from his hand and turns into a gas",
                             "it absorbs heat from the skin and evaporates"]},
            ],
        }],
        "traps": ["saying the sanitiser 'dries' without naming evaporation",
                  "saying it loses heat, when it gains heat from the hand"],
    },

    (35, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["evaporation", "heat"],
        "scenario_anchors": ["hand sanitiser", "Ali's hand", "wind"],
        "chains": [{
            "chain_id": "wind",
            "keypoints": [
                {"kp_id": "wnd_1", "position": 1, "facet": "action",
                 "statement": "blowing on his hand creates moving air, and wind speeds "
                              "up the rate of evaporation",
                 "accepts": ["the moving air makes it evaporate faster"]},
                {"kp_id": "wnd_2", "position": 2, "facet": "result",
                 "statement": "so the sanitiser gains heat from his hand more quickly "
                              "and evaporates faster",
                 "accepts": ["more heat is taken from his hand in the same time",
                             "it evaporates faster because it gains heat faster"]},
            ],
        }],
        "traps": ["naming wind without saying what it does to the rate of evaporation",
                  "saying the wind 'cools' the hand directly rather than through "
                  "faster evaporation"],
    },

    (36, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["forces", "energy"],
        "scenario_anchors": ["propeller", "boat"],
        "chains": [{
            "chain_id": "relation",
            "keypoints": [
                {"kp_id": "rel_1", "position": 1, "facet": "result",
                 "statement": "the greater the number of turns of the propeller, the "
                              "further the boat moves",
                 "accepts": ["the more turns, the longer the distance moved"]},
            ],
        }],
        "traps": ["quoting two rows of the table without stating the relationship"],
    },

    (36, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["energy"],
        "scenario_anchors": ["rubber band", "propeller", "boat"],
        "chains": [{
            "chain_id": "conversion",
            "keypoints": [
                {"kp_id": "cnv_1", "position": 1, "facet": "variable",
                 "statement": "the twisted rubber band stores elastic potential energy",
                 "accepts": ["it starts as elastic potential energy in the rubber band"]},
                {"kp_id": "cnv_2", "position": 2, "facet": "result",
                 "statement": "which becomes kinetic energy and sound energy at the "
                              "propeller, and kinetic energy of the boat",
                 "accepts": ["it turns into kinetic energy plus sound energy, and the "
                             "boat's kinetic energy"]},
            ],
        }],
        "traps": ["omitting sound, which can be heard as the propeller turns",
                  "starting from kinetic energy rather than the twisted rubber band"],
    },

    (36, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["experimental_design"],
        "scenario_anchors": ["boat", "bathtub", "20 turns"],
        "chains": [{
            "chain_id": "release",
            "keypoints": [
                {"kp_id": "rls_1", "position": 1, "facet": "result",
                 "statement": "human reaction time makes the moment of release differ "
                              "slightly between tries",
                 "accepts": ["he cannot let go at exactly the same instant each time",
                             "the water could still have been moving when he released "
                             "the boat"]},
            ],
        }],
        "traps": ["naming the number of turns, which was the same for both tries",
                  "saying the result is 'wrong' rather than naming a source of "
                  "variation"],
    },

    (37, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["heat", "measurement"],
        "chains": [{
            "chain_id": "read",
            "keypoints": [
                {"kp_id": "rd_1", "position": 1, "facet": "result",
                 "statement": "30 °C, which is room temperature",
                 "accepts": ["30 degrees Celsius"]},
            ],
        }],
        "traps": ["giving the value without its unit"],
    },

    (37, "b"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["heat", "measurement"],
        "chains": [{
            "chain_id": "read",
            "keypoints": [
                {"kp_id": "rd_1", "position": 1, "facet": "result",
                 "statement": "at time 1 minute", "accepts": ["1 min", "after one minute"]},
            ],
        }],
        "traps": ["giving a temperature where a time is asked for"],
    },

    (37, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["heat", "states_of_matter"],
        "scenario_anchors": ["hot oil", "water pipe", "point X", "sink protector"],
        "chains": [{
            "chain_id": "solidify",
            "keypoints": [
                {"kp_id": "sol_1", "position": 1, "facet": "action",
                 "statement": "the hot oil flows down through the sink protector into "
                              "the water pipe and loses heat to the cooler water there",
                 "accepts": ["the oil gives up heat to the cold water in the pipe"]},
                {"kp_id": "sol_2", "position": 2, "facet": "result",
                 "statement": "the oil cools to its freezing point and changes to a "
                              "solid, and more of it builds up at X over time",
                 "accepts": ["it hardens into a solid and collects at X",
                             "the oil solidifies and blocks the pipe at X"]},
            ],
        }],
        "traps": ["saying the oil 'gets cold' without naming the change of state",
                  "saying it loses energy rather than loses heat"],
    },

    (38, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["electricity", "magnetism"],
        "scenario_anchors": ["switch S", "bulb P", "bulb Q", "point A", "point B",
                             "iron bar", "iron cylinder"],
        "chains": [{
            "chain_id": "flash",
            "keypoints": [
                {"kp_id": "fls_1", "position": 1, "facet": "action",
                 "statement": "closing switch S completes the circuit, so bulbs P and Q "
                              "light and the iron cylinder becomes an electromagnet "
                              "that pulls the iron bar up to point B",
                 "accepts": ["with S closed the current flows, both bulbs light and the "
                             "electromagnet attracts the bar to B"]},
                {"kp_id": "fls_2", "position": 2, "facet": "result",
                 "statement": "at B the current stops flowing through bulb P and the "
                              "cylinder, so P goes out, the cylinder loses its "
                              "magnetism and the bar falls back to A — and the cycle "
                              "repeats, so bulb P flashes on and off",
                 "accepts": ["the bar at B cuts P out of the circuit, the magnet lets "
                             "go, the bar drops back and it all repeats, so P keeps "
                             "flashing"]},
            ],
        }],
        "traps": ["explaining only what happens when the switch is first closed",
                  "omitting why the bar returns to A, which is what makes it repeat"],
    },

    (38, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["electricity"],
        "scenario_anchors": ["bulb P", "bulb Q", "point A"],
        "chains": [{
            "chain_id": "lit",
            "keypoints": [
                {"kp_id": "lit_1", "position": 1, "facet": "result",
                 "statement": "bulbs P and Q", "accepts": ["both bulbs, P and Q"]},
            ],
        }],
        "traps": ["naming only one bulb"],
    },

    (38, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["electricity"],
        "scenario_anchors": ["bulb Q", "point B", "battery"],
        "chains": [{
            "chain_id": "brighter",
            "keypoints": [
                {"kp_id": "brt_1", "position": 1, "facet": "variable",
                 "statement": "with the iron bar at B, bulb Q is the only bulb left in "
                              "the circuit and still receives current from both "
                              "batteries",
                 "accepts": ["at B, bulb P is cut out and Q has both batteries to itself"]},
                {"kp_id": "brt_2", "position": 2, "facet": "result",
                 "statement": "so more current flows through bulb Q and it lights up "
                              "more brightly",
                 "accepts": ["a bigger current goes through Q, so it is brighter"]},
            ],
        }],
        "traps": ["saying Q is brighter without saying what changed in the circuit",
                  "saying the batteries became stronger"],
    },

    # "Use a pencil to complete the circuit below: correct the mistakes, and connect
    # the bulbs so one still lights if the other blows." [3]
    (39, None): {
        "response_mode": "drawn",
        "topics": ["electricity"],
        "scenario_anchors": ["battery", "bulb", "switch", "fixed metal plates"],
        "traps": [],
    },

    (40, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["states_of_matter", "heat"],
        "chains": [{
            "chain_id": "define",
            "keypoints": [
                {"kp_id": "def_1", "position": 1, "facet": "result",
                 "statement": "boiling is when a liquid gains heat and changes to a gas "
                              "at its boiling point",
                 "accepts": ["a liquid turns into a gas at its boiling point as it "
                             "gains heat"]},
            ],
        }],
        "traps": ["describing evaporation, which happens at any temperature and only "
                  "at the surface",
                  "omitting that heat is gained"],
    },

    (40, "b(i)"): {
        "mark_model": "per_keypoint",
        "topics": ["heat"],
        "scenario_anchors": ["part A", "part B", "electric pot", "glass top"],
        "chains": [{
            "chain_id": "nearer",
            "keypoints": [
                {"kp_id": "nr_1", "position": 1, "facet": "result",
                 "statement": "part A is nearer the electric pot, so it gains heat from "
                              "the pot faster than part B does",
                 "accepts": ["A is closer to the pot so it heats up more quickly than B",
                             "heat reaches A sooner because it is nearer the pot"]},
            ],
        }],
        "traps": ["saying A is hotter without saying it is nearer the source",
                  "saying heat 'rises' rather than that it is transferred through the "
                  "glass"],
    },

    (40, "b(ii)"): {
        "mark_model": "per_keypoint",
        "topics": ["heat", "expansion_and_contraction"],
        "scenario_anchors": ["part A", "part B", "glass top"],
        "chains": [{
            "chain_id": "crack",
            "keypoints": [
                {"kp_id": "crk_1", "position": 1, "facet": "result",
                 "statement": "part A gains heat and expands faster than part B, and "
                              "the uneven expansion cracks the glass top",
                 "accepts": ["A expands more than B, and that uneven expansion makes "
                             "the glass crack",
                             "one part expands before the other, so the glass breaks"]},
            ],
        }],
        "traps": ["naming expansion without saying it is uneven between A and B",
                  "saying the glass got 'too hot' with no expansion mentioned"],
    },
}
