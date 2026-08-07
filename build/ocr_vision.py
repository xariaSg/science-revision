"""OCR via the macOS Vision framework.

Substantially better than tesseract on these scans, and still entirely local -- no
API key, no network. On 2024 Q32(c) tesseract returns "predotors" for "predators"
and clips the underlined "Explanation:" heading to "ion:", losing the field split
that the marking model depends on (CLAUDE.md section 1.6). Vision reads the same
crop cleanly, heading included.

Returns lines with pixel bounding boxes, so the geometric segmentation built for
tesseract works unchanged on better input.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import Quartz
import Vision
from Foundation import NSURL

# Vision's accurate path. Fast (1) is roughly tesseract quality and not worth it.
RECOGNITION_LEVEL_ACCURATE = 0


@dataclass
class Line:
    text: str
    left: int
    top: int
    right: int
    bottom: int
    confidence: float

    @property
    def cx(self) -> float:
        return (self.left + self.right) / 2

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2


def recognise(path: Path, languages: tuple[str, ...] = ("en-US",)) -> list[Line]:
    url = NSURL.fileURLWithPath_(str(path))
    source = Quartz.CGImageSourceCreateWithURL(url, None)
    if source is None:
        raise ValueError(f"could not read image: {path}")
    image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
    width = Quartz.CGImageGetWidth(image)
    height = Quartz.CGImageGetHeight(image)

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(RECOGNITION_LEVEL_ACCURATE)
    request.setUsesLanguageCorrection_(True)
    request.setRecognitionLanguages_(list(languages))

    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None)
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"Vision failed on {path}: {error}")

    lines: list[Line] = []
    for observation in request.results() or []:
        candidate = observation.topCandidates_(1)
        if not candidate:
            continue
        box = observation.boundingBox()
        # Vision normalises coordinates with the origin at the bottom-left; page
        # geometry everywhere else in this project is pixels from the top-left.
        left = box.origin.x * width
        right = (box.origin.x + box.size.width) * width
        top = (1.0 - box.origin.y - box.size.height) * height
        bottom = (1.0 - box.origin.y) * height
        lines.append(Line(candidate[0].string(), int(left), int(top),
                          int(right), int(bottom), float(candidate[0].confidence())))

    lines.sort(key=lambda line: (line.top, line.left))
    return lines


DEFAULT_LANGUAGES = ("en-US",)


def _cache_path(image_path: Path, languages: tuple[str, ...]) -> Path:
    # The English cache is unsuffixed so the Science bundle's existing caches stay
    # valid; anything else is tagged, because the same page read in a different
    # language is a different result.
    tag = "" if languages == DEFAULT_LANGUAGES else "." + "-".join(languages)
    return image_path.parent.parent / "ocr-vision" / f"{image_path.stem}{tag}.json"


def page_lines(image_path: Path, refresh: bool = False,
               languages: tuple[str, ...] = DEFAULT_LANGUAGES) -> list[Line]:
    """Recognise a page, caching the result next to the tesseract cache."""
    cache = _cache_path(image_path, languages)
    if cache.exists() and not refresh:
        return [Line(**row) for row in json.loads(cache.read_text())]
    lines = recognise(image_path, languages)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps([line.__dict__ for line in lines], indent=1))
    return lines


@lru_cache(maxsize=64)
def page_text(image_path: Path, refresh: bool = False,
              languages: tuple[str, ...] = DEFAULT_LANGUAGES) -> str:
    return "\n".join(line.text for line in page_lines(image_path, refresh, languages))
