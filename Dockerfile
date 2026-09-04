# The app, both subjects' papers, and the speech model, in one image.
#
# Everything the practice loop needs is baked in: every rendered page for Science
# Booklets A and B and for Chinese Paper 2, every index, answer key and rubric, and
# the Whisper weights. Nothing is fetched when the container runs, so the promise in
# CLAUDE.md 2.2 survives being hosted -- the only outbound call is the optional one
# to the Anthropic API for grading, and without it the student can still practise,
# self-check and have the attempt logged.
#
# Three things are deliberately left out; see .dockerignore for the full list.
#
#   .env             The API key is passed in at run time. An image that carries a
#                    secret leaks it to everywhere the image goes.
#   papers/          The source PDFs are the ingestion pipeline's input, not the
#                    app's. Every route reads what build/ rendered out of them.
#   the answer pages The Chinese key and the Science answer scans are ~320MB that no
#                    route reads. Leaving them out makes "the answers are not
#                    reachable" a property of the image, not of the routing.
#
# COPYRIGHT. The image contains (c) MOE / SEAB question papers and (c) EPH answers.
# CLAUDE.md 2.1 applies to it exactly as it applies to the repo: it is a personal
# study tool built from materials already owned. Keep it private -- never push it to
# a public registry, and host it somewhere only this household reaches.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/huggingface

WORKDIR /app

# Runtime dependencies only -- see requirements-app.txt for why they are a separate
# file rather than requirements.txt.
COPY requirements-app.txt ./
RUN pip install --no-cache-dir -r requirements-app.txt

# The Whisper weights, fetched at build time rather than on the first recording. A
# first-run download would be both a network dependency and a minute of silence on
# the one interaction that has to feel immediate.
#
# HF_HUB_OFFLINE then holds it to that: the container never reaches out for a model,
# so changing PSLE_WHISPER_MODEL at run time cannot silently start a download -- it
# fails, and the fix is to rebuild with --build-arg WHISPER_MODEL=base.en. Chinese
# never records (CLAUDE.md 7.6), so a Chinese-only image can pass an empty string
# and save ~500MB.
ARG WHISPER_MODEL=small.en
ENV PSLE_WHISPER_MODEL=${WHISPER_MODEL} \
    HF_HUB_OFFLINE=1
RUN if [ -n "$WHISPER_MODEL" ]; then \
        HF_HUB_OFFLINE=0 python -c "from faster_whisper import WhisperModel; \
WhisperModel('$WHISPER_MODEL', device='cpu', compute_type='int8')"; \
    fi

# The papers, before the app code: they are ~550MB and change when a paper is
# backfilled, where app/ changes daily, and a layer only invalidates what follows it.
#
#   work/       the two full-paper Science unpacks (2024, 2025), Booklet B
#   work-b/     Booklet B for every backfilled year
#   work-a/     Booklet A -- pages and the question inventory
#   work-ans/   the Booklet A answer key (its page renders are excluded)
#   work-cn/    Chinese Paper 2 -- pages, index, key and rubrics
#   work-en-a/  English Paper 2 Booklet A -- pages and the question inventory
#   work-en-b/  English Paper 2 Booklet B -- pages and the question inventory
#   work-en-ans/ both English keys, as JSON (their page renders are excluded)
#   rubrics/    Science rubrics: the model answers, explanations and chains
#   review/     flags raised on a rubric, and the keys read by eye; written to
#               at run time
COPY work/ ./work/
COPY work-a/ ./work-a/
COPY work-b/ ./work-b/
COPY work-ans/ ./work-ans/
COPY work-cn/ ./work-cn/
COPY work-en-a/ ./work-en-a/
COPY work-en-b/ ./work-en-b/
COPY work-en-ans/ ./work-en-ans/
COPY rubrics/ ./rubrics/
COPY review/ ./review/

# work/ is the only unpack that holds a whole paper, answer pages included. The
# route already refuses to serve outside Booklet B, and this makes the filesystem
# agree with the route: what is not servable is not present. Booklet A's own pages
# are unaffected -- /api/mcq serves those from work-a/.
RUN python - <<'PY'
import json
from pathlib import Path

for questions in sorted(Path("work").glob("*/questions.json")):
    booklet_b = json.loads(questions.read_text())["booklet_b"]
    kept = removed = 0
    for page in sorted((questions.parent / "pages").glob("page-*.png")):
        if booklet_b["start"] <= int(page.stem.split("-")[1]) <= booklet_b["end"]:
            kept += 1
        else:
            page.unlink()
            removed += 1
    print(f"{questions.parent}: kept {kept} Booklet B pages "
          f"({booklet_b['start']}-{booklet_b['end']}), removed {removed}")
    assert kept == booklet_b["end"] - booklet_b["start"] + 1, "missing a page"
PY

COPY app/ ./app/

# Non-root, owning the two paths the app writes: the attempt log and the review
# flags. Both are mounted in docker-compose.yml so they outlive the container; the
# chown is what makes a plain `docker run` work as well.
RUN useradd --create-home --uid 10001 psle \
    && mkdir -p /app/data \
    && chown -R psle:psle /app/data /app/review
USER psle

EXPOSE 8000

# /api/subjects is the right probe: it is the first thing the home screen asks for,
# and it only answers once the indexes on disk are readable.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; \
urllib.request.urlopen('http://127.0.0.1:8000/api/subjects', timeout=4)"

# One worker on purpose: one child, one SQLite file, and a resident Whisper model
# that there is no reason to hold a second copy of.
CMD ["uvicorn", "main:app", "--app-dir", "app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
