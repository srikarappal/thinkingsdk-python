#!/usr/bin/env python3
"""
ThinkingSDK Performance Benchmark

This script measures the performance impact of ThinkingSDK on application code.
It runs identical code with and without SDK instrumentation to calculate overhead.

Usage:
    python benchmark.py [--iterations=100] [--functions=10] [--detailed]
"""

import time
import statistics
import argparse
import sys
from typing import List, Dict, Any, Callable
from contextlib import contextmanager

try:
    import thinkingsdk as thinking
except ImportError:
    print("ERROR: thinkingsdk not found. Make sure it's installed.")
    sys.exit(1)


class PerformanceBenchmark:
    """Performance benchmarking suite for ThinkingSDK."""
    
    def __init__(self, iterations: int = 100, functions_per_iteration: int = 10):
        self.iterations = iterations
        self.functions_per_iteration = functions_per_iteration
        self.results = {}
        
    def create_test_functions(self) -> List[Callable]:
        """Create a variety of test functions with different characteristics."""
        
        def simple_arithmetic(x: int, y: int) -> int:
            """Simple arithmetic operations."""
            return x + y * 2 - y // 2
            
        def string_operations(text: str) -> str:
            """String manipulation operations."""
            return text.upper().replace("TEST", "BENCHMARK").strip()
            
        def list_processing(items: List[int]) -> List[int]:
            """List processing operations."""
            return [x * 2 for x in items if x % 2 == 0]
            
        def dictionary_operations(data: Dict[str, Any]) -> Dict[str, Any]:
            """Dictionary manipulation operations."""
            result = {}
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    result[f"processed_{key}"] = value * 1.5
                else:
                    result[f"processed_{key}"] = str(value)
            return result
            
        def nested_function_calls(n: int) -> int:
            """Nested function call pattern."""
            def inner_function(x: int) -> int:
                def deepest_function(y: int) -> int:
                    return y * 3 + 1
                return deepest_function(x) + 2
            return inner_function(n) * 2
            
        def recursive_function(n: int) -> int:
            """Simple recursive function."""
            if n <= 1:
                return 1
            return n + recursive_function(n - 1)
            
        def exception_handling_function(x: int) -> str:
            """Function that may raise exceptions."""
            try:
                result = 100 / x if x != 0 else "undefined"
                return f"Result: {result}"
            except ZeroDivisionError:
                return "Division by zero handled"
                
        return [
            lambda: simple_arithmetic(10, 5),
            lambda: string_operations("test string for benchmark"),
            lambda: list_processing([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
            lambda: dictionary_operations({"a": 1, "b": 2.5, "c": "test"}),
            lambda: nested_function_calls(5),
            lambda: recursive_function(10),
            lambda: exception_handling_function(4),
        ]
    
    @contextmanager
    def sdk_context(self, enabled: bool = True):
        """Context manager for SDK sessions."""
        if enabled:
            thinking.start(
                api_key="sk_live_XXXX",
                server_url="http://localhost:8000",
                config={
                    'instrumentation': {'sample_rate': 1.0},  # Full sampling for accurate measurement
                    'sender': {'batch_size': 100}  # Larger batches to reduce network overhead
                }
            )
            
        try:
            yield
        finally:
            if enabled:
                thinking.stop()
    
    def run_benchmark_iteration(self, test_functions: List[Callable], with_sdk: bool = False) -> Dict[str, float]:
        """Run a single benchmark iteration."""
        times = []
        
        with self.sdk_context(with_sdk):
            start_time = time.perf_counter()
            
            for _ in range(self.functions_per_iteration):
                for func in test_functions:
                    func()
                    
            end_time = time.perf_counter()
            
        total_time = end_time - start_time
        avg_time_per_call = total_time / (len(test_functions) * self.functions_per_iteration)
        
        return {
            "total_time": total_time,
            "avg_time_per_call": avg_time_per_call,
            "function_calls": len(test_functions) * self.functions_per_iteration
        }
    
    def run_full_benchmark(self, detailed: bool = False) -> Dict[str, Any]:
        """Run the complete benchmark suite."""
        print("🚀 Starting ThinkingSDK Performance Benchmark")
        print("=" * 60)
        
        test_functions = self.create_test_functions()
        print(f"📊 Test configuration:")
        print(f"   - Iterations: {self.iterations}")
        print(f"   - Functions per iteration: {self.functions_per_iteration}")
        print(f"   - Total function calls per run: {len(test_functions) * self.functions_per_iteration}")
        
        # Benchmark without SDK
        print(f"\n📍 Running benchmark WITHOUT SDK ({self.iterations} iterations)...")
        without_sdk_times = []
        
        for i in range(self.iterations):
            result = self.run_benchmark_iteration(test_functions, with_sdk=False)
            without_sdk_times.append(result["total_time"])
            
            if detailed and (i + 1) % 10 == 0:
                print(f"   Completed {i + 1}/{self.iterations} iterations")
        
        # Benchmark with SDK
        print(f"\n📍 Running benchmark WITH SDK ({self.iterations} iterations)...")
        with_sdk_times = []
        
        for i in range(self.iterations):
            result = self.run_benchmark_iteration(test_functions, with_sdk=True)
            with_sdk_times.append(result["total_time"])
            
            if detailed and (i + 1) % 10 == 0:
                print(f"   Completed {i + 1}/{self.iterations} iterations")
        
        # Calculate statistics
        without_sdk_stats = {
            "mean": statistics.mean(without_sdk_times),
            "median": statistics.median(without_sdk_times),
            "stdev": statistics.stdev(without_sdk_times) if len(without_sdk_times) > 1 else 0,
            "min": min(without_sdk_times),
            "max": max(without_sdk_times)
        }
        
        with_sdk_stats = {
            "mean": statistics.mean(with_sdk_times),
            "median": statistics.median(with_sdk_times),
            "stdev": statistics.stdev(with_sdk_times) if len(with_sdk_times) > 1 else 0,
            "min": min(with_sdk_times),
            "max": max(with_sdk_times)
        }
        
        # Calculate overhead
        overhead_percent = ((with_sdk_stats["mean"] - without_sdk_stats["mean"]) / without_sdk_stats["mean"]) * 100
        median_overhead_percent = ((with_sdk_stats["median"] - without_sdk_stats["median"]) / without_sdk_stats["median"]) * 100
        
        results = {
            "test_config": {
                "iterations": self.iterations,
                "functions_per_iteration": self.functions_per_iteration,
                "total_function_calls": len(test_functions) * self.functions_per_iteration
            },
            "without_sdk": without_sdk_stats,
            "with_sdk": with_sdk_stats,
            "overhead": {
                "mean_percent": overhead_percent,
                "median_percent": median_overhead_percent,
                "absolute_mean_ms": (with_sdk_stats["mean"] - without_sdk_stats["mean"]) * 1000,
                "absolute_median_ms": (with_sdk_stats["median"] - without_sdk_stats["median"]) * 1000
            },
            "raw_data": {
                "without_sdk_times": without_sdk_times,
                "with_sdk_times": with_sdk_times
            }
        }
        
        self.results = results
        return results
    
    def print_results(self, results: Dict[str, Any]):
        """Print benchmark results in a formatted way."""
        print("\n" + "=" * 60)
        print("📊 BENCHMARK RESULTS")
        print("=" * 60)
        
        config = results["test_config"]
        without_sdk = results["without_sdk"]
        with_sdk = results["with_sdk"]
        overhead = results["overhead"]
        
        print(f"\n🧪 Test Configuration:")
        print(f"   Iterations: {config['iterations']}")
        print(f"   Function calls per test: {config['total_function_calls']}")
        
        print(f"\n⏱️  Timing Results (seconds):")
        print(f"   WITHOUT SDK:")
        print(f"     Mean:   {without_sdk['mean']:.6f}s")
        print(f"     Median: {without_sdk['median']:.6f}s")
        print(f"     StdDev: {without_sdk['stdev']:.6f}s")
        print(f"     Range:  {without_sdk['min']:.6f}s - {without_sdk['max']:.6f}s")
        
        print(f"\n   WITH SDK:")
        print(f"     Mean:   {with_sdk['mean']:.6f}s")
        print(f"     Median: {with_sdk['median']:.6f}s")
        print(f"     StdDev: {with_sdk['stdev']:.6f}s")
        print(f"     Range:  {with_sdk['min']:.6f}s - {with_sdk['max']:.6f}s")
        
        print(f"\n📈 Performance Overhead:")
        print(f"   Mean overhead:   {overhead['mean_percent']:+.2f}%")
        print(f"   Median overhead: {overhead['median_percent']:+.2f}%")
        print(f"   Absolute mean:   {overhead['absolute_mean_ms']:+.3f}ms")
        print(f"   Absolute median: {overhead['absolute_median_ms']:+.3f}ms")
        
        # Performance assessment
        print(f"\n🎯 Performance Assessment:")
        if abs(overhead['mean_percent']) < 5:
            assessment = "✅ EXCELLENT - Very low overhead"
        elif abs(overhead['mean_percent']) < 15:
            assessment = "✅ GOOD - Acceptable overhead"
        elif abs(overhead['mean_percent']) < 30:
            assessment = "⚠️  MODERATE - Noticeable overhead"
        else:
            assessment = "❌ HIGH - Significant overhead"
            
        print(f"   {assessment}")
        
        # Per-call overhead
        calls_per_second_without = config['total_function_calls'] / without_sdk['mean']
        calls_per_second_with = config['total_function_calls'] / with_sdk['mean']
        
        print(f"\n📊 Throughput:")
        print(f"   Without SDK: {calls_per_second_without:,.0f} calls/second")
        print(f"   With SDK:    {calls_per_second_with:,.0f} calls/second")
        print(f"   Difference:  {calls_per_second_with - calls_per_second_without:+,.0f} calls/second")
        
    def save_results(self, filename: str = "benchmark_results.json"):
        """Save benchmark results to a JSON file."""
        import json
        
        if not self.results:
            print("No results to save. Run benchmark first.")
            return
            
        # Add timestamp and system info
        import platform
        self.results["metadata"] = {
            "timestamp": time.time(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor()
        }
        
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
            
        print(f"\n💾 Results saved to {filename}")
    
    def memory_benchmark(self) -> Dict[str, Any]:
        """Run a memory usage benchmark (basic implementation)."""
        print("\n🔍 Running memory usage benchmark...")
        
        import gc
        import sys
        
        def get_memory_usage():
            """Get basic memory usage information."""
            gc.collect()  # Force garbage collection
            return sys.getsizeof(gc.get_objects())
        
        # Memory usage without SDK
        memory_before = get_memory_usage()
        
        with self.sdk_context(False):
            test_functions = self.create_test_functions()
            for func in test_functions * 10:  # Run more iterations
                func()
                
        memory_without_sdk = get_memory_usage() - memory_before
        
        # Memory usage with SDK
        memory_before = get_memory_usage()
        
        with self.sdk_context(True):
            test_functions = self.create_test_functions()
            for func in test_functions * 10:  # Run more iterations
                func()
                
        memory_with_sdk = get_memory_usage() - memory_before
        
        memory_overhead = memory_with_sdk - memory_without_sdk
        memory_overhead_percent = (memory_overhead / memory_without_sdk) * 100 if memory_without_sdk > 0 else 0
        
        results = {
            "without_sdk_bytes": memory_without_sdk,
            "with_sdk_bytes": memory_with_sdk,
            "overhead_bytes": memory_overhead,
            "overhead_percent": memory_overhead_percent
        }
        
        print(f"   Memory without SDK: {memory_without_sdk:,} bytes")
        print(f"   Memory with SDK:    {memory_with_sdk:,} bytes") 
        print(f"   Memory overhead:    {memory_overhead:+,} bytes ({memory_overhead_percent:+.1f}%)")
        
        return results


def main():
    """Main entry point for benchmark script."""
    parser = argparse.ArgumentParser(description="ThinkingSDK Performance Benchmark")
    parser.add_argument("--iterations", type=int, default=50, 
                       help="Number of benchmark iterations (default: 50)")
    parser.add_argument("--functions", type=int, default=5,
                       help="Function calls per iteration (default: 5)")
    parser.add_argument("--detailed", action="store_true",
                       help="Show detailed progress information")
    parser.add_argument("--save", type=str, default="benchmark_results.json",
                       help="Save results to file (default: benchmark_results.json)")
    parser.add_argument("--memory", action="store_true",
                       help="Include memory usage benchmark")
    
    args = parser.parse_args()
    
    # Check if server is running
    try:
        import requests
        response = requests.get("http://localhost:8000/insights", timeout=2)
        if response.status_code != 200:
            print("⚠️  Warning: Server responded with unexpected status")
    except requests.exceptions.RequestException:
        print("❌ ERROR: ThinkingSDK server is not running!")
        print("   Please start the server first:")
        print("   uvicorn thinking_sdk_server.server:app --reload --port 8000")
        return
    
    # Run benchmark
    benchmark = PerformanceBenchmark(
        iterations=args.iterations,
        functions_per_iteration=args.functions
    )
    
    try:
        results = benchmark.run_full_benchmark(detailed=args.detailed)
        benchmark.print_results(results)
        
        if args.memory:
            memory_results = benchmark.memory_benchmark()
            results["memory"] = memory_results
        
        if args.save:
            benchmark.save_results(args.save)
            
    except KeyboardInterrupt:
        print("\n⏹️  Benchmark interrupted by user")
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()