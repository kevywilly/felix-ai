#!/usr/bin/env python3

import subprocess
import signal
import sys
import time
import os
import threading
import queue
from datetime import datetime

scripts = [
    'felix/service/tof.py', 
    'felix/service/controller.py', 
    'felix/service/video.py', 
    'felix/service/autodrive.py',
]

processes = []
log_queue = queue.Queue()

def log_reader(proc, script_name, stream_type):
    """Read logs from a process in a separate thread"""
    stream = proc.stdout if stream_type == 'stdout' else proc.stderr
    for line in iter(stream.readline, ''):
        if line:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_queue.put(f"[{timestamp}] [{script_name}] {line.rstrip()}")
    stream.close()

def start_scripts():
    
    for script in scripts:
        try:
            # Check if script file exists
            if not os.path.exists(script):
                print(f"ERROR: Script {script} not found")
                continue
                
            proc = subprocess.Popen(['python3', script], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  text=True,
                                  bufsize=1)
            
            script_name = os.path.basename(script).replace('.py', '')
            
            # Start log reading threads
            stdout_thread = threading.Thread(target=log_reader, 
                                           args=(proc, script_name, 'stdout'))
            stderr_thread = threading.Thread(target=log_reader, 
                                           args=(proc, script_name, 'stderr'))
            
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            processes.append({
                'proc': proc,
                'script': script,
                'name': script_name,
                'stdout_thread': stdout_thread,
                'stderr_thread': stderr_thread
            })
            
            print(f"Started {script} with PID {proc.pid}")
        except Exception as e:
            print(f"Failed to start {script}: {e}")

def print_logs():
    """Print any new log messages"""
    while not log_queue.empty():
        try:
            message = log_queue.get_nowait()
            print(message)
        except queue.Empty:
            break

def stop_all():
    print("Stopping all scripts...")
    for proc_info in processes:
        proc = proc_info['proc']
        if proc.poll() is None:  # Process is still running
            print(f"Terminating process {proc.pid} ({proc_info['name']})")
            proc.terminate()
            
            # Give it a moment to terminate gracefully
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"Force killing process {proc.pid} ({proc_info['name']})")
                proc.kill()
                proc.wait()
    
    processes.clear()
    print("All scripts stopped")

def check_processes():
    """Check if any processes have died and report status"""
    running_count = 0
    for proc_info in processes:
        proc = proc_info['proc']
        if proc.poll() is None:
            running_count += 1
        else:
            # Process has died
            print(f"Process {proc.pid} ({proc_info['name']}) has exited with code {proc.returncode}")
    
    return running_count

def signal_handler(sig, frame):
    print(f"\nReceived signal {sig}")
    stop_all()
    sys.exit(0)

if __name__ == "__main__":
    # Handle both Ctrl+C and kill signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Starting all scripts...")
    start_scripts()
    
    if not processes:
        print("No processes started successfully. Exiting.")
        sys.exit(1)
    
    print("=" * 60)
    print("LIVE LOGS (Ctrl+C to stop all scripts)")
    print("=" * 60)
    
    try:
        while True:
            # Print any new log messages
            print_logs()
            
            # Check process status less frequently
            running = check_processes()
            if running == 0:
                print("All processes have stopped. Exiting.")
                break
            
            time.sleep(0.1)  # Check logs frequently for real-time feel
    except KeyboardInterrupt:
        stop_all()
    except Exception as e:
        print(f"Unexpected error: {e}")
        stop_all()
    
    print("Manager exiting.")