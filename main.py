# The controller communicates using ASCII commands terminated with a carriage return (\r).
# Serial communication uses 7 data bits, odd parity, 2 stop bits, and a default baud rate of 9600.
# For a complete list of supported commands, see Appendix B of the "SMD2 Stepper Motor Drive Manual".


import tkinter as tk #GUI construction
from tkinter import ttk, messagebox, scrolledtext #Message boxes and scrollable widgets
import serial #Enables serial port communication
import serial.tools.list_ports #Access the list of available serial ports
import threading #Allows background threads
import time #Time utilities
from datetime import datetime #Date and time utilities
import re #Regular expressions

# Motor parameters
MOTORS = {
    "Theta": {"ser_idx": 2, "sel": "B1", "v_cmd": "V1", "limit": 120001, "scale": 1000, "unit": "deg"},
    "Lift":  {"ser_idx": 1, "sel": "B2", "v_cmd": "V1", "limit": 1000, "scale": 250, "unit": "mm"},
    "Phi":   {"ser_idx": 1, "sel": "B1", "v_cmd": "V1", "limit": 18001, "scale": 100, "unit": "deg"}
}

#Automatically detect serial ports when the application starts
def detect_ports():
    return [p.device for p in serial.tools.list_ports.comports() 
            if "USB Serial Port" in p.description] # In the Windows Device Manager, the SMD2 modules appear as "USB Serial Port", followed by their corresponding COM port number.

def identify_module(com): #Read and identify the connected motor controller module
    try:
        ser_test = serial.Serial(port=com, baudrate=9600, bytesize=serial.SEVENBITS,
                                parity=serial.PARITY_ODD, stopbits=serial.STOPBITS_TWO, timeout=10) #Serial communication parameters
        ser_test.write(b'\rB2\r') #Select motor 2 (valid for Phi/Lift module, error for Theta module)
        time.sleep(0.1)
        ser_test.reset_input_buffer()
        ser_test.write(b"ID\r")
        time.sleep(0.2)
        answer = ser_test.read_until(b'\r').decode("ascii", errors="replace").strip()
        ser_test.close()
        return answer
    except: return ""

def detect_modules():
    ports = detect_ports()
    modules = {"module_1": None, "module_2": None}
    for p in ports:
        ans = identify_module(p)
        if "Y" in ans: modules["module_1"] = p #"Y" means that the module has 2 motors assigned (phi and lift in this case)
        elif "E5" in ans: modules["module_2"] = p #"E5" is an error message that appears when we try to select the second motor, it means that this module has only the theta motor
    return modules

detect_modules = detect_modules()
PORT_1 = detect_modules.get("module_1")
PORT_2 = detect_modules.get("module_2")

#Font definitions
FONT_TITLE = ("Arial", 13, "bold")
FONT_NORMAL = ("Arial", 11)
FONT_POS_NUM = ("Courier", 12, "bold")
FONT_BTN_LARGE = ("Arial", 12, "bold")
FONT_ENTRY = ("Arial", 12, "bold")
FONT_SMALL = ("Arial", 10)

