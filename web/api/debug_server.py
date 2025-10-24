#!/usr/bin/env python3
"""
Debug server for query2.py
Run this directly to debug with breakpoints.
"""
from http.server import HTTPServer
import sys
import os

# Load environment variables
from dotenv import load_dotenv
load_dotenv()  # Load from .env
load_dotenv('.env.local')  # Load from .env.local (overrides .env)

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the handler
from query2 import handler as Query2Handler

def run_debug_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, Query2Handler)
    print(f"🐛 Debug server running on http://localhost:{port}")
    print(f"   Test with: http://localhost:{port}/api/query2?query=test&date_start=2025-01-20&date_end=2025-01-24")
    print(f"   Set breakpoints in query2.py and attach debugger!")
    httpd.serve_forever()

if __name__ == '__main__':
    run_debug_server()

