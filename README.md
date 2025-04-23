# 🎞️ About This Repo 
This repo is to store API &deployment codes for ZAP scan to be deployed in a centralized server.

---
## Test Usage:

### Start scan (report will be auto-saved)
```
curl "http://172.26.93.12:5000/scan?url=http://172.26.92.177:8086/"
```

### Response will include:
```
{
   "status": "completed",
   "report_path": "/zap/reports/zap_scan_http___172.26.92.177_8086_20230815_143022.html",
   "target": "http://172.26.92.177:8086/"
}
```

### Test API
```
curl "http://172.26.92.185:8088/JSON/core/view/version/?apikey=zapp1ngk3y"
```

