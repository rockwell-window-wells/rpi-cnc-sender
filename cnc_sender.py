# -*- coding: utf-8 -*-
"""
Created on Mon Nov 11 10:49:28 2024

@author: Ryan.Larson
"""

import tkinter as tk
import serial
import time
import pickle

with open('config.pkl', 'rb') as f:
    config = pickle.load(f)
    

# Set up serial connection
serial_port = '/dev/ttyUSB0'  # Change this to the correct port
baud_rate = 115200
gcode_file_path = config['gcode_file_path']

# Initialize the serial connection
ser = serial.Serial(serial_port, baud_rate)
time.sleep(2)  # Wait for GRBL to initialize

# Send an initial command to wake up GRBL
ser.write(b"\r\n\r\n")
time.sleep(2)
ser.flushInput()

def move_to_load_position():
    """Move the router out of the way for loading stock."""
    load_position_command = "G0 X0 Y0 Z10"  # Adjust coordinates as needed
    ser.write((load_position_command + '\n').encode())
    ser.flush()
    print("Moved to load position")

def run_gcode():
    """Send Gcode commands from the file to the CNC router."""
    with open(gcode_file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith('('):  # Ignore comments
                ser.write((line + '\n').encode())
                ser.flush()
                response = ser.readline().decode().strip()  # Read response
                print(f"Sent: {line}, Response: {response}")
                time.sleep(0.1)  # Small delay to prevent command overload

# GUI setup
root = tk.Tk()
root.title("Shapeoko Controller")

load_button = tk.Button(root, text="Move to Load Position", command=move_to_load_position, font=('Helvetica', 14))
load_button.pack(pady=20)

run_button = tk.Button(root, text="Run Toolpath", command=run_gcode, font=('Helvetica', 14))
run_button.pack(pady=20)

root.geometry("400x300")
root.mainloop()
