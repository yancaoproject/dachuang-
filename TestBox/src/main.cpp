#include <Arduino.h>
#include <Arduino_FreeRTOS.h>
#include <Array.h>
#include "Configuration.h"

#include <SoftwareSerial.h>
// 避免使用已配置的引脚，这里假设使用其他引脚
SoftwareSerial SerialCommand(2, 3);

// 减少全局变量，将 frequency 移到需要使用的地方
// int frequency = 10;

void taskCommandInterface(void* parameters);
TaskHandle_t taskCommandInterfaceHandle = NULL;
void taskLooper(void* parameters);
TaskHandle_t taskLooperHandle = NULL;

void setup() {
    // NewPinConfiguration(2, ARRAY(PinFunction::readDigital, PinFunction::writeDigital))
    // NewPinConfiguration(3, ARRAY(PinFunction::readDigital, PinFunction::writeDigital, PinFunction::writeAnalog))
    NewPinConfiguration(4, ARRAY(PinFunction::readDigital, PinFunction::writeDigital))
    NewPinConfiguration(5, ARRAY(PinFunction::readDigital, PinFunction::writeDigital, PinFunction::writeAnalog))
    NewPinConfiguration(6, ARRAY(PinFunction::readDigital, PinFunction::writeDigital, PinFunction::writeAnalog))
    NewPinConfiguration(7, ARRAY(PinFunction::readDigital, PinFunction::writeDigital))
    NewPinConfiguration(8, ARRAY(PinFunction::readDigital, PinFunction::writeDigital))
    NewPinConfiguration(9, ARRAY(PinFunction::readDigital, PinFunction::writeDigital, PinFunction::writeAnalog))
    NewPinConfiguration(10, ARRAY(PinFunction::readDigital, PinFunction::writeDigital, PinFunction::writeAnalog))
    NewPinConfiguration(11, ARRAY(PinFunction::readDigital, PinFunction::writeDigital, PinFunction::writeAnalog))
    NewPinConfiguration(A0, ARRAY(PinFunction::readDigital, PinFunction::writeDigital, PinFunction::readAnalog))
    NewPinConfiguration(A1, ARRAY(PinFunction::readDigital, PinFunction::writeDigital, PinFunction::readAnalog))
    NewPinConfiguration(A2, ARRAY(PinFunction::readDigital, PinFunction::writeDigital, PinFunction::readAnalog))
    NewPinConfiguration(A3, ARRAY(PinFunction::readDigital, PinFunction::writeDigital, PinFunction::readAnalog))
    NewPinConfiguration(A4, ARRAY(PinFunction::readDigital, PinFunction::writeDigital, PinFunction::readAnalog))
    NewPinConfiguration(A5, ARRAY(PinFunction::readDigital, PinFunction::writeDigital, PinFunction::readAnalog))
    
    Serial.begin(115200);
    Serial.println(F("Debug Start")); // 使用 F() 宏将字符串存储在 Flash 中
    SerialCommand.begin(115200);
    
    // 进一步减小任务堆栈大小
    BaseType_t xReturned = xTaskCreate(
        taskCommandInterface, "Command Interface", 256, NULL, 1, &taskCommandInterfaceHandle
    );

    if (xReturned != pdPASS) {
        // 任务创建失败，处理错误
        Serial.println(F("Task creation failed!"));
    }

    xReturned = xTaskCreate(
        taskLooper, "Looper", 256, NULL, 1, &taskLooperHandle
    );

    if (xReturned != pdPASS) {
        // 任务创建失败，处理错误
        Serial.println(F("Task creation failed!"));
    }

    // vTaskStartScheduler();
    vTaskSuspend(taskLooperHandle);
}

void loop() { }

// FreeRTOS Tasks

