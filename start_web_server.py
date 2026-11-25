#!/usr/bin/env python3
"""
Lightweight Web Server Launcher for Genomic BAM Coverage Dashboard.
Starts a local HTTP server and automatically opens web_dashboard.html in your default web browser.
"""

import os
import sys
import webbrowser
import http.server
import socketserver

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)


def main():
    url = f"http://localhost:{PORT}/web_dashboard.html"
    print("\n" + "="*70)
    print("  GENOMIC BAM COVERAGE ON HADOOP - WEB DASHBOARD SERVER")
    print("="*70)
    print(f"[*] Serving web dashboard from: {DIRECTORY}")
    print(f"[*] Dashboard URL: {url}")
    print("[*] Opening your default web browser...")
    print("[*] Press Ctrl + C to stop the local web server anytime.\n")

    webbrowser.open(url)

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[+] Web server stopped.")


if __name__ == "__main__":
    main()
