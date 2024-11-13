# -*- coding: utf-8 -*-
"""
Created on Mon Nov 11 10:49:28 2024

@author: Ryan.Larson
"""

import tkinter as tk
import serial
from serial.tools import list_ports
import time
import pickle
from queue import Queue

with open('config.pkl', 'rb') as f:
    config = pickle.load(f)
    

# Set up serial connection
ports = list_ports.comports()
if ports:
    serial_port = ports[0]
else:
    print('No serial ports available')
    serial_port = '/dev/ttyUSB0'
# serial_port = '/dev/ttyUSB0'  # Change this to the correct port
baud_rate = 115200
gcode_file_path = config['gcode_file_path']

# Initialize the serial connection
# ser = serial.Serial(serial_port, baud_rate)
print("Initializing serial connection (dummy)")
time.sleep(2)  # Wait for GRBL to initialize

# Send an initial command to wake up GRBL
# ser.write(b"\r\n\r\n")
print("Sending command to wake GRBL (dummy)")
time.sleep(2)
# ser.flushInput()

buffer_queue = Queue(maxsize=16)

def exit_fullscreen(event=None):
    root.attributes('-fullscreen', False)  # Exit full-screen

def move_to_load_position():
    """Move the router out of the way for loading stock."""
    load_position_command = "G0 X0 Y0 Z10"  # Adjust coordinates as needed
    # ser.write((load_position_command + '\n').encode())
    # ser.flush()
    print(f"Moved to load position {load_position_command}")
    status_label.config(text=f'Sent: {load_position_command} (dummy)')
    root.update_idletasks()

def run_gcode():
    """Send Gcode commands from the file to the CNC router."""
    with open(gcode_file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith('('):  # Ignore comments
                # ser.write((line + '\n').encode())
                # ser.flush()
                # response = ser.readline().decode().strip()  # Read response
                # print(f"Sent: {line}, Response: {response}")
                # print(f'Sent: {line} (dummy)')
                
                # status_label.config(text=f'Sent: {line} (dummy)')
                # root.update_idletasks()
                
                # time.sleep(0.1)  # Small delay to prevent command overload
                buffer_queue.put(line)
                send_buffered_commands()
                
    # Send remaining commands in buffer
    while not buffer_queue.empty():
        send_buffered_commands()
                
    status_label.config(text="COMPLETE")
    root.update_idletasks()
    
def send_buffered_commands():
    """Send commands from the buffer if there's space."""
    while not buffer_queue.empty():
        command = buffer_queue.get()
        
        # ser.write((command + '\n').encode())
        # ser.flush()
        # response = ser.readline().decode().strip()
        # print(f"Sent: {command}, Response: {response}")
        
        print(f'Sent: {command} (dummy)')
        status_label.config(text=f'Sent: {command} (dummy)')
        root.update_idletasks()
        
        time.sleep(0.05)  # Adjust for faster throughput if stable
    
# GUI setup
root = tk.Tk()
root.title("Shapeoko Controller")

# load_button = tk.Button(root, text="Move to Load Position", command=move_to_load_position, font=('Helvetica', 14))
# load_button.pack(pady=20)

# run_button = tk.Button(root, text="Run Toolpath", command=run_gcode, font=('Helvetica', 14))
# run_button.pack(pady=20)

# Frame for the buttons, making them left and right aligned
button_frame = tk.Frame(root)
button_frame.pack(pady=100)  # Add space above buttons for layout

# Left button (Move to Load Position)
load_button = tk.Button(button_frame, text="Move to Load Position", command=move_to_load_position,
                        font=('Helvetica', 18), width=20, height=5)
load_button.grid(row=0, column=0, padx=20)  # Padding for spacing

# Right button (Run Toolpath)
run_button = tk.Button(button_frame, text="Run Toolpath", command=run_gcode,
                       font=('Helvetica', 18), width=20, height=5)
run_button.grid(row=0, column=1, padx=20)  # Padding for spacing

# Status label to display the current line being sent
status_label = tk.Label(root, text="Status: Ready", font=('Helvetica', 12))
status_label.pack(pady=20)

# root.geometry("400x300")
# root.wm_attributes('-fullscreen', True)

root.after(100, lambda: root.attributes('-fullscreen', True))
root.bind("<Escape>", exit_fullscreen)
root.mainloop()