from flask import Flask, request, jsonify, send_file, abort
import requests
import time
import urllib.parse
import os
from datetime import datetime

app = Flask(__name__)

# Configuration
ZAP_URL = "http://zap:8088"
API_KEY = "zapp1ngk3y"
REPORT_DIR = "/zap/reports"
SCAN_TIMEOUT = 600  # 10 minutes

def setup_environment():
    """Ensure reports directory exists"""
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.chmod(REPORT_DIR, 0o777)

def generate_report_filename(target_url):
    """Generate timestamped report filename"""
    safe_url = target_url.replace('://', '_').replace('/', '_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{REPORT_DIR}/zap_scan_{safe_url}_{timestamp}.html"

def prepare_target(target_url):
    """Set up ZAP context and spider target"""
    try:
        # 1. Create context
        requests.get(f"{ZAP_URL}/JSON/context/action/newContext/?contextName=scan_context&apikey={API_KEY}")
        
        # 2. Include target
        include_url = f"{ZAP_URL}/JSON/context/action/includeInContext/?contextName=scan_context®ex={urllib.parse.quote(target_url)}.*&apikey={API_KEY}"
        requests.get(include_url)
        
        # 3. Run spider
        spider_url = f"{ZAP_URL}/JSON/spider/action/scan/?url={urllib.parse.quote(target_url)}&contextName=scan_context&apikey={API_KEY}"
        requests.get(spider_url)
        time.sleep(5)  # Let spider initialize
    except Exception as e:
        raise Exception(f"Target preparation failed: {str(e)}")

def run_scan(target_url):
    """Execute full scan and save report"""
    try:
        # 1. Prepare target
        prepare_target(target_url)
        
        # 2. Start active scan
        scan_url = f"{ZAP_URL}/JSON/ascan/action/scan/?url={urllib.parse.quote(target_url)}&contextName=scan_context&apikey={API_KEY}"
        scan_res = requests.get(scan_url)
        if scan_res.status_code != 200:
            raise Exception(f"Scan failed to start: {scan_res.text}")
        
        scan_id = scan_res.json().get("scan")
        
        # 3. Wait for completion
        start_time = time.time()
        while time.time() - start_time < SCAN_TIMEOUT:
            status = requests.get(f"{ZAP_URL}/JSON/ascan/view/status/?scanId={scan_id}&apikey={API_KEY}").json().get("status", 0)
            if int(status) >= 100:
                break
            time.sleep(5)
        else:
            raise Exception("Scan timed out")
        
        # 4. Generate and save report
        report = requests.get(f"{ZAP_URL}/OTHER/core/other/htmlreport/?apikey={API_KEY}").text
        report_path = generate_report_filename(target_url)
        
        with open(report_path, 'w') as f:
            f.write(report)
        
        return {
            "status": "completed",
            "report_path": report_path,
            "target": target_url
        }
        
    except Exception as e:
        raise Exception(f"Scan failed: {str(e)}")

@app.route('/scan', methods=['GET'])
def scan():
    """Single-call scan endpoint"""
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"status": "error", "message": "URL parameter is required"}), 400
    
    if not target_url.startswith(('http://', 'https://')):
        target_url = f"http://{target_url}"
    
    try:
        result = run_scan(target_url)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/download-report', methods=['GET'])
def download_report():
    """Endpoint to download the ZAP report file"""
    report_path = request.args.get('report_path')
    if not report_path or not os.path.exists(report_path):
        abort(404, description="Report file not found")
    return send_file(report_path, as_attachment=True)

if __name__ == "__main__":
    setup_environment()
    app.run(host="0.0.0.0", port=5000)