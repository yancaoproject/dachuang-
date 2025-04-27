import sys
import serial
import time
import csv
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTextEdit, QPushButton, QFileDialog, QTabWidget
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

class ArduinoCommunicator(QWidget):
    def __init__(self):
        super().__init__()
        self.ser_connections = {}
        self.loop_data = {}
        self.is_looping = {}
        self.plot_data = {}
        self.timers = {}
        self.plot_canvases = {}
        self.chart_windows = {}
        self.chart_tab_widget = QTabWidget()
        self.loop_data_labels = {}
        self.loop_data_texts = {}
        self.export_buttons = {}
        self.raw_data = {}  # 新增：存储原始数据
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Arduino 命令发送器')

        # 创建标签页控件，将串口显示功能与引脚配置分开
        tab_widget = QTabWidget()

        # 串口控制标签页
        serial_tab = QWidget()
        serial_layout = QVBoxLayout()

        # 多个串口选择控件
        self.port_combos = []  # 存储每个串口的下拉选择框
        self.connect_buttons = []  # 存储每个串口的连接按钮
        self.disconnect_buttons = []  # 存储每个串口的断开按钮
        self.refresh_buttons = []  # 存储每个串口的刷新按钮

        ports = self.get_available_ports()  # 获取当前可用的串口列表
        for i in range(3):  # 最多支持3个串口，可根据需要调整
            port_layout = QHBoxLayout()  # 每个串口的水平布局
            port_label = QLabel(f'选择串口 {i + 1}:')  # 串口选择标签
            port_combo = QComboBox()  # 串口选择下拉框
            port_combo.addItems(ports)  # 将可用串口添加到下拉框中
            refresh_button = QPushButton('刷新串口')  # 刷新串口按钮
            # 绑定刷新按钮的点击事件，点击时调用 on_refresh_ports 方法
            refresh_button.clicked.connect(lambda _, idx=i: self.on_refresh_ports(idx))
            connect_button = QPushButton('连接')  # 连接按钮
            # 绑定连接按钮的点击事件，点击时调用 on_connect 方法
            connect_button.clicked.connect(lambda _, idx=i: self.on_connect(idx))
            disconnect_button = QPushButton('断开')  # 断开按钮
            # 绑定断开按钮的点击事件，点击时调用 on_disconnect 方法
            disconnect_button.clicked.connect(lambda _, idx=i: self.on_disconnect(idx))
            disconnect_button.setEnabled(False)  # 初始时断开按钮不可用

            self.port_combos.append(port_combo)  # 将下拉框添加到列表中
            self.connect_buttons.append(connect_button)  # 将连接按钮添加到列表中
            self.disconnect_buttons.append(disconnect_button)  # 将断开按钮添加到列表中
            self.refresh_buttons.append(refresh_button)  # 将刷新按钮添加到列表中

            port_layout.addWidget(port_label)  # 将标签添加到水平布局中
            port_layout.addWidget(port_combo)  # 将下拉框添加到水平布局中
            port_layout.addWidget(refresh_button)  # 将刷新按钮添加到水平布局中
            port_layout.addWidget(connect_button)  # 将连接按钮添加到水平布局中
            port_layout.addWidget(disconnect_button)  # 将断开按钮添加到水平布局中
            serial_layout.addLayout(port_layout)  # 将水平布局添加到串口控制标签页的垂直布局中

        serial_tab.setLayout(serial_layout)  # 设置串口控制标签页的布局

        # 引脚配置标签页
        config_tab = QWidget()
        config_layout = QVBoxLayout()

        # 添加串口选择下拉框
        self.config_port_label = QLabel('选择发送指令的串口:')
        self.config_port_combo = QComboBox()
        self.config_port_combo.addItems([f'串口 {i + 1}' for i in range(3)])
        config_layout.addWidget(self.config_port_label)
        config_layout.addWidget(self.config_port_combo)

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

        config_layout.addLayout(command_layout)
        config_layout.addLayout(self.pin_layout)
        config_tab.setLayout(config_layout)

        # 图表显示部分
        self.plot_layout = QVBoxLayout()  # 用于存放所有图表的布局

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

        # 添加标签页
        tab_widget.addTab(serial_tab, "串口控制")
        tab_widget.addTab(config_tab, "引脚配置")

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(tab_widget)
        main_layout.addWidget(self.chart_tab_widget)  # 添加图表标签页控件
        main_layout.addWidget(self.loop_data_label)
        main_layout.addWidget(self.loop_data_text)
        main_layout.addWidget(self.export_button)

        # 为每个串口创建独立的循环数据显示控件
        for i in range(3):
            loop_data_label = QLabel(f'串口 {i + 1} 循环数据:')
            loop_data_text = QTextEdit()
            loop_data_text.setReadOnly(True)
            loop_data_text.hide()
            loop_data_label.hide()

            export_button = QPushButton(f'导出串口 {i + 1} 数据为CSV')
            export_button.clicked.connect(lambda _, idx=i: self.export_to_csv(idx))
            export_button.hide()

            self.loop_data_labels[i] = loop_data_label
            self.loop_data_texts[i] = loop_data_text
            self.export_buttons[i] = export_button

            main_layout.addWidget(loop_data_label)
            main_layout.addWidget(loop_data_text)
            main_layout.addWidget(export_button)

        self.setLayout(main_layout)

    def get_available_ports(self):
        # 使用 serial.tools.list_ports.comports() 获取当前可用的串口列表
        ports = list(list_ports.comports())
        # 提取每个串口的设备名称并返回
        return [port.device for port in ports]

    def on_refresh_ports(self, index):
        # 清空指定索引的串口下拉选择框
        self.port_combos[index].clear()
        # 获取当前可用的串口列表
        ports = self.get_available_ports()
        # 将可用串口添加到指定索引的下拉选择框中
        self.port_combos[index].addItems(ports)

    def on_connect(self, index):
        # 检查指定索引的串口是否已经连接
        if index in self.ser_connections and self.ser_connections[index] is not None:
            # 如果已经连接，在循环数据文本框中添加提示信息
            self.loop_data_text.append(f"串口 {index + 1} 已经连接")
            return
    
        # 获取指定索引的串口下拉选择框中选中的串口
        selected_port = self.port_combos[index].currentText()
        if not selected_port:
            # 如果未选择串口，在循环数据文本框中添加提示信息
            self.loop_data_text.append(f"请选择串口 {index + 1}")
            return
    
        try:
            # 尝试打开指定的串口，设置波特率和超时时间
            self.ser_connections[index] = serial.Serial(selected_port, BAUDRATE, timeout=TIMEOUT)
            # 在对应串口的循环数据文本框中添加连接成功的提示信息
            self.loop_data_texts[index].append(f"已连接到串口 {index + 1}: {selected_port}")
            # 禁用连接按钮
            self.connect_buttons[index].setEnabled(False)
            # 启用断开按钮
            self.disconnect_buttons[index].setEnabled(True)
            # 初始化指定索引的串口的循环数据列表
            self.loop_data[index] = []
            # 初始化指定索引的串口的绘图数据字典
            self.plot_data[index] = {}
            # 创建一个定时器对象
            self.timers[index] = QTimer(self)
            # 绑定定时器的超时事件，超时后调用 read_serial_data 方法
            self.timers[index].timeout.connect(lambda: self.read_serial_data(index))
            
            # 显示对应串口的循环数据相关控件
            self.loop_data_labels[index].show()
            self.loop_data_texts[index].show()
            self.export_buttons[index].show()
            self.timers[index].start(100)
    
            # 获取引脚配置串口的索引
            selected_index = self.config_port_combo.currentIndex()
    
            # 只有当串口索引不是引脚配置串口索引时才创建和显示图表
            if index != selected_index:
                # 为新连接的串口创建图表画布
                self.plot_canvases[index] = FigureCanvas(Figure(figsize=(5, 4), dpi=100))
                # 创建新的窗口来显示图表
                self.chart_windows[index] = ChartWindow(self.plot_canvases[index])
                self.chart_windows[index].setWindowTitle(f"串口 {index + 1} 图表")
                self.chart_windows[index].show()
            
            # 只有引脚配置指定串口才在连接时获取所有引脚 currentpinfunction
            if index == selected_index:
                self.get_pin_functions_for_index(index)
            
        except serial.SerialException as e:
            # 如果连接失败，在循环数据文本框中添加错误提示信息
            self.loop_data_texts[index].append(f"无法连接到串口 {index + 1}: {e}")
            # 将指定索引的串口连接对象设置为 None
            self.ser_connections[index] = None

    def on_disconnect(self, index):
        # 检查指定索引的串口是否已经连接
        if index in self.ser_connections and self.ser_connections[index] is not None:
            # 关闭指定索引的串口连接
            self.ser_connections[index].close()
            # 将指定索引的串口连接对象设置为 None
            self.ser_connections[index] = None
            # 在循环数据文本框中添加断开连接的提示信息
            self.loop_data_texts[index].append(f"串口 {index + 1} 已断开。")
            # 启用连接按钮
            self.connect_buttons[index].setEnabled(True)
            # 禁用断开按钮
            self.disconnect_buttons[index].setEnabled(False)
            # 检查指定索引的串口是否正在循环
            if index in self.is_looping and self.is_looping[index]:
                # 如果正在循环，停止循环并设置循环状态为 False
                self.is_looping[index] = False
                self.timers[index].stop()
            # 移除断开串口对应的图表标签页
            if index in self.plot_canvases:
                # 获取指定索引的图表画布在标签页控件中的索引
                tab_index = self.chart_tab_widget.indexOf(self.plot_canvases[index])
                if tab_index != -1:
                    # 如果找到图表画布，从标签页控件中移除该标签页
                    self.chart_tab_widget.removeTab(tab_index)
                # 从图表画布字典中删除指定索引的画布
                del self.plot_canvases[index]

            # 隐藏对应串口的循环数据相关控件
            self.loop_data_labels[index].hide()
            self.loop_data_texts[index].hide()
            self.loop_data_texts[index].clear()
            self.export_buttons[index].hide()
        else:
            # 关闭并删除对应的图表窗口
            if index in self.chart_windows:
                self.chart_windows[index].close()
                del self.chart_windows[index]

            # 关闭指定索引的串口连接
            self.ser_connections[index].close()
            # 将指定索引的串口连接对象设置为 None
            self.ser_connections[index] = None
            # 在循环数据文本框中添加断开连接的提示信息
            self.loop_data_texts[index].append(f"串口 {index + 1} 已断开。")
            # 启用连接按钮
            self.connect_buttons[index].setEnabled(True)
            # 禁用断开按钮
            self.disconnect_buttons[index].setEnabled(False)
            # 检查指定索引的串口是否正在循环
            if index in self.is_looping and self.is_looping[index]:
                # 如果正在循环，停止循环并设置循环状态为 False
                self.is_looping[index] = False
                self.timers[index].stop()
            # 移除断开串口对应的图表标签页
            if index in self.plot_canvases:
                # 获取指定索引的图表画布在标签页控件中的索引
                tab_index = self.chart_tab_widget.indexOf(self.plot_canvases[index])
                if tab_index != -1:
                    # 如果找到图表画布，从标签页控件中移除该标签页
                    self.chart_tab_widget.removeTab(tab_index)
                # 从图表画布字典中删除指定索引的画布
                del self.plot_canvases[index]

    def send_command(self):
        selected_index = self.config_port_combo.currentIndex()
        if selected_index not in self.ser_connections or self.ser_connections[selected_index] is None:
            self.loop_data_text.append(f"选择的串口 {selected_index + 1} 未连接")
            return

        command = self.command_combo.currentText()
        selected_pin = self.pin_combo.currentText()

        if command == 'getcurrentPinFunction':
            self.send_get_current_function(selected_index, selected_pin)
        elif command == 'functionMap':
            self.send_function_map(selected_index)
        elif command == 'getPinFunction':
            if isinstance(selected_pin, str) and selected_pin.startswith('A'):
                pin_num = ord(selected_pin[1]) - ord('0') + 14
            else:
                pin_num = int(selected_pin)
            self.send_get_pin_function(selected_index, pin_num)
        elif command == 'setPinFunction':
            selected_function = self.function_combo.currentText()
            function_num = function_map[selected_function]
            if isinstance(selected_pin, str) and selected_pin.startswith('A'):
                pin_num = ord(selected_pin[1]) - ord('0') + 14
            else:
                pin_num = int(selected_pin)
            self.send_set_pin_function(selected_index, pin_num, function_num)
        elif command == 'startLoop':
            self.send_general_command(selected_index, command)
        elif command == 'stopLoop':
            self.send_general_command(selected_index, command)

    def send_function_map(self, index):
        if index not in self.ser_connections or self.ser_connections[index] is None:
            self.loop_data_texts[index].append("未连接串口")
            return
        cmd_bytes = bytes([command_map['functionMap']])
        self.ser_connections[index].write(cmd_bytes + b'\r\n')
        time.sleep(0.1)
        response = self.ser_connections[index].readline().decode().strip()
        if response:
            self.loop_data_texts[index].append(f"串口 {index + 1} 响应: {response}")
        else:
            self.loop_data_texts[index].append(f"串口 {index + 1} 未收到响应。")

    def send_get_pin_function(self, index, pin):
        if index not in self.ser_connections or self.ser_connections[index] is None:
            self.loop_data_texts[index].append("未连接串口")
            return
        cmd_bytes = bytes([command_map['getPinFunction'], pin])
        self.ser_connections[index].write(cmd_bytes + b'\r\n')
        time.sleep(0.1)
        response = self.ser_connections[index].readline().decode().strip()
        if response:
            self.loop_data_texts[index].append(f"串口 {index + 1} 引脚 {pin} 功能响应: {response}")
        else:
            self.loop_data_texts[index].append(f"串口 {index + 1} 引脚 {pin} 未收到响应。")

    def send_set_pin_function(self, index, pin, function):
        if index not in self.ser_connections or self.ser_connections[index] is None:
            self.loop_data_texts[index].append("未连接串口")
            return
        cmd_bytes = bytes([command_map['setPinFunction'], pin, function])
        self.ser_connections[index].write(cmd_bytes + b'\r\n')
        time.sleep(0.1)
        response = self.ser_connections[index].readline().decode().strip()
        if response:
            self.loop_data_texts[index].append(f"串口 {index + 1} 设置引脚 {pin} 功能为 {function} 响应: {response}")
        else:
            self.loop_data_texts[index].append(f"串口 {index + 1} 设置引脚 {pin} 功能为 {function} 未收到响应。")

    def send_get_current_function(self, index, pin):
        if index not in self.ser_connections or self.ser_connections[index] is None:
            self.loop_data_text.append("Serial port not connected.")
            return
        try:
            if isinstance(pin, str) and pin.startswith('A'):
                pin_num = ord(pin[1]) - ord('0') + 14  # A0 -> 14, A1 -> 15, etc.
                cmd_bytes = bytes([command_map['getcurrentPinFunction'], pin_num])
            else:
                pin_num = int(pin)
                cmd_bytes = bytes([command_map['getcurrentPinFunction'], pin_num])

            self.ser_connections[index].write(cmd_bytes + b'\r\n')
            time.sleep(0.1)
            response = self.ser_connections[index].readline().decode().strip()
            if response:
                try:
                    # 将数字响应转换为对应的功能单词
                    function_num = int(response)
                    function_word = next((key for key, value in function_map.items() if value == function_num), '未知功能')
                    self.pin_labels[pin].setText(f'引脚 {pin}: {function_word}')
                except ValueError:
                    self.pin_labels[pin].setText(f'引脚 {pin}: {response}')
            else:
                self.pin_labels[pin].setText(f'引脚 {pin}: 未获取到功能')
        except KeyError:
            print(f"错误：在 self.pin_labels 字典中未找到键 {pin}")
            self.loop_data_text.append(f"错误：在 self.pin_labels 字典中未找到键 {pin}")

    def send_general_command(self, index, command):
        if index not in self.ser_connections or self.ser_connections[index] is None:
            self.loop_data_text.append("未连接串口")
            return
        cmd_bytes = bytes([command_map[command]])
        self.ser_connections[index].write(cmd_bytes + b'\r\n')
        time.sleep(0.1)
        response = self.ser_connections[index].readline().decode().strip()
        if response:
            self.loop_data_text.append(f"串口 {index + 1} 响应: {response}")
            if command == 'startLoop' and response == Response_map['ok']:
                self.is_looping[index] = True
                self.loop_data_label.show()
                self.loop_data_text.show()
                self.export_button.show()
                self.timers[index].start(100)
                self.plot_data[index] = {}
            elif command == 'stopLoop' and response == Response_map['ok']:
                self.is_looping[index] = False
                self.timers[index].stop()
                self.loop_data_label.hide()
                self.loop_data_text.hide()
                self.loop_data_text.clear()
                self.plot_canvases[index].hide()
        else:
            self.loop_data_text.append(f"串口 {index + 1} 未收到响应。")

    def read_serial_data(self, index):
        try:
            if index in self.ser_connections and self.ser_connections[index] and self.ser_connections[index].in_waiting > 0:
                data = self.ser_connections[index].readline().decode().strip()
                if data:
                    # 将数据添加到循环数据列表
                    self.loop_data[index].append(data)
                    # 在对应的循环数据文本框中显示数据
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    self.loop_data_texts[index].append(f"串口 {index + 1} [{timestamp}] {data}")
                
                    # 存储原始数据用于波形图
                    if index not in self.raw_data:
                        self.raw_data[index] = []
                    try:
                        # 尝试将数据转换为数值
                        value = float(data)
                        self.raw_data[index].append(value)
                        self.update_raw_image(index)
                    except ValueError:
                        # 如果转换失败，忽略该数据点
                        pass
        except serial.SerialException as e:
            # 捕获串口异常并添加错误信息到对应的循环数据文本框
            self.loop_data_texts[index].append(f"串口 {index + 1} 读取数据时发生串口异常: {e}")
            # 关闭串口连接并清理资源
            if index in self.ser_connections:
                try:
                    self.ser_connections[index].close()
                except:
                    pass
                self.ser_connections[index] = None
                self.connect_buttons[index].setEnabled(True)
                self.disconnect_buttons[index].setEnabled(False)
                self.timers[index].stop()
                if index in self.plot_canvases:
                    tab_index = self.chart_tab_widget.indexOf(self.plot_canvases[index])
                    if tab_index != -1:
                        self.chart_tab_widget.removeTab(tab_index)
                    del self.plot_canvases[index]
                self.loop_data_labels[index].hide()
                self.loop_data_texts[index].hide()
                self.loop_data_texts[index].clear()
                self.export_buttons[index].hide()
        except Exception as e:
            # 捕获其他异常并添加错误信息到对应的循环数据文本框
            self.loop_data_texts[index].append(f"串口 {index + 1} 读取数据时发生未知异常: {e}")

    def update_raw_image(self, index):
        if index in self.plot_canvases:
            canvas = self.plot_canvases[index]
            fig = canvas.figure
            fig.clear()
            ax = fig.add_subplot(111)
            
            # 获取原始数据
            img_data = self.raw_data[index]
            
            # 绘制波形图
            ax.plot(range(len(img_data)), img_data)
            
            ax.set_xlabel('数据点')
            ax.set_ylabel('数值')
            ax.set_title(f'串口 {index + 1} 波形图')
            
            canvas.draw()

    def update_plot(self, index):
        if index in self.plot_canvases:
            canvas = self.plot_canvases[index]
            canvas.figure.clear()
            ax = canvas.figure.add_subplot(111)
            for pin, (x, y) in self.plot_data[index].items():
                ax.plot(x, y, label=pin)
            ax.legend()
            canvas.draw()

    def export_to_csv(self, index):
        if index not in self.loop_data:
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "导出数据为CSV", "", "CSV Files (*.csv)")
        if file_path:
            with open(file_path, 'w', newline='') as csvfile:
                fieldnames = ['timestamp', 'data']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for item in self.loop_data[index]:
                    writer.writerow(item)

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

    def get_pin_functions_for_index(self, index):
        for pin in pin_ranges:
            self.send_get_current_function(index, str(pin))

    def closeEvent(self, event):
        for index in self.timers:
            self.timers[index].stop()
        for index in self.ser_connections:
            if self.ser_connections[index] is not None:
                self.ser_connections[index].close()
        print("所有串口已关闭。")
        event.accept()

# 图表画布类
class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(fig)
        self.setParent(parent)

# 窗口类
class ChartWindow(QWidget):
    def __init__(self, canvas):
        super().__init__()
        self.setWindowTitle('串口图表')
        layout = QVBoxLayout()
        layout.addWidget(canvas)
        self.setLayout(layout)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    communicator = ArduinoCommunicator()
    communicator.show()
    sys.exit(app.exec_())