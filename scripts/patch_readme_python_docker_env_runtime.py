from pathlib import Path
import re

p = Path("README.md")
txt = p.read_text(encoding="utf-8-sig")

section = """
## Running the Project

The project can be run in two ways:

1. Locally with Python
2. Through Docker

For the competition review, the recommended starting point is the already imported demo dashboard, because the demo case already includes the generated diagnostic artifacts, example outputs and final logs.

Open:

    http://localhost:8000/demo-dashboard

The full landing page is available at:

    http://localhost:8000/

---

## Option A - Run Locally with Python

Create and activate a virtual environment:

    py -m venv .venv
    .\\.venv\\Scripts\\Activate.ps1

Install dependencies:

    python -m pip install -r requirements.txt

Run the application:

    python run.py

Then open:

    http://localhost:8000/
    http://localhost:8000/demo-dashboard

Recommended Python version:

    Python 3.13 or higher

If using an older Python version, a different compatible resdata version may be required.

---

## Option B - Run with Docker

Docker is supported through the included Dockerfile.

Build the image:

    docker build -t 404-reservoir-not-found:latest .

Run the container without secrets:

    docker run --name 404-reservoir-not-found-demo -p 8000:8000 404-reservoir-not-found:latest

Then open:

    http://localhost:8000/
    http://localhost:8000/demo-dashboard

This mode is enough to inspect:

- the landing page;
- the demo dashboard;
- KPI cards;
- history-match maps;
- well-level diagnostics;
- recommendations;
- official examples;
- final logs.

To inspect Docker logs:

    docker logs 404-reservoir-not-found-demo --tail 200

To follow logs live:

    docker logs -f 404-reservoir-not-found-demo

To stop the container:

    docker stop 404-reservoir-not-found-demo

To remove and recreate the container:

    docker rm -f 404-reservoir-not-found-demo
    docker run --name 404-reservoir-not-found-demo -p 8000:8000 404-reservoir-not-found:latest

---

## Compass / LLM Chatbox Environment Variables

The repository intentionally does not include a local .env file.

This is required for security:

- .env may contain private API keys;
- .env is excluded by .gitignore;
- .env is excluded by .dockerignore;
- .env.example is included only as a safe template.

The dashboard demo can run without .env.

However, the AI chatbox / Compass LLM generation requires a Compass API key supplied at runtime.

Create a local .env file from the template:

    copy .env.example .env

Then edit .env and set:

    COMPASS_API_KEY=<your_compass_api_key>
    HOST=0.0.0.0
    PORT=8000

Run Docker with the environment file:

    docker rm -f 404-reservoir-not-found-demo
    docker run --name 404-reservoir-not-found-demo --env-file .env -p 8000:8000 404-reservoir-not-found:latest

Then open:

    http://localhost:8000/demo-dashboard

Important:

    If Docker is started without --env-file .env, the dashboard demo remains available, but Compass/LLM chat responses may be disabled or limited because no API key was supplied.

The API key is never stored in the repository or in the Docker image. It is provided only at runtime through:

    --env-file .env

---

## Suggested Reviewer Workflow

For a fast review:

    docker build -t 404-reservoir-not-found:latest .
    docker run --name 404-reservoir-not-found-demo -p 8000:8000 404-reservoir-not-found:latest

Open:

    http://localhost:8000/demo-dashboard

For full Compass/LLM chatbox testing:

    copy .env.example .env

Add a valid COMPASS_API_KEY to .env, then run:

    docker rm -f 404-reservoir-not-found-demo
    docker run --name 404-reservoir-not-found-demo --env-file .env -p 8000:8000 404-reservoir-not-found:latest

Open:

    http://localhost:8000/demo-dashboard

---
"""

patterns_to_remove = [
    r"## Running the Project[\s\S]*?---\s*",
    r"## Docker and Environment Variables[\s\S]*?---\s*",
    r"## Compass / LLM Chatbox Environment Variables[\s\S]*?---\s*",
    r"## Suggested Reviewer Workflow[\s\S]*?---\s*",
]

for pat in patterns_to_remove:
    txt = re.sub(pat, "", txt, count=1)

m = re.search(r"(# .+?\n(?:[\s\S]{0,1200}?))(?=\n## )", txt)

if m:
    insert_at = m.end(1)
    txt = txt[:insert_at].rstrip() + "\n\n" + section.strip() + "\n\n" + txt[insert_at:].lstrip()
else:
    txt = section.strip() + "\n\n" + txt

p.write_text(txt, encoding="utf-8")
print("[OK] README.md updated with Python + Docker + .env runtime instructions")
