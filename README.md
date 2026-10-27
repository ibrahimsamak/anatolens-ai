# AnatoLens AI

Anatomy lessons you can look at in 3D/AR and ask questions about. You point the camera at a textbook page, it figures out which lesson it is, shows the 3D model (spine and heart for now) with clickable structures, and a tutor answers questions about each structure in English or Arabic using only the reviewed lesson content.

Still early. The content is a dev seed, see the note at the bottom.

## What's in here

- `backend/` FastAPI app (Python 3.11+)
  - page recognition with a perceptual hash. Above `RECOGNITION_AUTO_THRESHOLD` it opens the lesson directly, between the min and auto threshold it asks the user to confirm, below that it gives up.
  - ontology resolver that maps what the user typed (English or Arabic, aliases, short forms like "lmbr") to a known structure, and refuses anything that isn't in `structures.yaml`
  - retrieval: dense (pgvector) + BM25, then GraphRAG over the anatomy graph (part_of, connects_to, flows_to, supplies) so the answer can mention neighbours of the structure
  - guardrails: questions outside anatomy/the lesson get redirected, and the answer is checked against the retrieved context before it's returned
  - a small LangGraph graph for the tutor: guard -> recognize -> explain
  - REST for recognition and the tutor (SSE), GraphQL (strawberry) for reading lessons and structures
- `content/` one folder per lesson: `lesson.yaml`, `structures.yaml`, `knowledge.en.yaml` / `knowledge.ar.yaml`, `hotspots.yaml` and the GLB/USDZ models. `content/_tools` has the scripts that build the models from BodyParts3D and compute the hotspot positions, plus two pages for checking a pack (`content_map.html`, `ontology.html`).
- `demo/` Vite + TypeScript page with `<model-viewer>`. AR uses WebXR if it can, otherwise Quick Look / Scene Viewer, otherwise the camera feed behind the model.
- `infra/` docker compose for Postgres (pgvector) and Redis.

## Running it

```bash
docker compose -f infra/docker-compose.yml up -d

cd backend
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on windows
pip install -e . -r requirements.txt
cp .env.example .env    # add OPENAI_API_KEY
alembic upgrade head
python -m app.seed_users
python -c "from app.db.session import SessionLocal; from app.content.ingest import ingest_pack; db=SessionLocal(); [print(ingest_pack(p, db)) for p in ('../content/spine', '../content/heart')]"
uvicorn app.main:app --reload
```

Then the demo:

```bash
cd demo
npm install
npm run dev
```

It calls the API on `http://localhost:8000` (change with `VITE_API`). The dev server also serves the models straight from `content/`.

The demo opens on a login screen. Click one of the demo accounts to sign in:

| Account | Role | What it can do |
| --- | --- | --- |
| `admin@anatolens.dev` | SUPER_ADMIN | everything, creates non-student accounts |
| `editor@anatolens.dev` | CONTENT_EDITOR | creates lessons, starts AI drafts (`/review.html`) |
| `reviewer@anatolens.dev` | MEDICAL_REVIEWER | approves or sends back AI drafts |
| `teacher@anatolens.dev` | TEACHER | lessons, quiz, a student's results via `results.html?user=<id>` |
| `amira@` / `omar@` / `lina@anatolens.dev` | STUDENT | lessons, quiz, own results |

AI drafts pause at medical review (a LangGraph `interrupt()` on a Postgres checkpointer, so a pending review survives a restart). Only an approved draft is written to the knowledge base as `APPROVED`. A rejected draft goes back to `CONTENT_REVIEW`.

Endpoints:
- `POST /api/v1/recognition/page` (image upload)
- `GET /api/v1/lessons/{id}`, `GET /api/v1/lessons/{id}/structures`
- `POST /api/v1/structures/{id}/explain`
- `POST /api/v1/tutor/ask` (SSE)
- `/graphql`
- `POST /api/v1/auth/register|login|refresh`, `GET /api/v1/auth/me` (JWT bearer; self-registration is STUDENT only)
- `POST /api/v1/admin/lessons`, `POST /api/v1/admin/lessons/{id}/transition`, `POST /api/v1/admin/lessons/{id}/author?structure_id=`, `GET /api/v1/admin/reviews`, `POST /api/v1/admin/review/{thread_id}` (role-guarded)

## Tests

```bash
cd backend && pytest
cd demo && npm test     # playwright smoke test
```

Some backend tests need the Postgres container running, and the LLM judge test needs `OPENAI_API_KEY`. The API and GraphQL tests run without either.

## Content and license notes

The knowledge files are a dev seed I wrote to get the retrieval path working. They're marked APPROVED only so the approved-only retriever returns something; they have not been medically reviewed. Don't use this for anything real.

The 3D models are derived from BodyParts3D (CC BY 4.0), details in `content/*/assets/ATTRIBUTION.md`.
