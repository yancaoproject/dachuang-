#ifndef CONFIGURATION_H_
#define CONFIGURATION_H_

#include <Arduino.h>
#include <Array.h>

// Commands

enum Command: uint8_t {
    functionMap,
    getPinFunction,
    getCurrentPinFunction,
    setPinFunction,
    startLoop,
    stopLoop,
};

enum Response: uint8_t {
    ok,
    error,
};

enum PinFunction: uint8_t {
    disable,
    readDigital,
    writeDigital,
    readAnalog,
    writeAnalog,
};

// Pin Configurations

struct PinConfiguration {
   public:
    int pin;
    PinFunction* functions;
    int functionsCount;
    PinFunction selectedFunction;

    PinConfiguration(int pin, PinFunction* functions, int functionsCount) {
        this->pin = pin;
        this->functions = functions;
        this->functionsCount = functionsCount;
        this->selectedFunction = PinFunction::disable;
    }
};

Array<PinConfiguration> PinConfigurations;

#define ARRAY(...) __VA_ARGS__
#define NewPinConfiguration(pin, funcs) \
    PinFunction functions##pin[] = {funcs}; \
    PinConfiguration configuration##pin(pin, functions##pin, sizeof(functions##pin)/sizeof(PinFunction)); \
    PinConfigurations.append(configuration##pin);

#endif