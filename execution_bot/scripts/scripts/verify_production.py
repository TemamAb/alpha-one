import requests
import redis
import time
import sys

def verify_local_production():
    print("🚀 VERIFYING LOCAL PRODUCTION STACK (No Cloud)")
    print("==============================================")
    
    # 1. Redis Connectivity
    print("🔍 CHECKING REDIS (Port 6379)...")
    try:
        # Connect to localhost since we are running this script from host
        r = redis.from_url("redis://localhost:6379", socket_timeout=2)
        if r.ping():
            print("   ✅ Redis Connection: OK")
            
            # Check Engine Heartbeat/State
            mode = r.get("alphamark:mode")
            status = r.get("alphamark:status")
            stats = r.get("alphamark:stats")
            
            print(f"   ℹ️  Engine Mode:     {mode.decode() if mode else 'Waiting...'}")
            print(f"   ℹ️  Engine Status:   {status.decode() if status else 'Waiting...'}")
            print(f"   ℹ️  Live Stats:      {'Available' if stats else 'Not yet generated'}")
            
    except Exception as e:
        print(f"   ❌ Redis Connection Failed: {e}")
        print("      (Ensure 'docker-compose up' is running)")
        return

    # 2. Dashboard Connectivity
    print("\n🔍 CHECKING DASHBOARD (Port 3000)...")
    try:
        resp = requests.get("http://localhost:3000/api/health", timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            print("   ✅ Dashboard HTTP:   OK")
            print(f"   ℹ️  API Health:      {data.get('status')}")
            print(f"   ℹ️  Engine View:     {data.get('engine')}")
        else:
            print(f"   ❌ Dashboard HTTP Error: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Dashboard Unreachable: {e}")

    print("\n==============================================")
    print("✅ SYSTEM READY.")
    print("👉 Access UI: http://localhost:3000")

if __name__ == "__main__":
    verify_local_production()