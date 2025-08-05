# tests/test_sample_data.py
"""Sample data and scenarios for testing ThinkingSDK."""

import time
import threading
from typing import Dict, List, Any


class SampleDataGenerator:
    """Generate realistic sample data for testing."""
    
    @staticmethod
    def create_call_event(func_name: str = "test_function", **kwargs) -> Dict[str, Any]:
        """Create a sample call event."""
        defaults = {
            "ts": time.time(),
            "pid": 12345,
            "thread": "MainThread",
            "event": "call",
            "func": func_name,
            "file": "test_file.py",
            "line": 42,
            "locals": {
                "arg1": "'test_value'",
                "arg2": "123",
                "local_var": "'local_value'"
            }
        }
        defaults.update(kwargs)
        return defaults
    
    @staticmethod
    def create_return_event(func_name: str = "test_function", return_value: str = "'result'", **kwargs) -> Dict[str, Any]:
        """Create a sample return event."""
        defaults = {
            "ts": time.time(),
            "pid": 12345,
            "thread": "MainThread",
            "event": "return",
            "func": func_name,
            "file": "test_file.py",
            "line": 45,
            "return_value": return_value
        }
        defaults.update(kwargs)
        return defaults
    
    @staticmethod
    def create_exception_event(exception_type: str = "ValueError", message: str = "Test error", **kwargs) -> Dict[str, Any]:
        """Create a sample exception event."""
        defaults = {
            "ts": time.time(),
            "pid": 12345,
            "thread": "MainThread",
            "event": "exception",
            "func": "failing_function",
            "file": "test_file.py",
            "line": 50,
            "exception": {
                "type": exception_type,
                "msg": f"'{message}'",
                "traceback": [
                    f'  File "test_file.py", line 50, in failing_function\n    raise {exception_type}("{message}")\n',
                    f'{exception_type}: {message}\n'
                ]
            }
        }
        defaults.update(kwargs)
        return defaults
    
    @staticmethod
    def create_thread_exception_event(thread_name: str = "WorkerThread", **kwargs) -> Dict[str, Any]:
        """Create a sample thread exception event."""
        defaults = {
            "ts": time.time(),
            "pid": 12345,
            "thread": thread_name,
            "event": "thread_exception",
            "exception": {
                "type": "RuntimeError",
                "msg": "'Thread execution failed'",
                "traceback": [
                    f'  File "worker.py", line 25, in worker_function\n    raise RuntimeError("Thread execution failed")\n',
                    'RuntimeError: Thread execution failed\n'
                ]
            }
        }
        defaults.update(kwargs)
        return defaults
    
    @staticmethod
    def create_event_batch(count: int = 10, event_types: List[str] = None) -> List[Dict[str, Any]]:
        """Create a batch of mixed sample events."""
        if event_types is None:
            event_types = ["call", "return", "exception"]
            
        events = []
        for i in range(count):
            event_type = event_types[i % len(event_types)]
            
            if event_type == "call":
                event = SampleDataGenerator.create_call_event(
                    func_name=f"function_{i}",
                    line=40 + i,
                    locals={f"param_{i}": f"'value_{i}'"}
                )
            elif event_type == "return":
                event = SampleDataGenerator.create_return_event(
                    func_name=f"function_{i}",
                    return_value=f"'result_{i}'",
                    line=45 + i
                )
            elif event_type == "exception":
                event = SampleDataGenerator.create_exception_event(
                    exception_type="ValueError" if i % 2 == 0 else "TypeError",
                    message=f"Error in function_{i}",
                    line=50 + i
                )
            elif event_type == "thread_exception":
                event = SampleDataGenerator.create_thread_exception_event(
                    thread_name=f"Worker-{i}"
                )
            else:
                # Default to call event
                event = SampleDataGenerator.create_call_event(func_name=f"default_function_{i}")
                
            # Add small time increment to each event
            event["ts"] = time.time() + (i * 0.001)
            events.append(event)
            
        return events