class Motor_Control:
    def __init__(self, root):
        self.root = root
        self.root.title("Stepper motor control")
        self.root.geometry("600x850")
        
        self.serial_lock = threading.Lock() #Ensure only one serial operation runs at a time
        self.running = True #Esta variable se mantiene True mientras el programa esté abierto
        self.ser1 = None #Module phi/lift
        self.ser2 = None #Module theta
        
        self.pos_vars = {name: tk.StringVar(value="---") for name in MOTORS}  #Motor position variables
        self.safety_unlock = {name: tk.BooleanVar(value=False) for name in MOTORS} #Boolean variable for the "enable" button
        self.entries = {}
        self.buttons = {name: [] for name in MOTORS}
        self.all_interactive_widgets = []

        self.setup_ui()
        self.conect_ports()
        self.update_button_states()
        
        self.set_ui_state("disabled") #It locks the GUI until it tries to connect to the modules and read the current positions
        self.root.after(500, self.read_initial_positions) #Asks for the positions 

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing) 

    def set_ui_state(self, state):
        for widget in self.all_interactive_widgets:
            try:
                widget.config(state=state)
            except: pass
        
        self.btn_stop.config(state="normal") #"Stop" button is always enabled
        
        if state == "normal": # Allows motor operation when the "Enable" checkbox is checked.
            self.update_button_states() 

    def conect_ports(self): #Connect to serial ports
        params = {'baudrate': 9600, 'bytesize': serial.SEVENBITS, 
                  'parity': serial.PARITY_ODD, 'stopbits': serial.STOPBITS_TWO, 'timeout': 600}
        if PORT_1:
            try: 
                self.ser1 = serial.Serial(PORT_1, **params)
                self.log(f"Module phi/lift connected to {PORT_1}")
            except: self.log("Error connecting module 1 (phi/lift)")
        if PORT_2:
            try: 
                self.ser2 = serial.Serial(PORT_2, **params)
                self.log(f"Module theta connected to {PORT_2}")
            except: self.log("Error connecting module 2 (theta)")

    def setup_ui(self): #Build the graphical user interface
        f1 = tk.LabelFrame(self.root, text=" Global Position Summary ", font=FONT_TITLE, padx=10, pady=10)
        f1.pack(fill="x", padx=15, pady=5)
        
        pos_container = tk.Frame(f1)
        pos_container.pack(side="left", fill="both", expand=True)

        for name in MOTORS:
            row = tk.Frame(pos_container)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{name}:", font=FONT_NORMAL, width=10, anchor="w").pack(side="left")
            tk.Label(row, textvariable=self.pos_vars[name], font=FONT_POS_NUM, fg="#0000CC").pack(side="left")
            tk.Label(row, text=MOTORS[name]["unit"], font=FONT_SMALL, fg="gray").pack(side="left", padx=5)
        
        btn_frame_right = tk.Frame(f1)
        btn_frame_right.pack(side="right", padx=5)
        
        btn_init = tk.Button(btn_frame_right, text="INITIALIZE", bg="#ff9800", 
                             font=("Arial", 9, "bold"), width=12, height=2, 
                             command=self.action_initialize_all)
        btn_init.pack(side="top", pady=2)
        
        self.btn_stop = tk.Button(btn_frame_right, text="STOP", bg="#f44336", fg="white", 
                             font=("Arial", 9, "bold"), width=12, height=2, 
                             command=self.action_emergency_stop)
        self.btn_stop.pack(side="top", pady=2)

        self.all_interactive_widgets.append(btn_init)
        
        for name in ["Phi", "Lift", "Theta"]:
            self.build_control_frame(name)

        f5 = tk.LabelFrame(self.root, text=" Log ", font=FONT_TITLE, padx=10, pady=10)
        f5.pack(fill="both", expand=True, padx=15, pady=5)
        self.log_box = scrolledtext.ScrolledText(f5, height=10, font=("Consolas", 9), bg="white")
        self.log_box.pack(fill="both", expand=True)

    def build_control_frame(self, name): #Builds the interface for the motors
        color_map = {"Theta": "#E1F5FE", "Lift": "#FFFDE7", "Phi": "#FFF3E0"}
        m = MOTORS[name]
        f = tk.LabelFrame(self.root, text=f" {name} ", font=FONT_TITLE, padx=10, pady=8, bg=color_map[name])
        f.pack(fill="x", padx=15, pady=5)

        cb = tk.Checkbutton(f, text="Enable", variable=self.safety_unlock[name], 
                       font=FONT_TITLE, bg=color_map[name], fg="red",
                       command=lambda n=name: self.on_check_toggle(n))
        cb.pack(side="left")
        self.all_interactive_widgets.append(cb)
        
        control_subframe = tk.Frame(f, bg=color_map[name])
        control_subframe.pack(side="right", expand=True)

        btn_m = tk.Button(control_subframe, text=" - ", font=FONT_BTN_LARGE, width=4, bg="#ffcccc", command=lambda n=name: self.safe_move(n, "-"))
        btn_m.pack(side="left", padx=10)

        entry_block = tk.Frame(control_subframe, bg=color_map[name])
        entry_block.pack(side="left", padx=5)
        
        ent = tk.Entry(entry_block, font=FONT_ENTRY, width=10, justify="center")
        ent.insert(0, "1.0")
        ent.pack(side="top")
        self.entries[name] = ent
        self.all_interactive_widgets.append(ent)

        btn_res = tk.Button(entry_block, text="Set to 0", font=FONT_SMALL, bg="#eeeeee", command=lambda n=name: self.action_reset_motor(n))
        btn_res.pack(side="top", pady=2)

        btn_p = tk.Button(control_subframe, text=" + ", font=FONT_BTN_LARGE, width=4, bg="#ccffcc", command=lambda n=name: self.safe_move(n, "+"))
        btn_p.pack(side="left", padx=10)
        
        self.buttons[name] = [btn_m, btn_p, btn_res]
        self.all_interactive_widgets.extend(self.buttons[name])

    def log(self, txt): #Write a message to the log window
        msg = f"[{datetime.now().strftime('%H:%M:%S')}] {txt}"
        self.log_box.insert(tk.END, msg + "\n")
        self.log_box.see(tk.END)
    
    def read_initial_positions(self): #Read all motor positions when the program starts
            self.log("Reading motor positions...")
            
            def reading_positions():
                with self.serial_lock:
                    # Module 1 sequence (it reads phi first, then lift)
                    if self.ser1:
                        for motor_name in ["Phi", "Lift"]:
                            m = MOTORS[motor_name]
                            self.log(f"Reading {motor_name} (Módulo 1)...")
                            pos = self.read_hardware_position(self.ser1, m["sel"], m["scale"], motor_name)
                            if pos is not None:
                                self.root.after(0, lambda n=motor_name, v=pos: self.pos_vars[n].set(f"{v:.3f}"))
                            time.sleep(0.1)
                    else:
                        self.log("ERROR: Module 1 not found.")

                    # Module 2 sequence (reads theta)
                    if self.ser2:
                        motor_name = "Theta"
                        m = MOTORS[motor_name]
                        self.log(f"Reading {motor_name} (Módulo 2)...")
                        pos = self.read_hardware_position(self.ser2, m["sel"], m["scale"], motor_name)
                        if pos is not None:
                            self.root.after(0, lambda n=motor_name, v=pos: self.pos_vars[n].set(f"{v:.3f}"))
                    else:
                        self.log("ERROR: Module 2 not found.")
                            
                self.log("All positions read")
                self.root.after(0, lambda: self.set_ui_state("normal")) #Unlocks the GUI after reading the positions

            threading.Thread(target=reading_positions, daemon=True).start()

    def read_hardware_position(self, ser, sel_cmd, scale, motor_name): #Read the current motor position from the controller
                try:
                    ser.reset_input_buffer()
                    ser.write(f"{sel_cmd}\r".encode('ascii')) #Select motor (B1 or B2)
                    ser.read_until(b'\r') 
                    time.sleep(0.1)
                
                    ser.write(b'V1\r') #We ask for the position
                
                    raw = ""
                    #When we are asking for the position, the module gives 2 answers, "Y" and the one with the position
                    for _ in range(2):
                        line = ser.read_until(b'\r').decode('ascii', errors='ignore').strip()
                        if line == "Y": #If the answer is "Y" we continue
                            continue
                        if line: #Ends the loop when answer is different from "Y" 
                            raw = line
                            break
            
                    if raw:
                        self.log(f"[{motor_name}] module answer: {raw}")
                        
                    match = re.search(r'([+-]?\d+)', raw)
                    self.log(f"Motor position: {match}")
                    if match:
                        return int(match.group(1)) / scale
                    return None
                except:
                    return None
    
    def safe_move(self, name, sign): #Move the selected motor
        m = MOTORS[name]
        ser = self.ser1 if m["ser_idx"] == 1 else self.ser2
        if not ser: return

        try:
            val_units = float(self.entries[name].get())
            steps = int(val_units * m["scale"]) #We apply the scale to transform from steps to degrees or mm
            if steps > m["limit"]:
                messagebox.showwarning("Limit", "Exceeds max steps")
                return
        except: return

        
        self.set_ui_state("disabled") #Locks the GUI until the movement is completed
        self.log(f"Moving {name}...")

        def run_movement():
            try:
                # 1. Send steps value
                with self.serial_lock:
                    ser.write(f"{m['sel']}\r".encode('ascii'))
                    ser.read_until(b'\r')
                    time.sleep(0.05)
                    ser.reset_input_buffer()
                    ser.write(f"{sign}{steps}\r".encode('ascii'))
                
                # 2. Wait until the movement ends
                ser.read_until(b'Y') 
                
                # 3. Ask for the new position
                with self.serial_lock:
                    ser.write(b'V1\r')
                    raw = ""
                    for _ in range(5):
                        line = ser.read_until(b'\r').decode('ascii', errors='ignore').strip()
                        if line == "Y":
                            continue
                        if line:
                            raw = line
                            break

                    match = re.search(r'([+-]?\d+)', raw)
                    if match:
                        hw_steps = int(match.group(1))
                        hw_units = hw_steps / m["scale"]
                        
                        
                        self.root.after(0, lambda n=name, v=hw_units: self.pos_vars[n].set(f"{v:.3f}"))
                    else:
                        self.log(f"Warning: Could not read position for {name}")

            except Exception as e:
                self.log(f"Error: {e}")
            
            self.root.after(0, lambda: self.set_ui_state("normal"))

        threading.Thread(target=run_movement, daemon=True).start()

    def action_reset_motor(self, name):
        if not self.safety_unlock[name].get(): return 
        m = MOTORS[name]
        ser = self.ser1 if m["ser_idx"] == 1 else self.ser2
        
        self.log(f"Resetting {name}...")
        
        def reset_proceso():
            with self.serial_lock:
                try:
                    # 1. Select motor and reset to zero
                    ser.write(f"{m['sel']}\r".encode('ascii'))
                    time.sleep(0.05)
                    ser.write(b'I1\r')
                    time.sleep(0.1) 
                    
                    # 2. Confirm that the new position is zero
                    pos = self.read_hardware_position(ser, m["sel"], m["scale"], name)
                    
                    if pos is not None:
                        # Aplicar lógica de inversión si es necesario (ej. Lift)
                        display_pos = -pos if m.get("inverted") else pos
                        self.root.after(0, lambda n=name, v=display_pos: self.pos_vars[n].set(f"{v:.3f}"))
                        self.log(f"{name} set to zero.")
                except Exception as e:
                    self.log(f"Error resetting {name}: {e}")

        threading.Thread(target=reset_proceso, daemon=True).start()

    def action_initialize_all(self):
        if messagebox.askyesno("Initialize", "Set ALL positions to zero?"):
            self.set_ui_state("disabled")
            
            def global_reset():
                try:
                    with self.serial_lock:
                        # 1. Sends I1 command to both modules
                        if self.ser1: self.ser1.write(b'I1\r')
                        if self.ser2: self.ser2.write(b'I1\r')
                        time.sleep(0.2)
                    
                    # 2. Reutilizar la función de lectura inicial para refrescar todo
                    # Esta función ya tiene los hilos y desbloquea la interfaz al acabar
                    self.read_initial_positions()
                    self.log("All motors reset to zero.")
                except Exception as e:
                    self.log(f"Global reset error: {e}")
                    self.root.after(0, lambda: self.set_ui_state("normal"))

            threading.Thread(target=global_reset, daemon=True).start()

    def action_emergency_stop(self): #Send an emergency stop command
        def send_stop():
            try:
                if self.ser1: 
                    self.ser1.write(b'K\r')
                    self.ser1.flush()
                if self.ser2: 
                    self.ser2.write(b'K\r')
                    self.ser2.flush()
                self.log("!!! EMERGENCY STOP SENT !!!")
            except Exception as e:
                self.log(f"Error sending STOP: {e}")

        threading.Thread(target=send_stop, daemon=True).start()

    def on_check_toggle(self, selected_name): #Ensure that only one motor can be enabled at a time
        if self.safety_unlock[selected_name].get():
            for name in MOTORS:
                if name != selected_name: self.safety_unlock[name].set(False)
        self.update_button_states()

    def update_button_states(self): #Enable or disable controls depending on the selected motor
        for name in MOTORS:
            state = "normal" if self.safety_unlock[name].get() else "disabled"
            for btn in self.buttons[name]: btn.config(state=state)
    
    
    def on_closing(self): #Close all serial ports and stop background processes before exiting
        self.running = False
        if self.ser1: self.ser1.close()
        if self.ser2: self.ser2.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = Motor_Control(root)
    root.mainloop()