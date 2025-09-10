"""
Shutdown API for WPP Streamlit application.
Creates a custom endpoint that JavaScript can call to signal shutdown.
"""

import json
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


class ShutdownAPIHandler(BaseHTTPRequestHandler):
    """HTTP handler for shutdown API requests."""

    def do_POST(self):
        """Handle POST requests to shutdown and heartbeat endpoints."""
        parsed_path = urlparse(self.path)
        print(f"API received POST request to: {parsed_path.path}")

        if parsed_path.path == "/wpp-shutdown":
            self._handle_shutdown()
        elif parsed_path.path == "/wpp-heartbeat":
            self._handle_heartbeat()
        else:
            print(f"Unknown endpoint requested: {parsed_path.path}")
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        """Handle GET requests for testing and image-based shutdown."""
        parsed_path = urlparse(self.path)
        print(f"API received GET request to: {parsed_path.path}")

        if parsed_path.path == "/wpp-status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            response = {"status": "running", "timestamp": time.time()}
            self.wfile.write(json.dumps(response).encode("utf-8"))
        elif parsed_path.path == "/wpp-shutdown":
            # Handle GET-based shutdown (for image fallback)
            query_params = parse_qs(parsed_path.query)
            reason = query_params.get("reason", ["unknown"])[0]
            print(f"Shutdown API called via GET: {reason}")

            # Send response
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"shutdown initiated")

            # Trigger shutdown in a separate thread
            threading.Thread(target=self._trigger_shutdown, args=(reason,), daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_shutdown(self):
        """Handle shutdown requests."""
        try:
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length).decode("utf-8")

            try:
                data = json.loads(post_data) if post_data else {}
            except json.JSONDecodeError:
                data = {}

            reason = data.get("reason", "unknown")
            print(f"Shutdown API called: {reason}")

            # Send response
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")  # Allow CORS
            self.end_headers()

            response = {"status": "shutdown_initiated", "reason": reason}
            self.wfile.write(json.dumps(response).encode("utf-8"))

            # Trigger shutdown in a separate thread to avoid blocking the response
            threading.Thread(target=self._trigger_shutdown, args=(reason,), daemon=True).start()

        except Exception as e:
            print(f"Error in shutdown API: {e}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def _handle_heartbeat(self):
        """Handle heartbeat requests."""
        try:
            # Read request body to get additional info
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length).decode("utf-8")
                try:
                    data = json.loads(post_data)
                    print(f"Heartbeat received: visible={data.get('visible', 'unknown')}, type={data.get('type', 'unknown')}")
                except json.JSONDecodeError:
                    print("Heartbeat received (invalid JSON)")
            else:
                print("Heartbeat received (no content)")

            # Update heartbeat timestamp in the server
            if hasattr(self.server, "api_server_instance"):
                self.server.api_server_instance.update_heartbeat()

            # Send response
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")  # Allow CORS
            self.end_headers()

            response = {"status": "heartbeat_received", "timestamp": time.time()}
            self.wfile.write(json.dumps(response).encode("utf-8"))

        except Exception as e:
            print(f"Error in heartbeat API: {e}")
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        """Suppress default HTTP server logging."""
        pass  # Don't log HTTP requests to avoid spam

    def _trigger_shutdown(self, reason: str):
        """Trigger server shutdown after a brief delay."""
        time.sleep(0.5)  # Give time for response to be sent
        print(f"Shutting down server (reason: {reason})...")

        try:
            # Try graceful shutdown first
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            # Force shutdown if needed
            os.kill(os.getpid(), signal.SIGKILL)


