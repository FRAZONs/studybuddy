# StudyBuddy AI

A small React and Tailwind study workspace with a FastAPI backend, SQLite notes, and a Gemini tutor. Four sample notes are created when the database is first initialized.

## Run locally

You need Python 3.13 and Node.js 22 or newer. Open two terminals in the project folder.

**Terminal 1 · FastAPI**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

On Windows PowerShell, run these commands from the project folder.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000
```

**Terminal 2 · React**

```bash
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. The interactive API reference is at <http://localhost:8000/api/docs>.

## Enable Gemini

Create a key in [Google AI Studio](https://aistudio.google.com/apikey). Set it in the terminal where FastAPI runs, then start or restart the backend.

```bash
export GEMINI_API_KEY="your-key"
```

```powershell
$env:GEMINI_API_KEY = "your-key"
```

`GEMINI_MODEL` defaults to `gemini-3.5-flash-lite` and can be overridden in the backend environment. The backend sends chat messages to Gemini and returns the reply. Notes and recommendations work without a key. Chat history stays in memory until the browser page is refreshed. Recently opened notes are stored in the browser. Notes themselves are shared by everyone who can access this demo instance.

## Try the demo

1. Open the **Docker** note and close it. The dashboard records it under **Recently viewed**.
2. Open **Recommendations**. Docker Compose, Kubernetes, and Container Networking should appear.
3. Search for **Docker** or **blueprint** to see title and content matching. Exact title and subject matches rank highest.
4. Create a note, edit it, then reload to see it persist.
5. In **AI Chat**, try “Explain Kubernetes pods simply.”

## Docker Compose

Docker Compose builds the frontend and backend, keeps the backend private to the Compose network, and stores SQLite data in a named volume. The frontend is available only on your computer at <http://localhost:8080>.

From the project root, create the ignored local environment file and add your Gemini key:

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

Set `GEMINI_API_KEY` in `backend/.env` to your key. Keep that file private; `.env` files are ignored by Git and excluded from the backend Docker build context. You can leave the key blank to use notes and recommendations without AI chat. Then start the app:

```powershell
docker compose up --build
```

Stop it with `Ctrl+C`; run `docker compose down` to stop and remove the containers. Your notes remain in the `studybuddy-data` volume. To remove the notes too, run `docker compose down --volumes`.

## Kubernetes

[`deployment.yaml`](./deployment.yaml) defines the namespace, backend and frontend Deployments/Services, backend configuration, and a persistent volume claim for SQLite. It deliberately does not contain a Gemini key. The frontend Service is internal to the cluster; use port-forwarding for a local demo.

Build the images from the project root:

```powershell
docker build -t studybuddy-backend:local -f backend\Dockerfile backend
docker build -t studybuddy-frontend:local -f frontend\Dockerfile frontend
```

Make these images available to your cluster before applying the manifest. For example, with Minikube:

```powershell
minikube image load studybuddy-backend:local
minikube image load studybuddy-frontend:local
```

On a remote cluster, push the images to a registry your cluster can access and update the two image names in `deployment.yaml`. The cluster must support persistent volume claims. Apply the manifest:

```powershell
kubectl apply -f deployment.yaml
```

To enable Gemini, create/update the Kubernetes Secret from the private local env file (created in the Compose instructions) and restart the backend so it reads the new value:

```powershell
kubectl -n studybuddy create secret generic studybuddy-secrets --from-env-file=backend/.env --dry-run=client -o yaml | kubectl apply -f -
kubectl -n studybuddy rollout restart deployment/studybuddy-backend
```

The Secret is optional if you leave chat disabled. For local access:

```powershell
kubectl -n studybuddy port-forward service/studybuddy-frontend 8080:80
```

Then open <http://localhost:8080>. The SQLite-backed API intentionally runs as one replica; this is a demo deployment, not a horizontally scalable or public production setup. Before exposing it on the internet, add authentication, TLS/Ingress, backups, and appropriate secret management. The backend also needs HTTPS egress to `generativelanguage.googleapis.com` for Gemini chat.

## API routes

| Method | Route | Purpose |
| --- | --- | --- |
| GET, POST | `/api/notes` | List and create notes |
| GET, PUT, DELETE | `/api/notes/{id}` | Read, update, and delete a note |
| GET | `/api/search?q=Docker` | Search and rank notes |
| GET | `/api/recommendations?subject=Docker` | Get suggestions from recent subjects |
| GET | `/api/chat/status` | Check if the backend has a Gemini key configured |
| POST | `/api/chat` | Send a conversation to Gemini |
| GET | `/api/health` | Check that the API and SQLite are ready |
