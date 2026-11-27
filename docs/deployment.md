# Deploying the web app

The web app runs from the `Dockerfile` in the repository root. Locally you do not need Docker: `python -m webapp`.

## Testing the image locally

```bash
docker build -t bioinvasion .
docker run --rm -p 127.0.0.1:7860:7860 bioinvasion        # then open http://127.0.0.1:7860
# all tests inside the image (reference data mounted read-only):
docker run --rm -v "$PWD":/src:ro -v ~/Git/manuscript/data:/ref:ro -e BIOINVASION_REFERENCE_DIR=/ref \
    -e PYTHONDONTWRITEBYTECODE=1 -w /src bioinvasion \
    sh -c "pip install -q --user pytest && python -m pytest -p no:cacheprovider -m 'slow or not slow' tests"
```

## Hugging Face Spaces (CPU basic: 2 vCPU, 16 GB RAM)

Docker Spaces need a PRO account ($9/month, checked 2026-11-27). The CPU basic hardware itself has no hourly cost, so
the PRO fee is the only cost as long as the hardware stays on CPU basic. Upgraded hardware is billed per hour (e.g.
CPU upgrade $0.03/hour, about $22/month); prices: https://huggingface.co/pricing#spaces

1. Create a Space at https://huggingface.co/new-space: SDK **Docker**, template **Blank**, hardware **CPU basic**,
   visibility public.
2. Hugging Face reads the Space settings from a header at the top of the Space's `README.md`. Create the Space with
   the website's default README, then, in this repository:
   ```bash
   git remote add space git@hf.co:spaces/<user>/<space>  # SSH: add your public key at huggingface.co/settings/keys
   git -c fetch.negotiationAlgorithm=noop fetch space   # plain 'git fetch' fails: "expected 'acknowledgments'"
   git checkout -b hf space/main             # the Space's own history (its README.md with the header)
   git checkout refactor -- Dockerfile .dockerignore requirements.txt pyproject.toml bioinvasion webapp
   git status                                # must list only these files as staged
   git commit -m "app from bioinvasionanalysis <commit>"
   git push space hf:main                    # Hugging Face builds the image and starts the app
   git checkout refactor
   ```
   For later updates, repeat the lines from `git checkout hf` (instead of `-b hf space/main`) on.
   **Never use `git add -A` or `git commit -a` on the `hf` branch**: it has no `.gitignore`, so your private data
   in `data/` and all results would be committed. Hugging Face rejects binary files in git anyway; the demo cost
   surface is therefore downloaded from GitHub during the build (see the `Dockerfile`).
   The header in the Space's README.md must contain `sdk: docker`; add `app_port: 7860` to be explicit (7860 is the
   default).
3. The build log and the app log are shown on the Space page ("Logs").

Notes:
- A Space on CPU basic sleeps after a period without visitors; the first visit afterwards takes about half a minute.
- The disk of a Space is not persistent: session folders disappear on restart, which is fine because they are
  temporary anyway (24 hours).
- Limits for visitors (raster cells, observations, upload size, concurrent computations) are set in
  `webapp/jobs.py`.

## Any other server

The same image runs anywhere Docker runs, e.g. on a small VM:
```bash
docker build -t bioinvasion .
docker run -d --restart unless-stopped -p 7860:7860 bioinvasion
```
Put a reverse proxy with HTTPS in front of it (e.g. Caddy: `reverse_proxy localhost:7860`).
