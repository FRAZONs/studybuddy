# StudyBuddy AI

StudyBuddy is a React study workspace backed by six independently runnable backend services: an API gateway, authentication/users, notes, search, recommendations, and the Gemini AI tutor. The demo uses SQLite and Docker Compose or Kubernetes for orchestration.

## Run locally with Docker Compose

Install Docker Desktop and start its engine. From the project root, preserve any existing Gemini key and add private auth settings to the ignored `backend/.env` file:

```powershell
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
$envFile = Get-Content backend\.env
if (-not ($envFile -match '^AUTH_TOKEN_SECRET=')) {
  $secret = python -c "import secrets; print(secrets.token_urlsafe(48))"
  Add-Content backend\.env "AUTH_TOKEN_SECRET=$secret"
  Remove-Variable secret
}
notepad backend\.env
```

In `backend/.env`, set a private `AUTH_ADMIN_USERNAME` and an `AUTH_ADMIN_PASSWORD` of at least 12 characters. Keep your Gemini key in `GEMINI_API_KEY`. The token secret must be at least 32 characters. Do not commit or share this file; it is Git-ignored. Compose passes the Gemini key only to the tutor service, while the auth token secret is shared with the services that validate user sessions.

Start the app:

```powershell
docker compose --env-file backend/.env up --build
```

Open <http://localhost:8080> and sign in with the configured admin account. The frontend is served on port 8080; the API gateway is available on localhost port 8081 for local frontend development. API health is at <http://localhost:8081/api/health>.

Stop with `Ctrl+C`, then run `docker compose down`. Notes and users persist in their separate `studybuddy-notes-data` and `studybuddy-auth-data` volumes. `docker compose down --volumes` also deletes them.

### Services

| Service | Responsibility |
| --- | --- |
| `studybuddy-gateway` | Routes `/api/*` to the appropriate internal service |
| `studybuddy-auth` | Admin bootstrap, sign-in, signed sessions, and admin-managed users |
| `studybuddy-notes` | User-owned note CRUD and SQLite persistence |
| `studybuddy-search` | Ranks a signed-in user's notes via the Notes service |
| `studybuddy-recommendations` | Suggests study topics based on recently opened subjects |
| `studybuddy-tutor` | Gemini chat grounded by [`backend/app_knowledge.txt`](./backend/app_knowledge.txt) |

The React frontend is an additional service, not counted among the six backend microservices. Protected service APIs require a bearer token. Accounts are admin-provisioned; public signup is disabled. To create a student account, sign in as the configured admin, open the **Users** page, and set a username and temporary password of at least 12 characters.

The API key is read only by the tutor service. Never put it in React code or commit it. The tutor reads `backend/app_knowledge.txt` on each chat request; edit the file and rebuild/restart the tutor container to publish knowledge changes.

## Kubernetes

[`deployment.yaml`](./deployment.yaml) defines the namespace, six backend Deployments/Services, the frontend, separate persistent volume claims for Notes and Auth, and gateway routing. It intentionally contains no API key or signing secret. The backend data services use one replica each because this demo uses SQLite.

Build the five Python service images from the project root:

```powershell
docker build -t studybuddy-notes:local --build-arg SERVICE=notes -f backend\Dockerfile backend
docker build -t studybuddy-search:local --build-arg SERVICE=search -f backend\Dockerfile backend
docker build -t studybuddy-recommendations:local --build-arg SERVICE=recommendations -f backend\Dockerfile backend
docker build -t studybuddy-tutor:local --build-arg SERVICE=tutor -f backend\Dockerfile backend
docker build -t studybuddy-auth:local --build-arg SERVICE=auth -f backend\Dockerfile backend
docker build -t studybuddy-frontend:local -f frontend\Dockerfile frontend
```

Load the images into a local cluster such as Minikube:

```powershell
minikube image load studybuddy-notes:local
minikube image load studybuddy-search:local
minikube image load studybuddy-recommendations:local
minikube image load studybuddy-tutor:local
minikube image load studybuddy-auth:local
minikube image load studybuddy-frontend:local
```

For a remote cluster, push the images to a registry it can access and update the image names in the manifest. Create the namespace and secret before applying the workloads. The auth token secret is required by the services; Gemini is optional. For a shared cluster, prefer your cluster's secret manager instead of sending a local env file.

```powershell
kubectl create namespace studybuddy --dry-run=client -o yaml | kubectl apply -f -
kubectl -n studybuddy create secret generic studybuddy-secrets --from-env-file=backend/.env --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f deployment.yaml
```

When you rotate or change secret values, update the Secret and restart workloads so the containers receive the new values:

```powershell
kubectl -n studybuddy create secret generic studybuddy-secrets --from-env-file=backend/.env --dry-run=client -o yaml | kubectl apply -f -
kubectl -n studybuddy rollout restart deployment
```

For a local demo, port-forward the frontend:

```powershell
kubectl -n studybuddy port-forward service/studybuddy-frontend 8080:80
```

Open <http://localhost:8080>. The cluster must support persistent volume claims and HTTPS egress to `generativelanguage.googleapis.com` for Gemini. This is a demo deployment, not a public production setup; add TLS/Ingress, backups, network policies, and operational secret management before exposing it publicly.

## API routes

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/auth/status` | Check whether auth is configured |
| POST | `/api/auth/login` | Sign in and receive a bearer token |
| GET | `/api/auth/me` | Get the signed-in user |
| GET, POST | `/api/auth/users` | Admin list/create accounts |
| GET, POST | `/api/notes` | List and create the signed-in user's notes |
| GET, PUT, DELETE | `/api/notes/{id}` | Read, update, and delete an owned note |
| GET | `/api/search?q=Docker` | Search the signed-in user's notes |
| GET | `/api/recommendations?subject=Docker` | Get subject-related suggestions |
| GET | `/api/chat/status` | Check whether the tutor has a Gemini key |
| POST | `/api/chat` | Send a conversation to Gemini |
| GET | `/api/health` | Check gateway health |