void taskCommandInterface(void* parameters) {
    while (true) {         
        if (SerialCommand.available() > 0) {
            uint8_t command = SerialCommand.read();
           
            switch (command) {
            case Command::functionMap:
                //SerialCommand.print(Response::ok);
                Serial.println(F("Function Map"));
                break;
            case Command::getPinFunction:
                if (SerialCommand.available() > 0) {
                    uint8_t pin = SerialCommand.read();
                    // 查找引脚配置
                    for (int i = 0; i < PinConfigurations.count(); i++) {
                        if (PinConfigurations[i].pin == pin) {
                            SerialCommand.print(Response::ok);
                            SerialCommand.print(PinConfigurations[i].functionsCount);
                            for (int j = 0; j < PinConfigurations[i].functionsCount; j++) {
                                SerialCommand.print(PinConfigurations[i].functions[j]);
                            }
                            Serial.print(F("Pin "));
                            Serial.print(pin);
                            Serial.println(F(" function retrieved"));
                            break;
                        }
                    }
                }
                break;
            case Command::getCurrentPinFunction:
                if (SerialCommand.available() > 0) {
                    uint8_t pin = SerialCommand.read();
                    // 查找引脚配置
                    for (int i = 0; i < PinConfigurations.count(); i++) {
                        if (PinConfigurations[i].pin == pin) {
                            SerialCommand.print(Response::ok);
                            SerialCommand.print(PinConfigurations[i].selectedFunction);
                            Serial.print(F("Pin "));
                            Serial.print(pin);
                            Serial.println(F(" function getted"));
                            break;
                        }
                    }
                }
                break;
            case Command::setPinFunction:
                if (SerialCommand.available() > 1) {
                    uint8_t pin = SerialCommand.read();
                    uint8_t function = SerialCommand.read();
                    // 查找引脚配置并设置功能
                    for (int i = 0; i < PinConfigurations.count(); i++) {
                        if (PinConfigurations[i].pin == pin) {
                            PinConfigurations[i].selectedFunction = static_cast<PinFunction>(function);
                            SerialCommand.print(Response::ok);
                            Serial.print(F("Pin "));
                            Serial.print(pin);
                            Serial.print(F(" function set to "));
                            Serial.println(function);
                            break;
                        }
                    }
                }
                break;
            case Command::startLoop:
                if (taskLooperHandle != NULL) {
                    vTaskResume(taskLooperHandle);
                    SerialCommand.print(Response::ok);
                    Serial.println(F("Start Loop"));
                } else {
                    SerialCommand.print(Response::error);
                    Serial.println(F("Task looper handle is NULL"));
                }
                break;
            case Command::stopLoop:
                vTaskSuspend(taskLooperHandle);
                vTaskResume(taskCommandInterfaceHandle);
                SerialCommand.print(Response::ok);
                Serial.println(F("Stop Loop"));
                break;
            default:
                //SerialCommand.print(Response::error);
                //Serial.print(F("Error"));
                break;
            }
        }
    }
}  
void taskLooper(void* parameters) {
    while (true) {
        float V_A = analogRead(A0);
        Serial.println(V_A);

// for(int i = 0; i < PinConfigurations.count(); i++) {
        //     switch (PinConfigurations[i].selectedFunction) {
        //         case PinFunction::readDigital:
        //             Serial.println(F("read digital"));
        //             break;
        //         case PinFunction::writeDigital:
        //             Serial.println(F("write digital"));
        //             break;
        //         case PinFunction::readAnalog:
        //             Serial.println(F("read analog")); // 修正错误信息
        //             break;
        //         case PinFunction::writeAnalog:
        //             Serial.println(F("write analog")); // 修正错误信息
        //             break;
        //         case PinFunction::disable:
        //             Serial.println(F("disable")); // 修正错误信息
        //             break;
        //     }
        // }
        
        if (SerialCommand.available() > 0) {
            uint8_t command = SerialCommand.read();
            switch (command) {
            case Command::stopLoop:
                vTaskSuspend(taskLooperHandle);
                vTaskResume(taskCommandInterfaceHandle);
                SerialCommand.print(Response::ok);
                Serial.println(F("Stop Loop"));
                break;
            default:
                //SerialCommand.print(Response::error);
                //Serial.println(F("Error"));
                break;
            }
        }

        // delay depending on capture Hz
        vTaskDelay(100 / portTICK_PERIOD_MS);
    }
}
