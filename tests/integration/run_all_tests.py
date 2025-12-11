#!/usr/bin/env python3
"""
Master test runner for Customer Support Assistant integration tests.

Executes tests in phases with fail-fast behavior.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List
import subprocess
from dataclasses import dataclass

@dataclass
class TestResult:
    """Result of a test execution."""
    phase: str
    test_name: str
    passed: bool
    duration: float


class TestRunner:
    """Orchestrates execution of all test phases."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[TestResult] = []
        self.start_time = time.time()
        
    def run_phase(self, phase_name: str, phase_dir: Path) -> bool:
        """Run all tests in a phase directory."""
        print(f"\n{'='*70}")
        print(f"Phase: {phase_name}")
        print(f"{'='*70}\n")
        
        test_files = sorted(phase_dir.glob("test_*.py"))
        
        if not test_files:
            print(f"⚠️  No test files found in {phase_dir}")
            return True
            
        for test_file in test_files:
            if not self._run_test_file(phase_name, test_file):
                return False
                
        return True
    
    def _run_test_file(self, phase_name: str, test_file: Path) -> bool:
        """Run a single test file using pytest or as a script."""
        test_name = test_file.stem
        print(f"▶ Running {test_name}...")
        
        start = time.time()
        
        # Check if file has pytest test functions or should be run as script
        with open(test_file, 'r') as f:
            content = f.read()
            has_pytest_tests = 'def test_' in content or '@pytest.' in content
        
        # Run as script if no pytest tests found, otherwise use pytest
        if not has_pytest_tests:
            cmd = [sys.executable, str(test_file)]
        else:
            cmd = [
                sys.executable, "-m", "pytest",
                str(test_file),
                "-v" if self.verbose else "-q",
                "--tb=short"
            ]
        
        # Set PYTHONPATH to project root for imports to work
        env = os.environ.copy()
        project_root = Path(__file__).parent.parent.parent
        env['PYTHONPATH'] = str(project_root)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                env=env
            )
            
            duration = time.time() - start
            passed = result.returncode == 0
            
            if passed:
                print(f"  ✅ {test_name} passed ({duration:.1f}s)\n")
            else:
                print(f"  ❌ {test_name} FAILED ({duration:.1f}s)\n")
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr)
            
            self.results.append(TestResult(
                phase=phase_name,
                test_name=test_name,
                passed=passed,
                duration=duration
            ))
            
            return passed
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start
            print(f"  ⏱️  {test_name} TIMEOUT ({duration:.1f}s)\n")
            self.results.append(TestResult(
                phase=phase_name,
                test_name=test_name,
                passed=False,
                duration=duration
            ))
            return False
            
        except Exception as e:
            duration = time.time() - start
            print(f"  ❌ {test_name} ERROR ({duration:.1f}s): {e}\n")
            self.results.append(TestResult(
                phase=phase_name,
                test_name=test_name,
                passed=False,
                duration=duration
            ))
            return False
    
    def print_summary(self) -> bool:
        """Print test execution summary."""
        total_duration = time.time() - self.start_time
        
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        # Group results by phase
        phases: Dict[str, List[TestResult]] = {}
        for result in self.results:
            if result.phase not in phases:
                phases[result.phase] = []
            phases[result.phase].append(result)
        
        total_passed = 0
        total_failed = 0
        failed_phase = None
        
        for phase_name in ["Setup", "Infrastructure", "Sub-agents", "Supervisor"]:
            if phase_name not in phases:
                continue
                
            phase_results = phases[phase_name]
            passed = sum(1 for r in phase_results if r.passed)
            failed = sum(1 for r in phase_results if not r.passed)
            
            total_passed += passed
            total_failed += failed
            
            status = "✅ PASSED" if failed == 0 else "❌ FAILED"
            print(f"\n{phase_name}: {status}")
            print(f"  Passed: {passed}/{len(phase_results)}")
            
            if failed > 0:
                failed_phase = phase_name
                print(f"  Failed tests:")
                for result in phase_results:
                    if not result.passed:
                        print(f"    • {result.test_name}")
        
        print(f"\n{'─' * 70}")
        print(f"Total: {total_passed} passed, {total_failed} failed")
        print(f"Duration: {total_duration:.1f}s")
        
        if total_failed > 0:
            print(f"\n❌ Tests FAILED in {failed_phase} phase")
            return False
        else:
            print(f"\n✅ All tests PASSED!")
            return True


def main() -> int:
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(
        description="Run Customer Support Assistant integration tests"
    )
    
    parser.add_argument(
        "--phase",
        action="append",
        choices=["setup", "infrastructure", "sub-agents", "supervisor"],
        help="Run specific phase(s) only"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Determine which phases to run
    phases_to_run = args.phase or ["setup", "infrastructure", "sub-agents", "supervisor"]
    
    runner = TestRunner(verbose=args.verbose)
    base_dir = Path(__file__).parent
    
    phase_map = {
        "setup": ("Setup", base_dir / "00_setup"),
        "infrastructure": ("Infrastructure", base_dir / "01_infrastructure"),
        "sub-agents": ("Sub-agents", base_dir / "02_sub_agents"),
        "supervisor": ("Supervisor", base_dir / "03_supervisor")
    }
    
    print("=" * 70)
    print("INTEGRATION TEST SUITE")
    print("=" * 70)
    
    # Run each phase
    all_passed = True
    for phase_key in phases_to_run:
        phase_name, phase_dir = phase_map[phase_key]
        
        if not phase_dir.exists():
            print(f"\n⚠️  Phase directory not found: {phase_dir}")
            continue
        
        if not runner.run_phase(phase_name, phase_dir):
            all_passed = False
            print(f"\n❌ Phase '{phase_name}' failed. Stopping (fail-fast).")
            break
    
    # Print summary
    success = runner.print_summary()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
