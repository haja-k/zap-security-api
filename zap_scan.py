import requests
import time
import urllib.parse
import sys
import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ZAP_URL = os.getenv('ZAP_URL')
API_KEY = os.getenv('ZAP_API_KEY')
REPORT_DIR = os.getenv('REPORT_DIR', "/zap/reports")
SPIDER_TIMEOUT = 300  # 5 minutes
SCAN_TIMEOUT = 1200  # 20 minutes

def clear_zap_state():
    """Clear previous ZAP state"""
    try:
        logger.debug("Clearing ZAP sessions and contexts")
        requests.get(f"{ZAP_URL}/JSON/core/action/newSession/?apikey={API_KEY}")
        requests.get(f"{ZAP_URL}/JSON/context/action/removeContext/?contextName=scan_context&apikey={API_KEY}")
    except Exception as e:
        logger.warning(f"Failed to clear ZAP state: {str(e)}")

def run_baseline_scan(target_url):
    """Baseline scan - passive only, no spider (FAST)"""
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
        
        # Get alerts
        alerts_res = requests.get(f"{ZAP_URL}/JSON/core/view/numberOfAlerts/?baseurl={urllib.parse.quote(target_url)}&apikey={API_KEY}")
        alerts_count = alerts_res.json().get('numberOfAlerts', 0)
        logger.info(f"Found {alerts_count} alerts")
        
        # Generate report
        logger.debug("Generating HTML report")
        report = requests.get(f"{ZAP_URL}/OTHER/core/other/htmlreport/?apikey={API_KEY}")
        return report.text
        
    except Exception as e:
        logger.error(f"Baseline scan failed: {str(e)}")
        return create_error_report(target_url, str(e), 'baseline')

def run_full_scan(target_url):
    """Complete scanning workflow with spider"""
    try:
        # Clear previous state
        clear_zap_state()

        # Context setup
        logger.debug("Creating new ZAP context")
        requests.get(f"{ZAP_URL}/JSON/context/action/newContext/?contextName=scan_context&apikey={API_KEY}")
        encoded_url = urllib.parse.quote(target_url + '.*')
        requests.get(f"{ZAP_URL}/JSON/context/action/includeInContext/?contextName=scan_context&regex={encoded_url}&apikey={API_KEY}")

        # Spider
        logger.debug(f"Running spider: {target_url}")
        spider = requests.get(f"{ZAP_URL}/JSON/spider/action/scan/?url={urllib.parse.quote(target_url)}&contextName=scan_context&recurse=true&subtreeOnly=false&apikey={API_KEY}")
        spider_id = spider.json().get("scan")
        
        if not spider_id:
            logger.warning("Spider failed to start, falling back to baseline scan")
            return run_baseline_scan(target_url)
        
        start_time = time.time()
        while time.time() - start_time < SPIDER_TIMEOUT:
            status = requests.get(f"{ZAP_URL}/JSON/spider/view/status/?scanId={spider_id}&apikey={API_KEY}").json().get('status', 0)
            logger.debug(f"Spider status: {status}%")
            if int(status) >= 100:
                break
            time.sleep(10)
        else:
            logger.warning("Spider timed out, proceeding with baseline scan")
            return run_baseline_scan(target_url)

        # Verify URLs in context
        urls_res = requests.get(f"{ZAP_URL}/JSON/context/view/urls/?contextName=scan_context&apikey={API_KEY}")
        logger.debug(f"URLs in context after spidering: {urls_res.text}")
        if not urls_res.json().get('urls'):
            logger.warning("No URLs found in context after spidering, using baseline scan")
            return run_baseline_scan(target_url)

        # Active Scan
        logger.debug("Starting active scan")
        scan = requests.get(f"{ZAP_URL}/JSON/ascan/action/scan/?url={urllib.parse.quote(target_url)}&contextName=scan_context&recurse=true&inScopeOnly=true&apikey={API_KEY}")
        scan_id = scan.json().get("scan")
        
        if not scan_id:
            logger.warning("Active scan failed to start")
            return run_baseline_scan(target_url)

        # Wait for completion
        start_time = time.time()
        while time.time() - start_time < SCAN_TIMEOUT:
            status = requests.get(f"{ZAP_URL}/JSON/ascan/view/status/?scanId={scan_id}&apikey={API_KEY}").json().get('status', 0)
            logger.debug(f"Scan status: {status}%")
            if int(status) >= 100:
                break
            time.sleep(10)
        else:
            logger.warning("Active scan timed out, generating partial report")

        # Generate report
        logger.debug("Generating HTML report")
        report = requests.get(f"{ZAP_URL}/OTHER/core/other/htmlreport/?apikey={API_KEY}")
        return report.text

    except Exception as e:
        logger.error(f"Full scan failed: {str(e)}, falling back to baseline")
        return run_baseline_scan(target_url)

def create_error_report(target_url, error_msg, mode='full'):
    """Create a minimal error report"""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>ZAP Scan Error Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .error {{ background-color: #fee; border: 1px solid #fcc; padding: 20px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>ZAP Security Scan - Error</h1>
    <div class="error">
        <p><strong>Target:</strong> {target_url}</p>
        <p><strong>Mode:</strong> {mode}</p>
        <p><strong>Error:</strong> {error_msg}</p>
        <p><strong>Time:</strong> {datetime.now().isoformat()}</p>
    </div>
</body>
</html>
    """
    return html

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python zap_scan.py <target_url> [mode]")
        print("Modes: baseline (default), full")
        sys.exit(1)

    target_url = sys.argv[1]
    scan_mode = sys.argv[2] if len(sys.argv) > 2 else 'baseline'
    
    # Ensure reports directory exists
    os.makedirs(REPORT_DIR, exist_ok=True)
    
    # Run scan based on mode
    if scan_mode == 'baseline':
        logger.info(f"Running baseline scan on {target_url}")
        result = run_baseline_scan(target_url)
    else:
        logger.info(f"Running full scan on {target_url}")
        result = run_full_scan(target_url)
    
    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"{REPORT_DIR}/zap_report_{scan_mode}_{timestamp}.html"
    
    with open(report_path, "w") as f:
        f.write(result if isinstance(result, str) else "Scan completed but no report generated")
    
    print(f"Scan completed. Report saved to {report_path}")