"""Authored rubric chains for the 2022 paper.

Kept as data here rather than edited into rubrics/2022.json by hand so that
re-scaffolding never loses the work and every chain is reviewable in one place.
Apply with:  python build/apply_authored.py --years 2022

Each entry is keyed (question, part). `mark_model` says how marks map onto the
rubric — see build/validate.py. Facets are variable / action / result.

Two sub-parts are answered by drawing on the paper and are marked
response_mode "drawn": Q37(c) asks for a curved line showing the toy's new path,
and Q39(b) for a completed parallel circuit. Neither can be spoken or graded from
a transcript, so they carry no chains rather than sitting in the queue looking
like missing work.

Three model answers reached this file badly damaged by the scan and were authored
from the question page instead: Q32(a) ("Wastes contain water and from."),
Q33(a) ("The water. hen teres were tubes carry water...") and Q30(c), whose two
halves only make sense against the blood-flow diagram on page 2.

These are authored from the EPH suggested answers, which are a publisher's
answers, not the official SEAB marking scheme.
"""

CHAINS: dict[tuple[int, str | None], dict] = {

    (29, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["human_impact", "interactions_within_environment"],
        "chains": [{
            "chain_id": "define",
            "keypoints": [
                {"kp_id": "def_1", "position": 1, "facet": "result",
                 "statement": "deforestation is the clearing or destruction of large "
                              "areas of forest",
                 "accepts": ["cutting down large areas of trees / forest"]},
            ],
        }],
        "traps": ["describing an effect of deforestation instead of saying what it is"],
    },

    (29, "b"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["human_impact", "photosynthesis",
                   "interactions_within_environment"],
        "chains": [{
            "chain_id": "gases",
            "keypoints": [
                {"kp_id": "gas_1", "position": 1, "facet": "action",
                 "statement": "after deforestation there are fewer trees left to carry "
                              "out photosynthesis",
                 "accepts": ["fewer trees means less photosynthesis takes place"]},
                {"kp_id": "gas_2", "position": 2, "facet": "result",
                 "statement": "less carbon dioxide is taken in and less oxygen given "
                              "out, so carbon dioxide in the air increases and oxygen "
                              "decreases",
                 "accepts": ["there is more carbon dioxide and less oxygen in the air",
                             "carbon dioxide builds up because fewer trees absorb it"]},
            ],
        }],
        "traps": ["naming the change in the gases without saying photosynthesis is "
                  "what falls",
                  "mentioning only carbon dioxide and omitting oxygen"],
    },

    (30, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["digestive_system"],
        "chains": [{
            "chain_id": "define",
            "keypoints": [
                {"kp_id": "def_1", "position": 1, "facet": "result",
                 "statement": "digestion is the breaking down of food into simpler "
                              "substances the body can absorb",
                 "accepts": ["food is broken down into simpler substances"]},
            ],
        }],
        "traps": ["describing chewing only — that is one step, not what digestion is",
                  "saying food is 'made smaller' without saying into what"],
    },

    (30, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["digestive_system"],
        "scenario_anchors": ["organ J", "organ K"],
        "chains": [{
            "chain_id": "identify",
            "keypoints": [
                {"kp_id": "id_1", "position": 1, "facet": "result",
                 "statement": "J is the large intestine and K is the mouth",
                 "accepts": ["J: large intestine, K: mouth"]},
            ],
        }],
        "traps": ["swapping J and K",
                  "naming the small intestine for J, which does not chew or absorb "
                  "water in the way the table shows"],
    },

    (30, "c(i)"): {
        "mark_model": "per_keypoint",
        "topics": ["digestive_system", "circulatory_system"],
        "scenario_anchors": ["P", "Q", "small intestine"],
        "chains": [{
            "chain_id": "absorbed",
            "keypoints": [
                {"kp_id": "abs_1", "position": 1, "facet": "result",
                 "statement": "digested food and carbon dioxide",
                 "accepts": ["digested food / nutrients and carbon dioxide"]},
            ],
        }],
        "traps": ["naming oxygen, which is higher at P than at Q",
                  "naming only one substance when two are asked for"],
    },

    (30, "c(ii)"): {
        "mark_model": "per_keypoint",
        "topics": ["circulatory_system", "respiration"],
        "scenario_anchors": ["P", "Q", "small intestine"],
        "chains": [{
            "chain_id": "delivered",
            "keypoints": [
                {"kp_id": "del_1", "position": 1, "facet": "result",
                 "statement": "oxygen", "accepts": ["oxygen gas"]},
            ],
        }],
        "traps": ["naming carbon dioxide, which is higher at Q than at P"],
    },

    (31, "a(i)"): {
        "mark_model": "per_keypoint",
        "topics": ["bacteria", "experimental_design"],
        "scenario_anchors": ["liquid T", "soap"],
        "chains": [{
            "chain_id": "conclude",
            "keypoints": [
                {"kp_id": "con_1", "position": 1, "facet": "result",
                 "statement": "liquid T is more effective than soap at killing bacteria",
                 "accepts": ["liquid T kills more bacteria than soap does"]},
            ],
        }],
        "traps": ["saying liquid T is 'better' without saying at what",
                  "stating the conclusion the wrong way round"],
    },

    (31, "a(ii)"): {
        "mark_model": "per_keypoint",
        "topics": ["bacteria", "experimental_design"],
        "scenario_anchors": ["liquid T", "soap", "3 minutes", "1 hour"],
        "chains": [{
            "chain_id": "evidence",
            "keypoints": [
                {"kp_id": "ev_1", "position": 1, "facet": "variable",
                 "statement": "3 minutes after cleaning, the number of bacteria left "
                              "after liquid T was smaller than after soap",
                 "accepts": ["at 3 minutes liquid T had fewer bacteria than soap"]},
                {"kp_id": "ev_2", "position": 2, "facet": "result",
                 "statement": "and after 1 hour the number after liquid T had risen "
                              "only slightly while the number after soap had more than "
                              "doubled",
                 "accepts": ["after an hour the soap count grew much more than the "
                             "liquid T count",
                             "liquid T kept the bacteria down for longer"]},
            ],
        }],
        "traps": ["repeating the conclusion instead of citing the readings",
                  "using only the 3-minute figures and ignoring what happens by 1 hour"],
    },

    (31, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["experimental_design"],
        "scenario_anchors": ["thumb", "liquid T", "soap"],
        "chains": [{
            "chain_id": "fair",
            "keypoints": [
                {"kp_id": "fair_1", "position": 1, "facet": "result",
                 "statement": "using the same thumb keeps the surface area exposed to "
                              "the bacteria the same each time",
                 "accepts": ["the same thumb means the same area of skin every time",
                             "it keeps the surface area constant"]},
            ],
        }],
        "traps": ["saying it makes the test 'fair' without naming what is kept the same",
                  "naming a variable the thumb does not control, such as the liquid used"],
    },

    # The scan renders this answer as "Wastes contain water and from." The question
    # asks why mosquitoes lay eggs on waste, and the answer is authored from it.
    (32, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["life_cycles", "interactions_within_environment"],
        "scenario_anchors": ["waste", "toilet"],
        "chains": [{
            "chain_id": "water",
            "keypoints": [
                {"kp_id": "wat_1", "position": 1, "facet": "result",
                 "statement": "the waste contains the water that mosquito larvae need "
                              "to hatch and develop in, and food for them",
                 "accepts": ["there is water in the waste for the eggs to hatch in",
                             "the larvae need water and food, and the waste has both"]},
            ],
        }],
        "traps": ["saying the waste is 'dirty' without naming water",
                  "describing adult mosquitoes' needs rather than the larvae's"],
    },

    (32, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["bacteria", "interactions_within_environment"],
        "scenario_anchors": ["waste"],
        "chains": [{
            "chain_id": "decompose",
            "keypoints": [
                {"kp_id": "dec_1", "position": 1, "facet": "result",
                 "statement": "bacteria, by the process of decomposition",
                 "accepts": ["bacteria — they decompose the waste",
                             "decomposers such as bacteria, through decomposition"]},
            ],
        }],
        "traps": ["naming the group without naming the process, or the other way round",
                  "naming mosquitoes, which are attracted by the gases rather than "
                  "producing them"],
    },

    (32, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["life_cycles", "interactions_within_environment"],
        "scenario_anchors": ["equipment X", "opening", "waste"],
        "chains": [{
            "chain_id": "attract",
            "keypoints": [
                {"kp_id": "att_1", "position": 1, "facet": "result",
                 "statement": "the gases from the waste attracted the mosquitoes to the "
                              "opening, because they use them to find somewhere to lay "
                              "their eggs",
                 "accepts": ["the mosquitoes follow the smell of the gases to the waste",
                             "the gases make the mosquitoes think there is waste to lay "
                             "eggs on"]},
            ],
        }],
        "traps": ["saying the mosquitoes were 'trapped' — that is what happens next, "
                  "not why they came"],
    },

    (32, "d"): {
        "mark_model": "per_keypoint",
        "topics": ["survival_of_the_species", "interactions_within_environment"],
        "scenario_anchors": ["clear plastic dome", "equipment X"],
        "chains": [{
            "chain_id": "starve",
            "keypoints": [
                {"kp_id": "stv_1", "position": 1, "facet": "result",
                 "statement": "there is no food or water inside the clear plastic dome "
                              "for the mosquitoes to survive on",
                 "accepts": ["they have nothing to eat or drink in the dome",
                             "the dome has no food and no water"]},
            ],
        }],
        "traps": ["saying they die of heat when the question points to the dome's "
                  "contents",
                  "naming only food or only water"],
    },

    # OCR leaves this as "The water. hen teres were tubes carry water from the roots
    # up the stem..." The question asks for the part stained red and its function.
    (33, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["plant_transport", "plant_system"],
        "scenario_anchors": ["stem", "red coloured water"],
        "chains": [{
            "chain_id": "tubes",
            "keypoints": [
                {"kp_id": "tub_1", "position": 1, "facet": "result",
                 "statement": "the water-carrying tubes, which carry water and mineral "
                              "salts from the roots up the stem to the rest of the plant",
                 "accepts": ["the water-carrying tubes — they transport water up the "
                             "plant",
                             "the tubes that carry water and minerals from the roots "
                             "to the leaves"]},
            ],
        }],
        "traps": ["naming the part without stating its function, when both are asked for",
                  "naming the food-carrying tubes, which carry sugar rather than water"],
    },

    (33, "b(i)"): {
        "mark_model": "per_keypoint",
        "topics": ["experimental_design", "plant_transport"],
        "scenario_anchors": ["beaker", "stem", "red coloured water"],
        "chains": [{
            "chain_id": "variable",
            "keypoints": [
                {"kp_id": "var_1", "position": 1, "facet": "variable",
                 "statement": "the temperature of the water in the beakers",
                 "accepts": ["how hot the water in each beaker is"]},
            ],
        }],
        "traps": ["naming something he should keep the same instead of change",
                  "naming what he should measure rather than what he changes"],
    },

    (33, "b(ii)"): {
        "mark_model": "per_keypoint",
        "topics": ["experimental_design", "plant_transport"],
        "scenario_anchors": ["beaker", "stem", "red coloured water"],
        "chains": [{
            "chain_id": "measure",
            "keypoints": [
                {"kp_id": "mea_1", "position": 1, "facet": "action",
                 "statement": "the time taken for the water-carrying tubes in each stem "
                              "to be stained red",
                 "accepts": ["how long the stem takes to turn red",
                             "time for the red colour to reach the top of the stem"]},
            ],
        }],
        "traps": ["naming the variable he changes rather than what he measures",
                  "saying 'the colour' without saying he times how long it takes"],
    },

    (34, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["photosynthesis", "plant_system"],
        "scenario_anchors": ["plant P", "openings"],
        "chains": [{
            "chain_id": "openings",
            "keypoints": [
                {"kp_id": "opn_1", "position": 1, "facet": "variable",
                 "statement": "as the temperature rises the average size of the openings "
                              "on the underside of the leaves increases",
                 "accepts": ["the warmer it gets, the wider the openings become"]},
                {"kp_id": "opn_2", "position": 2, "facet": "result",
                 "statement": "so plant P can take in more carbon dioxide and "
                              "photosynthesise faster",
                 "accepts": ["more carbon dioxide gets in, so the rate of "
                             "photosynthesis goes up"]},
            ],
        }],
        "traps": ["linking temperature straight to photosynthesis without the openings "
                  "in between",
                  "saying the plant 'grows better' rather than naming photosynthesis"],
    },

    # Any two of light, water and carbon dioxide earn the marks, so each route
    # accepts the others — the mark is for naming a second distinct factor, not for
    # naming a particular one.
    (34, "b"): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "topics": ["experimental_design", "photosynthesis"],
        "scenario_anchors": ["plant P"],
        "chains": [
            {"chain_id": "factor_one", "keypoints": [
                {"kp_id": "f1_1", "position": 1, "facet": "variable",
                 "statement": "the amount or brightness of the light the plant is "
                              "exposed to",
                 "accepts": ["how much light the plant gets",
                             "the amount of water the plant gets",
                             "the amount of carbon dioxide in the air around it"]}]},
            {"chain_id": "factor_two", "keypoints": [
                {"kp_id": "f2_1", "position": 1, "facet": "variable",
                 "statement": "the amount of water the plant gets",
                 "accepts": ["how much water it is given",
                             "the amount of carbon dioxide in the air around it",
                             "the amount or brightness of the light"]}]},
        ],
        "traps": ["naming only one factor when two are asked for",
                  "naming temperature, which is the variable being investigated"],
    },

    (35, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["forces", "measurement"],
        "chains": [{
            "chain_id": "read",
            "keypoints": [
                {"kp_id": "rd_1", "position": 1, "facet": "result",
                 "statement": "400 g", "accepts": ["400 grams"]},
            ],
        }],
        "traps": ["giving the value without its unit"],
    },

    (35, "b"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["forces", "measurement"],
        "chains": [{
            "chain_id": "read",
            "keypoints": [
                {"kp_id": "rd_1", "position": 1, "facet": "result",
                 "statement": "2 cm, the difference between 62 cm and 60 cm",
                 "accepts": ["2 cm", "it stretched by two centimetres"]},
            ],
        }],
        "traps": ["giving the final length rather than the extension",
                  "giving the value without its unit"],
    },

    (35, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["experimental_design", "forces"],
        "scenario_anchors": ["string R", "string S", "60 cm", "61 cm"],
        "chains": [{
            "chain_id": "lengths",
            "keypoints": [
                {"kp_id": "len_1", "position": 1, "facet": "result",
                 "statement": "strings R and S did not start at the same length — one "
                              "was 60 cm and the other 61 cm",
                 "accepts": ["their original lengths were different",
                             "R started at 60 cm but S started at 61 cm"]},
            ],
        }],
        "traps": ["naming a difference the table does not show, such as thickness",
                  "saying they are 'not the same' without saying in what"],
    },

    (35, "d"): {
        "mark_model": "per_keypoint",
        "topics": ["forces", "materials"],
        "scenario_anchors": ["string S", "800 g"],
        "chains": [{
            "chain_id": "broke",
            "keypoints": [
                {"kp_id": "brk_1", "position": 1, "facet": "result",
                 "statement": "string S broke when a mass beyond 800 g was hung on it",
                 "accepts": ["it snapped once more than 800 g was added",
                             "the load went past what string S could hold"]},
            ],
        }],
        "traps": ["saying the string 'stretched too much' without saying it broke",
                  "omitting the load at which it happened"],
    },

    (36, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["electricity", "magnetism", "sound"],
        "scenario_anchors": ["AB", "CD", "iron bar PQ", "bell", "metal nail"],
        "chains": [{
            "chain_id": "bell",
            "keypoints": [
                {"kp_id": "bel_1", "position": 1, "facet": "action",
                 "statement": "with the switch closed, current flows and AB and CD "
                              "become electromagnets that attract iron bar PQ, so its "
                              "hammer strikes the bell",
                 "accepts": ["the coils become magnetic and pull PQ across to hit the "
                             "bell"]},
                {"kp_id": "bel_2", "position": 2, "facet": "result",
                 "statement": "moving away breaks PQ's contact with the metal nail, so "
                              "the current stops, the electromagnets lose their "
                              "magnetism and PQ springs back — and the cycle repeats, "
                              "giving a continuous ringing",
                 "accepts": ["the circuit is broken, the magnet lets go, PQ returns and "
                             "it all happens again and again",
                             "the contact keeps making and breaking, so it rings over "
                             "and over"]},
            ],
        }],
        "traps": ["explaining one strike and never saying why the sound repeats",
                  "omitting that PQ leaving the nail is what breaks the circuit"],
    },

    (36, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["forces", "sound", "electricity"],
        "scenario_anchors": ["iron bar PQ", "bell", "spring"],
        "chains": [{
            "chain_id": "softer",
            "keypoints": [
                {"kp_id": "sof_1", "position": 1, "facet": "action",
                 "statement": "the stronger spring pushes back on PQ with a larger "
                              "force, so PQ strikes the bell with a smaller force",
                 "accepts": ["the stiffer spring resists more, so PQ hits the bell less "
                             "hard"]},
                {"kp_id": "sof_2", "position": 2, "facet": "result",
                 "statement": "so the sound produced is softer",
                 "accepts": ["the ting is quieter", "the bell sounds softer"]},
            ],
        }],
        "traps": ["saying the sound is softer with no reason given",
                  "saying the bell stops ringing altogether"],
    },

    (36, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["electricity", "materials"],
        "scenario_anchors": ["wooden rod", "bell"],
        "chains": [{
            "chain_id": "insulator",
            "keypoints": [
                {"kp_id": "ins_1", "position": 1, "facet": "result",
                 "statement": "no sound is produced, because wood is an electrical "
                              "insulator so no current can flow through the coils",
                 "accepts": ["there will be no ting — the wooden rod does not conduct "
                             "electricity, so the circuit is not complete"]},
            ],
        }],
        "traps": ["saying there is no sound without naming wood as an insulator",
                  "saying the sound is merely softer"],
    },

    (37, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["energy"],
        "scenario_anchors": ["rubber band", "toy", "A", "B"],
        "chains": [{
            "chain_id": "conversion",
            "keypoints": [
                {"kp_id": "cnv_1", "position": 1, "facet": "result",
                 "statement": "elastic potential energy in the rubber band becomes "
                              "gravitational potential energy plus kinetic energy plus "
                              "sound",
                 "accepts": ["elastic potential energy turns into kinetic and "
                             "gravitational potential energy and sound"]},
            ],
        }],
        "traps": ["naming kinetic energy alone and omitting the gain in height",
                  "starting from kinetic energy rather than the stretched rubber band"],
    },

    (37, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["forces", "energy"],
        "scenario_anchors": ["toy", "C", "D"],
        "chains": [{
            "chain_id": "descend",
            "keypoints": [
                {"kp_id": "des_1", "position": 1, "facet": "action",
                 "statement": "gravitational force pulls the toy downwards once it can "
                              "no longer stay up",
                 "accepts": ["gravity pulls it down", "its weight acts downwards"]},
                {"kp_id": "des_2", "position": 2, "facet": "result",
                 "statement": "air resistance acts against that motion, so the toy comes "
                              "down gradually rather than dropping straight away",
                 "accepts": ["air resistance opposes it so it sinks slowly",
                             "the air pushing up on it slows the fall"]},
            ],
        }],
        "traps": ["naming gravity alone with nothing opposing it",
                  "saying the toy 'ran out of energy' with no force named"],
    },

    # "Draw a curved line on Diagram 2 to show the new path of the toy." [2]
    (37, "c"): {
        "response_mode": "drawn",
        "topics": ["energy", "forces"],
        "scenario_anchors": ["toy", "rubber band"],
        "traps": [],
    },

    (38, None): {
        "mark_model": "per_chain",
        "chains_required": 2,
        "context_gate": "general",
        "topics": ["matter"],
        "chains": [
            {"chain_id": "space", "keypoints": [
                {"kp_id": "spc_1", "position": 1, "facet": "result",
                 "statement": "air occupies space",
                 "accepts": ["air takes up space", "air fills the room it is in"]}]},
            {"chain_id": "shape", "keypoints": [
                {"kp_id": "shp_1", "position": 1, "facet": "result",
                 "statement": "air takes the shape of its container",
                 "accepts": ["air has no fixed shape — it fits the container"]}]},
        ],
        "traps": ["giving only one property when two are asked for",
                  "giving a property of a liquid, such as a fixed volume with a free "
                  "surface"],
    },

    (39, "a"): {
        "mark_model": "per_keypoint",
        "topics": ["electricity"],
        "scenario_anchors": ["bulb", "switch"],
        "chains": [{
            "chain_id": "series",
            "keypoints": [
                {"kp_id": "ser_1", "position": 1, "facet": "result",
                 "statement": "the two bulbs were connected in series",
                 "accepts": ["in series, one after the other in a single loop"]},
            ],
        }],
        "traps": ["answering parallel, in which the second bulb would still light"],
    },

    # "Complete the circuit so that it will work as described." [3]
    (39, "b"): {
        "response_mode": "drawn",
        "topics": ["electricity"],
        "scenario_anchors": ["bulb L", "bulb R", "switch"],
        "traps": [],
    },

    (40, "a"): {
        "mark_model": "per_keypoint",
        "context_gate": "general",
        "topics": ["heat", "measurement"],
        "chains": [{
            "chain_id": "read",
            "keypoints": [
                {"kp_id": "rd_1", "position": 1, "facet": "result",
                 "statement": "74 °C", "accepts": ["74 degrees Celsius"]},
            ],
        }],
        "traps": ["giving the value without its unit"],
    },

    (40, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["heat", "materials"],
        "scenario_anchors": ["turkey", "oven"],
        "chains": [{
            "chain_id": "conduct",
            "keypoints": [
                {"kp_id": "cnd_1", "position": 1, "facet": "result",
                 "statement": "the turkey is a poor conductor of heat, so heat takes "
                              "time to travel from the hotter oven through to its "
                              "middle",
                 "accepts": ["heat moves slowly through the turkey because it conducts "
                             "heat poorly",
                             "it takes time for the heat to reach the inside"]},
            ],
        }],
        "traps": ["saying the turkey is 'big' without naming poor conduction",
                  "saying the oven is not hot enough, when the reading shows it is"],
    },
}
