# test_runner.py
"""
Master test runner — executes all test layers in sequence.
Stops at the first layer that fails.

Usage: python test_runner.py
"""
import subprocess
import sys
import os

TESTS = [
    ("1. Connectivity",       "tests/test_01_connectivity.py"),
    ("2. Authentication",     "tests/test_02_authentication.py"),
    ("3. Query Validation",   "tests/test_03_queries.py"),
    ("4. Data Collection",    "tests/test_04_data_collection.py"),
    ("5. End-to-End",         "tests/test_05_end_to_end.py"),
]


def main():
    print("=" * 70)
    print("  RSC DASHBOARD — DATA PIPELINE TEST SUITE")
    print("=" * 70)
    print()

    passed_layers = 0

    for name, script in TESTS:
        print(f"\n{'─'*70}")
        print(f"  LAYER {name}")
        print(f"{'─'*70}\n")

        result = subprocess.run(
            [sys.executable, script],
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )

        if result.returncode != 0:
            print(f"\n❌ LAYER {name} FAILED")
            print(f"   Fix the issues above before proceeding.")
            print(f"\n   Layers passed: {passed_layers}/{len(TESTS)}")
            sys.exit(1)

        passed_layers += 1

    print(f"\n{'='*70}")
    print(f"  ✅ ALL {passed_layers} LAYERS PASSED")
    print(f"{'='*70}")
    print(f"\n  Your data pipeline is working correctly.")
    print(f"  Launch the dashboard with:")
    print(f"\n    streamlit run dashboard.py\n")


if __name__ == "__main__":
    main()