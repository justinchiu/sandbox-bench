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
