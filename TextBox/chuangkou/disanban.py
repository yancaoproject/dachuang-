import sys
import serial
import time
import csv
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTextEdit, QPushButton, QFileDialog
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QTimer

# 配置串口参数
PORT = 'COM4'  # 根据实际情况修改
BAUDRATE = 115200
TIMEOUT = 1

# 定义命令类型及其枚举值
command_map = {
    'functionMap': 0,
    'getPinFunction': 1,
    'getcurrentPinFunction': 2,
    'setPinFunction': 3,
    'startLoop': 4,
    'stopLoop': 5
}

Response_map = {
    'ok':0,
    'error':1,
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

class ArduinoCommunicator(QWidget):
    def __init__(self):
        super().__init__()
        self.loop_data = []  # 存储循环捕获的数据
        self.is_looping = False  # 标志是否在循环捕获模式
        self.init_ui()
        self.ser = self.connect_serial()
        self.init_pins()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_serial_data)

    def init_ui(self):
        self.setWindowTitle('Arduino 命令发送器')

        # 命令、引脚和功能选择部分
        command_layout = QHBoxLayout()
        self.command_label = QLabel('选择命令:')
        self.command_combo = QComboBox()
        self.command_combo.addItems(list(command_map.keys()))
        self.command_combo.currentIndexChanged.connect(self.update_function_combo_visibility)

        self.pin_label = QLabel('选择引脚:')
        self.pin_combo = QComboBox()
        self.pin_combo.addItems([str(pin) for pin in pin_ranges])
        self.pin_combo.currentIndexChanged.connect(self.update_function_options)

        self.function_label = QLabel('选择功能:')
        self.function_combo = QComboBox()

        self.send_button = QPushButton('发送命令')
        self.send_button.clicked.connect(self.send_command)

        command_layout.addWidget(self.command_label)
        command_layout.addWidget(self.command_combo)
        command_layout.addWidget(self.pin_label)
        command_layout.addWidget(self.pin_combo)
        command_layout.addWidget(self.function_label)
        command_layout.addWidget(self.function_combo)
        command_layout.addWidget(self.send_button)

        # 隐藏功能选择下拉框，直到选择 setPinFunction 命令
        self.function_label.hide()
        self.function_combo.hide()

        # 引脚显示部分
        self.pin_layout = QVBoxLayout()
        self.pin_labels = {}
        for pin in pin_ranges:
            pin_str = str(pin)
            label = QLabel(f'引脚 {pin_str}: ')
            label.setFont(QFont('Arial', 12))
            self.pin_labels[pin_str] = label
            self.pin_layout.addWidget(label)

        # 响应显示部分
        self.response_label = QLabel('响应:')
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)

        # 循环数据显示部分
        self.loop_data_label = QLabel('循环数据:')
        self.loop_data_text = QTextEdit()
        self.loop_data_text.setReadOnly(True)
        self.loop_data_text.hide()
        self.loop_data_label.hide()

        # 导出CSV按钮
        self.export_button = QPushButton('导出数据为CSV')
        self.export_button.clicked.connect(self.export_to_csv)
        self.export_button.hide()

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addLayout(command_layout)
        main_layout.addLayout(self.pin_layout)
        main_layout.addWidget(self.response_label)
        main_layout.addWidget(self.response_text)
        main_layout.addWidget(self.loop_data_label)
        main_layout.addWidget(self.loop_data_text)
        main_layout.addWidget(self.export_button)

        self.setLayout(main_layout)

    def connect_serial(self):
        try:
            ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
            print(f"已连接到 {PORT}，波特率 {BAUDRATE}。")
            return ser
        except serial.SerialException:
            print(f"错误：无法打开串口 {PORT}。")
            sys.exit(1)

    def init_pins(self):
        for pin in pin_ranges:
            self.send_get_current_function(str(pin))

    def send_get_current_function(self, pin):
        try:
            if isinstance(pin, str) and pin.startswith('A'):
                pin_num = ord(pin[1]) - ord('0') + 14  # A0 -> 14, A1 -> 15, etc.
                cmd_bytes = bytes([command_map['getcurrentPinFunction'], pin_num])
            else:
                pin_num = int(pin)
                cmd_bytes = bytes([command_map['getcurrentPinFunction'], pin_num])

            self.ser.write(cmd_bytes + b'\r\n')
            time.sleep(0.1)
            response = self.ser.readline().decode().strip()
            if response:
                self.pin_labels[pin].setText(f'引脚 {pin}: {response}')
            else:
                self.pin_labels[pin].setText(f'引脚 {pin}: 未获取到功能')
        except KeyError:
            print(f"错误：在 self.pin_labels 字典中未找到键 {pin}")
            self.response_text.append(f"错误：在 self.pin_labels 字典中未找到键 {pin}")

    def send_command(self):
        command = self.command_combo.currentText()
        selected_pin = self.pin_combo.currentText()

        if command == 'getcurrentPinFunction':
            self.send_get_current_function(selected_pin)
        elif command == 'functionMap':
            self.send_function_map()
        elif command == 'getPinFunction':
            if isinstance(selected_pin, str) and selected_pin.startswith('A'):
                pin_num = ord(selected_pin[1]) - ord('0') + 14
            else:
                pin_num = int(selected_pin)
            self.send_get_pin_function(pin_num)
        elif command == 'setPinFunction':
            selected_function = self.function_combo.currentText()
            function_num = function_map[selected_function]
            if isinstance(selected_pin, str) and selected_pin.startswith('A'):
                pin_num = ord(selected_pin[1]) - ord('0') + 14
            else:
                pin_num = int(selected_pin)
            self.send_set_pin_function(pin_num, function_num)
        elif command == 'startLoop':
            self.send_general_command(command)
        elif command == 'stopLoop':
            self.send_general_command(command)

    def send_function_map(self):
        cmd_bytes = bytes([command_map['functionMap']])
        self.ser.write(cmd_bytes + b'\r\n')
        time.sleep(0.1)
        response = self.ser.readline().decode().strip()
        if response:
            self.response_text.append(f"响应: {response}")
        else:
            self.response_text.append("未收到响应。")

    def send_get_pin_function(self, pin):
        cmd_bytes = bytes([command_map['getPinFunction'], pin])
        self.ser.write(cmd_bytes + b'\r\n')
        time.sleep(0.1)
        response = self.ser.readline().decode().strip()
        if response:
            self.response_text.append(f"引脚 {pin} 功能响应: {response}")
        else:
            self.response_text.append(f"引脚 {pin} 未收到响应。")

    def send_set_pin_function(self, pin, function):
        cmd_bytes = bytes([command_map['setPinFunction'], pin, function])
        self.ser.write(cmd_bytes + b'\r\n')
        time.sleep(0.1)
        response = self.ser.readline().decode().strip()
        if response:
            self.response_text.append(f"设置引脚 {pin} 功能为 {function} 响应: {response}")
        else:
            self.response_text.append(f"设置引脚 {pin} 功能为 {function} 未收到响应。")

    def send_general_command(self, command):
        cmd_bytes = bytes([command_map[command]])
        self.ser.write(cmd_bytes + b'\r\n')
        time.sleep(0.1)
        response = self.ser.readline().decode().strip()
        if response:
            self.response_text.append(f"响应: {response}")
            if command == 'startLoop' and response == str(Response_map['ok']):
                self.is_looping = True
                self.loop_data_label.show()
                self.loop_data_text.show()
                self.export_button.show()
                self.timer.start(100)  # 每100ms检查一次串口
            elif command == 'stopLoop' and response == str(Response_map['ok']):
                self.is_looping = False
                self.timer.stop()
                self.loop_data_label.hide()
                self.loop_data_text.hide()
                self.loop_data_text.clear()
        else:
            self.response_text.append("未收到响应。")

    def read_serial_data(self):
        if self.is_looping and self.ser.in_waiting > 0:
            try:
                data = self.ser.readline().decode().strip()
                if data:
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    self.loop_data.append({'timestamp': timestamp, 'data': data})
                    self.loop_data_text.append(f"[{timestamp}] {data}")
            except Exception as e:
                self.response_text.append(f"读取串口数据错误: {e}")

    def export_to_csv(self):
        if not self.loop_data:
            self.response_text.append("没有数据可导出。")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "保存CSV文件", "", "CSV Files (*.csv)")
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=['timestamp', 'data'])
                    writer.writeheader()
                    for row in self.loop_data:
                        writer.writerow(row)
                self.response_text.append(f"数据已导出到 {file_path}")
            except Exception as e:
                self.response_text.append(f"导出CSV错误: {e}")

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

    def closeEvent(self, event):
        self.timer.stop()
        self.ser.close()
        print("串口已关闭。")
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    communicator = ArduinoCommunicator()
    communicator.show()
    sys.exit(app.exec_())