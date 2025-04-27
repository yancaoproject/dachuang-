# TestBox

## Master-Slave Communication

C: Computer (Master Device)
S: Microcontroller (Slave Device)

Getter and Setter is naming from the pespective of master device.

```
<string>: <size: uint8> <byte1> <byte2>
```

### Getter

Give all supported functions' mapping:

```
C: <Getter.func_map: uint8> <func_count: uint8> <func_num: uint8> <func_name: string> ...
```

Give all supported functions of a pin:

```
C: <Getter.check: uint8> <pin_num: uint8>
S: <func_count: uint8> <func_num1: uint8> <func_num2: uint8>
```

### Setter

```
C: <Setter.set_func: uint8> <pin_num: uint8> <func_num: uint8>
S: <Setter.OK: uint8>
```

### Looper

```
C: <Lopper.start_loop: uint8>
S: <func_num: uint8> <delta_t: uint8> <value: float32>
S: ...
C: <Lopper.stop_loop: uint8>
```