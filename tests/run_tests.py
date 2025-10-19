#!/usr/bin/env python3
"""
Test runner for AI Enrichment Pipeline
"""

import sys
import os
import subprocess
from pathlib import Path

def run_test_file(test_file):
    """Run a single test file"""
    print(f"\n{'='*60}")
    print(f"Running: {test_file}")
    print('='*60)
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=False, 
                              cwd=os.path.dirname(test_file))
        return result.returncode == 0
    except Exception as e:
        print(f"ERROR running {test_file}: {e}")
        return False

def main():
    """Run all tests"""
    tests_dir = Path(__file__).parent
    
    # Test files to run in order
    test_files = [
        'test_setup.py',
        'test_all_components.py', 
        'test_integration.py'
    ]
    
    print("AI Enrichment Pipeline Test Suite")
    print("=" * 60)
    
    passed = 0
    total = len(test_files)
    
    for test_file in test_files:
        test_path = tests_dir / test_file
        if test_path.exists():
            if run_test_file(str(test_path)):
                passed += 1
                print(f"✓ {test_file} PASSED")
            else:
                print(f"✗ {test_file} FAILED")
        else:
            print(f"⚠ {test_file} not found")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed.")
        return 1

if __name__ == '__main__':
    sys.exit(main())