class SampleScenarios:
    """Realistic application scenarios for testing."""
    
    @staticmethod
    def web_application_trace():
        """Generate events that might occur in a web application."""
        events = []
        base_time = time.time()
        
        # HTTP request arrives
        events.append({
            "ts": base_time,
            "pid": 12345,
            "thread": "MainThread",
            "event": "call",
            "func": "handle_request",
            "file": "app.py",
            "line": 15,
            "locals": {"request": "<Request object>", "method": "'GET'"}
        })
        
        # Authentication
        events.append({
            "ts": base_time + 0.001,
            "pid": 12345,
            "thread": "MainThread",
            "event": "call",
            "func": "authenticate_user",
            "file": "auth.py",
            "line": 25,
            "locals": {"token": "'Bearer abc123...'"}
        })
        
        # Database query
        events.append({
            "ts": base_time + 0.002,
            "pid": 12345,
            "thread": "MainThread",
            "event": "call",
            "func": "fetch_user_data",
            "file": "db.py",
            "line": 45,
            "locals": {"user_id": "123", "query": "'SELECT * FROM users WHERE id = ?'"}
        })
        
        # Business logic
        events.append({
            "ts": base_time + 0.003,
            "pid": 12345,
            "thread": "MainThread",
            "event": "call",
            "func": "process_user_data",
            "file": "business.py",
            "line": 30,
            "locals": {"user_data": "{'id': 123, 'name': 'John'}", "permissions": "['read', 'write']"}
        })
        
        # Response generation
        events.append({
            "ts": base_time + 0.004,
            "pid": 12345,
            "thread": "MainThread",
            "event": "return",
            "func": "handle_request",
            "file": "app.py",
            "line": 20,
            "return_value": "{'status': 200, 'data': {...}}"
        })
        
        return events
    
    @staticmethod
    def data_processing_pipeline():
        """Generate events from a data processing pipeline."""
        events = []
        base_time = time.time()
        
        # Data loading
        events.append({
            "ts": base_time,
            "pid": 12345,
            "thread": "DataProcessor",
            "event": "call",
            "func": "load_data",
            "file": "pipeline.py",
            "line": 10,
            "locals": {"source": "'s3://bucket/data.csv'", "format": "'csv'"}
        })
        
        # Data validation
        events.append({
            "ts": base_time + 0.1,
            "pid": 12345,
            "thread": "DataProcessor",
            "event": "call",
            "func": "validate_data",
            "file": "pipeline.py",
            "line": 25,
            "locals": {"rows": "10000", "columns": "25"}
        })
        
        # Data transformation
        events.append({
            "ts": base_time + 0.2,
            "pid": 12345,
            "thread": "DataProcessor",
            "event": "call",
            "func": "transform_data",
            "file": "pipeline.py",
            "line": 40,
            "locals": {"transformations": "['normalize', 'filter_nulls']"}
        })
        
        # Error during processing
        events.append({
            "ts": base_time + 0.25,
            "pid": 12345,
            "thread": "DataProcessor",
            "event": "exception",
            "func": "transform_data",
            "file": "pipeline.py",
            "line": 45,
            "exception": {
                "type": "ValueError",
                "msg": "'Invalid data format in row 5432'",
                "traceback": [
                    '  File "pipeline.py", line 45, in transform_data\n    processed_row = normalize_row(row)\n',
                    '  File "transforms.py", line 15, in normalize_row\n    raise ValueError("Invalid data format")\n',
                    'ValueError: Invalid data format in row 5432\n'
                ]
            }
        })
        
        return events
    
    @staticmethod
    def microservice_interaction():
        """Generate events from microservice interactions."""
        events = []
        base_time = time.time()
        
        # Service A calls Service B
        events.append({
            "ts": base_time,
            "pid": 12345,
            "thread": "MainThread",
            "event": "call",
            "func": "call_service_b",
            "file": "service_a.py",
            "line": 20,
            "locals": {"endpoint": "'http://service-b:8080/api/data'", "timeout": "5.0"}
        })
        
        # Service B processes request
        events.append({
            "ts": base_time + 0.001,
            "pid": 54321,
            "thread": "RequestHandler",
            "event": "call",
            "func": "handle_api_request",
            "file": "service_b.py",
            "line": 35,
            "locals": {"path": "'/api/data'", "method": "'GET'"}
        })
        
        # Service B calls database
        events.append({
            "ts": base_time + 0.002,
            "pid": 54321,
            "thread": "RequestHandler",
            "event": "call",
            "func": "query_database",
            "file": "db_client.py",
            "line": 15,
            "locals": {"query": "'SELECT * FROM items WHERE active = true'"}
        })
        
        # Database timeout error
        events.append({
            "ts": base_time + 5.1,
            "pid": 54321,
            "thread": "RequestHandler",
            "event": "exception",
            "func": "query_database",
            "file": "db_client.py",
            "line": 18,
            "exception": {
                "type": "TimeoutError",
                "msg": "'Database query timed out after 5 seconds'",
                "traceback": [
                    '  File "db_client.py", line 18, in query_database\n    result = connection.execute(query)\n',
                    'TimeoutError: Database query timed out after 5 seconds\n'
                ]
            }
        })
        
        return events
    
    @staticmethod
    def concurrent_processing():
        """Generate events from concurrent/parallel processing."""
        events = []
        base_time = time.time()
        
        # Main thread starts worker threads
        events.append({
            "ts": base_time,
            "pid": 12345,
            "thread": "MainThread",
            "event": "call",
            "func": "start_workers",
            "file": "concurrent.py",
            "line": 10,
            "locals": {"worker_count": "4", "task_queue_size": "100"}
        })
        
        # Worker threads start processing
        for i in range(4):
            events.append({
                "ts": base_time + 0.01 + (i * 0.001),
                "pid": 12345,
                "thread": f"Worker-{i}",
                "event": "call",
                "func": "worker_loop",
                "file": "concurrent.py",
                "line": 25,
                "locals": {"worker_id": f"{i}"}
            })
        
        # Some workers process tasks successfully
        for i in range(2):
            events.append({
                "ts": base_time + 0.1 + (i * 0.05),
                "pid": 12345,
                "thread": f"Worker-{i}",
                "event": "call",
                "func": "process_task",
                "file": "concurrent.py",
                "line": 40,
                "locals": {"task_id": f"task_{i}", "data": f"'task_data_{i}'"}
            })
        
        # One worker encounters an error
        events.append({
            "ts": base_time + 0.15,
            "pid": 12345,
            "thread": "Worker-2",
            "event": "thread_exception",
            "exception": {
                "type": "ConnectionError",
                "msg": "'Failed to connect to external service'",
                "traceback": [
                    '  File "concurrent.py", line 45, in process_task\n    result = external_service_call()\n',
                    'ConnectionError: Failed to connect to external service\n'
                ]
            }
        })
        
        return events


