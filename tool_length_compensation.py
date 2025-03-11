# -*- coding: utf-8 -*-
"""
Created on Tue Mar 11 09:21:02 2025

@author: Ryan.Larson
"""

import serial
from serial.tools import list_ports
import time
import re

def send_gcode(ser, command):
    """Send a G-code command and return the response."""
    ser.write((command + "\n").encode())  # Send command
    time.sleep(0.2)  # Wait for GRBL to process
    response = ser.readlines()  # Read all available lines
    return [line.decode().strip() for line in response]

def get_z_position(ser):
    """Query machine position and extract Z value."""
    response = send_gcode(ser, "?")
    for line in response:
        match = re.search(r"MPos:[-?\d.]+,[-?\d.]+,([-?\d.]+)", line)
        if match:
            return float(match.group(1))
    return None  # Return None if no Z position was found

def probe_tool():
    """Probes the tool and returns its Z position."""
    ser = serial.Serial(serial_port, baud_rate, timeout=1)  # Replace COMX with your port

    # Probe downward (adjust Z depth and feed rate as needed)
    response = send_gcode(ser, "G38.2 Z-50 F200")
    print(f"{response}")
    # time.sleep(10)  # Allow probe to complete
    
    send_gcode(ser, "G0 Z10")
    print(f"{response}")
    send_gcode(ser, "G38.2 Z-50 F100")
    print(f"{response}")
    time.sleep(5)

    input("Press ENTER when touching probe")

    # Read the probed Z position
    z_position = get_z_position(ser)
    
    print(f"z_position: {z_position}")
    
    ser.close()
    return z_position

def apply_tool_offset(reference_z):
    """Probes the new tool and applies compensation based on reference Z."""
    new_tool_z = probe_tool()
    
    if new_tool_z is None:
        print("Error: Could not retrieve new tool Z position.")
        return
    
    # Compute tool length difference
    offset = reference_z - new_tool_z
    print(f"Tool length difference: {offset:.4f} mm")

    # Apply compensation (G43 H1 can be used for tool length offsets)
    ser = serial.Serial(serial_port, baud_rate, timeout=1)
    send_gcode(ser, f"G43 Z{offset:.4f}")  # Apply tool offset
    ser.close()

    print("Tool length compensation applied.")



baud_rate = 115200
ports = list_ports.comports()
if ports:
    print(f'Ports available: {ports}')
    serial_port = ports[0].device
else:
    # print('No serial ports available. Entering dummy mode')
    raise Exception("No serial ports available")
ser = serial.Serial(serial_port, baud_rate)
print("Initializing serial connection")

# Send an initial command to wake up GRBL
ser.write(b"\r\n\r\n")
print("Sending command to wake GRBL")    
time.sleep(2)
ser.flushInput()

input("Press ENTER to continue...")

print("Homing")
ser.write(b"$H\n") # GRBL home command
ser.flush()
ser.reset_input_buffer()
ser.reset_output_buffer()

input("Press ENTER to continue...")

# Move to x y position of probe
xprobe = -21.550
yprobe = -350.500
zprobestart = -50.000

# send_gcode(ser, f"G0 X{xprobe} Y{yprobe}")
ser.write(b"G0 X-21.550 Y-350.500\n")

input("Press ENTER to continue...")

# -------------------------
# Initial Tool Setup
# -------------------------
print("Probing reference tool...")
reference_z = probe_tool()

if reference_z is None:
    print("Error: Could not retrieve reference Z position.")
else:
    print(f"Reference tool Z: {reference_z:.4f} mm")
    
    response = ser.write(b"G0 Z10\n")
    print(f"{response}")
    
    
    # Simulate tool change (User swaps tool manually)
    input("Change the tool and press ENTER to continue...")

    # Apply compensation for the new tool
    apply_tool_offset(reference_z)

