#!/usr/bin/env python3
"""Quick benchmark runner script."""

import subprocess
import sys
from pathlib import Path

def main():
    """Run performance benchmarks."""
    benchmark_script = Path(__file__).parent / "benchmarks" / "performance_benchmark.py"
    
    print("🚀 Running Git Data Distiller Performance Benchmarks")
    print("=" * 60)
    
    try:
        # Run the benchmark with quick mode
        result = subprocess.run([
            sys.executable, str(benchmark_script), "--quick"
        ], check=True, capture_output=False)
        
        print("\n✅ Benchmarks completed successfully!")
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Benchmarks failed with exit code {e.returncode}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"❌ Benchmark script not found: {benchmark_script}")
        sys.exit(1)

if __name__ == "__main__":
    main()