# Test helper functions
def generate_performance_test_data(num_events: int = 1000) -> List[Dict[str, Any]]:
    """Generate a large number of events for performance testing."""
    events = []
    base_time = time.time()
    
    for i in range(num_events):
        event_type = ["call", "return", "exception"][i % 3]
        
        if event_type == "call":
            event = {
                "ts": base_time + (i * 0.001),
                "pid": 12345,
                "thread": "MainThread",
                "event": "call",
                "func": f"function_{i}",
                "file": f"module_{i % 10}.py",
                "line": 20 + (i % 100),
                "locals": {
                    f"param_{j}": f"'value_{i}_{j}'" for j in range(min(5, i % 8 + 1))
                }
            }
        elif event_type == "return":
            event = {
                "ts": base_time + (i * 0.001),
                "pid": 12345,
                "thread": "MainThread",
                "event": "return",
                "func": f"function_{i}",
                "file": f"module_{i % 10}.py",
                "line": 25 + (i % 100),
                "return_value": f"'result_{i}'"
            }
        else:  # exception
            exception_types = ["ValueError", "TypeError", "RuntimeError", "KeyError"]
            event = {
                "ts": base_time + (i * 0.001),
                "pid": 12345,
                "thread": "MainThread",
                "event": "exception",
                "func": f"function_{i}",
                "file": f"module_{i % 10}.py",
                "line": 30 + (i % 100),
                "exception": {
                    "type": exception_types[i % len(exception_types)],
                    "msg": f"'Error in function_{i}'",
                    "traceback": [f"Error traceback for function_{i}"]
                }
            }
            
        events.append(event)
        
    return events


def validate_event_structure(event: Dict[str, Any]) -> bool:
    """Validate that an event has the expected structure."""
    required_fields = ["ts", "pid", "thread", "event"]
    
    # Check required fields
    for field in required_fields:
        if field not in event:
            return False
            
    # Validate timestamp
    if not isinstance(event["ts"], (int, float)):
        return False
        
    # Validate event type
    if event["event"] not in ["call", "return", "exception", "thread_exception"]:
        return False
        
    # Event-specific validation
    if event["event"] in ["call", "return"]:
        if not all(field in event for field in ["func", "file", "line"]):
            return False
            
    if event["event"] in ["exception", "thread_exception"]:
        if "exception" not in event:
            return False
        if not all(field in event["exception"] for field in ["type", "msg"]):
            return False
            
    return True


if __name__ == "__main__":
    # Demo usage of sample data generation
    print("=== Sample Call Event ===")
    call_event = SampleDataGenerator.create_call_event()
    print(call_event)
    
    print("\n=== Sample Exception Event ===")
    exception_event = SampleDataGenerator.create_exception_event()
    print(exception_event)
    
    print("\n=== Event Batch ===")
    batch = SampleDataGenerator.create_event_batch(5)
    for i, event in enumerate(batch):
        print(f"Event {i}: {event['event']} - {event.get('func', 'N/A')}")
        
    print("\n=== Web Application Trace ===")
    web_trace = SampleScenarios.web_application_trace()
    for event in web_trace:
        print(f"{event['ts']:.3f}: {event['func']} ({event['event']})")
        
    print("\n=== Event Validation ===")
    for event in batch[:3]:
        is_valid = validate_event_structure(event)
        print(f"Event valid: {is_valid}")