"""Local speech-to-text via faster-whisper.

Runs entirely on this machine -- no audio leaves it. The browser Web Speech API was
rejected for this (CLAUDE.md section 4): it ships audio to Google, Safari support is
poor, and it mishandles Singapore-accented child speech on exactly the words that
carry the marks.

`initial_prompt` biases recognition toward the vocabulary these answers need. Without
it, "upthrust" comes back as "up thrust", "photosynthesise" as "photo synthesise",
and a correct answer looks wrong before it ever reaches a grader.

Set PSLE_WHISPER_MODEL to switch size (default small.en; drop to base.en if slow).
"""

from __future__ import annotations

import os
import re
import tempfile
from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel

DEFAULT_MODEL = "small.en"

# Scenario anchors matter more than any single science term. Questions label things
# "plant E", "tube A", "substance X", and the marking gate checks that the answer
# operates on those labels (CLAUDE.md section 3.3). Whisper collapses them into words
# by default -- "plant E" comes back as "Planty" -- which destroys the anchor and
# fails a correct answer. Seeding the pattern keeps the letter separate.
ANCHORS = (
    "Labelled things keep their letter: plant E, plant F, plant G, plant K, "
    "animal Y, bird A, bird B, fish C, insect P, tube A, tube B, tube C, "
    "beaker X, container Q, substance P, substance Q, substance R, substance X, "
    "block A, block B, setup A, setup B, zone A, zone B, bulb L, magnet P."
)

# Terms that recur in Booklet B answers and that generic models get wrong.
GLOSSARY = (
    f"{ANCHORS} "
    "PSLE primary science. Terms: evaporation, condensation, boiling, melting, "
    "freezing, water vapour, dissolved oxygen, photosynthesis, photosynthesise, "
    "respiration, germination, pollination, fertilisation, seed dispersal, "
    "reproduce, adaptation, predator, prey, food chain, food web, habitat, "
    "decomposer, upthrust, gravitational force, elastic spring force, frictional "
    "force, magnetic force, electromagnet, closed circuit, open circuit, series, "
    "parallel, conductor, insulator, transparent, translucent, opaque, "
    "kinetic energy, potential energy, chemical potential energy, elastic "
    "potential energy, light energy, sound energy, heat energy, gains heat, "
    "loses heat, air resistance, fair test, variable, cell membrane, chloroplast, "
    "stomata, mineral salts, nutrients, digestion, small intestine, blood vessel."
)


def model_name() -> str:
    return os.environ.get("PSLE_WHISPER_MODEL", DEFAULT_MODEL)


@lru_cache(maxsize=2)
def _model(name: str) -> WhisperModel:
    # int8 on CPU is the practical choice on a laptop; float16 needs CUDA.
    return WhisperModel(name, device="cpu", compute_type="int8")


def build_prompt(anchors: list[str] | None = None) -> str:
    """Seed recognition, putting this question's own anchors first.

    A generic anchor list is not enough on its own: "plant E" is homophonous with
    "planty" and both model sizes get it wrong from the generic list alone. Naming
    the anchors this particular question uses is a far stronger bias.
    """
    if not anchors:
        return GLOSSARY
    return f"This question is about {', '.join(anchors)}. {GLOSSARY}"


# How Whisper spells a letter it has heard but not understood as a label. "plant E"
# comes back as "Planty"; "tube A" as "tubay".
LETTER_SOUNDS = {
    "a": ["a", "ay", "eh"], "b": ["b", "bee", "be"], "c": ["c", "see", "sea"],
    "d": ["d", "dee"], "e": ["e", "ee", "y", "ea"], "f": ["f", "ef"],
    "g": ["g", "gee", "jee"], "h": ["h", "aitch"], "i": ["i", "eye"],
    "j": ["j", "jay"], "k": ["k", "kay"], "l": ["l", "el"], "m": ["m", "em"],
    "n": ["n", "en"], "o": ["o", "oh"], "p": ["p", "pee"],
    "q": ["q", "cue", "queue"], "r": ["r", "ar"], "s": ["s", "es"],
    "t": ["t", "tee", "tea"], "u": ["u", "you"], "v": ["v", "vee"],
    "w": ["w"], "x": ["x", "ex"], "y": ["y", "why"], "z": ["z", "zed"],
}


def repair_anchors(text: str, anchors: list[str] | None) -> str:
    """Restore scenario anchors that speech-to-text ran together into one word.

    Prompt seeding is not enough on its own -- "plant E" is homophonous with
    "planty" and comes back wrong at every model size. This is not guesswork: the
    replacement set is exactly the anchors this question uses, read off its own
    page, so the only thing being decided is whether a heard sound was that label.

    The student still sees and can edit the result before anything is marked.
    """
    if not anchors:
        return text
    for anchor in anchors:
        noun, _, letter = anchor.rpartition(" ")
        if not noun or len(letter) != 1:
            continue
        sounds = LETTER_SOUNDS.get(letter.lower(), [letter.lower()])
        # "planty" / "plante" (run together) and "plant ee" (letter spelled out).
        pattern = re.compile(
            rf"\b{re.escape(noun)}\s*(?:{'|'.join(sounds)})\b", re.I)
        text = pattern.sub(f"{noun} {letter.upper()}", text)
    return text


def transcribe_file(path: str | Path, anchors: list[str] | None = None) -> str:
    segments, _ = _model(model_name()).transcribe(
        str(path),
        language="en",
        initial_prompt=build_prompt(anchors),
        vad_filter=True,
        beam_size=5,
    )
    text = " ".join(segment.text.strip() for segment in segments).strip()
    return repair_anchors(text, anchors)


def transcribe_bytes(payload: bytes, suffix: str = ".webm",
                     anchors: list[str] | None = None) -> str:
    with tempfile.NamedTemporaryFile(suffix=suffix or ".webm", delete=False) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    try:
        return transcribe_file(temp_path, anchors)
    finally:
        temp_path.unlink(missing_ok=True)
