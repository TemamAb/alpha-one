import os
import subprocess
import time
import sys

def run_command(command, shell=True, env=None):
    print(f"🚀 Executing: {command}")
    current_env = os.environ.copy()
    if env:
        current_env.update(env)
    process = subprocess.Popen(command, shell=shell, env=current_env)
    return process

def main():
    print("🌟 AlphaMark Arbitrage - Automated Simulation Startup")
    print("=====================================================")

    # Step 0: Port Cleanup
    print("🧹 Cleaning up ports and existing containers...")
    cleanup_path = os.path.join(os.getcwd(), "port_cleanup.bat")
    if os.path.exists(cleanup_path):
        subprocess.run([cleanup_path], shell=True)
    
    # Step 1: Start Docker Infrastructure
    print("🏗️  Starting Docker Stack (Redis + Dashboard)...")
    docker_active = True
    try:
        # Use docker-compose up for redis and dashboard only to keep bot local for logs
        subprocess.run(["docker-compose", "up", "-d", "redis", "dashboard"], check=True)
    except Exception as e:
        print(f"⚠️  Docker Infrastructure could not be started: {e}")
        print("👉 Proceeding in STANDALONE MODE (No Dashboard/Redis).")
        print("   Note: Ensure your .env has valid RPC URLs for Ethereum/Polygon.")
        docker_active = False

    # Step 2: Environment Setup
    sim_env = {
        "PAPER_TRADING_MODE": "true",
        "MAX_SEARCH_PATHS": "50000",
        "PYTHONPATH": os.getcwd()
    }
    if docker_active:
        sim_env["REDIS_URL"] = "redis://localhost:6379"

    # Wait for Redis health
    if docker_active:
        print("⏳ Waiting for Redis to stabilize...")
        time.sleep(5)

    # Step 3: Launch Bot
    print("🤖 Launching Arbitrage Engine...")
    bot_path = os.path.join("execution_bot", "scripts", "bot.py")
    bot_process = run_command(f"{sys.executable} {bot_path}", env=sim_env)

    try:
        bot_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down simulation...")
        bot_process.terminate()

if __name__ == "__main__":
    main()