class ShutdownAPIServer:
    """Simple HTTP server for shutdown API with heartbeat monitoring."""

    def __init__(self, port: int = 8502, max_runtime_minutes: int = 0, heartbeat_timeout: int = 10):
        self.port = port
        self.max_runtime_minutes = max_runtime_minutes
        self.heartbeat_timeout = heartbeat_timeout
        self.server: HTTPServer | None = None
        self.server_thread: threading.Thread | None = None
        self.heartbeat_thread: threading.Thread | None = None
        self.running = False
        self.start_time = time.time()
        self.last_heartbeat = time.time()

    def start(self):
        """Start the shutdown API server."""
        if self.running:
            print(f"Shutdown API server already running on port {self.port}")
            return

        # Try to find an available port starting from the requested port
        port_to_try = self.port
        max_attempts = 10

        for attempt in range(max_attempts):
            try:
                self.server = HTTPServer(("localhost", port_to_try), ShutdownAPIHandler)
                self.server.api_server_instance = self  # Store reference for heartbeat handling
                self.port = port_to_try  # Update the port we're actually using
                self.running = True
                self.server_thread = threading.Thread(target=self._run_server, daemon=True)
                self.server_thread.start()

                max_runtime_msg = f", max runtime: {self.max_runtime_minutes}m" if self.max_runtime_minutes > 0 else ""
                heartbeat_msg = f", heartbeat timeout: {self.heartbeat_timeout}s" if self.heartbeat_timeout > 0 else ""
                print(f"✅ Shutdown API server started on http://localhost:{self.port}{max_runtime_msg}{heartbeat_msg}")
                print("📡 Endpoints available:")
                print(f"  - POST http://localhost:{self.port}/wpp-shutdown")
                print(f"  - GET  http://localhost:{self.port}/wpp-shutdown")
                print(f"  - POST http://localhost:{self.port}/wpp-heartbeat")
                print(f"  - GET  http://localhost:{self.port}/wpp-status")

                # Start monitoring threads
                if self.max_runtime_minutes > 0 or self.heartbeat_timeout > 0:
                    self.heartbeat_thread = threading.Thread(target=self._monitor_health, daemon=True)
                    self.heartbeat_thread.start()

                return  # Success - exit the loop

            except OSError as e:
                if e.errno == 48 or "Address already in use" in str(e):  # Address already in use
                    print(f"❌ Port {port_to_try} is in use, trying {port_to_try + 1}...")
                    port_to_try += 1
                    continue
                else:
                    print(f"❌ OSError starting shutdown API server on port {port_to_try}: {e}")
                    print(f"❌ Error details: errno={getattr(e, 'errno', 'N/A')}, strerror={getattr(e, 'strerror', 'N/A')}")
                    break
            except Exception as e:
                print(f"❌ Exception starting shutdown API server on port {port_to_try}: {e}")
                print(f"❌ Exception type: {type(e).__name__}")
                import traceback

                print(f"❌ Traceback: {traceback.format_exc()}")
                break

        print(f"Could not start shutdown API server after trying ports {self.port}-{port_to_try}")
        self.running = False

    def stop(self):
        """Stop the shutdown API server."""
        self.running = False
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.server_thread:
            self.server_thread.join(timeout=1)

    def _run_server(self):
        """Run the HTTP server."""
        try:
            print(f"🚀 Starting HTTP server loop on port {self.port}...")
            self.server.serve_forever()
            print(f"🛑 HTTP server loop ended on port {self.port}")
        except Exception as e:
            if self.running:  # Only log if we didn't intentionally stop
                print(f"❌ Shutdown API server error: {e}")
                print(f"❌ Exception type: {type(e).__name__}")
                import traceback

                print(f"❌ Traceback: {traceback.format_exc()}")
            else:
                print(f"ℹ️  HTTP server stopped gracefully on port {self.port}")

    def _monitor_health(self):
        """Monitor maximum runtime and heartbeat health."""
        grace_period = 15  # 15 seconds grace period at startup

        while self.running:
            current_time = time.time()

            # Check maximum runtime
            if self.max_runtime_minutes > 0:
                elapsed_minutes = (current_time - self.start_time) / 60
                if elapsed_minutes >= self.max_runtime_minutes:
                    print(f"Maximum runtime of {self.max_runtime_minutes} minutes exceeded. Shutting down...")
                    self._trigger_shutdown("max_runtime_exceeded")
                    break

            # Check heartbeat timeout (only after grace period)
            if self.heartbeat_timeout > 0 and (current_time - self.start_time) > grace_period:
                heartbeat_age = current_time - self.last_heartbeat
                if heartbeat_age > self.heartbeat_timeout:
                    print(f"No heartbeat for {heartbeat_age:.1f}s (timeout: {self.heartbeat_timeout}s). Browser likely closed. Shutting down...")
                    self._trigger_shutdown("heartbeat_timeout")
                    break
                else:
                    # Debug: print heartbeat status periodically
                    if int(current_time) % 15 == 0:  # Every 15 seconds
                        print(f"Heartbeat status: last received {heartbeat_age:.1f}s ago (timeout: {self.heartbeat_timeout}s)")

            time.sleep(2)  # Check every 2 seconds for faster detection

    def update_heartbeat(self):
        """Update the heartbeat timestamp."""
        self.last_heartbeat = time.time()

    def _trigger_shutdown(self, reason: str):
        """Trigger server shutdown."""
        try:
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            os.kill(os.getpid(), signal.SIGKILL)


# Global API server instance
_api_server: ShutdownAPIServer | None = None


def start_shutdown_api(port: int = 8502, max_runtime_minutes: int = 0, heartbeat_timeout: int = 10):
    """Start the shutdown API server."""
    global _api_server

    print(f"🚀 start_shutdown_api called with port={port}, max_runtime={max_runtime_minutes}, heartbeat_timeout={heartbeat_timeout}")

    # First, test if we can bind to the port at all
    import socket

    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        test_socket.bind(("localhost", port))
        test_socket.close()
        print(f"✅ Port {port} is available for binding")
    except Exception as e:
        print(f"❌ Cannot bind to port {port}: {e}")
        # Try a few other ports
        for test_port in range(port + 1, port + 5):
            try:
                test_socket.bind(("localhost", test_port))
                test_socket.close()
                print(f"✅ Alternative port {test_port} is available")
                port = test_port
                break
            except Exception:
                continue
        else:
            print("❌ No available ports found")
            return None

    if _api_server is None:
        print("📦 Creating new ShutdownAPIServer instance...")
        _api_server = ShutdownAPIServer(port, max_runtime_minutes, heartbeat_timeout)
        _api_server.start()

        # Give it a moment to start up
        import time

        time.sleep(0.5)

        if _api_server.running:
            print(f"✅ API server successfully started on port {_api_server.port}")
        else:
            print("❌ API server failed to start")

    else:
        print(f"♻️  API server already exists, running={_api_server.running}")
        if not _api_server.running:
            print("🔄 Existing server not running, attempting restart...")
            _api_server.start()

    result_port = _api_server.port if _api_server and _api_server.running else None
    print(f"📤 start_shutdown_api returning port: {result_port}")
    return result_port


def stop_shutdown_api():
    """Stop the shutdown API server."""
    global _api_server

    if _api_server:
        _api_server.stop()
        _api_server = None


def is_shutdown_api_active() -> bool:
    """Check if shutdown API server is active."""
    global _api_server
    return _api_server is not None and _api_server.running


def get_shutdown_api_port() -> int | None:
    """Get the port the shutdown API server is running on."""
    global _api_server
    return _api_server.port if _api_server and _api_server.running else None
