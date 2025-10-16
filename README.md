# Sandbox Startup Benchmark

A benchmarking tool to measure and compare startup times for Morph, Modal, and Runloop sandboxes.

## Installation

```bash
# Install in development mode
pip install -e .

# Or install just the dependencies
pip install modal morphcloud runloop-api-client rich click psutil python-dotenv
```

## Configuration

Before running the benchmarks, you'll need to configure API keys for the sandbox providers:

### Modal
```bash
# Install Modal and authenticate
modal token new
```

### Runloop
```bash
# Set your Runloop API key
export RUNLOOP_API_KEY="your-api-key-here"
```

### Morph
Morph client should work with your existing authentication.

## Usage

Run the benchmark with default settings (10 iterations, 2 warmup):
```bash
python benchmark.py
```

Customize the number of iterations:
```bash
python benchmark.py --iterations 20 --warmup 5
```

Benchmark specific providers only:
```bash
python benchmark.py --providers modal runloop
```

## What It Measures

The benchmark measures the complete startup time for each sandbox, including:
- Sandbox initialization
- Python runtime startup
- Execution of a minimal test script
- Result retrieval

## Output

The tool provides:
- **Statistical Summary**: Mean, median, min, max, standard deviation, P95, and P99 latencies
- **Performance Comparison**: Relative performance between providers
- **JSON Export**: Detailed results saved to `benchmark_results_[timestamp].json`

## Example Output

```
🚀 Sandbox Startup Benchmark
Iterations: 10 (+ 2 warmup)
Python version: 3.13
--------------------------------------------------

📊 Benchmark Results (in seconds)

┏━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━┓
┃ Provider   ┃   Mean ┃  Median ┃   Min ┃   Max ┃ Std Dev ┃   P95 ┃   P99 ┃
┡━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━┩
│ ⚡ Morph   │  0.245 │   0.242 │ 0.221 │ 0.289 │   0.023 │ 0.285 │ 0.288 │
│ Modal      │  0.512 │   0.508 │ 0.487 │ 0.556 │   0.021 │ 0.551 │ 0.555 │
│ Runloop    │  0.387 │   0.385 │ 0.362 │ 0.421 │   0.019 │ 0.418 │ 0.420 │
└────────────┴────────┴─────────┴───────┴───────┴─────────┴───────┴───────┘

📈 Performance Comparison

  Modal is 2.09x slower (108.9% more time) than Morph
  Runloop is 1.58x slower (58.0% more time) than Morph
```

## Requirements

- Python 3.13+
- Internet connection for API calls
- Valid API credentials for each provider you want to test# sandbox-bench
