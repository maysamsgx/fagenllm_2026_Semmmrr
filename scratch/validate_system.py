import requests
import time

BASE_URL = "http://localhost:8000/api"

def validate_system():
    print("--- SYSTEM VALIDATION ---")
    
    # 1. Health Check
    try:
        res = requests.get("http://localhost:8000/health")
        print(f"Health: {res.json()['status']}")
    except:
        print("Backend not running. Please start it with: python main.py")
        return

    # 2. Check Analytics
    print("\nChecking Analytics...")
    aging = requests.get(f"{BASE_URL}/analytics/aging").json()
    print(f"Aging Buckets: {len(aging)} found")
    
    perf = requests.get(f"{BASE_URL}/analytics/performance").json()
    print(f"Performance Metrics: DSO={perf['dso']}, Recovery={perf['recovery_rate']}%")

    # 3. Check Disputes
    disputes = requests.get(f"{BASE_URL}/analytics/disputes").json()
    print(f"Active Disputes: {len(disputes)}")

    # 4. Trigger a Reconciliation Run
    print("\nTriggering Reconciliation Run...")
    requests.post(f"{BASE_URL}/reconciliation/run")
    
    # Wait for background task
    time.sleep(5)
    
    # 5. Verify Causal Links
    links = requests.get(f"{BASE_URL}/intel/causal-graph").json()
    print(f"Causal Links in System: {len(links['edges'])}")
    
    print("\nVALIDATION COMPLETE.")

if __name__ == "__main__":
    validate_system()
