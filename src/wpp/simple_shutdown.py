"""
Simple shutdown mechanism that monitors Streamlit session health
"""

import os
import signal
import threading
import time


class StreamlitShutdownMonitor:
    """Monitor Streamlit session health and shutdown when browser disconnects"""

    def __init__(self, max_runtime_minutes: int = 0, session_timeout_seconds: int = 30):
        self.max_runtime_minutes = max_runtime_minutes
        self.session_timeout_seconds = session_timeout_seconds
        self.start_time = time.time()
        self.last_activity = time.time()
        self.running = False
        self.monitor_thread = None
        self.session_active = True

    def start(self):
        """Start monitoring the session"""
        if self.running:
            return

        self.running = True
        self.last_activity = time.time()

        print("🚀 Starting Streamlit shutdown monitor")
        print(f"   - Session timeout: {self.session_timeout_seconds}s")
        if self.max_runtime_minutes > 0:
            print(f"   - Max runtime: {self.max_runtime_minutes}m")

        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)

    def update_activity(self):
        """Update last activity timestamp (call this when user interacts with app)"""
        self.last_activity = time.time()
        self.session_active = True

    def mark_session_inactive(self):
        """Mark the session as inactive (browser likely closed)"""
        self.session_active = False

    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            current_time = time.time()

            # Check maximum runtime
            if self.max_runtime_minutes > 0:
                elapsed_minutes = (current_time - self.start_time) / 60
                if elapsed_minutes >= self.max_runtime_minutes:
                    print(f"⏰ Maximum runtime of {self.max_runtime_minutes} minutes exceeded. Shutting down...")
                    self._trigger_shutdown("max_runtime_exceeded")
                    break

            # Check session timeout
            if self.session_timeout_seconds > 0:
                session_age = current_time - self.last_activity
                if session_age > self.session_timeout_seconds:
                    print(f"💔 No activity for {session_age:.1f}s (timeout: {self.session_timeout_seconds}s). Browser likely closed. Shutting down...")
                    self._trigger_shutdown("session_timeout")
                    break
                else:
                    # Debug: print session status every 15 seconds
                    if int(current_time) % 15 == 0:
                        print(f"💓 Session active: last activity {session_age:.1f}s ago (timeout: {self.session_timeout_seconds}s)")

            time.sleep(2)  # Check every 2 seconds

    def _trigger_shutdown(self, reason: str):
        """Trigger application shutdown"""
        print(f"🚪 Shutting down application (reason: {reason})...")

        try:
            # Try graceful shutdown first
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            # Force shutdown if needed
            os.kill(os.getpid(), signal.SIGKILL)


# Global monitor instance
_shutdown_monitor: StreamlitShutdownMonitor | None = None


def start_shutdown_monitor(max_runtime_minutes: int = 0, session_timeout_seconds: int = 30):
    """Start the shutdown monitor"""
    global _shutdown_monitor

    if _shutdown_monitor is None:
        _shutdown_monitor = StreamlitShutdownMonitor(max_runtime_minutes, session_timeout_seconds)
        _shutdown_monitor.start()
        return True
    else:
        print("♻️  Shutdown monitor already running")
        return False


def update_session_activity():
    """Update session activity (call this on user interactions)"""
    global _shutdown_monitor

    if _shutdown_monitor:
        _shutdown_monitor.update_activity()


def mark_session_inactive():
    """Mark session as inactive (browser closed)"""
    global _shutdown_monitor

    if _shutdown_monitor:
        _shutdown_monitor.mark_session_inactive()


def stop_shutdown_monitor():
    """Stop the shutdown monitor"""
    global _shutdown_monitor

    if _shutdown_monitor:
        _shutdown_monitor.stop()
        _shutdown_monitor = None


def is_monitor_active() -> bool:
    """Check if shutdown monitor is active"""
    global _shutdown_monitor
    return _shutdown_monitor is not None and _shutdown_monitor.running
