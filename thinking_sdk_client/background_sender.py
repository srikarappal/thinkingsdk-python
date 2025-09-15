# thinking_sdk_client/background_sender.py
import json
import time
import logging
import threading
import gzip
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class BackgroundSender:
    """Production-grade background sender with retry logic, batching, and circuit breaker.
    
    Runs in a separate thread to ensure non-blocking operation even under network issues.
    Includes exponential backoff, request batching, and graceful error handling.
    """
    
    def __init__(self, queue, api_key: str, server_url: str, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            queue: EventQueue instance to read events from
            api_key: API key for authentication
            server_url: Base URL of the ThinkingSDK server
            config: Configuration dictionary with optional settings:
                - batch_size: Number of events to send in each batch (default: 50)
                - max_batch_wait: Max seconds to wait before sending partial batch (default: 2.0)
                - retry_attempts: Number of retry attempts for failed requests (default: 3)
                - backoff_factor: Exponential backoff multiplier (default: 1.0)
                - circuit_breaker_threshold: Failures before opening circuit (default: 5)
                - circuit_breaker_timeout: Seconds to wait before retry after circuit opens (default: 60)
                - request_timeout: HTTP request timeout in seconds (default: 10)
                - exceptions_only: If True, only send exception events (default: True for MVP)
        """
        self.queue = queue
        self.api_key = api_key
        self.server_url = server_url.rstrip("/")
        self._config = config or {}
        
        # Configuration
        self.batch_size = self._config.get('batch_size', 50)
        self.max_batch_wait = self._config.get('max_batch_wait', 2.0)
        self.retry_attempts = self._config.get('retry_attempts', 3)
        self.backoff_factor = self._config.get('backoff_factor', 1.0)
        self.circuit_breaker_threshold = self._config.get('circuit_breaker_threshold', 5)
        self.circuit_breaker_timeout = self._config.get('circuit_breaker_timeout', 60)
        self.request_timeout = self._config.get('request_timeout', 10)
        self.exceptions_only = self._config.get('exceptions_only', True)  # MVP: Default to exceptions only
        
        # Thread control
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._session_lock = threading.Lock()  # Prevent concurrent session creation
        
        # State tracking
        self._consecutive_failures = 0
        self._circuit_open_time = None
        self._total_sent = 0
        self._total_failed = 0
        
        # Session-based auth
        self._session_token = None
        self._session_expires_at = 0
        self._customer_id = None
        
    def start(self) -> None:
        """Start the background sender thread."""
        if not self._thread.is_alive():
            self._thread.start()
            
    def stop(self, timeout: float = 5.0) -> None:
        """Stop the background sender thread gracefully.
        
        Args:
            timeout: Maximum seconds to wait for graceful shutdown
        """
        if self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=timeout)
                
    def _setup_session(self) -> requests.Session:
        """Create a configured requests session with retry logic."""
        session = requests.Session()
        
        # Configure retry strategy
        try:
            # Try newer urllib3 API first
            retry_strategy = Retry(
                total=self.retry_attempts,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST"],
                backoff_factor=self.backoff_factor,
                raise_on_status=False
            )
        except TypeError:
            # Fall back to older urllib3 API
            retry_strategy = Retry(
                total=self.retry_attempts,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["POST"],
                backoff_factor=self.backoff_factor,
                raise_on_status=False
            )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers with SDK information
        from ._version import __version__
        import platform
        
        # Build informative User-Agent: ThinkingSDK-Python/0.1.0 (Python 3.9.1; Darwin)
        sdk_language = "Python"  # This is the Python client
        python_version = platform.python_version()
        os_name = platform.system()
        
        user_agent = f"ThinkingSDK-{sdk_language}/{__version__} ({sdk_language} {python_version}; {os_name})"
        
        session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": user_agent,
            "X-SDK-Language": sdk_language,
            "X-SDK-Version": __version__
        })
        
        return session
        
    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is currently open."""
        if self._consecutive_failures < self.circuit_breaker_threshold:
            return False
            
        if self._circuit_open_time is None:
            self._circuit_open_time = time.time()
            return True
            
        # Check if circuit should be closed (timeout expired)
        if time.time() - self._circuit_open_time >= self.circuit_breaker_timeout:
            self._consecutive_failures = 0
            self._circuit_open_time = None
            return False
            
        return True
    
    def _ensure_session(self, session: requests.Session) -> bool:
        """Ensure we have a valid session token.
        
        Returns:
            True if session is valid, False otherwise
        """
        # Check if session is still valid (outside lock for performance)
        if hasattr(self, '_session_token') and self._session_token and time.time() < self._session_expires_at - 60:
            return True
        
        # Use lock to prevent concurrent session creation
        with self._session_lock:
            # Double-check pattern: another thread might have created session while we waited
            if hasattr(self, '_session_token') and self._session_token and time.time() < self._session_expires_at - 60:
                return True
                
            try:
                # Debug: Log what we're sending
                logging.debug(f"ThinkingSDK: Creating session with API key: {self.api_key[:20] if self.api_key else 'None'}...")
                logging.debug(f"ThinkingSDK: Server URL: {self.server_url}")
                
                # Create new session
                url = urljoin(self.server_url + "/", "auth/session")
                response = session.post(
                    url,
                    json={"api_key": self.api_key},
                    timeout=self.request_timeout
                )
                
                logging.debug(f"ThinkingSDK: Session response: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    self._session_token = data.get("session_token")
                    self._session_expires_at = time.time() + data.get("expires_in", 3600)
                    self._customer_id = data.get("customer_id")
                    
                    # Update session headers with token
                    session.headers["X-Session-Token"] = self._session_token
                    
                    logging.debug(f"ThinkingSDK: New session created for customer {self._customer_id}")
                    return True
                else:
                    logging.debug(f"ThinkingSDK: Session creation failed: {response.status_code}")
                    return False
                    
            except Exception as e:
                if self._config.get('debug', False):
                    import traceback
                    logging.debug(f"ThinkingSDK: Session creation error: {e}")
                    logging.debug(f"ThinkingSDK: Session creation traceback: {traceback.format_exc()}")
                else:
                    logging.debug(f"ThinkingSDK: Session creation error: {e}")
                return False
        
    def _send_batch(self, session: requests.Session, events: List[Dict[str, Any]]) -> bool:
        """Send a batch of events to the server.
        
        Args:
            session: Configured requests session
            events: List of event dictionaries to send
            
        Returns:
            True if successful, False otherwise
        """
        if self._is_circuit_open():
            return False
        
        # Try to ensure we have a valid session, but fall back to API key if needed
        has_session = self._ensure_session(session)
        if not has_session:
            logging.debug("ThinkingSDK: Failed to get session token, falling back to API key authentication")
            # Set API key header as fallback
            session.headers["X-THINKINGSDK-KEY"] = self.api_key
            
        try:
            url = urljoin(self.server_url + "/", "ingest")
            
            # Prepare batch payload
            batch_data = json.dumps({"events": events})
            
            # Compress if large
            headers = {}
            if len(batch_data) > getattr(self, 'compress_threshold', 1024):
                batch_data = gzip.compress(batch_data.encode('utf-8'))
                headers['Content-Encoding'] = 'gzip'
                logging.debug(f"ThinkingSDK: Compressed {len(events)} events")
            else:
                batch_data = batch_data.encode('utf-8')
            
            # Send batch
            try:
                response = session.post(
                    url,
                    data=batch_data,
                    headers=headers,
                    timeout=self.request_timeout
                )
                
                if response.status_code == 200:
                    self._consecutive_failures = 0
                    self._total_sent += len(events)
                    return True
                elif response.status_code == 401:
                    # Authentication failed
                    if has_session:
                        # Session expired or invalid - clear and retry once
                        self._session_token = None
                        self._session_expires_at = 0
                        
                        if self._ensure_session(session):
                            # Retry with new session
                            response = session.post(
                                url,
                                data=batch_data,
                                headers=headers,
                                timeout=self.request_timeout
                            )
                            if response.status_code == 200:
                                self._consecutive_failures = 0
                                self._total_sent += len(events)
                                return True
                        else:
                            # Fall back to API key
                            session.headers["X-THINKINGSDK-KEY"] = self.api_key
                            response = session.post(
                                url,
                                data=batch_data,
                                headers=headers,
                                timeout=self.request_timeout
                            )
                            if response.status_code == 200:
                                self._consecutive_failures = 0
                                self._total_sent += len(events)
                                return True
                    else:
                        # API key authentication failed - this is fatal
                        logging.debug("ThinkingSDK: API key authentication failed")
                        self._consecutive_failures += 1
                        return False
                    
                    logging.debug("ThinkingSDK: Authentication failed")
                    return False
                else:
                    # Other errors
                    logging.debug(f"ThinkingSDK: HTTP {response.status_code}")
                    self._consecutive_failures += 1
                    self._total_failed += len(events)
                    return False
                    
            except requests.exceptions.Timeout:
                logging.debug("ThinkingSDK: Request timeout")
                self._consecutive_failures += 1
                self._total_failed += len(events)
                return False
            except requests.exceptions.ConnectionError:
                logging.debug("ThinkingSDK: Connection error")
                self._consecutive_failures += 1
                self._total_failed += len(events)
                return False
                
        except Exception as e:
            self._consecutive_failures += 1
            self._total_failed += len(events)
            logging.debug(f"ThinkingSDK: Batch send failed: {e}")
            return False
            
    def _collect_batch(self) -> List[Dict[str, Any]]:
        """Collect a batch of events from the queue.
        
        Returns:
            List of events (may be empty)
        """
        batch = []
        batch_start_time = time.time()
        
        while len(batch) < self.batch_size:
            # Check if we should stop waiting
            if time.time() - batch_start_time > self.max_batch_wait:
                break
                
            # Try to get more events
            events = self.queue.pop_batch(min(50, self.batch_size - len(batch)))
            if events:
                batch.extend(events)
                batch_start_time = time.time()  # Reset timer when we get events
            else:
                # No events available, short sleep
                time.sleep(0.01)
                
            # Check stop signal
            if self._stop_event.is_set():
                break
                
        return batch
        
    def _run(self) -> None:
        """Main loop running in the background thread."""
        # Set up logging for thread
        logging.basicConfig(level=logging.WARNING)
        
        session = self._setup_session()
        
        while not self._stop_event.is_set():
            try:
                # Collect batch of events
                batch = self._collect_batch()
                
                if batch:
                    success = self._send_batch(session, batch)
                    if not success and self._is_circuit_open():
                        # Circuit is open, wait longer before retrying
                        time.sleep(min(30, self.circuit_breaker_timeout / 2))
                else:
                    # No events, short sleep
                    time.sleep(0.1)
                    
            except Exception as e:
                # Should never happen, but catch any unexpected errors
                logging.error(f"ThinkingSDK: Unexpected error in sender loop: {e}")
                time.sleep(1.0)
                
        # Drain remaining events on shutdown
        try:
            final_batch = self.queue.pop_batch(1000)  # Get up to 1000 remaining events
            if final_batch:
                self._send_batch(session, final_batch)
        except Exception:
            pass
            
    def get_stats(self) -> Dict[str, Any]:
        """Get sender statistics."""
        return {
            "thread_alive": self._thread.is_alive(),
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "consecutive_failures": self._consecutive_failures,
            "circuit_open": self._is_circuit_open(),
            "config": self._config.copy()
        }