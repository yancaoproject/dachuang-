import sys
import serial
import time
import csv
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTextEdit, QPushButton, QFileDialog
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QTimer
from serial.tools import list_ports
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# 配置串口参数
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

# 定义响应映射
Response_map = {
    'ok': 'ok',
    'error': 'error'
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

class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(PlotCanvas, self).__init__(fig)

class ArduinoCommunicator(QWidget):
    def __init__(self):
        super().__init__()
        self.ser = None
        self.loop_data = []
        self.plot_data = {str(pin): [] for pin in pin_ranges}
        self.pin_config = {str(pin): 'disable' for pin in pin_ranges}
        self.is_looping = False
        self.start_time = None
        self.reading_pins = []
        self.init_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_serial_data)

    def init_ui(self):
        self.setWindowTitle('Arduino 命令发送器')

        # 串口选择控件
        port_layout = QHBoxLayout()
        self.port_label = QLabel('选择串口:')
        self.port_combo = QComboBox()
        self.port_combo.addItems(self.get_available_ports())
        self.refresh_button = QPushButton('刷新串口')
        self.refresh_button.clicked.connect(self.on_refresh_ports)
        self.connect_button = QPushButton('连接')
        self.connect_button.clicked.connect(self.on_connect)
        self.disconnect_button = QPushButton('断开')
        self.disconnect_button.clicked.connect(self.on_disconnect)
        self.disconnect_button.setEnabled(False)
        port_layout.addWidget(self.port_label)
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(self.refresh_button)
        port_layout.addWidget(self.connect_button)
        port_layout.addWidget(self.disconnect_button)

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

        # 图形显示部分
        self.plot_canvas = PlotCanvas(self, width=5, height=4, dpi=100)
        self.plot_canvas.hide()

        # 导出CSV按钮
        self.export_button = QPushButton('导出数据为CSV')
        self.export_button.clicked.connect(self.export_to_csv)
        self.export_button.hide()

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addLayout(port_layout)
        main_layout.addLayout(command_layout)
        main_layout.addLayout(self.pin_layout)
        main_layout.addWidget(self.response_label)
        main_layout.addWidget(self.response_text)
        main_layout.addWidget(self.loop_data_label)
        main_layout.addWidget(self.loop_data_text)
        main_layout.addWidget(self.plot_canvas)
        main_layout.addWidget(self.export_button)

        self.setLayout(main_layout)

    def get_available_ports(self):
        ports = list(list_ports.comports())
        return [port.device for port in ports]

    def on_refresh_ports(self):
        self.port_combo.clear()
        ports = self.get_available_ports()
        self.port_combo.addItems(ports)

    def on_connect(self):
        if self.ser is not None:
            self.response_text.append("已经连接")
            return
        selected_port = self.port_combo.currentText()
        if not selected_port:
            self.response_text.append("请选择串口")
            return
        try:
            self.ser = serial.Serial(selected_port, BAUDRATE, timeout=TIMEOUT)
            self.response_text.append(f"已连接到 {selected_port}")
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.get_pin_functions()
        except serial.SerialException as e:
            self.response_text.append(f"错误：无法打开串口 {selected_port}。{e}")

    def on_disconnect(self):
        if self.ser is not None:
            self.ser.close()
            self.ser = None
            self.response_text.append("串口已断开。")
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            if self.is_looping:
                self.is_looping = False
                self.timer.stop()
                self.loop_data_label.hide()
                self.loop_data_text.hide()
                self.plot_canvas.hide()
                self.export_button.hide()

    def send_command(self):
        if self.ser is None:
            self.response_text.append("未连接串口")
            return
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
            self.pin_config[selected_pin] = selected_function
        elif command == 'startLoop':
            self.send_general_command(command)
        elif command == 'stopLoop':
            self.send_general_command(command)

    def send_function_map(self):
        if self.ser is None:
            self.response_text.append("未连接串口")
            return
        cmd_bytes = bytes([command_map['functionMap']])
        self.ser.write(cmd_bytes + b'\r\n')
        time.sleep(0.1)
        response = self.ser.readline().decode().strip()
        if response:
            self.response_text.append(f"响应: {response}")
        else:
            self.response_text.append("未收到响应。")

    def send_get_pin_function(self, pin):
        if self.ser is None:
            self.response_text.append("未连接串口")
            return
        cmd_bytes = bytes([command_map['getPinFunction'], pin])
        self.ser.write(cmd_bytes + b'\r\n')
        time.sleep(0.1)
        response = self.ser.readline().decode().strip()
        if response:
            self.response_text.append(f"引脚 {pin} 功能响应: {response}")
        else:
            self.response_text.append(f"引脚 {pin} 未收到响应。")

    def send_set_pin_function(self, pin, function):
        if self.ser is None:
            self.response_text.append("未连接串口")
            return
        cmd_bytes = bytes([command_map['setPinFunction'], pin, function])
        self.ser.write(cmd_bytes + b'\r\n')
        time.sleep(0.1)
        response = self.ser.readline().decode().strip()
        if response:
            self.response_text.append(f"设置引脚 {pin} 功能为 {function} 响应: {response}")
        else:
            self.response_text.append(f"设置引脚 {pin} 功能为 {function} 未收到响应。")

    def send_get_current_function(self, pin):
        if self.ser is None:
            self.response_text.append("Serial port not connected.")
            return
        try:
            if isinstance(pin, str) and pin.startswith('A'):
                pin_num = ord(pin[1]) - ord('0') + 14
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

    def send_general_command(self, command):
        if self.ser is None:
            self.response_text.append("未连接串口")
            return
        cmd_bytes = bytes([command_map[command]])
        self.ser.write(cmd_bytes + b'\r\n')
        time.sleep(0.1)
        # 修正：添加括号
        response = self.ser.readline().decode().strip()
        if response:
            self.response_text.append(f"响应: {response}")
            if command == 'startLoop':
                self.is_looping = True
                self.start_time = time.time()
                self.loop_data = []
                self.loop_data_label.show()
                self.loop_data_text.show()
                self.plot_canvas.show()
                self.export_button.show()
                self.timer.start(100)  # 每100毫秒读取一次数据
            elif command == 'stopLoop':
                self.is_looping = False
                self.timer.stop()
        else:
            self.response_text.append("未收到响应。")

    def read_serial_data(self):
        if self.ser is None or not self.is_looping:
            return
        try:
            while self.ser.in_waiting:
                line = self.ser.readline().decode().strip()
                if line:
                    self.loop_data.append(line)
                    self.loop_data_text.append(line)
                    # 解析数据并更新绘图
                    try:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            pin = parts[0]
                            value = float(parts[1])
                            if pin in self.plot_data:
                                self.plot_data[pin].append(value)
                                self.update_plot()
                    except ValueError:
                        pass
        except serial.SerialException as e:
            self.response_text.append(f"读取串口数据时出错: {e}")

    def update_plot(self):
        self.plot_canvas.axes.clear()
        for pin, data in self.plot_data.items():
            if data:
                time_points = [i * 0.1 for i in range(len(data))]  # 假设采样间隔为100毫秒
                self.plot_canvas.axes.plot(time_points, data, label=f'Pin {pin}')
        self.plot_canvas.axes.legend()
        self.plot_canvas.draw()

    def export_to_csv(self):
        if not self.loop_data:
            self.response_text.append("没有可导出的数据。")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "导出数据为CSV", "", "CSV Files (*.csv)")
        if file_path:
            try:
                with open(file_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['时间戳', '引脚', '数值'])
                    for line in self.loop_data:
                        try:
                            parts = line.split(',')
                            if len(parts) >= 2:
                                pin = parts[0]
                                value = parts[1]
                                timestamp = time.time() - self.start_time if self.start_time else 0
                                writer.writerow([timestamp, pin, value])
                        except ValueError:
                            pass
                self.response_text.append(f"数据已导出到 {file_path}")
            except Exception as e:
                self.response_text.append(f"导出数据时出错: {e}")

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
        functions = pin_functions.get(pin, [])
        self.function_combo.clear()
        self.function_combo.addItems(functions)

    def get_pin_functions(self):
        for pin in pin_ranges:
            self.send_get_pin_function(pin if not isinstance(pin, str) else ord(pin[1]) - ord('0') + 14)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ArduinoCommunicator()
    ex.show()
    sys.exit(app.exec_())