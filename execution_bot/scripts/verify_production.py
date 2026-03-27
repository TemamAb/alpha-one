import requests
import redis
import time
import sys
import os

def verify_local_production():
    print("🚀 VERIFYING LOCAL PRODUCTION STACK")
    print("====================================")
    
    # 0. Docker Status Check
    print("🔍 CHECKING DOCKER CONTAINERS...")
    try:
        import subprocess
        containers = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}: {{.Status}}"], stderr=subprocess.STDOUT).decode()
        print(f"   {containers.strip()}")
    except Exception:
        print("   ❌ Docker Engine: Not running or 'docker' command failed.")

    # 1. Redis Connectivity
    print("🔍 CHECKING REDIS (Port 6379)...")
    try:
        r = redis.from_url("redis://localhost:6379", socket_timeout=2)
        if r.ping():
            print("   ✅ Redis Connection: OK")
            
            # Check Engine Heartbeat/State
            try:
                mode = r.get("alphamark:mode")
                status = r.get("alphamark:status")
                stats = r.get("alphamark:stats")
                
                print(f"   ℹ️  Engine Mode:     {mode.decode() if mode else 'Waiting...'}")
                print(f"   ℹ️  Engine Status:   {status.decode() if status else 'Waiting...'}")
                print(f"   ℹ️  Live Stats:      {'Available' if stats else 'Not yet generated'}")
            except Exception as e:
                print(f"   ⚠️  Redis read warning: {e}")
            
    except Exception as e:
        print(f"   ❌ Redis Connection Failed: {e}")
        print("      (Ensure 'docker-compose up' is running)")

    # 2. Dashboard Connectivity
    # Checking Port 8080 as mapped in docker-compose.yml
    print("\n🔍 CHECKING DASHBOARD (Port 8080)...")
    try:
        resp = requests.get("http://localhost:8080/api/health", timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            print("   ✅ Dashboard HTTP:   OK")
            print(f"   ℹ️  API Health:      {data.get('status')}")
            print(f"   ℹ️  Engine View:     {data.get('engine')}")

            # Heartbeat check via /api/stats
            try:
                resp_stats = requests.get("http://localhost:8080/api/stats", timeout=2)
                if resp_stats.status_code == 200:
                    stats = resp_stats.json()
                    last_update = stats.get('lastUpdate')
                    if last_update:
                        seconds_ago = (time.time() * 1000 - last_update) / 1000
                        status_icon = "✅" if seconds_ago < 30 else "⚠️"
                        print(f"   {status_icon} Last Heartbeat: {seconds_ago:.1f}s ago")
                        print(f"   ℹ️  Active Opps:     {stats.get('activeOpps', 0)}")
                    else:
                        print("   ⚠️  Last Heartbeat:  No data yet (Bot might not be sending)")
            except Exception:
                print("   ❌ Heartbeat:       Could not fetch stats from dashboard")
        else:
            print(f"   ❌ Dashboard HTTP Error: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Dashboard Unreachable: {e}")

    print("\n==============================================")
    print("👉 Access UI: http://localhost:8080")

if __name__ == "__main__":
    verify_local_production()