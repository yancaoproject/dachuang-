import sys
import serial
import serial.tools.list_ports
import threading
import time
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTextEdit, QPushButton, QTabWidget, QRadioButton, QButtonGroup,
    QGridLayout, QGroupBox
)
from PyQt5.QtGui import QFont, QPalette, QColor
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import csv


# 定义命令类型及其枚举值
command_map = {
    'functionMap': 0,
    'getPinFunction': 1,
    'getcurrentPinFunction': 2,
    'setPinFunction': 3,
    'startLoop': 4,
    'stopLoop': 5
}

# 定义功能名称及其枚举值
function_map = {
    'disable': 0,
    'readDigital': 1,
    'writeDigital': 2,
    'readAnalog': 3,
    'writeAnalog': 4
}

# 假设引脚范围，可根据实际情况调整
pin_ranges = [i for i in range(4, 12)] + [f'A{i}' for i in range(0, 6)]

# 定义每个引脚支持的功能
pin_functions = {
    4: ['readDigital', 'writeDigital'],
    5: ['readDigital', 'writeDigital', 'writeAnalog'],
    6: ['readDigital', 'writeDigital', 'writeAnalog'],
    7: ['readDigital', 'writeDigital'],
    8: ['readDigital', 'writeDigital'],
    9: ['readDigital', 'writeDigital', 'writeAnalog'],
    10: ['readDigital', 'writeDigital', 'writeAnalog'],
    11: ['readDigital', 'writeDigital', 'writeAnalog'],
    'A0': ['readDigital', 'writeDigital', 'readAnalog'],
    'A1': ['readDigital', 'writeDigital', 'readAnalog'],
    'A2': ['readDigital', 'writeDigital', 'readAnalog'],
    'A3': ['readDigital', 'writeDigital', 'readAnalog'],
    'A4': ['readDigital', 'writeDigital', 'readAnalog'],
    'A5': ['readDigital', 'writeDigital', 'readAnalog']
}


