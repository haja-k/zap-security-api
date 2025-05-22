# 🎞️ At a glance 
This repository contains the API and deployment code for running ZAP (Zed Attack Proxy) scans on a centralized server. It provides a Flask-based service to initiate scans, generate reports, and download results, all containerized using Docker.


## 📝 Features
- **Automated ZAP Scanning**: Perform security scans on target URLs using OWASP ZAP.
- **RESTful API**: Initiate scans and download reports via simple HTTP endpoints.
- **Containerized Deployment**: Run the ZAP scanner and Flask service in Docker containers for easy deployment.
- **HTTPS Support**: Handles HTTPS targets with proper proxy configuration.
- **Detailed Logging**: Comprehensive logs for debugging scan failures.
- **Report Generation**: Automatically saves scan reports in HTML format to a shared volume.
- **Retry Mechanism**: Retries spider initiation to handle transient failures.

## 📂 Project Structure

- `zap_service.py`: Flask API for initiating scans and downloading reports.
- `zap_scan.py`: Standalone script for running ZAP scans (alternative to the API).
- `Dockerfile`: Dockerfile for the ZAP scanner container.
- `Dockerfile.flask`: Dockerfile for the Flask API container.
- `docker-compose.yml`: Docker Compose configuration for running both containers.
- `zap-server/reports/`: Host directory for storing ZAP reports.

## 🛠️ How to Run the Containers
### Prerequisites
- Docker and Docker Compose installed on the host machine.
- Access to the target server (e.g., `172.26.88.145`).

1. **Build and Start the Containers**
   Use Docker Compose to build and run the `zap` (ZAP scanner) and `zap-service` (Flask API) containers:
   ```bash
   docker-compose up -d --build
   ```
   - This starts:
     - `zap-scanner`: ZAP container on port `8088`.
     - `zap-flask`: Flask API container on port `5000`.

2. **Verify Containers Are Running**
   ```bash
   docker ps
   ```
   You should see `zap-scanner` and `zap-flask` containers running.

3. **Check Logs (Optional)**
   Monitor logs to ensure the containers start correctly:
   ```bash
   docker logs zap-scanner
   docker logs zap-flask
   ```

## 🌐 Test Endpoint

### Start a Scan
Initiate a ZAP scan on a target URL. The report will be automatically saved to `/zap/reports/` inside the container (mapped to `./zap-server/reports/` on the host).

#### Command
```bash
curl "http://<ip-address>:5000/scan?url=https://<application-url>"
```

#### Notes
- Replace `<application-url>` with your target URL.
- Ensure the target URL starts with `http://` or `https://`.

## 📄 Sample Response

Upon successful completion of the scan, the `/scan` endpoint returns a JSON response with the status, report path, and target URL.

### Example Response
```json
{
  "status": "completed",
  "report_path": "/zap/reports/zap_scan_20250522_1527.html",
  "target": "<application-url>"
}
```

#### Explanation
- `status`: Indicates the scan result (`completed` or `error`).
- `report_path`: Path to the generated HTML report inside the container.
- `target`: The URL that was scanned.

---

## 🔗 List of APIs

### 1. Start a Scan
- **Endpoint**: `/scan`
- **Method**: `GET`
- **Parameters**:
  - `url` (required): The target URL to scan (e.g., `https://www.google.com`).
- **Example**:
  ```bash
  curl "http://<ip-address>:5000/scan?url=<application-url>"
  ```
- **Response**:
  ```json
  {
    "status": "completed",
    "report_path": "/zap/reports/zap_scan_20250522_1527.html",
    "target": "<application-url>"
  }
  ```

### 2. Download a Report
- **Endpoint**: `/download-report`
- **Method**: `GET`
- **Parameters**:
  - `report_path` (required): The path to the report file (from the `/scan` response).
- **Example**:
  ```bash
  curl "http://<ip-address>:5000/download-report?report_path=/zap/reports/zap_scan_20250522_1527.html" --output report.html
  ```
- **Response**: Downloads the HTML report file.

### 3. Test ZAP API (Optional)
- **Endpoint**: ZAP’s API endpoint to check its version.
- **Method**: `GET`
- **Example**:
  ```bash
  curl "http://<ip-address>:8088/JSON/core/view/version/?apikey=zapp1ngk3y"
  ```
- **Response**:
  ```json
  {"version":"2.12.0"}
  ```

## ⚠️ Troubleshooting

- **Scan Fails with "Target preparation failed"**:
  - Check the logs for details:
    ```bash
    docker logs zap-flask
    docker logs zap-scanner
    ```
  - Ensure the target URL is accessible and doesn’t require authentication.
  - If authentication is needed, modify `zap_service.py` to include credentials (see ZAP documentation).

- **ZAP State Issues**:
  - Restart the ZAP container to clear its state:
    ```bash
    docker restart zap-scanner
    ```
