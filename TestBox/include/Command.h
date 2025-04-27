#ifndef COMMAND_H_
#define COMMAND_H_

// this is based on little-endian
// remainder is ignored
// 1 unit = 8 bit (char, uint_t)
// COMMAND_BUFFER_SIZE = requiredItemsInUnit + (EnderInUnit - 1) / ItemInUnit

#include <Arduino.h>

#ifndef COMMAND_BUFFER_SIZE
#define COMMAND_BUFFER_SIZE 5
#endif
#ifndef SERIAL_COMMAND
#define SERIAL_COMMAND Serial
#endif

enum InArgument {
    getPinFunction,
    setPinFunction,
    startLoop,
    endLoop,
};

enum OutArgument {
    ok,
};

template <typename Item, typename Ender>
class _Command {
   private:
    Ender ender;
    Item tempItem = 0;
    const int itemSize = sizeof(Item) / sizeof(uint8_t);
    const int enderSize = sizeof(Ender) / sizeof(uint8_t);
    int itemFilling = 0;
    int enderFilling = 0;
    int itemCountDuringEnder = 0;

   public:
    Item argv[COMMAND_BUFFER_SIZE];
    int argc = 0;

    _Command(Ender ender) {
        this->ender = ender;
    };

    bool command() {
        if (SERIAL_COMMAND.available() > 0) {
            uint8_t reading = SERIAL_COMMAND.read();
            if (reading == (uint8_t)(ender >> enderFilling*8)) {
                enderFilling += 1;
            } else {
                enderFilling = 0;
                itemCountDuringEnder = 0;
            }
            if (enderFilling == enderSize) {
                argc -= itemCountDuringEnder;
                if (argc > 0) {
                    return true;
                } else { clear(); }
            }
            tempItem += (Item)reading << itemFilling*8;
            itemFilling += 1;
            if (itemFilling == itemSize) {
                argv[argc] = tempItem;
                argc += 1;
                tempItem = 0;
                itemFilling = 0;
                if (enderFilling != 0) {
                    itemCountDuringEnder += 1;
                }
            }
        }
        return false;
    }

    void clear() {
        argc = 0;
        itemFilling = 0;
        tempItem = 0;
        enderFilling = 0;
        itemCountDuringEnder = 0;
    }
};

_Command<uint8_t, uint16_t> Command((uint16_t)'\r' + ((uint16_t)'\n' << 8));

#endif