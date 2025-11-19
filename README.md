## ZAP Security API

Flask + Docker service for running OWASP ZAP security scans on demand via a simple REST API. Designed for centralized, repeatable application security testing in CI/CD or ad-hoc use.

---

## Features

- **OWASP ZAP automation**: Trigger active scans against any HTTP(S) target.
- **REST API**: Start scans and download HTML reports via simple endpoints.
- **Containerized deployment**: ZAP engine and Flask API packaged in Docker, wired together with `docker-compose`.
- **Report management**: HTML reports automatically written to a shared host volume.
- **Resilient scanning**: Basic retry logic and detailed logging for troubleshooting.

---

## Project Structure

- `zap_service.py` – Flask API exposing scan and report download endpoints.
- `zap_scan.py` – Standalone ZAP scan script (no API required).
- `Dockerfile` – ZAP scanner image.
- `Dockerfile.flask` – Flask API image.
- `docker-compose.yml` – Orchestrates ZAP + Flask containers and shared volume.
- `zap-server/reports/` – Host directory where HTML reports are stored.

---

## Getting Started

### Prerequisites

- Docker
- Docker Compose
- Network access from the Docker host to your target application(s)

### 1. Configure environment

Copy `.env.example` to `.env` and update the values as needed:

```bash
cp .env.example .env
```

Edit `.env` to set your ZAP API key, timeouts, and other configuration.

### 2. Build and start the stack

From the repository root:

```bash
docker-compose up -d --build
```

This will start:

- `zap-scanner` (OWASP ZAP) on `8088`
- `zap-flask` (Flask API) on `5000`

Verify containers:

```bash
docker ps
```

(Optional) Check logs:

```bash
docker logs zap-scanner
docker logs zap-flask
```

---

## Usage

### 1. Start a scan

Trigger a scan of a target URL. The HTML report will be written to `/zap/reports/` in the container (mapped to `./zap-server/reports/` on the host).

```bash
curl "http://<host-ip>:5000/scan?url=https://<application-url>"
```

- Replace `<host-ip>` with the machine running Docker.
- Replace `<application-url>` with the target (including `http://` or `https://`).

**Sample response:**

```json
{
  "status": "completed",
  "report_path": "/zap/reports/zap_scan_20250522_1527.html",
  "target": "https://example.com"
}
```

### 2. Download a report

Use the `report_path` returned from `/scan`:

```bash
curl "http://<host-ip>:5000/download-report?report_path=/zap/reports/zap_scan_20250522_1527.html" --output report.html
```

This saves the HTML report as `report.html` locally.

### 3. Check ZAP is healthy (optional)

```bash
curl "http://<host-ip>:8088/JSON/core/view/version/?apikey=zapp1ngk3y"
```

**Expected response:**

```json
{"version":"2.12.0"}
```

---

## API Reference

### `GET /scan`

- **Description**: Starts a ZAP scan for the given URL.
- **Query parameters**:
  - `url` (required) – Target URL, e.g. `https://www.google.com`
- **Response** (`200`):

  ```json
  {
    "status": "completed" | "error",
    "report_path": "/zap/reports/zap_scan_YYYYMMDD_HHMM.html",
    "target": "<application-url>"
  }
  ```

### `GET /download-report`

- **Description**: Downloads a previously generated HTML report.
- **Query parameters**:
  - `report_path` (required) – Path returned from `/scan`
- **Response**: HTML file (use `--output` with `curl` to save it).

---

## Troubleshooting

- **Scan fails or times out**
  - Check logs:

    ```bash
    docker logs zap-flask
    docker logs zap-scanner
    ```

  - Confirm the target is reachable from the Docker host.
  - If the app requires authentication or custom headers, extend `zap_service.py` / `zap_scan.py` with the relevant ZAP authentication configuration.

- **ZAP stuck / bad state**
  - Restart the ZAP container:

    ```bash
    docker restart zap-scanner
    ```

---

## Why This Project

This project demonstrates:

- **Applied AppSec**: Automating OWASP ZAP for repeatable security testing.
- **API design**: A minimal REST interface for orchestrating security tools.
- **Containerization**: Clean separation between scanner and control plane using Docker and `docker-compose`.

It can be used as a starting point for integrating automated security scanning into CI/CD pipelines or building an internal "scan as a service" platform.
