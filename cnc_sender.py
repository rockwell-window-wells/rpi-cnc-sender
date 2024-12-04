#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov 11 10:49:28 2024

@author: Ryan.Larson
"""

import tkinter as tk
import serial
from serial.tools import list_ports
import time
import threading
import pickle
from queue import Queue

with open('config.pkl', 'rb') as f:
    config = pickle.load(f)
    
# Set up serial connection
ports = list_ports.comports()
if ports:
    print(f'Ports available: {ports}')
    serial_port = ports[0].device
    dummy_mode = False
    # serial_port = str(ports[0])
else:
    print('No serial ports available. Entering dummy mode')
    dummy_mode = True
    serial_port = '/dev/ttyUSB0'

baud_rate = 115200
gcode_file_path = config['gcode_file_path']

# Initialize the serial connection
if not dummy_mode:
    ser = serial.Serial(serial_port, baud_rate)
    print("Initializing serial connection")
else:
    ser = None
    print("Initializing serial connection (dummy mode)")
time.sleep(2)  # Wait for GRBL to initialize

# Send an initial command to wake up GRBL
if not dummy_mode:
    ser.write(b"\r\n\r\n")
    print("Sending command to wake GRBL")    
    time.sleep(2)
    ser.flushInput()

buffer_queue = Queue(maxsize=16)
pause_flag = threading.Event()
pause_flag.set()    # Initially not paused

def exit_fullscreen(event=None):
    root.attributes('-fullscreen', False)  # Exit full-screen

def pause_resume(dummy_mode):
    """Toggle pause and resume functionality."""
    if pause_flag.is_set():
        # Pause the CNC
        pause_flag.clear()
        if not dummy_mode:
            ser.write(b"!") # GRBL pause command
            ser.flush()
            ser.write(b"M5\n") # Stop spindle
            ser.flush()
        status_label.config(text="Paused", fg="red")
        pause_button.config(text="Resume", bg="green")
    else:
        # Resume the CNC
        if not dummy_mode:
            ser.write(b"~")     # GRBL resume command
            ser.flush()
            ser.write(b"M3 S1000\n") # Restart spindle
            ser.flush()
        pause_flag.set()
        status_label.config(text="Resumed", fg="green")
        pause_button.config(text="Pause", bg="red")

def run_gcode(dummy_mode):
    """Send Gcode commands from the file to the CNC router."""
    def gcode_thread():
        try:
            # Unlock the machine
            if not dummy_mode:
                ser.write(b"$X\n") # GRBL unlock command
                ser.flush()
                time.sleep(1)
                ser.write(b"$H\n") # Home the machine
                ser.flush()                
                status_label.config(text="Machine unlocked, starting toolpath")
        
            with open(gcode_file_path, 'r') as file:
                for line in file:
                    if not pause_flag.is_set():
                        time.sleep(0.1)  # Wait while paused
                        continue
                    line = line.strip()
                    if line and not line.startswith(';'):
                        buffer_queue.put(line)
                        send_buffered_commands(dummy_mode)
        except FileNotFoundError:
            status_label.config(text=f'Error: File not found at {gcode_file_path}')
        except Exception as e:
            status_label.config(text=f'Error reading file: {e}')
        finally:
            while not buffer_queue.empty():
                send_buffered_commands(dummy_mode)
            status_label.config(text="COMPLETE")
            
            # Lock the machine
            if not dummy_mode:
                ser.write(b"M5\n") # Stop spindle
                ser.flush()
                ser.write(b"$H\n") # Home the machine (optional locking mechanism)
                ser.flush()
                status_label.config(text="Machine locked and toolpath complete")
            else:
                status_label.config(text="Toolpath complete (dummy mode)")

    threading.Thread(target=gcode_thread, daemon=True).start()

# def move_to_load_position(dummy_mode):
    # """Move the router out of the way for loading stock."""
    # load_position_command = "G0 X0 Y0 Z10"  # Adjust coordinates as needed
    # if not dummy_mode:
        # ser.write((load_position_command + '\n').encode())
        # ser.flush()
        # status_label.config(text=f'Sent: {load_position_command}')
    # else:
        # print(f"Moved to load position {load_position_command} (dummy mode)")
        # status_label.config(text=f'Sent: {load_position_command} (dummy mode)')
    
    # root.update_idletasks()

# def run_gcode(dummy_mode):
    # """Send Gcode commands from the file to the CNC router."""
    # try:
        # # Unlock the machine
        # if not dummy_mode:
            # ser.write(b"$X\n") # GRBL unlock command
            # ser.flush()
            # time.sleep(1)
            # status_label.config(text="Machine unlocked, starting toolpath")
        
        # with open(gcode_file_path, 'r') as file:
            # # print(f'File: {file}')
            # for line in file:
                # # line = line.strip()
                # print(line)
                # if line and not line.startswith(';'):  # Ignore comments
                    # buffer_queue.put(line)
                    # send_buffered_commands(dummy_mode)
    # except FileNotFoundError:
        # print(f'File not found: {gcode_file_path}')
        # status_label.config(text=f'Error: File not found at {gcode_file_path}')
    # except Exception as e:
        # print(f'Error reading file: {e}')
        # status_label.config(text=f'Error reading file: {e}')
    # finally:
        # # Send remaining commands in buffer
        # while not buffer_queue.empty():
            # send_buffered_commands(dummy_mode)
            
        # # Lock the machine
        # if not dummy_mode:
            # ser.write(b"M5\n") # Stop spindle
            # ser.flush()
            # ser.write(b"$H\n") # Home the machine (optional locking mechanism)
            # ser.flush()
            # status_label.config(text="Machine locked and toolpath complete")
        # else:
            # status_label.config(text="Toolpath complete (dummy mode)")
                
    # status_label.config(text="COMPLETE")
    # root.update_idletasks()
    
def send_buffered_commands(dummy_mode):
    """Send commands from the buffer if there's space."""
    if buffer_queue.empty():
        print('Buffer queue is empty. No data being read.')
        status_label.config(text='Buffer queue is empty. No data being read.')
        root.update_idletasks()
    while not buffer_queue.empty():
        command = buffer_queue.get()
        print(command)
        
        if not dummy_mode:
            ser.write((command + '\n').encode())
            ser.flush()
            response = ser.readline().decode().strip()
            print(f"Sent: {command}, Response: {response}")
            
            if response == 'ok':
                # print(f'Sent: {command} (dummy)')
                status_label.config(text=f'Sent: {command}')
            else:
                status_label.config(text=f'Error with command: {command}, Response: {response}')
            root.update_idletasks()
            
            time.sleep(0.05)  # Adjust for faster throughput if stable
        else:
            print(f'Sent: {command} dummy')
            status_label.config(text=f'Sent: {command}')
            root.update_idletasks()
            time.sleep(0.05)
    
# GUI setup
root = tk.Tk()
root.title("Shapeoko Controller")

# Frame for the buttons, making them left and right aligned
button_frame = tk.Frame(root)
button_frame.pack(pady=100)  # Add space above buttons for layout

# Left button (Pause/Resume
pause_button = tk.Button(
    button_frame,
    text="Pause",
    command=lambda: pause_resume(dummy_mode),
    font=('Helvetica', 18),
    width=20,
    height=5,
    bg="red",
    fg="white"
)
pause_button.grid(row=0, column=0, padx=20)

# Right button (Run Toolpath)
run_button = tk.Button(button_frame, text="Run Toolpath", command=lambda: run_gcode(dummy_mode),
                       font=('Helvetica', 18), width=20, height=5)
run_button.grid(row=0, column=1, padx=20)  # Padding for spacing

# Status label to display the current line being sent
status_label = tk.Label(root, text="Status: Ready", font=('Helvetica', 12))
status_label.pack(pady=20)

root.after(100, lambda: root.attributes('-fullscreen', True))
root.bind("<Escape>", exit_fullscreen)
root.mainloop()
