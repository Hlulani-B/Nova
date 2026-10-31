from testcases import long_python_challenges 
from subprocess import run_python_code

def run_tests():
    print("🚀 Starting Challenge Test Suite...\n")
    
    passed_count = 0
    total_challenges = len(long_python_challenges)

    for index, challenge in enumerate(long_python_challenges, start=1):
        actual = run_python_code(challenge["code"])
        expected = challenge["expected"]
        
        passed = (actual == expected)
        
        if passed:
            passed_count += 1
            print(f"✅ Challenge {index}: PASSED")
        else:
            print(f"❌ Challenge {index}: FAILED")
            print(f"   Expected: {repr(expected)}")
            print(f"   Got:      {repr(actual)}")
            print("-" * 40)

    print("\n" + "=" * 40)
    print(f"📊 Test Summary: {passed_count}/{total_challenges} challenges passed.")
    print("=" * 40)

if __name__ == "__main__":
    run_tests()