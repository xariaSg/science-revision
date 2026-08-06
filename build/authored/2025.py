"""Authored rubric chains for the 2025 paper.

Apply with:  python build/apply_authored.py --years 2025
See build/authored/2024.py for the conventions, and build/validate.py for what
mark_model, context_gate and response_mode mean.

Two sub-parts are answered by drawing on the paper rather than in words -- Q30(b)
asks for arrows on a food web, Q35 for a completed circuit. They carry
response_mode "drawn" and no chains: they cannot be spoken and cannot be graded
from a transcript, and marking them this way keeps them out of the review queue as
finished rather than missing.
"""

CHAINS: dict[tuple[int, str | None], dict] = {

    (29, "a"): {
        "mark_model": "per_keypoint", "context_gate": "general",
        "topics": ["human_system"],
        "chains": [{"chain_id": "name", "keypoints": [
            {"kp_id": "nam_1", "position": 1, "facet": "result",
             "statement": "the skeletal system", "accepts": ["skeleton"]}]}],
        "traps": ["naming the muscular system instead"],
    },

    (29, "b"): {
        "mark_model": "per_chain", "chains_required": 2, "context_gate": "general",
        "topics": ["human_system"],
        "chains": [
            {"chain_id": "support", "keypoints": [
                {"kp_id": "sup_1", "position": 1, "facet": "result",
                 "statement": "the skeletal system supports the body",
                 "accepts": ["it gives the body its shape and holds it up"]}]},
            {"chain_id": "protect", "keypoints": [
                {"kp_id": "pro_1", "position": 1, "facet": "result",
                 "statement": "it protects important parts of the body",
                 "accepts": ["it protects organs such as the brain, heart and lungs"]}]},
        ],
        "traps": ["giving only one function when two are asked for",
                  "answering movement alone, which is the muscular system's role"],
    },

    (30, "a(i)"): {
        "mark_model": "per_keypoint", "topics": ["food_chain"],
        "scenario_anchors": ["organism R", "organism Q"],
        "chains": [{"chain_id": "producers", "keypoints": [
            {"kp_id": "prd_1", "position": 1, "facet": "result",
             "statement": "R and Q", "accepts": ["Q and R"]}]}],
        "traps": ["choosing an organism that is eaten rather than one that makes "
                  "its own food"],
    },

    (30, "a(ii)"): {
        "mark_model": "per_keypoint", "topics": ["food_chain"],
        "scenario_anchors": ["organism T", "organism U"],
        "chains": [{"chain_id": "consumers", "keypoints": [
            {"kp_id": "con_1", "position": 1, "facet": "result",
             "statement": "T and U", "accepts": ["U and T"]}]}],
        "traps": ["choosing an organism that is only eaten, or only eats"],
    },

    # "Use a pencil to draw arrows to show the food relationships."
    (30, "b"): {"response_mode": "drawn", "topics": ["food_chain"], "chains": []},

    (31, "a"): {
        "mark_model": "per_keypoint", "topics": ["digestive_system"],
        "scenario_anchors": ["organ C"],
        "chains": [{"chain_id": "identify", "keypoints": [
            {"kp_id": "id_1", "position": 1, "facet": "result",
             "statement": "C, the small intestine",
             "accepts": ["C", "the small intestine"]}]}],
        "traps": ["naming the stomach or the large intestine"],
    },

    (31, "b(i)"): {
        "mark_model": "per_keypoint", "topics": ["digestive_system"],
        "chains": [{"chain_id": "trend", "keypoints": [
            {"kp_id": "trd_1", "position": 1, "facet": "result",
             "statement": "the amount of undigested food decreases",
             "accepts": ["it goes down", "it gets less"]}]}],
        "traps": ["saying it increases, or that it stays the same"],
    },

    (31, "b(ii)"): {
        "mark_model": "per_keypoint", "topics": ["digestive_system"],
        "chains": [{"chain_id": "trend", "keypoints": [
            {"kp_id": "trd_1", "position": 1, "facet": "result",
             "statement": "the amount of undigested food remains the same",
             "accepts": ["it does not change", "it stays constant"]}]}],
        "traps": ["saying it decreases — no digestion happens in the large "
                  "intestine, only water is absorbed"],
    },

    (32, "a"): {
        "mark_model": "per_chain", "chains_required": 2, "context_gate": "general",
        "topics": ["photosynthesis"],
        "chains": [
            {"chain_id": "food", "keypoints": [
                {"kp_id": "fd_1", "position": 1, "facet": "result",
                 "statement": "plants make sugar (food) during photosynthesis",
                 "accepts": ["photosynthesis makes food for the plant"]}]},
            {"chain_id": "oxygen", "keypoints": [
                {"kp_id": "ox_1", "position": 1, "facet": "result",
                 "statement": "plants release oxygen into the surrounding air",
                 "accepts": ["oxygen is given out"]}]},
        ],
        "traps": ["giving only one function when two are asked for",
                  "describing what photosynthesis needs rather than what it produces"],
    },

    (32, "b"): {
        "mark_model": "per_chain", "chains_required": 2,
        "scenario_anchors": ["6 pm"],
        "topics": ["photosynthesis", "respiration"],
        "chains": [
            {"chain_id": "daylight", "keypoints": [
                {"kp_id": "day_1", "position": 1, "facet": "result",
                 "statement": "the carbon dioxide decreased from 1 pm to 6 pm",
                 "accepts": ["it fell during the afternoon while there was sunlight"]}]},
            {"chain_id": "after_sunset", "keypoints": [
                {"kp_id": "ngt_1", "position": 1, "facet": "result",
                 "statement": "the carbon dioxide increased from 6 pm to 9 pm",
                 "accepts": ["it rose after the sun set"]}]},
        ],
        "traps": ["describing only one of the two periods",
                  "saying the amount 'changed' without the direction"],
    },

    (32, "c"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["the soil"],
        "topics": ["experimental_design", "photosynthesis"],
        "chains": [{"chain_id": "control", "keypoints": [
            {"kp_id": "ctl_1", "position": 1, "facet": "variable",
             "statement": "to stop the soil affecting the carbon dioxide reading, so "
                          "any change is due to the plant alone",
             "accepts": ["to stop water evaporating from the soil and changing the "
                         "rate of photosynthesis",
                         "to stop microorganisms in the soil respiring and releasing "
                         "carbon dioxide"]}]}],
        "traps": ["saying it is 'to make it a fair test' without naming what the "
                  "soil would otherwise change"],
    },

    (33, "a"): {
        "mark_model": "per_keypoint", "context_gate": "general",
        "topics": ["life_cycles"],
        "chains": [{"chain_id": "order", "keypoints": [
            {"kp_id": "ord_1", "position": 1, "facet": "result",
             "statement": "egg, larva, pupa, adult",
             "accepts": ["egg then larva then pupa then adult"]}]}],
        "traps": ["giving a three-stage life cycle, which has no pupa"],
    },

    (33, "b"): {
        "mark_model": "per_keypoint", "topics": ["experimental_design"],
        "scenario_anchors": ["repellent F"],
        "chains": [{"chain_id": "identify", "keypoints": [
            {"kp_id": "id_1", "position": 1, "facet": "result",
             "statement": "F", "accepts": ["repellent F"]}]}],
        "traps": ["choosing the repellent with the most mosquitoes remaining"],
    },

    (33, "c"): {
        "mark_model": "per_chain", "chains_required": 1,
        "topics": ["experimental_design"],
        "chains": [{"chain_id": "control", "keypoints": [
            {"kp_id": "ctl_1", "position": 1, "facet": "variable",
             "statement": "repeat the test with no repellent applied to his hand",
             "accepts": ["do the same thing but without any repellent"]},
            {"kp_id": "ctl_2", "position": 2, "facet": "result",
             "statement": "count the mosquitoes that stay on his hand for more than "
                          "one minute, keeping everything else the same",
             "accepts": ["count the mosquitoes the same way as before"]}]}],
        "traps": ["changing something else as well as removing the repellent",
                  "describing a control experiment in general terms without saying "
                  "what to do here"],
    },

    (33, "d"): {
        "mark_model": "per_chain", "chains_required": 1,
        "topics": ["characteristics_of_living_things"],
        "chains": [{"chain_id": "air", "keypoints": [
            {"kp_id": "air_1", "position": 1, "facet": "variable",
             "statement": "the holes let air enter the tank",
             "accepts": ["so air can get in"]},
            {"kp_id": "air_2", "position": 2, "facet": "result",
             "statement": "so the mosquitoes can respire and stay alive",
             "accepts": ["the mosquitoes need air to breathe and survive"]}]}],
        "traps": ["saying 'so they can breathe' without linking it to survival",
                  "answering that it stops the mosquitoes escaping"],
    },

    (34, "a"): {
        "mark_model": "per_keypoint", "context_gate": "general",
        "topics": ["reproduction_in_plants"],
        "chains": [{"chain_id": "name", "keypoints": [
            {"kp_id": "nam_1", "position": 1, "facet": "result",
             "statement": "fertilisation", "accepts": []}]}],
        "traps": ["answering 'pollination', which happens before fertilisation"],
    },

    (34, "b"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["fruit X", "fruit Y", "zone A", "zone B"],
        "topics": ["reproduction_in_plants", "adaptation"],
        "chains": [{"chain_id": "dispersal", "keypoints": [
            {"kp_id": "dsp_1", "position": 1, "facet": "result",
             "statement": "fruit X is more likely in zone B and fruit Y in zone A",
             "accepts": ["X at the bottom of the forest, Y at the top"]},
            {"kp_id": "dsp_2", "position": 2, "facet": "action",
             "statement": "the hooks on fruit X cling to the fur of animals or the "
                          "clothes of people walking on the ground",
             "accepts": ["fruit X is carried away by animals it hooks onto"]},
            {"kp_id": "dsp_3", "position": 3, "facet": "action",
             "statement": "the wing-like structures on fruit Y let it be carried by "
                          "the wind, which is stronger at the top of the forest",
             "accepts": ["fruit Y is blown away by the wind"]}]}],
        "traps": ["naming the zones without saying what carries each fruit",
                  "describing the structures without linking them to a zone"],
    },

    # "Use a pencil to complete the circuit below."
    (35, None): {"response_mode": "drawn", "topics": ["electricity"], "chains": []},

    (36, "a"): {
        "mark_model": "per_keypoint", "context_gate": "general",
        "topics": ["materials"],
        "chains": [{"chain_id": "name", "keypoints": [
            {"kp_id": "nam_1", "position": 1, "facet": "result",
             "statement": "flexible", "accepts": ["flexibility"]}]}],
        "traps": ["naming a property the described behaviour does not show"],
    },

    (36, "b"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["the plastic lid", "the glass jar"],
        "topics": ["expansion_and_contraction"],
        "chains": [{"chain_id": "expansion", "keypoints": [
            {"kp_id": "exp_1", "position": 1, "facet": "variable",
             "statement": "both gained heat, but the plastic lid expanded more than "
                          "the glass jar",
             "accepts": ["the lid expands more than the jar when heated"]},
            {"kp_id": "exp_2", "position": 2, "facet": "result",
             "statement": "so the lid became slightly larger than the jar opening and "
                          "was held less tightly, making it easier to remove",
             "accepts": ["the lid is looser and comes off more easily"]}]}],
        "traps": ["saying the lid expanded without comparing it to the jar",
                  "saying heat was gained without saying what that did"],
    },

    (37, None): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["object S", "the 20 g mass"],
        "topics": ["experimental_design", "measurement"],
        "chains": [{"chain_id": "displacement", "keypoints": [
            {"kp_id": "dis_1", "position": 1, "facet": "action",
             "statement": "lower the 20 g mass alone into the full beaker first and "
                          "discard the water it displaces",
             "accepts": ["submerge the mass by itself and do not collect that water"]},
            {"kp_id": "dis_2", "position": 2, "facet": "action",
             "statement": "tie object S to the 20 g mass and lower both in until "
                          "fully submerged",
             "accepts": ["attach the mass so that object S, which floats, is held "
                         "under the water"]},
            {"kp_id": "dis_3", "position": 3, "facet": "result",
             "statement": "collect the water that overflows in the measuring "
                          "cylinder; its volume is the volume of object S",
             "accepts": ["measure the displaced water to get the volume of S"]}]}],
        "traps": ["not weighing object S down, so it floats and is not fully "
                  "submerged",
                  "collecting the water displaced by the 20 g mass as well, which "
                  "adds the mass's volume to the answer"],
    },

    (38, "a"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["point T"],
        "topics": ["energy"],
        "chains": [{"chain_id": "conversion", "keypoints": [
            {"kp_id": "cnv_1", "position": 1, "facet": "action",
             "statement": "kinetic energy from the turning drum is converted into "
                          "elastic potential energy stored in the compressed spring",
             "accepts": ["the spring stores elastic potential energy as it is "
                         "compressed"]},
            {"kp_id": "cnv_2", "position": 2, "facet": "result",
             "statement": "when released, that elastic potential energy converts into "
                          "kinetic energy, and as the ball rises to point T into "
                          "gravitational potential energy as well",
             "accepts": ["at point T the ball has both kinetic and gravitational "
                         "potential energy"]}]}],
        "traps": ["naming energy forms without saying what converts into what",
                  "stopping at kinetic energy and omitting the potential energy at "
                  "point T"],
    },

    (38, "b"): {
        "mark_model": "per_keypoint", "context_gate": "general",
        "topics": ["forces"],
        "chains": [{"chain_id": "name", "keypoints": [
            {"kp_id": "nam_1", "position": 1, "facet": "result",
             "statement": "elastic spring force", "accepts": ["spring force"]}]}],
        "traps": ["answering 'elastic potential energy', which is an energy not a "
                  "force"],
    },

    (38, "c"): {
        "mark_model": "per_keypoint", "context_gate": "general",
        "topics": ["measurement"],
        "chains": [{"chain_id": "read", "keypoints": [
            {"kp_id": "rd_1", "position": 1, "facet": "result",
             "statement": "3", "accepts": ["three"]}]}],
        "traps": [],
    },

    (38, "d"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["the toy"],
        "topics": ["energy", "measurement"],
        "chains": [{"chain_id": "faster", "keypoints": [
            {"kp_id": "fst_1", "position": 1, "facet": "result",
             "statement": "more peaks would be seen in the same 4 seconds, because "
                          "the handle hits the cardboard more often",
             "accepts": ["there would be more peaks", "the peaks would be closer "
                         "together"]}]}],
        "traps": ["saying the peaks would be taller rather than more frequent"],
    },

    (39, "a"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["the shirt"],
        "topics": ["evaporation", "condensation"],
        "chains": [{"chain_id": "mist", "keypoints": [
            {"kp_id": "mst_1", "position": 1, "facet": "action",
             "statement": "water in the shirt gained heat from the hot appliance and "
                          "evaporated into water vapour",
             "accepts": ["the water was heated and turned into water vapour"]},
            {"kp_id": "mst_2", "position": 2, "facet": "result",
             "statement": "the water vapour met the cooler surroundings, lost heat "
                          "and condensed into tiny water droplets seen as mist",
             "accepts": ["the vapour cooled and condensed into droplets"]}]}],
        "traps": ["naming evaporation or condensation alone when both are needed",
                  "saying the water 'disappeared' with no change of state"],
    },

    (39, "b"): {
        "mark_model": "per_keypoint",
        "topics": ["evaporation"],
        "chains": [{"chain_id": "evaporate", "keypoints": [
            {"kp_id": "evp_1", "position": 1, "facet": "result",
             "statement": "the tiny water droplets gained heat from the surroundings "
                          "and evaporated into water vapour",
             "accepts": ["they were heated and turned into water vapour"]}]}],
        "traps": ["saying the mist 'dried up' without naming evaporation or heat"],
    },

    (39, "c"): {
        "mark_model": "per_keypoint",
        "topics": ["heat", "materials"],
        "chains": [{"chain_id": "conductor", "keypoints": [
            {"kp_id": "cnd_1", "position": 1, "facet": "result",
             "statement": "metal, because it is a good conductor of heat and lets "
                          "heat flow quickly to the shirt",
             "accepts": ["steel — it conducts heat well to the shirt"]}]}],
        "traps": ["naming a material without saying it conducts heat well",
                  "choosing a poor conductor such as plastic or wood"],
    },

    (40, "a"): {
        "mark_model": "per_chain", "chains_required": 1,
        "scenario_anchors": ["the iron block"],
        "topics": ["electricity", "magnetism"],
        "chains": [{"chain_id": "switch", "keypoints": [
            {"kp_id": "swt_1", "position": 1, "facet": "variable",
             "statement": "with the switch open no current flows, so the iron bar "
                          "loses its magnetism",
             "accepts": ["the electromagnet switches off when the circuit is broken"]},
            {"kp_id": "swt_2", "position": 2, "facet": "result",
             "statement": "the bar no longer attracts the iron block, so the block "
                          "drops",
             "accepts": ["the iron block falls"]}]}],
        "traps": ["saying the block drops without naming the loss of magnetism"],
    },

    (40, "b"): {
        "mark_model": "per_chain", "chains_required": 1,
        "scenario_anchors": ["object P", "the iron block"],
        "topics": ["energy"],
        "chains": [{"chain_id": "height", "keypoints": [
            {"kp_id": "hgt_1", "position": 1, "facet": "variable",
             "statement": "at a greater height the iron block has more gravitational "
                          "potential energy",
             "accepts": ["higher up means more potential energy"]},
            {"kp_id": "hgt_2", "position": 2, "facet": "result",
             "statement": "more of it converts into kinetic energy, so the block hits "
                          "object P harder and drives it deeper into the sand",
             "accepts": ["it hits object P with a greater impact so P goes deeper"]}]}],
        "traps": ["saying it hits harder without naming the energy conversion",
                  "attributing the effect to a greater force rather than height"],
    },

    (40, "c"): {
        "mark_model": "per_keypoint",
        "scenario_anchors": ["object P", "the iron block"],
        "topics": ["energy"],
        "chains": [{"chain_id": "mass", "keypoints": [
            {"kp_id": "mas_1", "position": 1, "facet": "action",
             "statement": "use an iron block of greater mass, dropped from the same "
                          "height",
             "accepts": ["use a heavier iron block"]},
            {"kp_id": "mas_2", "position": 2, "facet": "result",
             "statement": "the heavier block has more gravitational potential energy, "
                          "so more kinetic energy on impact and object P goes deeper",
             "accepts": ["more energy means a greater impact and P sinks further"]}]}],
        "traps": ["changing the height, which is the variable already tested in (b)",
                  "suggesting a heavier block without explaining why it goes deeper"],
    },
}
