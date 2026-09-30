# NorthStar startup scripts

These Windows scripts restart the project using the repository's `.venv`.

## First-time setup

From the project root:

```bat
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
copy .env.example .env
```

Fill in `.env` with the Azure Foundry agent names, endpoint, and ServiceNow credentials. Authenticate Azure once:

```bat
az login --scope https://ai.azure.com/.default
```

## Start the app

Open two Command Prompt windows from the project root and run one command in each:

```bat
scripts\start-backend.cmd
```

```bat
scripts\start-frontend.cmd
```

The backend runs at `http://localhost:8000`; the frontend runs at the Vite URL, normally `http://localhost:5173`.

`start-backend.cmd` always calls `.venv\Scripts\activate.bat` and starts Uvicorn with the venv's Python. It also checks that `.env` exists.

## Verify the backend

In a third terminal:

```bat
curl http://localhost:8000/api/health
```

Expected:

```json
{"status":"ok"}
```

## Run the live headless check

From `backend` in an activated venv, run:

```bat
python run_scenario3.py
```

This uses live Foundry agents and creates a real ServiceNow ticket. Do not run it as a routine startup check.
