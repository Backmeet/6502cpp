import re

'''
- var name = literal ; declare variable in current scope
- set name = literal ; assign to an existing variable
- buffer name size [= list_literal] ; create a buffer with size
- buffer read name index var ; var = buffer[index]
- buffer write name var index ; buffer[index] = var
- def name: ; function / label def
- def name  ; function / label def
- return
- call name
- jump name
- if [var or value] op [var or value]
- while [var or value] op [var or value]
- end
- math name = [var or value] op [var or value] ; arithmetic assignment
- read addres var
- write addres [var or value]
- comments with //...
ops are + - > < == !=
some special ones are
+?: on add overflow?
-?: on sub negitive?

also convert these for optamizations

[var or value] + 1 -> INC or any other INCs
[var or value] - 1 -> DEC or any other DECs
[var or value] == 0 -> zero flag
and const expresstions
like
1 == 0 or 1 + 2 to a constant loop

a value literal can be
010001b
0xFFFF
0XFF
123
'a'
"a"
&lvar lower part of pointer
&hvar higer part of pointer

a list literal is
[value literal, ...]

static allocation starts at FF00 FEFF ... and goes downwards 
FFF0: sp low
FFEF: sp high

00FF: temp
'''

tokenize_ = re.compile(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\[[^\]]*\]|[^\s"'\[\]]+''')
comment = re.compile(r'''//.*$''')

def tokenize(line: str):
    return tokenize_.findall(comment.sub("", line))

def clamp(x, mi, mx):
    return max(min(x, mx), mi)

def compile(program: str):
    
    compiled = r'''
; code made by simplified asm ver 0.4
startup:
    SEI           ; disable irqs
    JSR main
    EXIT: JMP EXIT

NOPI:
    NOP
    RTI

NOP_:
    NOP
    RTS
'''
    allocated = {}
    free_addresses = set(range(0xFF00, -1, -1))  # Start from FF00 down to 0
    lablestack = []
    jumplabels = []

    nmihandlername = "NOPI"
    irqhandlername = "NOPI"

    def _newid():
        n = 0
        while 1:
            yield n
            n += 1
    
    newid = _newid()

    def allocate(name, size=1):
        if name in allocated:
            return format(allocated[name][0], "X")  # Return first address already assigned

        if len(free_addresses) < size:
            raise MemoryError("Not enough free memory")

        # Pick the highest `size` addresses from free_addresses
        block = sorted(free_addresses, reverse=True)[:size]

        for addr in block:
            free_addresses.remove(addr)

        allocated[name] = block
        return format(block[0], "X")  # Return first address assigned

    def deallocate(name):
        if name in allocated:
            block = allocated[name]
            for addr in block:
                free_addresses.add(addr)
            del allocated[name]

    def exists(name):
        if name not in allocated:
            return False
        return True
    
    def error(msg, line, lineno):
        print(f"@{lineno}: {line}\nerror: {msg}")
        exit()

    def parse_value(val: str):
        """
        The value may be given in three ways:
        - As a decimal integer (e.g. "123")
        - As a binary literal ending with 'b' (e.g. "100001b")
        - As a hex literal starting with a '0x'
        - As an encoded character (e.g. '"a"' or simply a key that exists in the encoding)
        """
        if val.endswith("b"):
            bin_part = val[:-1]
            if all(c in "01" for c in bin_part) and bin_part:
                return format(int(bin_part, 2), 'X')
            else:
                raise ValueError("Invalid binary literal")
        elif val.isdigit():
            return format(int(val), "X")
        elif val.startswith("0x"):
            return val[2:]
        elif ((val.startswith('"') and val.endswith('"')) or 
            (val.startswith("'") and val.endswith("'"))):
            text = val[1:-1]
            if len(text) == 1:
                return format(ord(text), "X")
            else:
                raise ValueError("Encoded values must be a single character")
        elif val[0] == "&":
            return allocate(var[2:])[2:]
        else:
            raise ValueError("Invalid value format " + val)


    def math(a: str, op: str, b: str, line, i, resultaddr="0000", jumpiftrue=False, jumptotrue="NOP", jumptofalse="NOP"):
        a = a.strip()
        b = b.strip()
        op = op.strip()
        out = []
        aconst = not exists(a)
        bconst = not exists(b)
        bvalue = 0
        if not aconst:
            out.extend([
                f"LDA ${allocate(a)}"
            ])
        else:
            value = parse_value(a)
            if not (0 <= int(value, 16) <= 255):
                error(f"in math of a: {a} b: {b}, with {op} const a: {a} is more then 8bits", line, i)
            out.extend([
                f"LDA #${value}"
            ])
        if bconst:
            bvalue = parse_value(b)
            if not (0 <= int(bvalue, 16) <= 255):
                error(f"in math of a: {a} b: {b}, with {op} const b: {b} is more then 8bits", line, i)
        

        if aconst and bconst:
            error(f"in math of a: {a} b: {b}, with {op} both a and b are const, optamzie the src code", line, i)
        
        if aconst and a == "1" and op == "+":
            return [
                f"INC ${allocate(b)}"
            ]
            
        if bconst and b == "1" and op == "+":
            return [
                f"INC ${allocate(a)}"
            ]

        if aconst and a == "1" and op == "-":
            return [
                f"DEC ${allocate(b)}"
            ]

        if bconst and b == "1" and op == "-":
            return [
                f"DEC ${allocate(a)}"
            ]
        
        if op == "+":
            out.extend(["CLC"])
            out.extend([
                f"ADC #{bvalue}"
            ] if bconst else [
                f"ADC ${allocate(b)}"
            ])
            if jumpiftrue:
                label = f"skip_{next(newid)}"
                out.extend([
                    f"CMP #0",
                    f"BNE {label}",      # skip if A != B
                    f"JMP {jumptotrue}", # execute jump if A == B
                    f"{label}:",
                    f"JMP {jumptofalse}"
                ])
            else:
                out.extend([
                    f"STA ${resultaddr}"
                ])

        elif op == "-":
            out.extend(["CLC"])
            out.extend([
                f"SBC #{bvalue}"
            ] if bconst else [
                f"SBC ${allocate(b)}"
            ])
            if jumpiftrue:
                label = f"skip_{next(newid)}"
                out.extend([
                    f"CMP #0",
                    f"BNE {label}",      # skip if A != B
                    f"JMP {jumptotrue}", # execute jump if A == B
                    f"{label}:",
                    f"JMP {jumptofalse}"
                ])
            else:
                out.extend([
                    f"STA ${resultaddr}"
                ])

        elif op in {">", "<", "==", "!="}:
            out.extend([
                f"CMP #{bvalue}"
            ] if bconst else [
                f"CMP ${allocate(b)}"
            ])

            if op == ">":
                label = f"skip_{next(newid)}"
                if jumpiftrue:
                    out.extend([
                        f"BEQ {label}",      # skip if A == B
                        f"BCC {label}",      # skip if A < B
                        f"JMP {jumptotrue}", # execute jump if A > B
                        f"{label}:",
                        f"JMP {jumptofalse}"
                    ])
                else:
                    label2 = f"skip_{next(newid)}"
                    out.extend([
                        f"BEQ {label}",      # skip if A == B
                        f"BCC {label}",      # skip if A < B
                        f"LDA #1",           # set addr to 1 if A > B
                        f"JMP {label2}",
                        f"{label}:",
                        f"LDA #0",           # set it to 0
                        f"{label2}:",
                        f"STA ${resultaddr}"
                    ])
            if op == "<":
                label = f"skip_{next(newid)}"
                if jumpiftrue:
                    out.extend([
                        f"BCS {label}",      # skip if A > B
                        f"JMP {jumptotrue}", # execute jump if A < B
                        f"{label}:",
                        f"JMP {jumptofalse}"
                    ])
                else:
                    label2 = f"skip_{next(newid)}"
                    out.extend([
                        f"BCS {label}",      # skip if A > B
                        f"LDA #1",           # set addr to 1 if A < B
                        f"JMP {label2}",
                        f"{label}:",
                        f"LDA #0",           # set it to 0
                        f"{label2}:",
                        f"STA ${resultaddr}"
                    ])
            if op == "==":
                label = f"skip_{next(newid)}"
                if jumpiftrue:
                    out.extend([
                        f"BNE {label}",      # skip if A != B
                        f"JMP {jumptotrue}", # execute jump if A == B
                        f"{label}:",
                        f"JMP {jumptofalse}"
                    ])
                else:
                    label2 = f"skip_{next(newid)}"
                    out.extend([
                        f"BNE {label}",      # skip if A != B
                        f"LDA #1",           # set addr to 1 if A == B
                        f"JMP {label2}",
                        f"{label}:",
                        f"LDA #0",           # set it to 0
                        f"{label2}:",
                        f"STA ${resultaddr}"
                    ])
            if op == "!=":
                label = f"skip_{next(newid)}"
                if jumpiftrue:
                    out.extend([
                        f"BEQ {label}",      # skip if A == B
                        f"JMP {jumptotrue}", # execute jump if A != B
                        f"{label}:",
                        f"JMP {jumptofalse}"
                    ])
                else:
                    label2 = f"skip_{next(newid)}"
                    out.extend([
                        f"BEQ {label}",      # skip if A == B
                        f"LDA #1",           # set addr to 1 if A != B
                        f"JMP {label2}",
                        f"{label}:",
                        f"LDA #0",           # set it to 0
                        f"{label2}:",
                        f"STA ${resultaddr}"
                    ])
            return out
        elif op == "+?":
            out.extend(["CLC"])
            label = f"skip_{next(newid)}"
            out.extend([
                f"ADC #{bvalue}"
            ] if bconst else [
                f"ADC ${allocate(b)}"
            ])
            if jumpiftrue:
                out.extend([
                    f"BCS {label}",      # skip if A > B
                    f"JMP {jumptotrue}", # execute jump if A < B
                    f"{label}:",
                    f"JMP {jumptofalse}"
                ])
            else:
                label2 = f"skip_{next(newid)}"
                out.extend([
                    f"BCS {label}",      # skip if A > B
                    f"LDA #1",           # set addr to 1 if A < B
                    f"JMP {label2}",
                    f"{label}:",
                    f"LDA #0",           # set it to 0
                    f"{label2}:",
                    f"STA ${resultaddr}"
                ])
        elif op == "-?":
            out.extend(["CLC"])
            label = f"skip_{next(newid)}"
            out.extend([
                f"SBC #{bvalue}"
            ] if bconst else [
                f"SBC ${allocate(b)}"
            ])
            if jumpiftrue:
                out.extend([
                    f"BCS {label}",      # skip if A > B
                    f"JMP {jumptotrue}", # execute jump if A < B
                    f"{label}:",
                    f"JMP {jumptofalse}"
                ])
            else:
                label2 = f"skip_{next(newid)}"
                out.extend([
                    f"BCS {label}",      # skip if A > B
                    f"LDA #1",           # set addr to 1 if A < B
                    f"JMP {label2}",
                    f"{label}:",
                    f"LDA #0",           # set it to 0
                    f"{label2}:",
                    f"STA ${resultaddr}"
                ])
        out[-1] += "\n"
        return out

    for i, line in enumerate(program.splitlines()):
        line = line.strip()
        if not line:
            continue
        parts = tokenize(line)
        if not parts:
            continue
        cmd = parts[0]
        args = parts[1:]
        appended = []
        
        match cmd:                
            case "var":
                match args[0]:
                    case "remove":  # var remove name
                        deallocate(args[1])
                        appended.append(f"; deallocate({args[1]})")

                    case _:  # var name = value
                        if args[1] != "=":
                            error("= not found in var declare", line, i)
                        appended.extend([
                            f"LDA #${parse_value(args[2])}",
                            f"STA ${allocate(args[0])}\n"
                        ] if not exists(args[2]) else [
                            f"LDA ${allocate(args[2])}",
                            f"STA ${allocate(args[0])}\n"
                        ])
        
            case "math": # math var = [var value] op [var value]
                         # [var] @[value: error]
                if args[1] != "=":
                    error("= not found in math stmt", line, i) 
                var = args[0]
                a = args[2]
                b = args[4]
                op = args[3]
                if not exists(var):
                    error("result var in math is not a allocated varible", line, i)
                out = math(a, op, b, line, i, allocate(var))
                appended.extend(out)

            case "forever":  # forever
                label = f"forever_{next(newid)}"
                lablestack.append((label, "forever"))
                appended.extend([
                    label + ":\n"
                ])

            case "jump":  # jump lable
                if args[0] in jumplabels:
                    appended.extend([
                        f"JMP {args[0]}\n"
                    ])
            
            case "if":  # if [var or value] op [var or value]
                        # if [var] @[value: error]
                labelend = f"ifend_{next(newid)}"
                labelstart = f"ifstart_{next(newid)}"
                lablestack.append((labelend, "if"))
                appended.extend([labelstart + ":"])
                if len(args) == 1:
                    if exists(args[0]): # if [var]
                        appended.extend([
                            f"LDA ${allocate(args[0])}",
                            f"CMP #0",
                            f"BEQ {labelend}\n" # if [var] == 0 then skip
                        ])
                    else:
                        error("if with static cond, optamize to aways exec or never", line, i)
                elif len(args) == 3:
                    a, op, b = args
                    out = math(a, op, b, line, i, None, True, labelstart, labelend)
                    appended.extend(out)

            case "while":  # while [var or value] op [var or value]
                           # while [var] @[value: error]
                labelend = f"whileend_{next(newid)}"
                labelstart = f"whilestart_{next(newid)}"
                lablestack.append((labelstart, "while", labelend)) # put the end label at the end and a jump to start
                appended.extend([labelstart + ":"])
                if len(args) == 1:
                    if exists(args[0]): # while [var]
                        appended.extend([
                            f"LDA ${allocate(args[0])}",
                            f"CMP #0",
                            f"BEQ {labelend}\n" # if [var] == 0 then skip
                        ])
                    else:
                        error("while with static cond, optamize to aways exec or never", line, i)
                elif len(args) == 3:
                    a, op, b = args
                    labelloop = f"while_{next(newid)}"
                    out = math(a, op, b, line, i, None, True, labelloop, labelend)
                    appended.extend(out)
                    appended.extend([labelloop + ":\n"])


            case "def": # def name:
                if args[0].endswith(":"):
                    label = args[0][:-1]
                    jumplabels.append(label)
                    appended.extend([
                        args[0] + "\n"
                    ])

            case "call": # call name arg1 arg2 arg3...
                for arg in args[1:]:
                    if exists(arg):
                        pass
                    else:
                        value
                        appended.extend([

                        ])

                if args[0] in jumplabels:
                    appended.extend([
                        f"JSR {args[0]}\n"
                    ])
            case "return": # return [intrrupt]
                if len(args) != 0: # RTI
                    appended.extend([
                        f"RTI\n"
                    ])
                else:
                    appended.extend([
                        f"RTS\n"
                    ])
            case "end": # end
                if lablestack:
                    info = lablestack.pop()
                    label = info[0]
                    type = info[1]
                    if type == "while":
                        appended.extend([
                            f"JMP {label}",
                            f"{info[2]}:\n" # loop end / exit
                        ])
                    elif type == "forever":
                        appended.extend([
                            f"JMP {label}\n",
                        ])
                    elif type == "if":
                        appended.extend([
                            f"{label}:\n"
                        ])
            
            case "buffer":
                match args[0]:
                    case "read": # buffer read name index var
                        name = args[1]
                        index = args[2]
                        var = args[3]
                        if not exists(name):
                            error("in buffer index read buffer name is not a allocated buffer", line, i)
                        if not exists(var):
                            error("in buffer index read dst var is not a allocated var", line, i)
                        if exists(index): # dynamic reading
                            block = allocated[name]                            

                            appended.extend([
                                f"LDY ${allocate(index)}",
                                f"LDA ${format(block[0], "X")},Y",
                                f"STA ${allocate(var)}\n"
                            ])
                        else:           # static reading
                            index = int(parse_value(index), 16)
                            block = allocated[name]
                            if index > (len(block) - 1):
                                error("in buffer index read, with static index, index is more than the size of the buffer", line, i)
                            if index < 0:
                                error("in buffer index read, with static index, index is less than 0", line, i)
                            
                            appended.extend([
                                f"LDA ${format(block[index], "X")}",
                                f"STA ${allocate(var)}\n"
                            ])
                            
                    case "write": # buffer write name var index
                        name = args[1]
                        index = args[3]
                        var = args[2]
                        if not exists(name):
                            error("in buffer index write buffer name is not a allocated buffer", line, i)
                        if not exists(var):
                            error("in buffer index read src var is not a allocated var", line, i)
                        if exists(index): # dynamic writeing
                            block = allocated[name]                            

                            appended.extend([
                                f"LDY ${allocate(index)}",
                                f"LDA ${allocate(var)}",
                                f"STA ${format(block[0], "X")},Y\n"
                            ])
                        else:           # static writeing
                            index = int(parse_value(index), 16)
                            block = allocated[name]
                            if index > (len(block) - 1):
                                error("in buffer index write, with static index, index is more than the size of the buffer", line, i)
                            if index < 0:
                                error("in buffer index write, with static index, index is less than 0", line, i)
                            
                            appended.extend([
                                f"LDA ${allocate(var)}",
                                f"STA ${format(block[index], "X")}\n"
                            ])
                    
                    case _: # buffer name size [= list]
                        name = args[0]
                        size = args[1]
                        if exists(size):
                            error("buffers have a compile time size for runtime sizes make your own allocator", line, i)
                        size = int(parse_value(size), 16)
                        if not (0 <= size <= 255):
                            error("buffers have a max size of 255", line, i)
                        allocate(name, size + 1)
                        block = allocated[name]
                        if len(args) > 2 and args[2] == "=":
                            # list literal bru
                            list_str :str= args[3]
                            if not (list_str[0] == "[" and list_str[-1] == "]"):
                                error("list literal does not have matched []", line, i)
                            list_str = list_str[1:-1]
                            list_itemstr = tokenize(list_str)
                            while "," in list_itemstr: list_itemstr.remove(",")

                            if (len(list_itemstr) - 1) > size:
                                error("literal is bigger than allocated buffer", line, i)

                            for i, item in enumerate(list_itemstr):
                                if exists(item.replace(",", "")):
                                    item = item.replace(",", "")
                                    appended.extend([
                                        f"LDA ${allocate(item)}",
                                        f"STA ${format(block[i], "X")}"
                                    ])
                                else:
                                    value = parse_value(item)
                                    if not (0 <= int(value, 16) <= 255):
                                        error(f"list literal @ index {i} is not 8bit", line, i)
                                    appended.extend([
                                        f"LDA #${value}",
                                        f"STA ${format(block[i], "X")}\n"
                                    ])
                            
            case "read": # read addres var
                addres = args[0]
                var = args[1]
                if not exists(var):
                    error("in read, var is not a allocated var", line, i)
                if exists(addres):
                    block = allocated[addres]
                    if len(block) < 2:
                        error("for reading from a dynamic addres, the allocated var must be a buffer or size > 2", line, i)
                    appended.extend([
                        f"LDY #0",
                        f"LDA (${allocate(addres)}),Y",
                        f"STA ${allocate(var)}\n"
                    ])
                else:
                    value = parse_value(addres)
                    appended.extend([
                        f"LDA ${value}",
                        f"STA ${allocate(var)}\n"
                    ])

            case "write": # write addres [var or value]
                addres = args[0]
                var = args[1]
                varconst = not exists(var)
                if exists(addres):
                    block = allocated[addres]
                    if len(block) < 2:
                        error("for reading from a dynamic addres, the allocated var must be a buffer or size > 2", line, i)
                    appended.extend([
                        f"LDA {"$" + allocate(var) if not varconst else "#$" + parse_value(var)}",
                        f"LDY #0",
                        f"STA (${allocate(addres)}),Y\n"
                    ])
                else:
                    value = parse_value(addres)
                    appended.extend([
                        f"LDA {"$" + allocate(var) if not varconst else "#$" + parse_value(var)}",
                        f"STA ${value}\n"
                    ])

            case _: # bruv
                error("invalid cmd", line, i)

        
        # Debug output (optional)
        print(f"\ncmd: {cmd}; args: {args}; line No: {i};")
        print("  -> Allocated:")
        for key, value in allocated.items():
            print(f"     -> {key}: {value if len(value) == 1 else '[' + format(value[0], "X") + '...' + format(value[1], "X") + ']'}")
        print("  -> Generated instructions:")
        for instr in appended:
            print(f"     -> {instr}")
        
        # Append the generated instructions to the output list.
        for instr in appended:
            compiled += instr + "\n"
    compiled += f'''
.segment "VECTOR"
    .word {nmihandlername}
    .word startup
    .word {irqhandlername}
'''
    return compiled

if __name__ == "__main__":
    sample = '''
// stack pointer
var sp = 0

// stack buffer
buffer stack 255

// temporary variable
var temp = 0

def push:
    buffer write stack temp sp
    math sp = sp + 1
    return

def pop:
    math sp = sp - 1
    buffer read stack sp temp
    return

def printchar:
    call pop
    write 0xFFF8 temp
    write 0xFFF9 1
    return

def main:
    call printchar "H"
    return

'''
    out = compile(sample)
    print("\n--- COMPILED OUTPUT ---\n")
    print(out)
    open(r"E:\vs code\files\6502cpp\compiler\sa65\helloworld.asm", "w").write(out)
