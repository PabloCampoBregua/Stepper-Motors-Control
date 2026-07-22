# TOF Motors Control

Python application developed to control three stepper motors through external **SMD2 Stepper Motor Drive** controllers via serial communication.

## Features

- Automatic serial port detection
- Independent control of Theta, Phi, and Lift motors
- Real-time position monitoring
- Motor position initialization
- Emergency stop
- Activity log

## Technologies

- Python
- Tkinter
- pySerial
- threading

## Installation

```bash
pip install pyserial
```

## Run

```bash
python main.py
```

## Hardware

This software is designed to communicate with SMD2 Stepper Motor Drive controllers through serial (RS-232/USB) interfaces.

## Disclaimer

This application was developed for laboratory instrumentation and requires compatible motor controllers to operate.

## Authorship & Acknowledgements

This project was designed and developed by **Pablo Campo Bregua**.

AI tools were used to assist with debugging, code refactoring, and documentation. All design decisions, communication protocols, and application functionality were implemented by the author.
