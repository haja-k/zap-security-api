import requests
import time
import urllib.parse
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ZAP_URL = "http://localhost:8088"
API_KEY = "zapp1ngk3y"
SPIDER_TIMEOUT = 300  # 5 minutes

def clear_zap_state():
    """Clear previous ZAP state"""
    try:
        logger.debug("Clearing ZAP sessions and contexts")
        requests.get(f"{ZAP_URL}/JSON/core/action/newSession/?apikey={API_KEY}")
        requests.get(f"{ZAP_URL}/JSON/context/action/removeContext/?contextName=scan_context&apikey={API_KEY}")
    except Exception as e:
        logger.warning(f"Failed to clear ZAP state: {str(e)}")

def run_full_scan(target_url):
    """Complete scanning workflow"""
    try:
        # Clear previous state
        clear_zap_state()

        # Context setup
        logger.debug("Creating new ZAP context")
        requests.get(f"{ZAP_URL}/JSON/context/action/newContext/?contextName=scan_context&apikey={API_KEY}")
        encoded_url = urllib.parse.quote(target_url + '.*')
        requests.get(f"{ZAP_URL}/JSON/context/action/includeInContext/?contextName=scan_context®ex={encoded_url}&apikey={API_KEY}")

        # Spider
        logger.debug(f"Running spider: {target_url}")
        spider = requests.get(f"{ZAP_URL}/JSON/spider/action/scan/?url={urllib.parse.quote(target_url)}&contextName=scan_context&recurse=true&subtreeOnly=false&apikey={API_KEY}")
        spider_id = spider.json().get("scan")
        start_time = time.time()
        while time.time() - start_time < SPIDER_TIMEOUT:
            status = requests.get(f"{ZAP_URL}/JSON/spider/view/status/?scanId={spider_id}&apikey={API_KEY}").json().get('status', 0)
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

        # Active Scan
        logger.debug("Starting active scan")
        scan = requests.get(f"{ZAP_URL}/JSON/ascan/action/scan/?url={urllib.parse.quote(target_url)}&contextName=scan_context&recurse=true&inScopeOnly=true&apikey={API_KEY}")
        scan_id = scan.json().get("scan")

        # Wait for completion
        while True:
            status = requests.get(f"{ZAP_URL}/JSON/ascan/view/status/?scanId={scan_id}&apikey={API_KEY}").json().get('status', 0)
            logger.debug(f"Scan status: {status}%")
            if int(status) >= 100:
                break
            time.sleep(10)

        # Generate report
        logger.debug("Generating HTML report")
        report = requests.get(f"{ZAP_URL}/OTHER/core/other/htmlreport/?apikey={API_KEY}")
        return report.text

    except Exception as e:
        logger.error(f"Scan failed: {str(e)}")
        return f"Scan failed: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python zap_scan.py <target_url>")
        sys.exit(1)

    result = run_full_scan(sys.argv[1])
    with open("/zap/reports/zap_report.html", "w") as f:
        f.write(result if isinstance(result, str) else "Scan completed but no report generated")
    print("Scan completed. Report saved to /zap/reports/zap_report.html")