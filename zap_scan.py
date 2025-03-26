import requests
import time
import urllib.parse
import sys

ZAP_URL = "http://localhost:8088"
API_KEY = "zapp1ngk3y"

def run_full_scan(target_url):
    """Complete scanning workflow"""
    try:
        # 1. Context setup
        requests.get(f"{ZAP_URL}/JSON/context/action/newContext/?contextName=scan_context&apikey={API_KEY}")
        encoded_url = urllib.parse.quote(target_url + '.*')
        requests.get(f"{ZAP_URL}/JSON/context/action/includeInContext/?contextName=scan_context&regex={encoded_url}&apikey={API_KEY}")
        
        # 2. Spider
        spider = requests.get(f"{ZAP_URL}/JSON/spider/action/scan/?url={urllib.parse.quote(target_url)}&apikey={API_KEY}")
        time.sleep(5)
        
        # 3. Active Scan
        scan = requests.get(f"{ZAP_URL}/JSON/ascan/action/scan/?url={urllib.parse.quote(target_url)}&apikey={API_KEY}")
        scan_id = scan.json().get("scan")
        
        # 4. Wait for completion
        while True:
            status = requests.get(f"{ZAP_URL}/JSON/ascan/view/status/?scanId={scan_id}&apikey={API_KEY}")
            if status.json().get("status") == "100":
                break
            time.sleep(10)
        
        # 5. Generate report
        report = requests.get(f"{ZAP_URL}/OTHER/core/other/htmlreport/?apikey={API_KEY}")
        return report.text
    
    except Exception as e:
        return f"Scan failed: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python zap_scan.py <target_url>")
        sys.exit(1)
    
    result = run_full_scan(sys.argv[1])
    with open("/zap/reports/zap_report.html", "w") as f:
        f.write(result if isinstance(result, str) else "Scan completed but no report generated")
    print("Scan completed. Report saved to /zap/reports/zap_report.html")