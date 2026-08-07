"""Authored rubric chains for the 2021 paper.

Kept as data here rather than edited into rubrics/2021.json by hand so that
re-scaffolding never loses the work and every chain is reviewable in one place.
Apply with:  python build/apply_authored.py --years 2021

Each entry is keyed (question, part). `mark_model` says how marks map onto the
rubric — see build/validate.py. Facets are variable / action / result.

A pre-2023 paper, so it is tagged `pre-2023` by the scaffold and the student can
filter it out. Q29 is on cells, which leaves the syllabus in 2026; it is tagged
`cells` so it shows as out of scope rather than being deleted.

Value-reading sub-parts (Q36(b), Q36(c), Q37(a)) declare context_gate "general".
The gate exists to catch a memorised recital dressed up as an answer, and a
one-word reading off a graph has no scenario language to offer it — gating those
on anchors would zero a correct answer.

These are authored from the EPH suggested answers, which are a publisher's
answers, not the official SEAB marking scheme.
"""

CHAINS: dict[tuple[int, str | None], dict] = {

    (29, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["cells"],
        "scenario_anchors": ["part R", "part S"],
        "chains": [{
            "chain_id": "identify",
            "keypoints": [
                {"kp_id": "id_1", "position": 1, "facet": "result",
                 "statement": "R is the cytoplasm and S is the nucleus",
                 "accepts": ["R is cytoplasm, S is the nucleus"]},
            ],
        }],
        "traps": ["naming only one of the two parts",
                  "swapping the nucleus and the cytoplasm"],
    },

    # Two separate functions, one mark each, so each is its own route rather than
    # two links of one chain.
    (29, "b"): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "topics": ["cells"],
        "scenario_anchors": ["part P", "part Q"],
        "chains": [
            {"chain_id": "wall", "keypoints": [
                {"kp_id": "wall_1", "position": 1, "facet": "result",
                 "statement": "P is the cell wall, which gives the cell a definite "
                              "shape and strength",
                 "accepts": ["P supports the cell / keeps its shape",
                             "the cell wall makes the cell firm"]}]},
            {"chain_id": "membrane", "keypoints": [
                {"kp_id": "mem_1", "position": 1, "facet": "result",
                 "statement": "Q is the cell membrane, which controls the substances "
                              "that enter and leave the cell",
                 "accepts": ["Q decides what goes in and out of the cell",
                             "the cell membrane lets some substances through"]}]},
        ],
        "traps": ["giving a function for only one of P and Q",
                  "saying the membrane 'protects' the cell without saying it "
                  "controls what passes through"],
    },

    (30, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["respiratory_system", "human_system"],
        "chains": [{
            "chain_id": "function",
            "keypoints": [
                {"kp_id": "fun_1", "position": 1, "facet": "result",
                 "statement": "the respiratory system takes oxygen into the body and "
                              "removes carbon dioxide from it",
                 "accepts": ["it brings in oxygen and gets rid of carbon dioxide",
                             "it lets the body take in oxygen and breathe out "
                             "carbon dioxide"]},
            ],
        }],
        "traps": ["naming only the oxygen half and omitting carbon dioxide",
                  "describing breathing movements rather than what they achieve"],
    },

    (30, "b"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["respiratory_system"],
        "chains": [{
            "chain_id": "parts",
            "keypoints": [
                {"kp_id": "prt_1", "position": 1, "facet": "result",
                 "statement": "the nose, the windpipe and the lungs",
                 "accepts": ["nose, trachea, lungs"]},
            ],
        }],
        "traps": ["naming organs of another system, such as the heart"],
    },

    (30, "c"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["respiratory_system", "circulatory_system", "human_system"],
        "chains": [{
            "chain_id": "exchange",
            "keypoints": [
                {"kp_id": "exc_1", "position": 1, "facet": "action",
                 "statement": "oxygen from the air breathed in is absorbed into the "
                              "bloodstream at the lungs",
                 "accepts": ["the lungs pass oxygen into the blood",
                             "oxygen goes from the lungs into the blood"]},
                {"kp_id": "exc_2", "position": 2, "facet": "result",
                 "statement": "the blood carries that oxygen to all parts of the body "
                              "for respiration, and carries the carbon dioxide "
                              "produced back to the lungs to be breathed out",
                 "accepts": ["the blood delivers oxygen round the body and brings "
                             "carbon dioxide back to the lungs"]},
            ],
        }],
        "traps": ["describing the two systems separately without connecting them",
                  "stopping at the lungs and never saying where the oxygen goes"],
    },

    (31, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["digestive_system"],
        "scenario_anchors": ["part Q", "part R"],
        "chains": [{
            "chain_id": "digest",
            "keypoints": [
                {"kp_id": "dig_1", "position": 1, "facet": "result",
                 "statement": "between part Q and part R the small intestine digests "
                              "more of the food into sugar, so the amount of sugar "
                              "increases",
                 "accepts": ["more starch is broken down into sugar between Q and R",
                             "digestive juice at Q turns more food into sugar by R"]},
            ],
        }],
        "traps": ["saying the sugar increases without naming digestion as the cause",
                  "answering about the stomach, where starch is not digested"],
    },

    (31, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["digestive_system", "circulatory_system"],
        "scenario_anchors": ["part R", "part S"],
        "chains": [{
            "chain_id": "absorb",
            "keypoints": [
                {"kp_id": "abs_1", "position": 1, "facet": "result",
                 "statement": "between part R and part S the small intestine absorbs "
                              "the sugar into the bloodstream, so the amount of sugar "
                              "left in the food decreases",
                 "accepts": ["the sugar is absorbed into the blood, so less is left",
                             "sugar passes out of the small intestine into the blood"]},
            ],
        }],
        "traps": ["saying the sugar is 'used up' rather than absorbed",
                  "naming absorption without saying the sugar amount falls"],
    },

    (31, "c"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["digestive_system"],
        "chains": [{
            "chain_id": "large",
            "keypoints": [
                {"kp_id": "lrg_1", "position": 1, "facet": "result",
                 "statement": "the large intestine, which absorbs water from the "
                              "undigested food",
                 "accepts": ["large intestine — it takes water out of what is left"]},
            ],
        }],
        "traps": ["naming the organ without stating its function",
                  "saying it digests food — digestion is finished by then"],
    },

    # Two trends in one data set: the number rises to 28 °C and falls after it. Each
    # is a mark in its own right, so they are parallel routes, not one split point.
    (32, "a"): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "topics": ["life_cycles", "interactions_within_environment"],
        "scenario_anchors": ["22 °C", "28 °C", "38 °C"],
        "chains": [
            {"chain_id": "rise", "keypoints": [
                {"kp_id": "rise_1", "position": 1, "facet": "result",
                 "statement": "as the temperature rises from 22 °C to 28 °C, more "
                              "mosquito eggs hatch",
                 "accepts": ["between 22 °C and 28 °C the number hatching goes up"]}]},
            {"chain_id": "fall", "keypoints": [
                {"kp_id": "fall_1", "position": 1, "facet": "result",
                 "statement": "as the temperature rises further to 38 °C, fewer "
                              "mosquito eggs hatch",
                 "accepts": ["above 28 °C the number hatching drops again",
                             "at 38 °C very few eggs hatch"]}]},
        ],
        "traps": ["giving only 'the hotter it is the more eggs hatch' and missing "
                  "that the trend reverses",
                  "quoting the numbers without saying what they show"],
    },

    (32, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["floating_and_sinking", "materials"],
        "scenario_anchors": ["ball", "well"],
        "chains": [{
            "chain_id": "float",
            "keypoints": [
                {"kp_id": "flt_1", "position": 1, "facet": "result",
                 "statement": "the balls float on water",
                 "accepts": ["they stay on the surface of the water",
                             "they are less dense than water so they float"]},
            ],
        }],
        "traps": ["describing the balls' colour or size, which the diagram does not "
                  "put to the test",
                  "saying they are 'light' rather than that they float"],
    },

    (32, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["life_cycles", "interactions_within_environment"],
        "scenario_anchors": ["ball", "well"],
        "chains": [{
            "chain_id": "cover",
            "keypoints": [
                {"kp_id": "cov_1", "position": 1, "facet": "result",
                 "statement": "the layer of balls covers the water surface, so adult "
                              "mosquitoes cannot reach the water to lay their eggs",
                 "accepts": ["mosquitoes cannot get to the water to lay eggs",
                             "the balls block the surface so larvae cannot reach the "
                             "air to breathe through their breathing tubes",
                             "larvae cannot breathe because the surface is covered"]},
            ],
        }],
        "traps": ["saying the balls 'kill' the mosquitoes",
                  "stating that fewer mosquitoes breed without saying what the "
                  "balls physically prevent"],
    },

    (33, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["life_cycles"],
        "chains": [{
            "chain_id": "feeding",
            "keypoints": [
                {"kp_id": "fed_1", "position": 1, "facet": "result",
                 "statement": "a larva takes in food and water but a pupa does not",
                 "accepts": ["the pupa does not feed while the larva does",
                             "larvae eat, pupae do not"]},
            ],
        }],
        "traps": ["describing only the pupa without comparing it with the larva",
                  "saying they 'look different' rather than naming a difference"],
    },

    (33, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["evaporation", "life_cycles"],
        "scenario_anchors": ["nectar", "honey"],
        "chains": [{
            "chain_id": "evaporate",
            "keypoints": [
                {"kp_id": "evp_1", "position": 1, "facet": "action",
                 "statement": "beating its wings makes air move over the nectar, "
                              "which speeds up the evaporation of the water in it",
                 "accepts": ["fanning makes the water in the nectar evaporate faster",
                             "the moving air increases the rate of evaporation"]},
                {"kp_id": "evp_2", "position": 2, "facet": "result",
                 "statement": "the amount of water in the nectar falls until it is "
                              "much lower than the amount of sugar, and honey is formed",
                 "accepts": ["once enough water has gone, what is left is honey",
                             "the nectar becomes concentrated enough to be honey"]},
            ],
        }],
        "traps": ["saying the nectar 'dries up' with no mention of evaporation",
                  "naming evaporation but never reaching the formation of honey"],
    },

    (33, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["heredity"],
        "scenario_anchors": ["bee T", "bee K"],
        "chains": [{
            "chain_id": "inherit",
            "keypoints": [
                {"kp_id": "inh_1", "position": 1, "facet": "result",
                 "statement": "the offspring inherit characteristics from both parents, "
                              "so they take the fierce behaviour towards humans from "
                              "bee T even though bee K does not have it",
                 "accepts": ["the young get characteristics from both bee T and bee K",
                             "the fierceness was passed down from bee T"]},
            ],
        }],
        "traps": ["saying the offspring 'learnt' the behaviour rather than inherited it",
                  "naming only one parent as the source of every characteristic"],
    },

    (34, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["photosynthesis"],
        "scenario_anchors": ["liquid Y", "leaf disc"],
        "chains": [{
            "chain_id": "float",
            "keypoints": [
                {"kp_id": "pho_1", "position": 1, "facet": "result",
                 "statement": "the leaf disc photosynthesises, and the oxygen bubbles "
                              "it produces carry it up to the surface of liquid Y",
                 "accepts": ["oxygen made during photosynthesis makes the disc rise",
                             "the disc floats up because photosynthesis produces "
                             "oxygen bubbles"]},
            ],
        }],
        "traps": ["naming photosynthesis without saying what makes the disc rise",
                  "saying the disc 'gets lighter' with no gas named"],
    },

    # Two independent fair-test improvements, one mark each.
    (34, "b"): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "topics": ["experimental_design", "photosynthesis"],
        "scenario_anchors": ["leaf disc", "liquid Y"],
        "chains": [
            {"chain_id": "repeat", "keypoints": [
                {"kp_id": "rep_1", "position": 1, "facet": "action",
                 "statement": "repeat the experiment more than once and compare, to "
                              "check the results are consistent",
                 "accepts": ["do it two more times and see if the results agree",
                             "repeat and take an average"]}]},
            {"chain_id": "same_leaf", "keypoints": [
                {"kp_id": "sam_1", "position": 1, "facet": "action",
                 "statement": "cut all the leaf discs from the same leaf so that each "
                              "disc has a similar number of tiny openings",
                 "accepts": ["use discs from one leaf so they have the same number of "
                             "stomata",
                             "take every disc from the same leaf"]}]},
        ],
        "traps": ["offering only one improvement when two are asked for",
                  "saying 'be more accurate' without naming what to change"],
    },

    (34, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["photosynthesis"],
        "scenario_anchors": ["liquid Y"],
        "chains": [{
            "chain_id": "gas",
            "keypoints": [
                {"kp_id": "gas_1", "position": 1, "facet": "result",
                 "statement": "carbon dioxide — liquid Y contains more of it than the "
                              "water does, so more photosynthesis takes place",
                 "accepts": ["carbon dioxide", "there is more carbon dioxide in "
                             "liquid Y than in the water"]},
            ],
        }],
        "traps": ["naming oxygen, which is the gas produced rather than the one used"],
    },

    (35, None): {
        "mark_model": "per_keypoint",
        "topics": ["condensation", "heat"],
        "scenario_anchors": ["mask", "spectacles"],
        "chains": [{
            "chain_id": "fog",
            "keypoints": [
                {"kp_id": "fog_1", "position": 1, "facet": "action",
                 "statement": "the warm water vapour in his breath escapes through the "
                              "gap at the top of the mask and reaches the cooler "
                              "surface of the spectacles",
                 "accepts": ["his warm breath goes up out of the mask onto the lenses",
                             "water vapour from his breath meets the cold lens"]},
                {"kp_id": "fog_2", "position": 2, "facet": "result",
                 "statement": "the water vapour loses heat to the cooler lens and "
                              "condenses into tiny water droplets on it",
                 "accepts": ["it cools down and condenses into little drops of water",
                             "the vapour gives up heat and turns back into water on "
                             "the lens"]},
            ],
        }],
        "traps": ["saying the spectacles get 'wet' without naming condensation",
                  "saying the vapour 'loses energy' rather than loses heat",
                  "omitting that the lens surface is cooler than the breath"],
    },

    (36, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["heat", "measurement"],
        "chains": [{
            "chain_id": "define",
            "keypoints": [
                {"kp_id": "def_1", "position": 1, "facet": "result",
                 "statement": "temperature is a measure of how hot an object is",
                 "accepts": ["it tells you how hot or cold something is"]},
            ],
        }],
        "traps": ["defining temperature as heat — they are not the same thing"],
    },

    (36, "b"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["heat", "measurement"],
        "chains": [{
            "chain_id": "read",
            "keypoints": [
                {"kp_id": "rd_1", "position": 1, "facet": "result",
                 "statement": "30 °C", "accepts": ["30 degrees Celsius"]},
            ],
        }],
        "traps": ["giving the value without its unit"],
    },

    (36, "c"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["heat", "measurement"],
        "chains": [{
            "chain_id": "read",
            "keypoints": [
                {"kp_id": "rd_1", "position": 1, "facet": "result",
                 "statement": "10 minutes", "accepts": ["10 min", "at ten minutes"]},
            ],
        }],
        "traps": ["giving the value without its unit"],
    },

    (36, "d"): {
        "mark_model": "per_keypoint",
        "topics": ["heat", "expansion_and_contraction"],
        "scenario_anchors": ["bubble"],
        "chains": [{
            "chain_id": "expand",
            "keypoints": [
                {"kp_id": "exp_1", "position": 1, "facet": "result",
                 "statement": "the gas trapped in the bubble gained heat from the sun "
                              "and expanded",
                 "accepts": ["the air inside got hotter and took up more space",
                             "the gas absorbed heat and expanded"]},
            ],
        }],
        "traps": ["saying the gas 'rose' rather than expanded",
                  "naming expansion without saying the gas gained heat"],
    },

    (37, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["sound", "measurement"],
        "chains": [{
            "chain_id": "read",
            "keypoints": [
                {"kp_id": "rd_1", "position": 1, "facet": "result",
                 "statement": "3", "accepts": ["three"]},
            ],
        }],
        "traps": ["counting peaks that are background sound rather than droplets"],
    },

    (37, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["sound", "experimental_design"],
        "scenario_anchors": ["sound sensor", "plate"],
        "chains": [{
            "chain_id": "background",
            "keypoints": [
                {"kp_id": "bg_1", "position": 1, "facet": "result",
                 "statement": "the sound sensor was picking up background sound from "
                              "the surroundings, such as the power supply connected "
                              "to it",
                 "accepts": ["it detected noise from other things nearby",
                             "there is background noise in the room the sensor picks up"]},
            ],
        }],
        "traps": ["attributing the reading to droplets hitting the plate, when the "
                  "level is the same as before the first drop fell"],
    },

    (37, "c"): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "topics": ["sound", "energy", "experimental_design"],
        "scenario_anchors": ["sound sensor", "plate", "pail"],
        "chains": [
            {"chain_id": "nearer", "keypoints": [
                {"kp_id": "nr_1", "position": 1, "facet": "action",
                 "statement": "move the sound sensor nearer to the plate so it picks "
                              "up more of the sound made",
                 "accepts": ["put the sensor closer to the plate"]}]},
            {"chain_id": "higher", "keypoints": [
                {"kp_id": "hi_1", "position": 1, "facet": "action",
                 "statement": "raise the pail higher above the plate, so each droplet "
                              "hits with greater impact and makes a louder sound",
                 "accepts": ["increase the height of the pail from the plate",
                             "drop the water from higher up so the sound is louder"]}]},
        ],
        "traps": ["offering only one change when two are asked for",
                  "suggesting a louder sound source rather than changing the set-up"],
    },

    (38, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["magnetism", "electricity"],
        "scenario_anchors": ["metal bar", "metal cylinder"],
        "chains": [{
            "chain_id": "not_magnet",
            "keypoints": [
                {"kp_id": "nm_1", "position": 1, "facet": "result",
                 "statement": "no — the bar is attracted only while current flows and "
                              "the cylinder is an electromagnet; a magnet would be "
                              "attracted at all times",
                 "accepts": ["no, because it is only pulled when the current is on",
                             "if it were a magnet it would be attracted even with the "
                             "switch open"]},
            ],
        }],
        "traps": ["answering 'no' with no reason",
                  "saying the bar is made of iron without addressing when it is "
                  "attracted"],
    },

    (38, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["magnetism", "electricity", "forces"],
        "scenario_anchors": ["switch A", "iron rod", "metal cylinder", "spring",
                             "carrot"],
        "chains": [{
            "chain_id": "cycle",
            "keypoints": [
                {"kp_id": "cyc_1", "position": 1, "facet": "action",
                 "statement": "when switch A is closed the metal cylinder becomes an "
                              "electromagnet and attracts the iron rod, compressing "
                              "the spring",
                 "accepts": ["closing the switch makes the cylinder magnetic and pulls "
                             "the rod down, squashing the spring"]},
                {"kp_id": "cyc_2", "position": 2, "facet": "result",
                 "statement": "when switch A is opened the cylinder loses its "
                              "magnetism, so the compressed spring pushes the rod back "
                              "up and the carrot rises above the hole",
                 "accepts": ["opening the switch stops the attraction and the spring "
                             "pushes the carrot up"]},
            ],
        }],
        "traps": ["describing only the switch-closed half of the cycle",
                  "saying the spring 'lets go' without naming the pushing force"],
    },

    (38, "c"): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "topics": ["magnetism", "electricity"],
        "scenario_anchors": ["metal cylinder", "iron rod"],
        "chains": [
            {"chain_id": "turns", "keypoints": [
                {"kp_id": "trn_1", "position": 1, "facet": "action",
                 "statement": "increase the number of turns of wire around the metal "
                              "cylinder, so the electromagnet pulls on the iron rod "
                              "more strongly",
                 "accepts": ["wind more coils of wire around the cylinder"]}]},
            {"chain_id": "batteries", "keypoints": [
                {"kp_id": "bat_1", "position": 1, "facet": "action",
                 "statement": "increase the number of batteries in the circuit, so the "
                              "electromagnet pulls on the iron rod more strongly",
                 "accepts": ["add more batteries", "use a bigger current"]}]},
        ],
        "traps": ["offering only one change when two are asked for",
                  "suggesting a bigger cylinder, which does not change the current"],
    },

    (39, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["measurement", "experimental_design"],
        "scenario_anchors": ["coin bank", "measuring cylinder"],
        "chains": [{
            "chain_id": "displace",
            "keypoints": [
                {"kp_id": "dis_1", "position": 1, "facet": "action",
                 "statement": "fill the empty coin bank completely with water, then "
                              "pour that water into a measuring cylinder",
                 "accepts": ["fill it to the top with water and tip the water into a "
                             "measuring cylinder"]},
                {"kp_id": "dis_2", "position": 2, "facet": "result",
                 "statement": "the volume of water measured is the volume of the space "
                              "inside the coin bank",
                 "accepts": ["read the volume — that is the space inside the bank"]},
            ],
        }],
        "traps": ["describing the pouring without saying what the reading tells you",
                  "measuring the outside of the bank rather than the space inside it"],
    },

    (39, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["measurement", "materials"],
        "scenario_anchors": ["coin bank", "coin"],
        "chains": [{
            "chain_id": "gaps",
            "keypoints": [
                {"kp_id": "gap_1", "position": 1, "facet": "result",
                 "statement": "the coins are round, so gaps are left between them when "
                              "they are packed together, and those gaps take up part "
                              "of the space inside the bank",
                 "accepts": ["there are spaces between the round coins that waste some "
                             "of the room",
                             "circular coins cannot pack without leaving gaps"]},
            ],
        }],
        "traps": ["saying the coins are 'too big' rather than that gaps remain",
                  "noting the gaps without saying they use up part of the volume"],
    },

    (40, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["forces", "energy"],
        "scenario_anchors": ["spring", "rocket"],
        "chains": [{
            "chain_id": "relation",
            "keypoints": [
                {"kp_id": "rel_1", "position": 1, "facet": "result",
                 "statement": "the greater the compression of the spring, the greater "
                              "the distance moved by the rocket",
                 "accepts": ["the more the spring is squashed, the further the rocket "
                             "goes"]},
            ],
        }],
        "traps": ["quoting two rows of the table without stating the relationship",
                  "saying the rocket goes 'further' without saying what was changed"],
    },

    (40, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["forces"],
        "scenario_anchors": ["point G", "rocket", "ramp"],
        "chains": [{
            "chain_id": "forces",
            "keypoints": [
                {"kp_id": "frc_1", "position": 1, "facet": "result",
                 "statement": "gravitational force and frictional force",
                 "accepts": ["gravity and friction",
                             "its weight and the friction with the ramp"]},
            ],
        }],
        "traps": ["including the spring's push, which no longer acts once the rocket "
                  "has left the spring",
                  "naming only one of the two forces"],
    },

    (40, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["energy"],
        "scenario_anchors": ["point H", "rocket"],
        "chains": [{
            "chain_id": "energy",
            "keypoints": [
                {"kp_id": "eng_1", "position": 1, "facet": "result",
                 "statement": "kinetic energy and gravitational potential energy",
                 "accepts": ["it is moving so it has kinetic energy, and it is high up "
                             "so it has gravitational potential energy"]},
            ],
        }],
        "traps": ["naming elastic potential energy, which was spent at the launch",
                  "naming only one of the two forms"],
    },

    (40, "d"): {
        "mark_model": "per_keypoint",
        "topics": ["experimental_design", "measurement"],
        "scenario_anchors": ["sand pit", "rocket"],
        "chains": [{
            "chain_id": "mark",
            "keypoints": [
                {"kp_id": "mrk_1", "position": 1, "facet": "result",
                 "statement": "the rocket makes a dent where it lands in the sand, "
                              "giving a clear mark from which the distance can be "
                              "measured",
                 "accepts": ["it leaves a mark in the sand so you know exactly where "
                             "it landed",
                             "on a hard floor it would slide or bounce, but the sand "
                             "records the landing point"]},
            ],
        }],
        "traps": ["saying the sand is 'softer' without saying what that lets him "
                  "measure",
                  "saying the result is 'more accurate' with no mechanism"],
    },
}
