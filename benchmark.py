#!/usr/bin/env python3
"""
Startup time benchmark for Morph, Modal, and Runloop sandboxes
Measures how long it takes to spin up and execute a minimal Python script
"""

import time
import statistics
import json
import os
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

console = Console()

# Standardized VM Configuration across all providers
# All sandboxes use: 1 vCPU, 2GB RAM, 2GB disk (where configurable)
# Note: Runloop requires minimum 2GB RAM for 1 vCPU (1:2 ratio)
VM_CONFIG = {
    "vcpus": 1,
    "memory_mb": 2048,  # 2GB (minimum for Runloop with 1 vCPU)
    "disk_gb": 2        # 2GB
}

# Simple test script that sandboxes will execute
TEST_SCRIPT = """
import sys
print(f"Python {sys.version_info.major}.{sys.version_info.minor} ready")
"""


class SandboxBenchmark:
    def __init__(self, concurrent: int = 50, batches: int = 2):
        self.concurrent = concurrent  # Number of sandboxes to run concurrently
        self.batches = batches  # Number of batches to run
        self.results: Dict[str, List[float]] = {}

    async def run_single_morph_sandbox(self, client, snapshot_id: str) -> float:
        """Run a single Morph sandbox and return the execution time"""
        start = time.perf_counter()

        # Start instance using async API
        instance = await client.instances.astart(snapshot_id=snapshot_id)

        # Wait for instance to be ready
        await instance.await_until_ready()

        # Use async SSH context manager
        async with instance.assh() as ssh:
            # Write the test script and execute it
            await ssh.arun(f"echo '{TEST_SCRIPT}' > /tmp/test.py")
            result = await ssh.arun("python3 /tmp/test.py")

        # Stop the instance
        await instance.astop()

        elapsed = time.perf_counter() - start
        return elapsed

    async def benchmark_morph(self) -> List[float]:
        """Benchmark Morph sandbox startup time with concurrent execution"""
        times = []

        from morphcloud.api import MorphCloudClient

        console.print("\n[cyan]Testing Morph sandbox startup...[/cyan]")
        console.print(f"  Running {self.concurrent} sandboxes concurrently, {self.batches} batches")

        # Initialize Morph client
        client = MorphCloudClient()

        # Create a snapshot for testing with standardized VM config using async API
        snapshot = await client.snapshots.acreate(
            image_id="morphvm-minimal",
            vcpus=VM_CONFIG["vcpus"],
            memory=VM_CONFIG["memory_mb"],
            disk_size=VM_CONFIG["disk_gb"] * 1024  # Convert GB to MB
        )

        # Run batches
        for batch_num in range(self.batches):
            console.print(f"\n  Batch {batch_num + 1}/{self.batches}:")

            # Create tasks for concurrent execution
            tasks = []
            for i in range(self.concurrent):
                task = asyncio.create_task(self.run_single_morph_sandbox(client, snapshot.id))
                tasks.append(task)

            # Wait for all tasks in batch to complete
            batch_times = await asyncio.gather(*tasks)

            # Display batch results
            for i, elapsed in enumerate(batch_times):
                console.print(f"    Sandbox {i+1}: {elapsed:.3f}s")

            times.extend(batch_times)

        # Display results immediately after running
        self.display_provider_results("Morph", times)
        return times

    async def run_single_modal_sandbox(self, app) -> float:
        """Run a single Modal sandbox and return the execution time"""
        import modal

        start = time.perf_counter()

        # Create and run a Modal sandbox with standardized configuration using async API
        sandbox = await modal.Sandbox.create.aio(
            "python3", f"-c \"{TEST_SCRIPT}\"",
            app=app,
            cpu=float(VM_CONFIG["vcpus"]),  # 1 CPU core
            memory=VM_CONFIG["memory_mb"],   # 2GB RAM
            timeout=60  # 60 second timeout
        )

        # Wait for completion using async API
        await sandbox.wait.aio()

        # Read output (optional, for verification)
        output = await sandbox.stdout.read.aio()

        elapsed = time.perf_counter() - start
        return elapsed

    async def benchmark_modal(self) -> List[float]:
        """Benchmark Modal sandbox startup time with concurrent execution"""
        times = []

        import modal

        console.print("\n[magenta]Testing Modal sandbox startup...[/magenta]")
        console.print(f"  Running {self.concurrent} sandboxes concurrently, {self.batches} batches")

        # Create or look up Modal app using async API
        app = await modal.App.lookup.aio("sandbox-benchmark", create_if_missing=True)

        # Run batches
        for batch_num in range(self.batches):
            console.print(f"\n  Batch {batch_num + 1}/{self.batches}:")

            # Create tasks for concurrent execution
            tasks = []
            for i in range(self.concurrent):
                task = asyncio.create_task(self.run_single_modal_sandbox(app))
                tasks.append(task)

            # Wait for all tasks in batch to complete
            batch_times = await asyncio.gather(*tasks)

            # Display batch results
            for i, elapsed in enumerate(batch_times):
                console.print(f"    Sandbox {i+1}: {elapsed:.3f}s")

            times.extend(batch_times)

        # Display results immediately after running
        self.display_provider_results("Modal", times)
        return times

    async def run_single_runloop_sandbox(self, client) -> float:
        """Run a single Runloop sandbox and return the execution time"""
        from runloop_api_client.types import LaunchParameters

        start = time.perf_counter()

        # Create and run a devbox with standardized configuration
        # Note: Runloop requires CPU:memory ratio between 1:2 and 1:8
        # With 1 CPU, we need minimum 2GB memory
        launch_params = LaunchParameters(
            # Set resources - Runloop requires 1:2 CPU:memory ratio minimum
            custom_cpu_cores=VM_CONFIG["vcpus"],  # 1 CPU core
            custom_gb_memory=2,  # 2 GB memory (minimum for 1 CPU)
            custom_disk_size=VM_CONFIG["disk_gb"],  # 2 GB disk
            resource_size_request="CUSTOM_SIZE"  # Use custom sizing
        )

        # Create devbox and wait for it to be running
        devbox = await client.devboxes.create_and_await_running(
            launch_parameters=launch_params
        )

        # Execute the test script
        result = await client.devboxes.execute(
            id=devbox.id,
            command=f"python3 -c '{TEST_SCRIPT}'"
        )

        # Clean up - shutdown the devbox
        await client.devboxes.shutdown(devbox.id)

        elapsed = time.perf_counter() - start
        return elapsed

    async def benchmark_runloop(self) -> List[float]:
        """Benchmark Runloop sandbox startup time with concurrent execution"""
        times = []

        from runloop_api_client import AsyncRunloop
        from runloop_api_client.types import LaunchParameters

        console.print("\n[yellow]Testing Runloop sandbox startup...[/yellow]")
        console.print(f"  Running {self.concurrent} sandboxes concurrently, {self.batches} batches")

        # Initialize Runloop client
        api_key = os.getenv("RUNLOOP_API_KEY")
        if not api_key:
            console.print("[red]RUNLOOP_API_KEY not set. Please set your API key.[/red]")
            return []

        client = AsyncRunloop(bearer_token=api_key)

        # Run batches
        for batch_num in range(self.batches):
            console.print(f"\n  Batch {batch_num + 1}/{self.batches}:")

            # Create tasks for concurrent execution
            tasks = []
            for i in range(self.concurrent):
                task = asyncio.create_task(self.run_single_runloop_sandbox(client))
                tasks.append(task)

            # Wait for all tasks in batch to complete
            batch_times = await asyncio.gather(*tasks)

            # Display batch results
            for i, elapsed in enumerate(batch_times):
                console.print(f"    Sandbox {i+1}: {elapsed:.3f}s")

            times.extend(batch_times)

        # Display results immediately after running
        self.display_provider_results("Runloop", times)
        return times

    def display_provider_results(self, provider: str, times: List[float]):
        """Display results for a single provider immediately after running"""
        if not times:
            console.print(f"[red]No results for {provider}[/red]")
            return

        sorted_times = sorted(times, reverse=True)

        # Create a simple table showing all iterations
        console.print(f"\n[bold]{provider} Results (sorted descending):[/bold]")
        for i, time_val in enumerate(sorted_times):
            if i == 0:
                # Cold start (slowest)
                console.print(f"  Run {i+1}: [bold red]{time_val:.3f}s[/bold red] (cold start)")
            else:
                console.print(f"  Run {i+1}: {time_val:.3f}s")

        # Show quick stats
        mean = statistics.mean(times)
        median = statistics.median(times)
        console.print(f"  [dim]Mean: {mean:.3f}s, Median: {median:.3f}s, Best: {sorted_times[-1]:.3f}s[/dim]")

    def calculate_stats(self, times: List[float]) -> Dict[str, float]:
        """Calculate statistics from timing data"""
        if not times:
            return {
                "mean": 0,
                "median": 0,
                "min": 0,
                "max": 0,
                "std_dev": 0,
                "p95": 0,
                "p99": 0,
            }

        sorted_times = sorted(times)
        n = len(sorted_times)

        return {
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            "p95": sorted_times[int(n * 0.95)] if n > 0 else 0,
            "p99": sorted_times[int(n * 0.99)] if n > 0 else 0,
        }

    async def run_benchmarks(self, providers: Optional[List[str]] = None):
        """Run benchmarks for specified providers"""
        console.print("\n[bold green]🚀 Sandbox Startup Benchmark[/bold green]")
        console.print(f"Concurrent sandboxes: {self.concurrent}")
        console.print(f"Batches: {self.batches}")
        console.print(f"Total runs per provider: {self.concurrent * self.batches}")
        console.print(f"Python version: 3.13")
        console.print(f"VM Configuration: {VM_CONFIG['vcpus']} vCPU, {VM_CONFIG['memory_mb']}MB RAM, {VM_CONFIG['disk_gb']}GB disk")
        console.print("-" * 50)

        # Default to all providers if not specified
        if providers is None:
            providers = ["morph", "modal", "runloop"]

        # Run benchmarks for selected providers
        if "morph" in providers:
            self.results["Morph"] = await self.benchmark_morph()
        if "modal" in providers:
            self.results["Modal"] = await self.benchmark_modal()
        if "runloop" in providers:
            self.results["Runloop"] = await self.benchmark_runloop()

        # Filter out empty results
        self.results = {k: v for k, v in self.results.items() if v}

        if not self.results:
            console.print("\n[red]❌ No benchmarks completed successfully[/red]")
            console.print("[dim]Please install SDKs and configure API keys[/dim]")
            return

        # Display all iterations sorted descending
        console.print("\n[bold]📊 All Iterations (sorted descending, in seconds)[/bold]\n")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Iteration", style="dim", width=10)

        # Add a column for each provider
        for provider in self.results.keys():
            table.add_column(provider, justify="right", style="cyan")

        # Sort times for each provider (descending)
        sorted_results = {}
        for provider, times in self.results.items():
            sorted_results[provider] = sorted(times, reverse=True)

        # Add rows for each iteration
        total_runs = self.concurrent * self.batches
        for i in range(total_runs):
            row = [f"Run {i+1}"]
            for provider in self.results.keys():
                if i < len(sorted_results[provider]):
                    time_val = sorted_results[provider][i]
                    # Highlight cold start (typically the slowest/first in descending order)
                    if i == 0:
                        row.append(f"[bold red]{time_val:.3f}[/bold red]")
                    else:
                        row.append(f"{time_val:.3f}")
                else:
                    row.append("-")
            table.add_row(*row)

        console.print(table)

        # Also show summary statistics
        console.print("\n[bold]📈 Summary Statistics[/bold]\n")

        summary_table = Table(show_header=True, header_style="bold magenta")
        summary_table.add_column("Provider", style="cyan", width=12)
        summary_table.add_column("Cold Start", justify="right", style="red")
        summary_table.add_column("Best", justify="right", style="green")
        summary_table.add_column("Mean", justify="right")
        summary_table.add_column("Median", justify="right")

        stats = {}
        for provider, times in self.results.items():
            stats[provider] = self.calculate_stats(times)
            sorted_times = sorted(times, reverse=True)

            summary_table.add_row(
                provider,
                f"{sorted_times[0]:.3f}" if sorted_times else "-",  # Cold start (slowest)
                f"{sorted_times[-1]:.3f}" if sorted_times else "-",  # Best (fastest)
                f"{stats[provider]['mean']:.3f}",
                f"{stats[provider]['median']:.3f}"
            )

        console.print(summary_table)

        # Performance comparison
        if len(stats) > 1:
            console.print("\n[bold]📈 Performance Comparison[/bold]\n")

            providers_sorted = sorted(stats.items(), key=lambda x: x[1]["mean"])
            base_provider, base_stats = providers_sorted[0]

            for provider, provider_stats in providers_sorted[1:]:
                diff = provider_stats["mean"] - base_stats["mean"]
                percent = (diff / base_stats["mean"]) * 100
                factor = provider_stats["mean"] / base_stats["mean"]

                console.print(f"  {provider} is [red]{factor:.2f}x slower[/red] ({percent:.1f}% more time) than {base_provider}")

        # Save results to JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_results_{timestamp}.json"

        output_data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "concurrent": self.concurrent,
                "batches": self.batches,
                "total_runs": self.concurrent * self.batches,
                "python_version": "3.13",
                "vm_config": VM_CONFIG
            },
            "raw_times": {k: v for k, v in self.results.items()},
            "statistics": stats,
        }

        with open(filename, 'w') as f:
            json.dump(output_data, f, indent=2)

        console.print(f"\n[dim]Results saved to {filename}[/dim]")


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark sandbox startup times")
    parser.add_argument(
        "--concurrent",
        type=int,
        default=50,
        help="Number of concurrent sandboxes per batch (default: 50)"
    )
    parser.add_argument(
        "--batches",
        type=int,
        default=2,
        help="Number of batches to run (default: 2)"
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=["morph", "modal", "runloop"],
        help="Providers to benchmark (default: all)"
    )

    args = parser.parse_args()

    benchmark = SandboxBenchmark(
        concurrent=args.concurrent,
        batches=args.batches
    )

    await benchmark.run_benchmarks(providers=args.providers)


if __name__ == "__main__":
    asyncio.run(main())
