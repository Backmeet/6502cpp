def compile(code: str) -> bytearray:
    MEM_SIZE = 0x10000
    memory = bytearray([0x00] * MEM_SIZE)

    lines = code.split("\n")
    labels = {}
    reserved = {}
    vectors = {"RESET": 0xFFFC, "NMI": 0xFFFA, "IRQ": 0xFFFE}
    free_mem_ptr = 0x0200  # first free memory for .res

    pc = 0x0000
    current_org = 0x0000

    # 6502 opcodes by mnemonic and addressing mode
    OPCODES = {
        "LDA": {"imm": 0xA9, "zp": 0xA5, "abs": 0xAD, "zpX": 0xB5, "absX": 0xBD, "absY": 0xB9, "indY": 0xB1},
        "STA": {"zp": 0x85, "abs": 0x8D, "zpX": 0x95, "absX": 0x9D, "absY": 0x99, "indY": 0x91},
        "ADC": {"imm": 0x69, "zp": 0x65, "abs": 0x6D, "zpX": 0x75, "absX": 0x7D, "absY": 0x79, "indY": 0x71},
        "SBC": {"imm": 0xE9, "zp": 0xE5, "abs": 0xED, "zpX": 0xF5, "absX": 0xFD, "absY": 0xF9, "indY": 0xF1},
        "INX": {"impl": 0xE8}, "DEX": {"impl": 0xCA},
        "INY": {"impl": 0xC8}, "DEY": {"impl": 0x88},
        "JMP": {"abs": 0x4C, "ind": 0x6C},
        "JSR": {"abs": 0x20},
        "RTS": {"impl": 0x60}, "NOP": {"impl": 0xEA},
        "ASL": {"acc": 0x0A, "zp": 0x06, "abs": 0x0E, "zpX": 0x16, "absX": 0x1E},
        "LSR": {"acc": 0x4A, "zp": 0x46, "abs": 0x4E, "zpX": 0x56, "absX": 0x5E},
        "ROL": {"acc": 0x2A, "zp": 0x26, "abs": 0x2E, "zpX": 0x36, "absX": 0x3E},
        "ROR": {"acc": 0x6A, "zp": 0x66, "abs": 0x6E, "zpX": 0x76, "absX": 0x7E},
        "BEQ": {"rel": 0xF0}, "BNE": {"rel": 0xD0}, "BCS": {"rel": 0xB0}, "BCC": {"rel": 0x90},
        "CMP": {"imm": 0xC9, "zp": 0xC5, "abs": 0xCD, "zpX": 0xD5, "absX": 0xDD, "absY": 0xD9, "indY": 0xD1},
        "CPX": {"imm": 0xE0, "zp": 0xE4, "abs": 0xEC},
        "CPY": {"imm": 0xC0, "zp": 0xC4, "abs": 0xCC},
        "AND": {"imm": 0x29, "zp": 0x25, "abs": 0x2D, "zpX": 0x35, "absX": 0x3D, "absY": 0x39, "indY": 0x31},
        "ORA": {"imm": 0x09, "zp": 0x05, "abs": 0x0D, "zpX": 0x15, "absX": 0x1D, "absY": 0x19, "indY": 0x11},
        "EOR": {"imm": 0x49, "zp": 0x45, "abs": 0x4D, "zpX": 0x55, "absX": 0x5D, "absY": 0x59, "indY": 0x51},
        "CLC": {"impl": 0x18}, "SEC": {"impl": 0x38}
    }

    # Parse operand recursively
    def parse_operand(operand: str) -> int | None:
        operand = operand.strip().upper()
        if operand == "A":  # accumulator mode
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
        line = line.strip()
        line = line.split(";", 1)[0].strip()
        if not line or line.startswith(";"): 
            continue
        if line.startswith(".org"):
            val_str = line.split()[1].strip()
            if val_str.startswith("$"):
                current_org = int(val_str[1:], 16)
            else:
                current_org = int(val_str)
            pc = current_org
        elif line.startswith(".res"):
            _, name, val = line.split()
            if val.startswith("$"):
                val = int(val[1:], 16)
            else:
                val = int(val)
            reserved[name] = free_mem_ptr
            memory[free_mem_ptr] = val & 0xFF
            free_mem_ptr += 1
        elif line.startswith(".onStart"):
            labels["__VECTOR_RESET__"] = line.split()[1]
        elif line.startswith(".onNMI"):
            labels["__VECTOR_NMI__"] = line.split()[1]
        elif line.startswith(".onIRQ"):
            labels["__VECTOR_IRQ__"] = line.split()[1]
        elif ":" in line:
            lbl = line.split(":")[0].strip()
            labels[lbl] = pc
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
                        size = 2 if opval <= 0xFF else 3
                    except Exception:
                        size = 3
            pc += size

    # Second pass: encode instructions
    pc = current_org
    for line in lines:
        line = line.strip()
        line = line.split(";", 1)[0].strip()
        if not line or line.startswith(";") or line.startswith(".") or ":" in line: 
            continue
        parts = line.split(maxsplit=1)
        instr = parts[0].upper()
        operand = parts[1] if len(parts) > 1 else None
        if instr not in OPCODES:
            raise ValueError(f"Unknown instruction: {instr}")
        mode = "impl"
        opval = None
        if operand:
            opval = parse_operand(operand)
            if opval is None:
                mode = "acc"
            elif operand.startswith("#"):
                mode = "imm"
            elif operand.startswith("(") and operand.endswith(")"):
                mode = "ind"
            elif opval <= 0xFF:
                mode = "zp"
            else:
                mode = "abs"
        if instr in ("BEQ", "BNE", "BCS", "BCC"):
            mode = "rel"
            offset = opval - (pc + 2)
            if not -128 <= offset <= 127:
                raise ValueError("Branch out of range")
            opval = offset & 0xFF
        opcode = OPCODES[instr].get(mode)
        if opcode is None:
            if mode == "abs" and "abs" in OPCODES[instr]:
                opcode = OPCODES[instr]["abs"]
            else:
                raise ValueError(f"Addressing mode {mode} not supported for {instr}")
        memory[pc] = opcode
        pc += 1
        if mode in ("imm", "zp", "rel"):
            memory[pc] = opval & 0xFF
            pc += 1
        elif mode in ("abs", "ind"):
            memory[pc] = opval & 0xFF
            memory[pc + 1] = (opval >> 8) & 0xFF
            pc += 2

    # Write vectors
    for vec_name, vec_addr in vectors.items():
        lbl = f"__VECTOR_{vec_name}__"
        if lbl in labels:
            addr = labels[labels[lbl]]
            memory[vec_addr] = addr & 0x00FF
            memory[vec_addr + 1] = (addr & 0xFF00) >> 8

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