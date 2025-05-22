from flask import Flask, request, jsonify, send_file, abort
import requests
import time
import urllib.parse
import os
from datetime import datetime
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
ZAP_URL = "http://zap:8088"
API_KEY = "zapp1ngk3y"
REPORT_DIR = "/zap/reports"
SCAN_TIMEOUT = 1200  # 20 minutes
SPIDER_TIMEOUT = 300  # 5 minutes
SPIDER_RETRIES = 3  # Retry spider initiation up to 3 times

def setup_environment():
    """Ensure reports directory exists"""
    logger.debug(f"Creating directory {REPORT_DIR} if it doesn't exist")
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.chmod(REPORT_DIR, 0o777)

def generate_report_filename(target_url):
    """Generate timestamped report filename"""
    safe_url = target_url.replace('://', '_').replace('/', '_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"{REPORT_DIR}/zap_scan_{safe_url}_{timestamp}.html"
    logger.debug(f"Generated report filename: {report_path}")
    return report_path

def clear_zap_state():
    """Clear previous ZAP state"""
    try:
        logger.debug("Clearing ZAP sessions and contexts")
        new_session_res = requests.get(f"{ZAP_URL}/JSON/core/action/newSession/?apikey={API_KEY}")
        logger.debug(f"New session response: {new_session_res.text}, Status Code: {new_session_res.status_code}")
        remove_context_res = requests.get(f"{ZAP_URL}/JSON/context/action/removeContext/?contextName=scan_context&apikey={API_KEY}")
        logger.debug(f"Remove context response: {remove_context_res.text}, Status Code: {remove_context_res.status_code}")
    except Exception as e:
        logger.warning(f"Failed to clear ZAP state: {str(e)}")

def start_spider(target_url):
    """Start ZAP spider with retries"""
    spider_url = f"{ZAP_URL}/JSON/spider/action/scan/?url={urllib.parse.quote(target_url)}&contextName=scan_context&recurse=true&subtreeOnly=false&apikey={API_KEY}"
    for attempt in range(SPIDER_RETRIES):
        try:
            logger.debug(f"Attempt {attempt + 1}: Running spider: {target_url}")
            spider_res = requests.get(spider_url)
            logger.debug(f"Spider response: {spider_res.text}, Status Code: {spider_res.status_code}")
            if spider_res.status_code != 200:
                logger.error(f"Spider initiation failed: {spider_res.text}")
                if attempt < SPIDER_RETRIES - 1:
                    logger.debug("Retrying spider initiation after 5 seconds")
                    time.sleep(5)
                    continue
                raise Exception(f"Spider initiation failed after {SPIDER_RETRIES} attempts: {spider_res.text}")
            spider_data = spider_res.json()
            spider_id = spider_data.get('scan')
            if not spider_id:
                logger.error(f"Spider response missing 'scan' ID: {spider_data}")
                if attempt < SPIDER_RETRIES - 1:
                    logger.debug("Retrying spider initiation after 5 seconds")
                    time.sleep(5)
                    continue
                raise Exception(f"Spider response missing 'scan' ID after {SPIDER_RETRIES} attempts: {spider_data}")
            return spider_id
        except Exception as e:
            logger.error(f"Spider attempt {attempt + 1} failed: {str(e)}")
            if attempt < SPIDER_RETRIES - 1:
                logger.debug("Retrying spider initiation after 5 seconds")
                time.sleep(5)
                continue
            raise Exception(f"Spider initiation failed after {SPIDER_RETRIES} attempts: {str(e)}")

def prepare_target(target_url):
    """Set up ZAP context and spider target"""
    try:
        # Clear previous state
        clear_zap_state()

        # Create context
        logger.debug("Creating new ZAP context")
        context_res = requests.get(f"{ZAP_URL}/JSON/context/action/newContext/?contextName=scan_context&apikey={API_KEY}")
        logger.debug(f"Context creation response: {context_res.text}, Status Code: {context_res.status_code}")
        if context_res.status_code != 200:
            raise Exception(f"Context creation failed: {context_res.text}")

        # Include target in context
        logger.debug(f"Including target in context: {urllib.parse.quote(target_url)}.*")
        include_url = f"{ZAP_URL}/JSON/context/action/includeInContext/?contextName=scan_context&regex={urllib.parse.quote(target_url)}.*&apikey={API_KEY}"
        logger.debug(f"Constructed include URL: {include_url}")
        include_res = requests.get(include_url)
        logger.debug(f"Include in context response: {include_res.text}, Status Code: {include_res.status_code}")
        if include_res.status_code != 200:
            raise Exception(f"Include in context failed: {include_res.text}")

        # Start spider with retries
        spider_id = start_spider(target_url)
        logger.debug(f"Spider started with ID: {spider_id}")

        # Wait for spider to complete
        start_time = time.time()
        while time.time() - start_time < SPIDER_TIMEOUT:
            status_res = requests.get(f"{ZAP_URL}/JSON/spider/view/status/?scanId={spider_id}&apikey={API_KEY}")
            logger.debug(f"Spider status response: {status_res.text}, Status Code: {status_res.status_code}")
            if status_res.status_code != 200:
                logger.error(f"Failed to get spider status: {status_res.text}")
                raise Exception(f"Failed to get spider status: {status_res.text}")
            status = status_res.json().get('status', 0)
            logger.debug(f"Spider status: {status}%")
            if int(status) >= 100:
                break
            time.sleep(10)
        else:
            logger.error("Spider timed out")
            raise Exception("Spider timed out")

        # Verify URLs in context
        urls_res = requests.get(f"{ZAP_URL}/JSON/context/view/urls/?contextName=scan_context&apikey={API_KEY}")
        logger.debug(f"URLs in context after spidering: {urls_res.text}")
        if not urls_res.json().get('urls'):
            logger.error("No URLs found in context after spidering")
            raise Exception("No URLs found in context after spidering")

    except Exception as e:
        logger.error(f"Target preparation failed: {str(e)}")
        raise Exception(f"Target preparation failed: {str(e)}")

def run_scan(target_url):
    """Execute full scan and save report"""
    try:
        # Prepare target
        logger.debug(f"Preparing target: {target_url}")
        prepare_target(target_url)

        # Start active scan
        logger.debug("Starting active scan")
        scan_url = f"{ZAP_URL}/JSON/ascan/action/scan/?url={urllib.parse.quote(target_url)}&contextName=scan_context&recurse=true&inScopeOnly=true&apikey={API_KEY}"
        scan_res = requests.get(scan_url)
        logger.debug(f"Scan start response: {scan_res.text}, Status Code: {scan_res.status_code}")
        if scan_res.status_code != 200:
            logger.error(f"Scan failed to start: {scan_res.text}")
            raise Exception(f"Scan failed to start: {scan_res.text}")

        scan_id = scan_res.json().get("scan")
        logger.debug(f"Scan ID: {scan_id}")
        if not scan_id:
            raise Exception(f"Scan response missing 'scan' ID: {scan_res.json()}")

        # Wait for completion
        start_time = time.time()
        while time.time() - start_time < SCAN_TIMEOUT:
            status = requests.get(f"{ZAP_URL}/JSON/ascan/view/status/?scanId={scan_id}&apikey={API_KEY}").json().get("status", 0)
            logger.debug(f"Scan status: {status}%")
            if int(status) >= 100:
                break
            time.sleep(5)
        else:
            logger.error("Scan timed out")
            raise Exception("Scan timed out")

        # Generate and save report
        logger.debug("Generating HTML report")
        report = requests.get(f"{ZAP_URL}/OTHER/core/other/htmlreport/?apikey={API_KEY}").text
        report_path = generate_report_filename(target_url)

        logger.debug(f"Writing report to {report_path}")
        with open(report_path, 'w') as f:
            f.write(report)

        return {
            "status": "completed",
            "report_path": report_path,
            "target": target_url
        }

    except Exception as e:
        logger.error(f"Scan failed: {str(e)}")
        raise Exception(f"Scan failed: {str(e)}")

@app.route('/scan', methods=['GET'])
def scan():
    """Single-call scan endpoint"""
    logger.debug("Received /scan request")
    target_url = request.args.get('url')
    logger.debug(f"Requested URL: {target_url}")
    if not target_url:
        logger.error("No URL parameter provided")
        return jsonify({"status": "error", "message": "URL parameter is required"}), 400

    if not target_url.startswith(('http://', 'https://')):
        target_url = f"http://{target_url}"
        logger.debug(f"Prepended http to URL: {target_url}")

    try:
        result = run_scan(target_url)
        logger.info(f"Scan completed successfully: {result}")
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Scan failed: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/download-report', methods=['GET'])
def download_report():
    """Endpoint to download the ZAP report file"""
    logger.debug("Received /download-report request")
    report_path = request.args.get('report_path')
    logger.debug(f"Received report_path: {report_path}")

    if not report_path:
        logger.error("No report_path provided")
        abort(400, description="report_path parameter is required")

    if not os.path.exists(report_path):
        logger.error(f"File does not exist at path: {report_path}")
        abort(404, description=f"Report file not found at {report_path}")

    logger.info(f"Serving file: {report_path}")
    return send_file(report_path, as_attachment=True)

if __name__ == "__main__":
    setup_environment()
    app.run(host="0.0.0.0", port=5000)