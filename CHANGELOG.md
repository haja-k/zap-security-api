# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-11-19

### Added
- **Environment Configuration**: Added `.env` file support for configurable settings (ZAP URL, API key, timeouts, etc.) using `python-dotenv`
- **Multiple Scan Modes**: Implemented three scan modes in `zap_service.py`:
  - `baseline`: Fast passive-only scanning (no spider)
  - `quick`: Limited spidering + active scanning (10-minute timeout)
  - `full`: Comprehensive spidering + full active scanning (20-minute timeout)
- **Health Check Endpoint**: New `/health` endpoint to verify ZAP connectivity and version
- **Error Report Generation**: Automatic HTML error reports when scans fail, with troubleshooting guidance
- **Requirements Management**: Created `requirements.txt` with pinned versions for Flask, requests, and python-dotenv
- **Enhanced Logging**: Improved logging throughout the application with structured messages
- **Security Improvements**: Added directory traversal protection in report downloads

### Changed
- **README.md Rewrite**: Completely rewrote documentation for clarity, conciseness, and recruiter appeal with step-by-step setup and usage
- **Docker Configuration**: Updated `Dockerfile.flask` to install from `requirements.txt` instead of hardcoded packages
- **Docker Compose Enhancements**: Added environment variable support, configurable ports/limits, and network isolation
- **API Improvements**: Enhanced `/scan` endpoint to support POST requests and multiple scan modes
- **Report Naming**: Changed to mode-specific timestamps (e.g., `zap_report_baseline_20251119_143000.html`)
- **Standalone Script**: Updated `zap_scan.py` to use environment variables and support baseline/full modes with fallback logic

### Fixed
- **Scan Reliability**: Added retry logic for spider initiation and fallback to baseline scans on failures
- **Timeout Handling**: Implemented proper timeouts for different scan modes to prevent indefinite hangs
- **Error Handling**: Better exception handling with detailed error messages and partial report generation
- **URL Validation**: Improved URL preprocessing and validation in scan endpoints

### Technical Details
- **Dependencies**: Added `python-dotenv==1.0.0` for environment variable loading
- **Environment Variables**: All configuration now supports `.env` with sensible defaults
- **Container Networking**: Added dedicated Docker network for service communication
- **Resource Limits**: Made CPU/memory limits configurable via environment variables