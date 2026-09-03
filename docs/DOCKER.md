# Running the app in a container

The image is self-contained: the app, both subjects' papers, and the speech model.
Nothing is downloaded when it runs.

```bash
docker compose up --build
```

Then open <http://localhost:8000>. Read the microphone note below before sitting a
Science paper on any other device.

---

## What is in the image

| | |
|---|---|
| Science Booklet A | 2012–2025 — 14 years of pages, the question inventory, the answer key |
| Science Booklet B | 2012–2025 — pages, inventory, and rubrics for 2021–2025 |
| Chinese Paper 2 | 2012–2025 — pages, index, answer key and rubrics |
| Whisper `small.en` | so the first recording transcribes immediately, offline |

and what is not, deliberately:

- **`.env`.** The API key is read on the host and injected at run time. An image
  carrying a secret leaks it everywhere the image goes.
- **`papers/`.** The source PDFs are the ingestion pipeline's input. The app only
  reads what `build/` rendered out of them.
- **The answers, as images.** `work-ans/*/pages`, `work-cn/*/answer-pages` and the
  Science answer crops are ~320MB that no route reads. The Chinese key is already
  unpacked to a directory no route reaches (CLAUDE.md §7.1); leaving the renders out
  of the image extends that to Science. `work/`'s two full-paper unpacks are pruned
  to their Booklet B range during the build for the same reason — the route already
  refuses to serve outside it, and now the filesystem agrees.
- **`data/attempts.db`.** Runtime state, mounted rather than baked in — see below.

Expect roughly 1.6GB built. The page scans are 300 dpi PNGs and are most of it.

## The API key

`docker-compose.yml` reads the existing `.env` at start-up, so grading works with no
extra step. Without `ANTHROPIC_API_KEY` the app still runs — the student practises,
self-checks against the model answer, and the attempt is still logged (CLAUDE.md
§2.2). `/api/grading` reports which of the two it is, and the UI says so up front.

Chinese chosen answers (Q1–Q32) are marked against the key and never need it at all.

## Practice history survives the container

`./data` and `./review` are bind-mounted, so the attempt log the local app has
already built up is the one the container reads and writes, and a backup is a file
copy. Delete the container as often as you like; the history is in the repo
directory, not in the image.

On Linux the container's user (uid 10001) must be able to write those two
directories — `docker compose run --user "$(id -u):$(id -g)" psle`, or `chown` them.
Docker Desktop on macOS handles it already.

## The microphone needs a secure context

Browsers only grant microphone access on `https://` or on `localhost`. Over plain
`http://` to a LAN address, `getUserMedia` is not merely refused — it is absent — and
the app degrades to its typed path with "No microphone access — type your answer
instead."

So:

- **On this machine**, <http://localhost:8000> is a secure context. Everything works.
- **On another device on the network**, spoken answers will not work over
  `http://192.168.x.x:8000`. Everything else does.
- **Chinese is unaffected** either way: answers there are typed and chosen by design,
  never spoken (CLAUDE.md §7.6).

To record from another device, put TLS in front of the container — a reverse proxy
with a certificate from `mkcert`, trusted on the tablet — or, on desktop Chrome,
allow the origin under `chrome://flags/#unsafely-treat-insecure-origin-as-secure`.

There is no login. Anyone who can reach the port can read the papers, so keep it to
the home network; `127.0.0.1:8000:8000` in `docker-compose.yml` restricts it to this
machine.

## After backfilling a paper

The build pipeline runs on the host — it needs macOS Vision OCR, which is why it is
not in the image. Re-run whichever stage changed (CLAUDE.md §7.7 for Chinese), then:

```bash
docker compose up --build -d
```

Only the layers after the changed directory are rebuilt; the dependency and Whisper
layers are cached.

## Useful commands

```bash
docker compose logs -f
```

```bash
docker compose down
```

A Chinese-only image, without the ~500MB of Whisper weights:

```bash
WHISPER_MODEL= docker compose build
```

## Copyright

The image contains © MOE / SEAB question papers and © EPH answers. CLAUDE.md §2.1
applies to it as it applies to the repo: a personal study tool built from materials
already owned is a different thing from redistribution. Keep the image private —
never push it to a public registry, and host it somewhere only this household
reaches.
