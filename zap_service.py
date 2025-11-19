from flask import Flask, request, jsonify, send_file, abort
import requests
import time
import urllib.parse
import os
from datetime import datetime
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration from environment variables with defaults
ZAP_URL = os.getenv("ZAP_URL", "http://zap:8088")
API_KEY = os.getenv("API_KEY")
REPORT_DIR = os.getenv("REPORT_DIR", "/zap/reports")
SCAN_TIMEOUT = int(os.getenv("SCAN_TIMEOUT", "1200"))  # 20 minutes
SPIDER_TIMEOUT = int(os.getenv("SPIDER_TIMEOUT", "300"))  # 5 minutes
SPIDER_RETRIES = int(os.getenv("SPIDER_RETRIES", "3"))  # Retry spider initiation up to 3 times

# Scan modes
SCAN_MODE_BASELINE = 'baseline'  # Fast passive scan, no spider
SCAN_MODE_QUICK = 'quick'        # Limited spider + active scan
SCAN_MODE_FULL = 'full'          # Full spider + comprehensive scan

def setup_environment():
    """Ensure reports directory exists"""
    logger.debug(f"Creating directory {REPORT_DIR} if it doesn't exist")
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.chmod(REPORT_DIR, 0o777)

def generate_report_filename(target_url, mode='baseline'):
    """Generate timestamped report filename"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"zap_report_{mode}_{timestamp}.html"
    report_path = os.path.join(REPORT_DIR, report_filename)
    logger.debug(f"Generated report filename: {report_path}")
    return report_path, report_filename

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

def run_baseline_scan(target_url):
    """Execute baseline scan - passive only, no spider (FAST)"""
    try:
        logger.info(f"Running baseline scan on {target_url}")
        
        # Access URL through ZAP proxy (triggers passive scanning)
        logger.debug("Accessing target URL through ZAP...")
        access_url = f"{ZAP_URL}/JSON/core/action/accessUrl/?url={urllib.parse.quote(target_url)}&apikey={API_KEY}"
        access_res = requests.get(access_url, timeout=30)
        logger.debug(f"Access URL response: {access_res.text}, Status: {access_res.status_code}")
        
        # Give passive scanners time to finish
        logger.debug("Waiting for passive scanners...")
        time.sleep(5)
        
        # Get alerts count
        alerts_res = requests.get(f"{ZAP_URL}/JSON/core/view/numberOfAlerts/?baseurl={urllib.parse.quote(target_url)}&apikey={API_KEY}")
        alerts_count = alerts_res.json().get('numberOfAlerts', 0)
        logger.info(f"Found {alerts_count} alerts")
        
        # Generate report
        logger.debug("Generating HTML report")
        report = requests.get(f"{ZAP_URL}/OTHER/core/other/htmlreport/?apikey={API_KEY}").text
        report_path, report_filename = generate_report_filename(target_url, 'baseline')
        
        logger.debug(f"Writing report to {report_path}")
        with open(report_path, 'w') as f:
            f.write(report)
        
        return {
            "success": True,
            "status": "completed",
            "report_path": report_filename,
            "scan_id": "baseline",
            "alerts_count": alerts_count,
            "mode": "baseline"
        }
    
    except Exception as e:
        logger.error(f"Baseline scan failed: {str(e)}")
        # Create error report
        report_path, report_filename = generate_report_filename(target_url, 'baseline')
        create_error_report(report_path, target_url, str(e), 'baseline')
        return {
            "success": False,
            "status": "failed",
            "error": str(e),
            "report_path": report_filename
        }

def run_quick_scan(target_url):
    """Execute quick scan with limited spider and active scanning"""
    try:
        logger.info(f"Running quick scan on {target_url}")
        
        # Prepare target (includes spider)
        logger.debug(f"Preparing target: {target_url}")
        prepare_target(target_url)
        
        # Start active scan with light policy
        logger.debug("Starting quick active scan")
        scan_url = f"{ZAP_URL}/JSON/ascan/action/scan/?url={urllib.parse.quote(target_url)}&contextName=scan_context&recurse=true&inScopeOnly=true&apikey={API_KEY}"
        scan_res = requests.get(scan_url)
        logger.debug(f"Scan start response: {scan_res.text}, Status Code: {scan_res.status_code}")
        
        if scan_res.status_code != 200:
            raise Exception(f"Scan failed to start: {scan_res.text}")
        
        scan_id = scan_res.json().get("scan")
        if not scan_id:
            raise Exception(f"Scan response missing 'scan' ID: {scan_res.json()}")
        
        # Wait for completion (shorter timeout for quick scan)
        start_time = time.time()
        timeout = 600  # 10 minutes for quick scan
        while time.time() - start_time < timeout:
            status = requests.get(f"{ZAP_URL}/JSON/ascan/view/status/?scanId={scan_id}&apikey={API_KEY}").json().get("status", 0)
            logger.debug(f"Scan status: {status}%")
            if int(status) >= 100:
                break
            time.sleep(5)
        else:
            logger.warning("Quick scan timed out, generating partial report")
        
        # Get alerts count
        alerts_res = requests.get(f"{ZAP_URL}/JSON/core/view/numberOfAlerts/?baseurl={urllib.parse.quote(target_url)}&apikey={API_KEY}")
        alerts_count = alerts_res.json().get('numberOfAlerts', 0)
        
        # Generate report
        logger.debug("Generating HTML report")
        report = requests.get(f"{ZAP_URL}/OTHER/core/other/htmlreport/?apikey={API_KEY}").text
        report_path, report_filename = generate_report_filename(target_url, 'quick')
        
        with open(report_path, 'w') as f:
            f.write(report)
        
        return {
            "success": True,
            "status": "completed",
            "report_path": report_filename,
            "scan_id": scan_id,
            "alerts_count": alerts_count,
            "mode": "quick"
        }
    
    except Exception as e:
        logger.error(f"Quick scan failed: {str(e)}")
        report_path, report_filename = generate_report_filename(target_url, 'quick')
        create_error_report(report_path, target_url, str(e), 'quick')
        return {
            "success": False,
            "status": "failed",
            "error": str(e),
            "report_path": report_filename
        }

def run_full_scan(target_url):
    """Execute full comprehensive scan"""
    try:
        logger.info(f"Running full scan on {target_url}")
        
        # Prepare target
        logger.debug(f"Preparing target: {target_url}")
        prepare_target(target_url)
        
        # Start active scan
        logger.debug("Starting full active scan")
        scan_url = f"{ZAP_URL}/JSON/ascan/action/scan/?url={urllib.parse.quote(target_url)}&contextName=scan_context&recurse=true&inScopeOnly=true&apikey={API_KEY}"
        scan_res = requests.get(scan_url)
        logger.debug(f"Scan start response: {scan_res.text}, Status Code: {scan_res.status_code}")
        
        if scan_res.status_code != 200:
            raise Exception(f"Scan failed to start: {scan_res.text}")
        
        scan_id = scan_res.json().get("scan")
        if not scan_id:
            raise Exception(f"Scan response missing 'scan' ID: {scan_res.json()}")
        
        # Wait for completion
        start_time = time.time()
        while time.time() - start_time < SCAN_TIMEOUT:
            status = requests.get(f"{ZAP_URL}/JSON/ascan/view/status/?scanId={scan_id}&apikey={API_KEY}").json().get("status", 0)
            logger.debug(f"Scan status: {status}%")
            if int(status) >= 100:
                break
            time.sleep(10)
        else:
            logger.warning("Full scan timed out, generating partial report")
        
        # Get alerts count
        alerts_res = requests.get(f"{ZAP_URL}/JSON/core/view/numberOfAlerts/?baseurl={urllib.parse.quote(target_url)}&apikey={API_KEY}")
        alerts_count = alerts_res.json().get('numberOfAlerts', 0)
        
        # Generate report
        logger.debug("Generating HTML report")
        report = requests.get(f"{ZAP_URL}/OTHER/core/other/htmlreport/?apikey={API_KEY}").text
        report_path, report_filename = generate_report_filename(target_url, 'full')
        
        with open(report_path, 'w') as f:
            f.write(report)
        
        return {
            "success": True,
            "status": "completed",
            "report_path": report_filename,
            "scan_id": scan_id,
            "alerts_count": alerts_count,
            "mode": "full"
        }
    
    except Exception as e:
        logger.error(f"Full scan failed: {str(e)}")
        report_path, report_filename = generate_report_filename(target_url, 'full')
        create_error_report(report_path, target_url, str(e), 'full')
        return {
            "success": False,
            "status": "failed",
            "error": str(e),
            "report_path": report_filename
        }

def create_error_report(report_path, target_url, error_msg, mode):
    """Create a minimal error report when scan fails"""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>ZAP Scan Error Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .error {{ background-color: #fee; border: 1px solid #fcc; padding: 20px; border-radius: 5px; }}
        .info {{ background-color: #eef; border: 1px solid #ccf; padding: 15px; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>ZAP Security Scan - Error</h1>
    <div class="error">
        <h2>Scan Failed</h2>
        <p><strong>Error:</strong> {error_msg}</p>
    </div>
    <div class="info">
        <p><strong>Target:</strong> {target_url}</p>
        <p><strong>Scan Mode:</strong> {mode}</p>
        <p><strong>Time:</strong> {datetime.now().isoformat()}</p>
    </div>
    <h3>Common Reasons for Failure:</h3>
    <ul>
        <li>Target URL requires authentication</li>
        <li>Target URL is not accessible from ZAP server</li>
        <li>Target URL blocks automated scanning (anti-bot protection)</li>
        <li>Network connectivity issues</li>
        <li>Target application is down or slow to respond</li>
    </ul>
    <h3>Recommendations:</h3>
    <ul>
        <li>Try using <strong>baseline</strong> mode for authenticated apps</li>
        <li>Verify the target URL is accessible</li>
        <li>Check ZAP server logs for more details</li>
        <li>Consider configuring authentication in ZAP</li>
    </ul>
</body>
</html>
    """
    try:
        with open(report_path, 'w') as f:
            f.write(html)
        logger.info(f"Created error report at {report_path}")
    except Exception as e:
        logger.error(f"Failed to create error report: {str(e)}")

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        # Check ZAP connection
        version_res = requests.get(f"{ZAP_URL}/JSON/core/view/version/?apikey={API_KEY}", timeout=5)
        if version_res.status_code == 200:
            version = version_res.json().get('version', 'unknown')
            return jsonify({
                'status': 'healthy',
                'zap_version': version,
                'timestamp': datetime.now().isoformat()
            }), 200
        else:
            return jsonify({
                'status': 'unhealthy',
                'error': 'ZAP not responding'
            }), 503
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503

