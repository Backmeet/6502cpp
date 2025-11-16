def compile(code: str) -> bytearray:
    MEM_SIZE = 0x10000
    memory = bytearray([0x00] * MEM_SIZE)

    lines = code.split("\n")
    labels = {}
    reserved = {}
    vectors = {"RESET": 0xFFFC, "NMI": 0xFFFA, "IRQ": 0xFFFE}
    free_mem_ptr = 0x0200

    pc = 0x0000
    current_org = 0x0000

    IMPL_TO_ACC = {"ASL", "LSR", "ROL", "ROR"}
    ABS_CONVERT_REL = {"BPL", "BMI", "BVC", "BVS", "BCC", "BCS", "BNE", "BEQ"} # abs values for these instructions will become a relative offset automaticaly
    OPCODES = {
        "LDA": {"imm": 0xA9, "zp": 0xA5, "abs": 0xAD, "zpX": 0xB5, "absX": 0xBD, "absY": 0xB9, "indX": 0xA1, "indY": 0xB1},
        "LDX": {"imm": 0xA2, "zp": 0xA6, "abs": 0xAE, "zpY": 0xB6, "absY": 0xBE},
        "LDY": {"imm": 0xA0, "zp": 0xA4, "abs": 0xAC, "zpX": 0xB4, "absX": 0xBC},
        "STA": {"zp": 0x85, "abs": 0x8D, "zpX": 0x95, "absX": 0x9D, "absY": 0x99, "indX": 0x81, "indY": 0x91},
        "STX": {"zp": 0x86, "abs": 0x8E, "zpY": 0x96},
        "STY": {"zp": 0x84, "abs": 0x8C, "zpX": 0x94},
        "ADC": {"imm": 0x69, "zp": 0x65, "abs": 0x6D, "zpX": 0x75, "absX": 0x7D, "absY": 0x79, "indX": 0x61, "indY": 0x71},
        "SBC": {"imm": 0xE9, "zp": 0xE5, "abs": 0xED, "zpX": 0xF5, "absX": 0xFD, "absY": 0xF9, "indX": 0xE1, "indY": 0xF1},
        "CMP": {"imm": 0xC9, "zp": 0xC5, "abs": 0xCD, "zpX": 0xD5, "absX": 0xDD, "absY": 0xD9, "indX": 0xC1, "indY": 0xD1},
        "CPX": {"imm": 0xE0, "zp": 0xE4, "abs": 0xEC},
        "CPY": {"imm": 0xC0, "zp": 0xC4, "abs": 0xCC},
        "AND": {"imm": 0x29, "zp": 0x25, "abs": 0x2D, "zpX": 0x35, "absX": 0x3D, "absY": 0x39, "indX": 0x21, "indY": 0x31},
        "ORA": {"imm": 0x09, "zp": 0x05, "abs": 0x0D, "zpX": 0x15, "absX": 0x1D, "absY": 0x19, "indX": 0x01, "indY": 0x11},
        "EOR": {"imm": 0x49, "zp": 0x45, "abs": 0x4D, "zpX": 0x55, "absX": 0x5D, "absY": 0x59, "indX": 0x41, "indY": 0x51},
        "INX": {"impl": 0xE8}, "DEX": {"impl": 0xCA},
        "INY": {"impl": 0xC8}, "DEY": {"impl": 0x88},
        "INC": {"zp": 0xE6, "zpX": 0xF6, "abs": 0xEE, "absX": 0xFE},
        "DEC": {"zp": 0xC6, "zpX": 0xD6, "abs": 0xCE, "absX": 0xDE},
        "JMP": {"abs": 0x4C, "ind": 0x6C},
        "JSR": {"abs": 0x20},
        "RTS": {"impl": 0x60}, "NOP": {"impl": 0xEA},
        "ASL": {"acc": 0x0A, "zp": 0x06, "abs": 0x0E, "zpX": 0x16, "absX": 0x1E},
        "LSR": {"acc": 0x4A, "zp": 0x46, "abs": 0x4E, "zpX": 0x56, "absX": 0x5E},
        "ROL": {"acc": 0x2A, "zp": 0x26, "abs": 0x2E, "zpX": 0x36, "absX": 0x3E},
        "ROR": {"acc": 0x6A, "zp": 0x66, "abs": 0x6E, "zpX": 0x76, "absX": 0x7E},
        "BIT": {"zp": 0x24, "abs": 0x2C},
        "TAX": {"impl": 0xAA}, "TXA": {"impl": 0x8A},
        "TAY": {"impl": 0xA8}, "TYA": {"impl": 0x98},
        "TSX": {"impl": 0xBA}, "TXS": {"impl": 0x9A},
        "PHA": {"impl": 0x48}, "PHP": {"impl": 0x08}, "PLA": {"impl": 0x68}, "PLP": {"impl": 0x28},
        "CLC": {"impl": 0x18}, "SEC": {"impl": 0x38},
        "CLD": {"impl": 0xD8}, "SED": {"impl": 0xF8},
        "CLI": {"impl": 0x58}, "SEI": {"impl": 0x78},
        "CLV": {"impl": 0xB8},
        "BRK": {"impl": 0x00}, "RTI": {"impl": 0x40},
        "BPL": {"rel": 0x10}, "BMI": {"rel": 0x30},
        "BVC": {"rel": 0x50}, "BVS": {"rel": 0x70},
        "BCC": {"rel": 0x90}, "BCS": {"rel": 0xB0},
        "BNE": {"rel": 0xD0}, "BEQ": {"rel": 0xF0},
    }


    def parse_operand(operand: str) -> int | None:
        operand = operand.strip().upper()
        if operand == "A":
            return None
        if operand.startswith("#"):
            if operand[1] == "$":
                return int(operand[2:], 16)
            return int(operand[1:])
        elif operand.startswith("$"):
            return int(operand[1:], 16)
        elif operand.isdigit():
            return int(operand)
        elif operand in labels:
            return labels[operand]
        elif operand in reserved:
            return reserved[operand]
        for op in ("+", "-", "*", "/"):
            if op in operand:
                left, right = operand.split(op, 1)
                lval = parse_operand(left)
                rval = parse_operand(right)
                if op == "+": return lval + rval
                if op == "-": return lval - rval
                if op == "*": return lval * rval
                if op == "/": return lval // rval
        raise ValueError(f"Unknown operand: {operand}")

    # First pass: labels, reserves, org, vectors, pc sizing
    for line in lines:
        line = line.strip().split(";", 1)[0]
        if not line or line.startswith(";"):
            continue
        if line.startswith(".org"):
            val_str = line.split()[1]
            current_org = int(val_str[1:], 16) if val_str.startswith("$") else int(val_str)
            pc = current_org
        elif line.startswith(".reserve"):
            _, name, val = line.split()
            val = int(val[1:], 16) if val.startswith("$") else int(val)
            reserved[name] = free_mem_ptr
            memory[free_mem_ptr] = val & 0xFF
            free_mem_ptr += 1
        elif line.startswith(".set"): # .set name = value
            _, name, __, val = line.split()
            if __ != "=":
                raise SyntaxError("no = found in .set directive")
            val = int(val[1:], 16) if val.startswith("$") else int(val)
            labels[name] = val
        elif line.startswith(".onStart"):
            labels["__VECTOR_RESET__"] = line.split()[1]
        elif line.startswith(".onNMI"):
            labels["__VECTOR_NMI__"] = line.split()[1]
        elif line.startswith(".onIRQ"):
            labels["__VECTOR_IRQ__"] = line.split()[1]
        elif ":" in line:
            labels[line.split(":")[0]] = pc
        else:
            parts = line.split(maxsplit=1)
            instr = parts[0].upper()
            operand = parts[1] if len(parts) > 1 else None
            if instr not in OPCODES:
                raise ValueError(f"Unknown instruction: {instr}")
            size = 1
            if operand:
                if operand.startswith("#"):
                    size = 2
                elif operand.startswith("(") and operand.endswith(")"):
                    size = 3
                else:
                    try:
                        opval = parse_operand(operand)
                        # enforce abs for JMP/JSR regardless of value
                        if instr in ("JMP", "JSR"):
                            size = 3
                        else:
                            size = 2 if opval <= 0xFF else 3
                    except Exception:
                        size = 3
            pc += size

    # Second pass: encode instructions
    pc = current_org
    for line in lines:
        line = line.strip().split(";", 1)[0]
        if not line or line.startswith(";") or line.startswith(".") or ":" in line:
            continue
        parts = line.split(maxsplit=1)
        instr = parts[0].upper()
        operand = parts[1] if len(parts) > 1 else None
        mode = "impl"
        opval = None
        if operand:
            op_str = operand.strip().upper()

            if op_str.startswith("#"):
                mode = "imm"
                opval = parse_operand(op_str)
            elif op_str.startswith("(") and op_str.endswith(")"):
                inner = op_str[1:-1].strip()
                if inner.endswith(",Y"):
                    inner = inner[:-2].strip()
                    opval = parse_operand(inner)
                    mode = "indY"
                elif inner.endswith(",X"):
                    inner = inner[:-2].strip()
                    opval = parse_operand(inner)
                    mode = "indX"
                else:
                    opval = parse_operand(inner)
                    mode = "ind"
            elif op_str.endswith(",X"):
                base = op_str[:-2].strip()
                opval = parse_operand(base)
                mode = "zpX" if opval <= 0xFF else "absX"
            elif op_str.endswith(",Y"):
                base = op_str[:-2].strip()
                opval = parse_operand(base)
                mode = "zpY" if opval <= 0xFF else "absY"
            elif instr in ("JMP", "JSR"):
                mode = "abs"
                opval = parse_operand(op_str)
            else:
                opval = parse_operand(op_str)
                mode = "zp" if opval <= 0xFF else "abs"

        if instr in ABS_CONVERT_REL:
            mode = "rel"
            offset = opval - (pc + 2)
            if not -128 <= offset <= 127:
                raise ValueError("Branch out of range, line: ", line, " found offset of: ", offset)
            opval = offset & 0xFF

        # Map indX/indY opcodes for instructions that support them
        if mode == "indX":
            if instr not in OPCODES or "indX" not in OPCODES[instr]:
                raise ValueError(f"Addressing mode (indirect,X) not supported for {instr}")
        elif mode == "indY":
            if instr not in OPCODES or "indY" not in OPCODES[instr]:
                raise ValueError(f"Addressing mode (indirect),Y not supported for {instr}")

        if mode == "impl" and instr in IMPL_TO_ACC:
            mode = "acc"

        opcode = OPCODES[instr].get(mode)
        if opcode is None:
            if mode in ("abs", "absX", "absY") and "abs" in OPCODES[instr]:
                opcode = OPCODES[instr]["abs"]
            else:
                raise ValueError(f"Addressing mode {mode} not supported for {instr}")

        memory[pc] = opcode
        pc += 1

        if mode in ("imm", "zp", "rel", "zpX", "zpY", "indY", "indX"):
            memory[pc] = opval & 0xFF
            pc += 1
        elif mode in ("abs", "absX", "absY", "ind"):
            memory[pc] = opval & 0xFF
            memory[pc + 1] = (opval >> 8) & 0xFF
            pc += 2

    # Write vectors
    for vec_name, vec_addr in vectors.items():
        lbl = f"__VECTOR_{vec_name}__"
        if lbl in labels:
            addr = labels[labels[lbl]]
            memory[vec_addr] = addr & 0x00FF
            memory[vec_addr + 1] = (addr >> 8) & 0xFF

    return memory


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python co6502.py <input.asm> <output.bin>")
        sys.exit(1)    

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    with open(input_file, "r") as f:
        code = f.read()

    mem = compile(code)

    with open(output_file, "wb") as f:
        f.write(bytes(mem))