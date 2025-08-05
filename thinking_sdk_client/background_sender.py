# thinking_sdk_client/background_sender.py
import json
import time
import logging
import threading
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
        
        # Thread control
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        
        # State tracking
        self._consecutive_failures = 0
        self._circuit_open_time = None
        self._total_sent = 0
        self._total_failed = 0
        
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
        
        # Set default headers
        session.headers.update({
            "X-THINKINGSDK-KEY": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "ThinkingSDK-Client/1.0"
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
            
        try:
            url = urljoin(self.server_url + "/", "ingest")
            
            # For batch sending, we'll send events one by one for now
            # In production, server should support batch endpoint
            success_count = 0
            
            for event in events:
                try:
                    response = session.post(
                        url,
                        data=json.dumps(event),
                        timeout=self.request_timeout
                    )
                    
                    if response.status_code == 200:
                        success_count += 1
                    elif response.status_code == 401:
                        # Authentication error - no point in retrying
                        logging.warning("ThinkingSDK: Authentication failed, check API key")
                        return False
                    else:
                        # Other errors will be handled by retry logic
                        logging.debug(f"ThinkingSDK: HTTP {response.status_code}: {response.text}")
                        
                except requests.exceptions.Timeout:
                    logging.debug("ThinkingSDK: Request timeout")
                except requests.exceptions.ConnectionError:
                    logging.debug("ThinkingSDK: Connection error")
                except Exception as e:
                    logging.debug(f"ThinkingSDK: Unexpected error: {e}")
                    
            # Consider batch successful if majority of events were sent
            if success_count > len(events) * 0.5:
                self._consecutive_failures = 0
                self._total_sent += success_count
                return True
            else:
                self._consecutive_failures += 1
                self._total_failed += len(events) - success_count
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