@app.route('/scan', methods=['GET', 'POST'])
def scan():
    """Scan endpoint supporting multiple modes"""
    logger.debug("Received /scan request")
    
    # Get parameters from GET or POST
    if request.method == 'POST':
        data = request.get_json() or {}
        target_url = data.get('url')
        scan_mode = data.get('mode', SCAN_MODE_BASELINE)
    else:
        target_url = request.args.get('url')
        scan_mode = request.args.get('mode', SCAN_MODE_BASELINE)
    
    logger.debug(f"Requested URL: {target_url}, Mode: {scan_mode}")
    
    if not target_url:
        logger.error("No URL parameter provided")
        return jsonify({
            "status": "error",
            "message": "URL parameter is required"
        }), 400
    
    if not target_url.startswith(('http://', 'https://')):
        target_url = f"https://{target_url}"
        logger.debug(f"Prepended https to URL: {target_url}")
    
    # Validate scan mode
    if scan_mode not in [SCAN_MODE_BASELINE, SCAN_MODE_QUICK, SCAN_MODE_FULL]:
        logger.error(f"Invalid scan mode: {scan_mode}")
        return jsonify({
            "status": "error",
            "message": f"Invalid scan mode. Use: {SCAN_MODE_BASELINE}, {SCAN_MODE_QUICK}, or {SCAN_MODE_FULL}"
        }), 400
    
    try:
        # Execute scan based on mode
        logger.info(f"Starting {scan_mode} scan for {target_url}")
        
        if scan_mode == SCAN_MODE_BASELINE:
            result = run_baseline_scan(target_url)
        elif scan_mode == SCAN_MODE_QUICK:
            result = run_quick_scan(target_url)
        elif scan_mode == SCAN_MODE_FULL:
            result = run_full_scan(target_url)
        
        if result.get('success'):
            logger.info(f"Scan completed successfully: {result}")
            return jsonify(result), 200
        else:
            logger.error(f"Scan failed: {result.get('error')}")
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Scan exception: {str(e)}")
        return jsonify({
            "status": "failed",
            "error": str(e)
        }), 500

@app.route('/download-report', methods=['GET'])
def download_report():
    """Endpoint to download the ZAP report file"""
    logger.debug("Received /download-report request")
    report_path = request.args.get('report_path')
    logger.debug(f"Received report_path: {report_path}")

    if not report_path:
        logger.error("No report_path provided")
        abort(400, description="report_path parameter is required")
    
    # Security: prevent directory traversal - use only the filename
    report_filename = os.path.basename(report_path)
    full_path = os.path.join(REPORT_DIR, report_filename)
    logger.debug(f"Full path: {full_path}")

    if not os.path.exists(full_path):
        logger.error(f"File does not exist at path: {full_path}")
        abort(404, description=f"Report file not found: {report_filename}")

    logger.info(f"Serving file: {full_path}")
    return send_file(full_path, 
                    mimetype='text/html',
                    as_attachment=True,
                    download_name='zap-security-report.html')

if __name__ == "__main__":
    setup_environment()
    app.run(host="0.0.0.0", port=5000)