class SerialTab(QWidget):
    def __init__(self, port):
        super().__init__()
        self.port = port
        self.ser = None
        self.data_x = []
        self.data_y = []
        self.counter = 0
        self.mode = "serial_display"
        self.lock = threading.Lock()  # 添加线程锁
        self.init_ui()
        self.start_serial_thread()
        self.csv_file = open(f'{port}.csv', 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['Time', 'Data'])

    def init_ui(self):
        main_layout = QVBoxLayout()

        # 模式选择部分
        mode_layout = QHBoxLayout()
        self.serial_display_radio = QRadioButton('串口显示模式')
        self.pin_config_radio = QRadioButton('引脚配置模式')
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.serial_display_radio)
        self.mode_group.addButton(self.pin_config_radio)
        self.serial_display_radio.setChecked(True)
        self.serial_display_radio.toggled.connect(self.mode_changed)
        self.pin_config_radio.toggled.connect(self.mode_changed)
        mode_layout.addWidget(self.serial_display_radio)
        mode_layout.addWidget(self.pin_config_radio)
        main_layout.addLayout(mode_layout)

        # 串口控制和命令部分
        control_layout = QHBoxLayout()
        self.serial_label = QLabel('选择串口:')
        self.serial_combo = QComboBox()
        self.refresh_ports()
        self.connect_button = QPushButton('连接串口')
        self.connect_button.clicked.connect(self.connect_serial)
        control_layout.addWidget(self.serial_label)
        control_layout.addWidget(self.serial_combo)
        control_layout.addWidget(self.connect_button)

        self.command_label = QLabel('选择命令:')
        self.command_combo = QComboBox()
        self.command_combo.addItems(list(command_map.keys()))
        self.command_combo.currentIndexChanged.connect(self.update_function_combo_visibility)
        control_layout.addWidget(self.command_label)
        control_layout.addWidget(self.command_combo)

        self.pin_label = QLabel('选择引脚:')
        self.pin_combo = QComboBox()
        self.pin_combo.addItems([str(pin) for pin in pin_ranges])
        self.pin_combo.currentIndexChanged.connect(self.update_function_options)
        control_layout.addWidget(self.pin_label)
        control_layout.addWidget(self.pin_combo)

        self.function_label = QLabel('选择功能:')
        self.function_combo = QComboBox()
        control_layout.addWidget(self.function_label)
        control_layout.addWidget(self.function_combo)

        self.send_button = QPushButton('发送命令')
        self.send_button.clicked.connect(self.send_command)
        control_layout.addWidget(self.send_button)

        main_layout.addLayout(control_layout)

        # 隐藏功能选择下拉框，直到选择 setPinFunction 命令
        self.function_label.hide()
        self.function_combo.hide()

        # 引脚显示和数据显示部分
        display_layout = QHBoxLayout()

        # 引脚显示部分
        pin_group = QGroupBox("引脚配置")
        pin_grid = QGridLayout()
        self.pin_labels = {}
        row = 0
        col = 0
        for pin in pin_ranges:
            label = QLabel(f'引脚 {pin}: ')
            label.setFont(QFont('Arial', 12))
            self.pin_labels[str(pin)] = label
            pin_grid.addWidget(label, row, col)
            col += 1
            if col == 4:
                col = 0
                row += 1
        pin_group.setLayout(pin_grid)
        display_layout.addWidget(pin_group)

        # 数据显示部分
        data_group = QGroupBox("数据显示")
        data_layout = QVBoxLayout()
        self.response_label = QLabel('响应:')
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        data_layout.addWidget(self.response_label)
        data_layout.addWidget(self.response_text)

        # 串口数据显示图像
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('Data')
        data_layout.addWidget(self.canvas)
        data_group.setLayout(data_layout)
        display_layout.addWidget(data_group)

        main_layout.addLayout(display_layout)

        self.setLayout(main_layout)

        # 设置界面颜色
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.WindowText, QColor(30, 30, 30))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(230, 230, 230))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
        palette.setColor(QPalette.ToolTipText, QColor(30, 30, 30))
        palette.setColor(QPalette.Text, QColor(30, 30, 30))
        palette.setColor(QPalette.Button, QColor(230, 230, 230))
        palette.setColor(QPalette.ButtonText, QColor(30, 30, 30))
        palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        self.setPalette(palette)

    def start_serial_thread(self):
        try:
            self.ser = serial.Serial(self.port, baudrate=115200, timeout=1)
            self.response_text.append(f"已成功连接到 {self.port}")
            thread = threading.Thread(target=self.read_serial_data)
            thread.daemon = True
            thread.start()
        except serial.SerialException as e:
            self.response_text.append(f"连接 {self.port} 时出现错误: {e}")

    def read_serial_data(self):
        while True:
            if self.ser and self.ser.is_open:
                try:
                    line = self.ser.readline().decode().strip()
                    if line:
                        if self.mode == "serial_display":
                            self.process_serial_data(line)
                except Exception as e:
                    self.response_text.append(f"读取数据时出错: {e}")
            time.sleep(0.01)

    def process_serial_data(self, line):
        try:
            data = float(line)
            self.data_x.append(self.counter)
            self.data_y.append(data)
            self.counter += 1
            self.response_text.append(f"收到数据: {data}")
            self.csv_writer.writerow([time.time(), data])
            self.update_plot()
        except ValueError:
            self.response_text.append(f"无效数据: {line}")

    def update_plot(self):
        self.ax.clear()
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('Data')
        self.ax.plot(self.data_x, self.data_y)
        self.canvas.draw()

    def send_command(self):
        if not self.ser or not self.ser.is_open:
            self.response_text.append("请先连接串口")
            return

        command = self.command_combo.currentText()
        selected_pin = self.pin_combo.currentText()

        if command == 'getcurrentPinFunction':
            self.send_get_current_function(selected_pin)
        elif command == 'functionMap':
            self.send_function_map()
        elif command == 'getPinFunction':
            if isinstance(selected_pin, str) and selected_pin.startswith('A'):
                pin_num = ord(selected_pin[1]) - ord('0') + 10
            else:
                pin_num = int(selected_pin)
            self.send_get_pin_function(pin_num)
        elif command == 'setPinFunction':
            selected_function = self.function_combo.currentText()
            function_num = function_map[selected_function]
            if isinstance(selected_pin, str) and selected_pin.startswith('A'):
                pin_num = ord(selected_pin[1]) - ord('0') + 10
            else:
                pin_num = int(selected_pin)
            self.send_set_pin_function(pin_num, function_num)
        elif command == 'startLoop':
            self.send_general_command(command)
        elif command == 'stopLoop':
            self.send_general_command(command)

    def send_get_current_function(self, pin):
        try:
            if isinstance(pin, str) and pin.startswith('A'):
                pin_num = ord(pin[1]) - ord('0') + 10
                cmd_bytes = bytes([command_map['getcurrentPinFunction'], pin_num])
            else:
                pin_num = int(pin)
                cmd_bytes = bytes([command_map['getcurrentPinFunction'], pin_num])

            with self.lock:
                self.ser.write(cmd_bytes + b'\r\n')
            self.response_text.append(f"已发送命令: {cmd_bytes + b'\r\n'}")
            time.sleep(0.1)
            with self.lock:
                response = self.ser.readline().decode().strip()
            self.response_text.append(f"接收到的响应: {response}")
            if response:
                self.pin_labels[pin].setText(f'引脚 {pin}: {response}')
            else:
                self.pin_labels[pin].setText(f'引脚 {pin}: 未获取到功能')
        except KeyError:
            self.response_text.append(f"错误：在 self.pin_labels 字典中未找到键 {pin}")
        except Exception as e:
            self.response_text.append(f"获取引脚 {pin} 功能时出错: {e}")

    def send_function_map(self):
        try:
            cmd_bytes = bytes([command_map['functionMap']])
            with self.lock:
                self.ser.write(cmd_bytes + b'\r\n')
            self.response_text.append(f"已发送命令: {cmd_bytes + b'\r\n'}")
            time.sleep(0.1)
            with self.lock:
                response = self.ser.readline().decode().strip()
            self.response_text.append(f"接收到的响应: {response}")
            if response:
                self.response_text.append(f"响应: {response}")
            else:
                self.response_text.append("未收到响应。")
        except Exception as e:
            self.response_text.append(f"发送 functionMap 命令时出错: {e}")

    def send_get_pin_function(self, pin):
        try:
            cmd_bytes = bytes([command_map['getPinFunction'], pin])
            with self.lock:
                self.ser.write(cmd_bytes + b'\r\n')
            self.response_text.append(f"已发送命令: {cmd_bytes + b'\r\n'}")
            time.sleep(0.1)
            with self.lock:
                response = self.ser.readline().decode().strip()
            self.response_text.append(f"接收到的响应: {response}")
            if response:
                self.response_text.append(f"引脚 {pin} 功能响应: {response}")
            else:
                self.response_text.append(f"引脚 {pin} 未收到响应。")
        except Exception as e:
            self.response_text.append(f"发送 getPinFunction 命令时出错: {e}")

    def send_set_pin_function(self, pin, function):
        try:
            cmd_bytes = bytes([command_map['setPinFunction'], pin, function])
            with self.lock:
                self.ser.write(cmd_bytes + b'\r\n')
            self.response_text.append(f"已发送命令: {cmd_bytes + b'\r\n'}")
            time.sleep(0.1)
            with self.lock:
                response = self.ser.readline().decode().strip()
            self.response_text.append(f"接收到的响应: {response}")
            if response:
                self.response_text.append(f"设置引脚 {pin} 功能为 {function} 响应: {response}")
            else:
                self.response_text.append(f"设置引脚 {pin} 功能为 {function} 未收到响应。")
        except Exception as e:
            self.response_text.append(f"发送 setPinFunction 命令时出错: {e}")

    def send_general_command(self, command):
        try:
            cmd_bytes = bytes([command_map[command]])
            with self.lock:
                self.ser.write(cmd_bytes + b'\r\n')
            self.response_text.append(f"已发送命令: {cmd_bytes + b'\r\n'}")
            time.sleep(0.1)
            with self.lock:
                response = self.ser.readline().decode().strip()
            self.response_text.append(f"接收到的响应: {response}")
            if response:
                self.response_text.append(f"响应: {response}")
            else:
                self.response_text.append("未收到响应。")
        except Exception as e:
            self.response_text.append(f"发送 {command} 命令时出错: {e}")

    def update_function_combo_visibility(self):
        command = self.command_combo.currentText()
        if command == 'setPinFunction':
            self.function_label.show()
            self.function_combo.show()
            self.update_function_options()
        else:
            self.function_label.hide()
            self.function_combo.hide()

    def update_function_options(self):
        selected_pin = self.pin_combo.currentText()
        if isinstance(selected_pin, str) and selected_pin.startswith('A'):
            pin = selected_pin
        else:
            pin = int(selected_pin)
        functions = pin_functions[pin]
        self.function_combo.clear()
        self.function_combo.addItems(functions)

    def mode_changed(self):
        if self.pin_config_radio.isChecked():
            self.mode = "pin_config"
            self.response_text.append("已切换到引脚配置模式")
            self.get_all_currentpin()
        else:
            self.mode = "serial_display"
            self.response_text.append("已切换到串口显示模式")

    def get_all_currentpin(self):
        for pin in pin_ranges:
            self.send_get_current_function(str(pin))

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        self.serial_combo.clear()
        for port in ports:
            self.serial_combo.addItem(port.device)

    def connect_serial(self):
        port = self.serial_combo.currentText()
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.ser = serial.Serial(port, baudrate=115200, timeout=1)
            self.response_text.append(f"已成功连接到 {port}")
        except serial.SerialException as e:
            self.response_text.append(f"连接 {port} 时出现错误: {e}")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        self.setLayout(layout)

    def add_serial_tab(self, port):
        tab = SerialTab(port)
        self.tab_widget.addTab(tab, port)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    ports = serial.tools.list_ports.comports()
    for port in ports:
        window.add_serial_tab(port.device)
    window.show()
    sys.exit(app.exec_())