from flask import Flask, request, send_file, jsonify
import requests
import time
import urllib.parse
import os

app = Flask(__name__)

# Configuration
ZAP_URL = "http://zap:8088"
API_KEY = "zapp1ngk3y"
REPORT_DIR = "/zap/reports"
REPORT_PATH = f"{REPORT_DIR}/zap_report.html"
SCAN_TIMEOUT = 600  # 10 minutes

def setup_environment():
    """Ensure required directories exist"""
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.chmod(REPORT_DIR, 0o777)

def prepare_target(target_url):
    """Prepare target URL for scanning"""
    try:
        # 1. Create or get default context
        context_url = f"{ZAP_URL}/JSON/context/action/newContext/?contextName=Default&apikey={API_KEY}"
        requests.get(context_url)

        # 2. Include target in context
        include_url = f"{ZAP_URL}/JSON/context/action/includeInContext/?contextName=Default&regex={urllib.parse.quote(target_url)}.*&apikey={API_KEY}"
        requests.get(include_url)

        # 3. Spider the target first
        spider_url = f"{ZAP_URL}/JSON/spider/action/scan/?url={urllib.parse.quote(target_url)}&contextName=Default&apikey={API_KEY}"
        spider_res = requests.get(spider_url)
        if spider_res.status_code != 200:
            raise Exception(f"Spider failed: {spider_res.text}")

        # Wait for spider to complete
        time.sleep(5)
        return True
    except Exception as e:
        raise Exception(f"Preparation failed: {str(e)}")

def start_scan(target_url):
    """Start active scan"""
    scan_url = f"{ZAP_URL}/JSON/ascan/action/scan/?url={urllib.parse.quote(target_url)}&contextName=Default&apikey={API_KEY}"
    response = requests.get(scan_url)
    if response.status_code != 200:
        raise Exception(f"Scan failed: {response.text}")
    return response.json().get("scan")

def wait_for_scan(scan_id):
    """Wait for scan completion"""
    start_time = time.time()
    while time.time() - start_time < SCAN_TIMEOUT:
        status_url = f"{ZAP_URL}/JSON/ascan/view/status/?scanId={scan_id}&apikey={API_KEY}"
        status = requests.get(status_url).json().get("status", 0)
        if int(status) >= 100:
            return True
        time.sleep(5)
    return False

def generate_report():
    """Generate HTML report"""
    report_url = f"{ZAP_URL}/OTHER/core/other/htmlreport/?apikey={API_KEY}"
    return requests.get(report_url).text

@app.route('/scan', methods=['GET'])
def scan():
    """Scan endpoint"""
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"status": "error", "message": "URL parameter is required"}), 400

    if not target_url.startswith(('http://', 'https://')):
        target_url = f"http://{target_url}"

    try:
        # 1. Prepare target
        prepare_target(target_url)

        # 2. Start scan
        scan_id = start_scan(target_url)

        # 3. Wait for completion
        if not wait_for_scan(scan_id):
            return jsonify({"status": "error", "message": "Scan timed out"}), 500

        # 4. Generate report
        report = generate_report()
        with open(REPORT_PATH, 'w') as f:
            f.write(report)

        return send_file(REPORT_PATH, as_attachment=True)

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    setup_environment()
    app.run(host="0.0.0.0", port=5000)