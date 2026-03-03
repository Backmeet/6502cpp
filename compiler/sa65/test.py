import re

tokenize_ = re.compile(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\[[^\]]*\]|[^\s"'\[\]]+''')
comment = re.compile(r'''//.*$''')

def tokenize(line: str):
    return tokenize_.findall(comment.sub("", line))

def compile(program: str):

    compiled = r'''
; simplified asm v0.8 runtime allocation + control flow + math + buffers
startup:
    SEI
    LDA #$F0
    STA $FFF0  ; low sp
    LDA #$FF
    STA $FFEF  ; high sp
    LDA #$00
    STA $FF00  ; low HP
    LDA #$F0
    STA $FF01  ; high HP
    JSR main

ALLOC:
    ; A = size
    LDA $FF00
    CLC
    ADC A
    STA $FE00
    LDA $FF01
    ADC #0
    STA $FE01
    LDA $FE00
    STA $FF00
    LDA $FE01
    STA $FF01
    RTS

NOPI:
    NOP
    RTI

NOP_:
    NOP
    RTS
'''

    newid = 0
    def newlabel(prefix):
        nonlocal newid
        l = f"{prefix}_{newid}"
        newid += 1
        return l

    stack_vars = {}
    lablestack = {}

    def parse_value(val: str):
        if val.endswith("b"):
            return format(int(val[:-1], 2), 'X')
        elif val.startswith("0x"):
            return val[2:]
        elif val.isdigit():
            return format(int(val), 'X')
        elif val.startswith('"') and val.endswith('"') and len(val) == 3:
            return format(ord(val[1]), 'X')
        elif val.startswith("'") and val.endswith("'") and len(val) == 3:
            return format(ord(val[1]), 'X')
        return None

    def math(a: str, op: str, b: str, resultaddr=None, jumpiftrue=False, jumptotrue="NOP", jumptofalse="NOP"):
        out = []
        aval = parse_value(a) or f"${stack_vars[a]}"
        bval = parse_value(b) or f"${stack_vars[b]}"        
        if op == "+":
            out.append(f"LDA {aval}")
            out.append("CLC")
            out.append(f"ADC {bval}")
            if resultaddr:
                out.append(f"STA ${resultaddr}")
        elif op == "-":
            out.append(f"LDA {aval}")
            out.append("SEC")
            out.append(f"SBC {bval}")
            if resultaddr:
                out.append(f"STA ${resultaddr}")
        elif op in {"==", "!=", ">", "<"}:
            out.append(f"LDA {aval}")
            out.append(f"CMP {bval}")
            label = newlabel("cmp_skip")
            if jumpiftrue:
                if op == "==": out.append(f"BNE {label}")
                if op == "!=": out.append(f"BEQ {label}")
                if op == ">": out.append(f"BCS {label}")
                if op == "<": out.append(f"BCV {label}")
                out.append(f"JMP {jumptotrue}")
                out.append(f"{label}:")
                out.append(f"JMP {jumptofalse}")
            elif resultaddr:
                label2 = newlabel("cmp_res")
                if op == "==": out.append(f"BNE {label}")
                if op == "!=": out.append(f"BEQ {label}")
                if op == ">": out.append(f"BCS {label}")
                if op == "<": out.append(f"BCV {label}")
                out.append(f"LDA #1")
                out.append(f"JMP {label2}")
                out.append(f"{label}:")
                out.append(f"LDA #0")
                out.append(f"{label2}:")
                out.append(f"STA ${resultaddr}")
        return out

    for i, line in enumerate(program.splitlines()):
        line = line.strip()
        if not line:
            continue
        parts = tokenize(line)
        if not parts:
            continue
        cmd, args = parts[0], parts[1:]
        appended = []

        match cmd:
            case "var":
                if args[0] == "16":
                    name = args[1]
                    val = args[3] if args[2] == "=" else "0"
                    appended.append(f"LDA #{parse_value(val) or 0}")
                    appended.append(f"STA ${name}_low")
                    appended.append(f"LDA #0")
                    appended.append(f"STA ${name}_high")
                    stack_vars[name] = f"{name}_low"
                else:
                    name = args[0]
                    val = parse_value(args[2])
                    appended.append(f"LDA #${val}")
                    appended.append(f"STA ${name}_ptr")
                    stack_vars[name] = f"{name}_ptr"

            case "buffer":
                name = args[0]
                if "[" in args[1]:
                    size_expr = args[1][1:-1]
                    appended.append(f"LDA #{parse_value(size_expr) or f'${stack_vars[size_expr]}'}")
                    appended.append(f"JSR ALLOC")
                    appended.append(f"STA ${name}_low")
                    appended.append(f"LDA $FE01")
                    appended.append(f"STA ${name}_high")
                    stack_vars[name] = f"{name}_low"
                    if len(args) > 2 and args[2] == "=":
                        vals = args[3].strip("[]")
                        for idx, v in enumerate(vals.split(",")):
                            v = v.strip()
                            appended.append(f"LDA #{parse_value(v)}")
                            appended.append(f"STA ${name}+{idx}")

            case "math":
                var = args[0]
                a, op, b = args[2], args[3], args[4]
                appended.extend(math(a, op, b, resultaddr=stack_vars[var]))

            case "call":
                appended.append(f"JSR {args[0]}")

            case "return":
                appended.append("RTS")

            case "def":
                label = args[0].rstrip(":")
                appended.append(f"{label}:")

            case "while":
                start = newlabel("while_start")
                end = newlabel("while_end")
                lablestack[start] = ("while", end)
                appended.append(f"{start}:")
                a, op, b = args if len(args) == 3 else (args[0], "!=", "0")
                appended.extend(math(a, op, b, jumpiftrue=True, jumptotrue=start, jumptofalse=end))

            case "if":
                end = newlabel("if_end")
                lablestack[end] = ("if",)
                a, op, b = args if len(args) == 3 else (args[0], "!=", "0")
                appended.extend(math(a, op, b, jumpiftrue=True, jumptotrue="NOP", jumptofalse=end))

            case "forever":
                start = newlabel("forever")
                lablestack[start] = ("forever",)
                appended.append(f"{start}:")

            case "end":
                if lablestack:
                    key = next(reversed(lablestack))
                    info = lablestack.pop(key)
                    if info[0] == "while":
                        start, end = key, info[1]
                        appended.extend([f"JMP {start}", f"{end}:"])
                    elif info[0] == "forever":
                        start = key
                        appended.append(f"JMP {start}")

        for instr in appended:
            compiled += instr + "\n"

    compiled += ".segment \"VECTOR\"\n.word NOPI\n.word startup\n.word NOPI\n"
    return compiled

if __name__ == "__main__":
    sample = '''
var sp = 0
var temp = 0

def main:
    var n = 0
    buffer list[10] = [1,2,3]
    while n != 5
        math n = n + 1
    end
    forever
        math n = n + 1
    end
'''
    out = compile(sample)
    print(out)
