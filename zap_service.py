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

def ensure_default_context():
    """Ensure default context exists with proper configuration"""
    try:
        # Create context if needed
        context_list = requests.get(
            f"{ZAP_URL}/JSON/context/view/contextList/?apikey={API_KEY}"
        ).json().get("contextList", [])
        
        if "Default Context" not in context_list:
            requests.get(
                f"{ZAP_URL}/JSON/context/action/newContext/?contextName=Default%20Context&apikey={API_KEY}"
            )
        
        # Enable all technologies
        requests.get(
            f"{ZAP_URL}/JSON/context/action/includeAllContextTechnologies/?contextName=Default%20Context&apikey={API_KEY}"
        )
    except Exception as e:
        raise Exception(f"Context setup failed: {str(e)}")

def verify_url_accessible(target_url):
    """Verify target URL is reachable through ZAP"""
    try:
        test_url = f"{ZAP_URL}/JSON/core/action/accessUrl/?url={urllib.parse.quote(target_url)}&apikey={API_KEY}"
        response = requests.get(test_url, timeout=10)
        return response.json().get("Result") == "OK"
    except Exception:
        return False

def add_to_context(target_url):
    """Add URL pattern to scanning context"""
    ensure_default_context()
    encoded_url = urllib.parse.quote(target_url, safe='')
    context_url = f"{ZAP_URL}/JSON/context/action/includeInContext/?contextName=Default%20Context&regex={encoded_url}.*&apikey={API_KEY}"
    response = requests.get(context_url)
    if response.status_code != 200:
        raise Exception(f"Failed to add URL to context: {response.text}")

def spider_target(target_url):
    """Run spider against target"""
    spider_url = f"{ZAP_URL}/JSON/spider/action/scan/?url={urllib.parse.quote(target_url)}&apikey={API_KEY}"
    response = requests.get(spider_url)
    if response.status_code != 200:
        raise Exception(f"Spider failed: {response.text}")
    return response.json().get("scan")

def start_active_scan(target_url):
    """Start active ZAP scan"""
    scan_url = f"{ZAP_URL}/JSON/ascan/action/scan/?url={urllib.parse.quote(target_url)}&apikey={API_KEY}"
    response = requests.get(scan_url)
    if response.status_code != 200:
        raise Exception(f"Scan failed: {response.text}")
    return response.json().get("scan")

def get_scan_status(scan_id):
    """Check scan progress"""
    status_url = f"{ZAP_URL}/JSON/ascan/view/status/?scanId={scan_id}&apikey={API_KEY}"
    try:
        response = requests.get(status_url)
        return int(response.json().get("status", 0))
    except Exception:
        return 0

def generate_report():
    """Generate HTML report"""
    try:
        report_url = f"{ZAP_URL}/OTHER/core/other/htmlreport/?apikey={API_KEY}"
        response = requests.get(report_url)
        return response.text
    except Exception:
        return "<html><body><h1>Error generating report</h1></body></html>"

def wait_for_completion(scan_id, timeout=SCAN_TIMEOUT):
    """Wait for scan completion with timeout"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = get_scan_status(scan_id)
        if status >= 100:
            return True
        time.sleep(10)
    return False

@app.route('/scan', methods=['GET'])
def scan():
    """Main scanning endpoint"""
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"status": "error", "message": "URL parameter is required"}), 400
    
    if not target_url.startswith(('http://', 'https://')):
        target_url = f"http://{target_url}"

    try:
        # Verify accessibility
        if not verify_url_accessible(target_url):
            return jsonify({"status": "error", "message": f"Target URL {target_url} is not accessible"}), 400

        # Setup context
        add_to_context(target_url)

        # Run spider
        spider_id = spider_target(target_url)
        time.sleep(5)  # Brief pause after spider

        # Start active scan
        scan_id = start_active_scan(target_url)
        
        # Wait for completion
        if not wait_for_completion(scan_id):
            return jsonify({"status": "error", "message": "Scan timed out"}), 500

        # Generate and save report
        report = generate_report()
        with open(REPORT_PATH, "w") as f:
            f.write(report)

        return send_file(REPORT_PATH, as_attachment=True, mimetype='text/html')

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health endpoint that always returns healthy"""
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    setup_environment()
    app.run(host="0.0.0.0", port=5000)