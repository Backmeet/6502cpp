#include <vector>
#include <iostream>
#include <unordered_map>
#include <memory>
#include <windows.h>
#include <iostream>
#include <string>
#include <sstream>
#include <map>
#include <algorithm>
#include <fstream>
#include <cstdint>
#include <chrono>
#include <conio.h>
#include <thread>
#include <functional>

std::vector<uint8_t> readFileRaw(const std::string& path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) {
        throw std::runtime_error("Failed to open file: " + path);
    }

    file.seekg(0, std::ios::end);
    std::streamsize size = file.tellg();
    file.seekg(0, std::ios::beg);

    std::vector<uint8_t> buffer(size);
    if (!file.read(reinterpret_cast<char*>(buffer.data()), size)) {
        throw std::runtime_error("Failed to read file: " + path);
    }

    return buffer;
}

void keyListener(std::function<void(char)> callback) {
    while (true) {
        if (_kbhit()) {
            char key = _getch();   // read ASCII of pressed key
            callback(key);         // call the callback immediately
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}

struct CPU {

    // Flags

    bool INDPageBug = false;
    
    bool RTCompute = true;
    float timePerCycle_ms = 0.001;

    bool PrintAllowed = true;
    uint16_t PrintCharAddres = 0x0000;
    uint16_t PrintInvokeAddres = 0x0001;

    bool InputAllowed = true;
    uint16_t InputCharAddres = 0x0002;

    bool JMPUseIndirect = false;

    struct Instruction {
        const char* name;
        uint8_t (CPU::*operate)();
        uint8_t (CPU::*addrmode)();
        uint8_t cycles;
    };

    uint8_t A, X, Y;
    uint8_t SP = 255;
    uint16_t PC = 0;
    uint8_t Status;
    enum FLAGS { C=0, Z=1, I=2, D=3, B=4, U=5, V=6, N=7 };
    uint8_t memory[0x10000];
    uint16_t fetched;
    uint16_t addres;
    Instruction instrutionMap[0x100];

    bool getFlag(FLAGS f) { return (Status >> f) & 1; }
    void setFlag(FLAGS f, bool v) { if(v) Status |= (1 << f); else Status &= ~(1 << f); }
    void push(uint8_t value) { memory[0x0100 + SP] = value; SP--; }
    uint8_t pop() { SP++; return memory[0x0100 + SP]; }

    void interruptNMI() {
        // Push PC (high, then low)
        push((PC >> 8) & 0xFF);
        push(PC & 0xFF);

        // Save a copy of Status with correct B and U before pushing
        uint8_t saved = Status;

        // Clear Break (B) for IRQ/NMI pushes
        setFlag(B, 0);
        // Ensure Unused (U) is always set
        setFlag(U, 1);

        push(Status);

        // Restore original Status register after push
        Status = saved;

        // Set Interrupt Disable flag so no further IRQs
        setFlag(I, 1);

        // Load new PC from NMI vector
        PC = memory[0xFFFA] | (memory[0xFFFB] << 8);
    }

    void inputIntrupt(char c) {
        memory[InputCharAddres] = c;
        interruptNMI();
    }

    void runFromReset() {
        PC = memory[0xFFFC] | (memory[0xFFFD]<<8);
        
        if (InputAllowed) {
            std::thread listner(keyListener, [this](char c) { inputIntrupt(c); });
            listner.detach();
        }
        
        while(1) {
            uint8_t opcode = memory[PC++];
            Instruction ins = instrutionMap[opcode];
            (this->*ins.addrmode)();
            (this->*ins.operate)();
            //printf("%s; fetched: %d, addres: %d\n", ins.name, fetched, addres);
            Sleep(timePerCycle_ms * ins.cycles);
            if (PrintAllowed and memory[PrintInvokeAddres]) {
                memory[PrintInvokeAddres] = 0;
                std::cout << (char)memory[PrintCharAddres];
            }
        }

    }

    uint8_t IMP() { fetched = 0; return 0; }
    uint8_t ACC() { fetched = A; return 0; }
    uint8_t IMM() { addres = PC++; fetched = memory[addres]; return 0; }
    uint8_t ZP0() { addres = memory[PC++]; fetched = memory[addres]; return 0; }
    uint8_t ZPX() { addres = (memory[PC++] + X) & 0xFF; fetched = memory[addres]; return 0; }
    uint8_t ZPY() { addres = (memory[PC++] + Y) & 0xFF; fetched = memory[addres]; return 0; }
    uint8_t ABS() { 
        uint8_t _1 = memory[PC++];
        uint8_t _2 = memory[PC++];
        uint16_t _3 = _2 << 8;
        uint16_t _4 = _1 | _3;
        addres = _4;
        fetched = memory[addres]; 
        return 0; 
    }
    uint8_t ABX() { addres = (memory[PC++] | (memory[PC++] << 8)) + X; fetched = memory[addres]; return 0; }
    uint8_t ABY() { addres = (memory[PC++] | (memory[PC++] << 8)) + Y; fetched = memory[addres]; return 0; }
    
    // special as it needs to replicate that bug
    uint8_t IND() {
        JMPUseIndirect = true;
        uint16_t ptr_lo = memory[PC++];
        uint16_t ptr_hi = memory[PC++];
        uint16_t ptr = (ptr_hi << 8) | ptr_lo;

        uint16_t addr_lo = memory[ptr];
        uint16_t addr_hi;

        if (INDPageBug && (ptr & 0xFF) == 0xFF) {
            // emulate 6502 page boundary bug
            addr_hi = memory[ptr & 0xFF00];
        } else {
            // normal behavior
            addr_hi = memory[ptr + 1];
        }

        addres = (addr_hi << 8) | addr_lo;
        return 0;
    }


    uint8_t IZX() { uint8_t t = memory[PC++]; addres = memory[(uint8_t)(t+X)] | (memory[(uint8_t)(t+X+1)] << 8); fetched = memory[addres]; return 0; }
    uint8_t IZY() { uint8_t t = memory[PC++]; addres = (memory[t] | (memory[(t+1)&0xFF] << 8)) + Y; fetched = memory[addres]; return 0; }
    uint8_t REL() { addres = PC++; return (int8_t)memory[addres]; }

    uint8_t BRK() { PC++; push((PC>>8)&0xFF); push(PC&0xFF); setFlag(B,1); setFlag(I,1); push(Status); PC = memory[0xFFFE] | (memory[0xFFFF]<<8); return 0; }
    uint8_t ORA() { A |= fetched; setFlag(Z, A==0); setFlag(N, A&0x80); return 0; }
    uint8_t AND() { A &= fetched; setFlag(Z, A==0); setFlag(N, A&0x80); return 0; }
    uint8_t EOR() { A ^= fetched; setFlag(Z, A==0); setFlag(N, A&0x80); return 0; }
    uint8_t ADC() { uint16_t temp = A + fetched + getFlag(C); setFlag(C,temp>0xFF); setFlag(Z,(temp&0xFF)==0); setFlag(V, (~(A^fetched) & (A^temp)) & 0x80); setFlag(N,temp&0x80); A=temp&0xFF; return 0; }
    uint8_t SBC() { uint16_t temp = A - fetched - (1-getFlag(C)); setFlag(C,temp<0x100); setFlag(Z,(temp&0xFF)==0); setFlag(V, ((A^temp)&0x80) && ((A^fetched)&0x80)); setFlag(N,temp&0x80); A=temp&0xFF; return 0; }
    uint8_t CMP() { uint8_t temp = A - fetched; setFlag(C,A>=fetched); setFlag(Z,temp==0); setFlag(N,temp&0x80); return 0; }
    uint8_t CPX() { uint8_t temp = X - fetched; setFlag(C,X>=fetched); setFlag(Z,temp==0); setFlag(N,temp&0x80); return 0; }
    uint8_t CPY() { uint8_t temp = Y - fetched; setFlag(C,Y>=fetched); setFlag(Z,temp==0); setFlag(N,temp&0x80); return 0; }
    uint8_t LDA() { A = fetched; setFlag(Z, A==0); setFlag(N, A&0x80); return 0; }
    uint8_t LDX() { X = fetched; setFlag(Z, X==0); setFlag(N, X&0x80); return 0; }
    uint8_t LDY() { Y = fetched; setFlag(Z, Y==0); setFlag(N, Y&0x80); return 0; }
    uint8_t STA() { memory[addres] = A; return 0; } // simplified
    uint8_t STX() { memory[addres] = X; return 0; }
    uint8_t STY() { memory[addres] = Y; return 0; }
    uint8_t INX() { X++; setFlag(Z,X==0); setFlag(N,X&0x80); return 0; }
    uint8_t INY() { Y++; setFlag(Z,Y==0); setFlag(N,Y&0x80); return 0; }
    uint8_t DEX() { X--; setFlag(Z,X==0); setFlag(N,X&0x80); return 0; }
    uint8_t DEY() { Y--; setFlag(Z,Y==0); setFlag(N,Y&0x80); return 0; }
    uint8_t ASL() { uint16_t temp = fetched<<1; setFlag(C,temp&0x100); setFlag(Z,(temp&0xFF)==0); setFlag(N,temp&0x80); fetched = temp&0xFF; return 0; }
    uint8_t LSR() { setFlag(C,fetched&0x01); fetched >>=1; setFlag(Z,fetched==0); setFlag(N,0); return 0; }
    uint8_t ROL() { uint16_t temp = (fetched<<1)|getFlag(C); setFlag(C,temp&0x100); setFlag(Z,(temp&0xFF)==0); setFlag(N,temp&0x80); fetched = temp&0xFF; return 0; }
    uint8_t ROR() { uint16_t temp = (fetched>>1)|(getFlag(C)<<7); setFlag(C,fetched&0x01); setFlag(Z,(temp&0xFF)==0); setFlag(N,temp&0x80); fetched = temp&0xFF; return 0; }
    uint8_t NOP() { return 0; }
    uint8_t XXX() { return 0; }
    uint8_t TAX() { X = A; setFlag(Z,X==0); setFlag(N,X&0x80); return 0; }
    uint8_t TAY() { Y = A; setFlag(Z,Y==0); setFlag(N,Y&0x80); return 0; }
    uint8_t TXA() { A = X; setFlag(Z,A==0); setFlag(N,A&0x80); return 0; }
    uint8_t TYA() { A = Y; setFlag(Z,A==0); setFlag(N,A&0x80); return 0; }
    uint8_t TSX() { X = SP; setFlag(Z,X==0); setFlag(N,X&0x80); return 0; }
    uint8_t TXS() { SP = X; return 0; }
    uint8_t PHA() { push(A); return 0; }
    uint8_t PHP() { push(Status | (1<<B) | (1<<U)); return 0; }
    uint8_t PLA() { A = pop(); setFlag(Z,A==0); setFlag(N,A&0x80); return 0; }
    uint8_t PLP() { Status = pop(); setFlag(U,1); return 0; }
    uint8_t JMP() { 
        if (JMPUseIndirect) {
            PC = memory[addres];
            JMPUseIndirect = false;
        } else {
            PC = addres; 
        } 
        return 0; 
    }
    uint8_t JSR() { 
        PC--; 
        push((PC>>8)&0xFF); 
        push(PC&0xFF); 
        PC = addres; 
        return 0; 
    }
    uint8_t RTS() { uint16_t lo = pop(); uint16_t hi = pop(); PC = (hi<<8)|lo; PC++; return 0; }
    uint8_t BCC() { int8_t offset = fetched; if(!getFlag(C)) { PC += offset; return 1; } return 0; }
    uint8_t BCS() { int8_t offset = fetched; if(getFlag(C)) { PC += offset; return 1; } return 0; }
    uint8_t BEQ() { int8_t offset = fetched; if(getFlag(Z)) { PC += offset; return 1; } return 0; }
    uint8_t BNE() { int8_t offset = fetched; if(!getFlag(Z)) { PC += offset; return 1; } return 0; }
    uint8_t BPL() { int8_t offset = fetched; if(!getFlag(N)) { PC += offset; return 1; } return 0; }
    uint8_t BMI() { int8_t offset = fetched; if(getFlag(N)) { PC += offset; return 1; } return 0; }
    uint8_t BVC() { int8_t offset = fetched; if(!getFlag(V)) { PC += offset; return 1; } return 0; }
    uint8_t BVS() { int8_t offset = fetched; if(getFlag(V)) { PC += offset; return 1; } return 0; }
    uint8_t CLC() { setFlag(C,0); return 0; }
    uint8_t SEC() { setFlag(C,1); return 0; }
    uint8_t CLI() { setFlag(I,0); return 0; }
    uint8_t SEI() { setFlag(I,1); return 0; }
    uint8_t CLV() { setFlag(V,0); return 0; }
    uint8_t CLD() { setFlag(D,0); return 0; }
    uint8_t SED() { setFlag(D,1); return 0; }
    uint8_t INC() { fetched++; setFlag(Z,fetched==0); setFlag(N,fetched&0x80); return 0; }
    uint8_t DEC() { fetched--; setFlag(Z,fetched==0); setFlag(N,fetched&0x80); return 0; }
    uint8_t BIT() { uint8_t temp = A & fetched; setFlag(Z, temp == 0); setFlag(N, fetched & 0x80); setFlag(V, fetched & 0x40); return 0; }
    uint8_t RTI() { Status = pop(); /* pull status from stack */ setFlag(U, 1); /* unused flag is always 1 */ uint16_t lo = pop(); /* pull low byte of PC */ uint16_t hi = pop(); /* pull high byte of PC */ PC = (hi << 8) | lo; return 0; }

    CPU() {
        instrutionMap[0x00] = { "BRK", &CPU::BRK, &CPU::IMP, 7 };
        instrutionMap[0x01] = { "ORA", &CPU::ORA, &CPU::IZX, 6 };
        instrutionMap[0x02] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x03] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0x04] = { "NOP", &CPU::NOP, &CPU::ZP0, 3 };
        instrutionMap[0x05] = { "ORA", &CPU::ORA, &CPU::ZP0, 3 };
        instrutionMap[0x06] = { "ASL", &CPU::ASL, &CPU::ZP0, 5 };
        instrutionMap[0x07] = { "XXX", &CPU::XXX, &CPU::IMP, 5 };
        instrutionMap[0x08] = { "PHP", &CPU::PHP, &CPU::IMP, 3 };
        instrutionMap[0x09] = { "ORA", &CPU::ORA, &CPU::IMM, 2 };
        instrutionMap[0x0A] = { "ASL", &CPU::ASL, &CPU::ACC, 2 };
        instrutionMap[0x0B] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x0C] = { "NOP", &CPU::NOP, &CPU::ABS, 4 };
        instrutionMap[0x0D] = { "ORA", &CPU::ORA, &CPU::ABS, 4 };
        instrutionMap[0x0E] = { "ASL", &CPU::ASL, &CPU::ABS, 6 };
        instrutionMap[0x0F] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };

        instrutionMap[0x10] = { "BPL", &CPU::BPL, &CPU::REL, 2 };
        instrutionMap[0x11] = { "ORA", &CPU::ORA, &CPU::IZY, 5 };
        instrutionMap[0x12] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x13] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0x14] = { "NOP", &CPU::NOP, &CPU::ZPX, 4 };
        instrutionMap[0x15] = { "ORA", &CPU::ORA, &CPU::ZPX, 4 };
        instrutionMap[0x16] = { "ASL", &CPU::ASL, &CPU::ZPX, 6 };
        instrutionMap[0x17] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };
        instrutionMap[0x18] = { "CLC", &CPU::CLC, &CPU::IMP, 2 };
        instrutionMap[0x19] = { "ORA", &CPU::ORA, &CPU::ABY, 4 };
        instrutionMap[0x1A] = { "NOP", &CPU::NOP, &CPU::IMP, 2 };
        instrutionMap[0x1B] = { "XXX", &CPU::XXX, &CPU::IMP, 7 };
        instrutionMap[0x1C] = { "NOP", &CPU::NOP, &CPU::ABX, 4 };
        instrutionMap[0x1D] = { "ORA", &CPU::ORA, &CPU::ABX, 4 };
        instrutionMap[0x1E] = { "ASL", &CPU::ASL, &CPU::ABX, 7 };
        instrutionMap[0x1F] = { "XXX", &CPU::XXX, &CPU::IMP, 7 };

        instrutionMap[0x20] = { "JSR", &CPU::JSR, &CPU::ABS, 6 };
        instrutionMap[0x21] = { "AND", &CPU::AND, &CPU::IZX, 6 };
        instrutionMap[0x22] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x23] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0x24] = { "BIT", &CPU::BIT, &CPU::ZP0, 3 };
        instrutionMap[0x25] = { "AND", &CPU::AND, &CPU::ZP0, 3 };
        instrutionMap[0x26] = { "ROL", &CPU::ROL, &CPU::ZP0, 5 };
        instrutionMap[0x27] = { "XXX", &CPU::XXX, &CPU::IMP, 5 };
        instrutionMap[0x28] = { "PLP", &CPU::PLP, &CPU::IMP, 4 };
        instrutionMap[0x29] = { "AND", &CPU::AND, &CPU::IMM, 2 };
        instrutionMap[0x2A] = { "ROL", &CPU::ROL, &CPU::ACC, 2 };
        instrutionMap[0x2B] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x2C] = { "BIT", &CPU::BIT, &CPU::ABS, 4 };
        instrutionMap[0x2D] = { "AND", &CPU::AND, &CPU::ABS, 4 };
        instrutionMap[0x2E] = { "ROL", &CPU::ROL, &CPU::ABS, 6 };
        instrutionMap[0x2F] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };

        instrutionMap[0x30] = { "BMI", &CPU::BMI, &CPU::REL, 2 };
        instrutionMap[0x31] = { "AND", &CPU::AND, &CPU::IZY, 5 };
        instrutionMap[0x32] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x33] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0x34] = { "NOP", &CPU::NOP, &CPU::ZPX, 4 };
        instrutionMap[0x35] = { "AND", &CPU::AND, &CPU::ZPX, 4 };
        instrutionMap[0x36] = { "ROL", &CPU::ROL, &CPU::ZPX, 6 };
        instrutionMap[0x37] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };
        instrutionMap[0x38] = { "SEC", &CPU::SEC, &CPU::IMP, 2 };
        instrutionMap[0x39] = { "AND", &CPU::AND, &CPU::ABY, 4 };
        instrutionMap[0x3A] = { "NOP", &CPU::NOP, &CPU::IMP, 2 };
        instrutionMap[0x3B] = { "XXX", &CPU::XXX, &CPU::IMP, 7 };
        instrutionMap[0x3C] = { "NOP", &CPU::NOP, &CPU::ABX, 4 };
        instrutionMap[0x3D] = { "AND", &CPU::AND, &CPU::ABX, 4 };
        instrutionMap[0x3E] = { "ROL", &CPU::ROL, &CPU::ABX, 7 };
        instrutionMap[0x3F] = { "XXX", &CPU::XXX, &CPU::IMP, 7 };

        instrutionMap[0x40] = { "RTI", &CPU::RTI, &CPU::IMP, 6 };
        instrutionMap[0x41] = { "EOR", &CPU::EOR, &CPU::IZX, 6 };
        instrutionMap[0x42] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x43] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0x44] = { "NOP", &CPU::NOP, &CPU::ZP0, 3 };
        instrutionMap[0x45] = { "EOR", &CPU::EOR, &CPU::ZP0, 3 };
        instrutionMap[0x46] = { "LSR", &CPU::LSR, &CPU::ZP0, 5 };
        instrutionMap[0x47] = { "XXX", &CPU::XXX, &CPU::IMP, 5 };
        instrutionMap[0x48] = { "PHA", &CPU::PHA, &CPU::IMP, 3 };
        instrutionMap[0x49] = { "EOR", &CPU::EOR, &CPU::IMM, 2 };
        instrutionMap[0x4A] = { "LSR", &CPU::LSR, &CPU::ACC, 2 };
        instrutionMap[0x4B] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x4C] = { "JMP", &CPU::JMP, &CPU::ABS, 3 };
        instrutionMap[0x4D] = { "EOR", &CPU::EOR, &CPU::ABS, 4 };
        instrutionMap[0x4E] = { "LSR", &CPU::LSR, &CPU::ABS, 6 };
        instrutionMap[0x4F] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };
    
        instrutionMap[0x50] = { "BVC", &CPU::BVC, &CPU::REL, 2 };
        instrutionMap[0x51] = { "EOR", &CPU::EOR, &CPU::IZY, 5 };
        instrutionMap[0x52] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x53] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0x54] = { "NOP", &CPU::NOP, &CPU::ZPX, 4 };
        instrutionMap[0x55] = { "EOR", &CPU::EOR, &CPU::ZPX, 4 };
        instrutionMap[0x56] = { "LSR", &CPU::LSR, &CPU::ZPX, 6 };
        instrutionMap[0x57] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };
        instrutionMap[0x58] = { "CLI", &CPU::CLI, &CPU::IMP, 2 };
        instrutionMap[0x59] = { "EOR", &CPU::EOR, &CPU::ABY, 4 };
        instrutionMap[0x5A] = { "NOP", &CPU::NOP, &CPU::IMP, 2 };
        instrutionMap[0x5B] = { "XXX", &CPU::XXX, &CPU::IMP, 7 };
        instrutionMap[0x5C] = { "NOP", &CPU::NOP, &CPU::ABX, 4 };
        instrutionMap[0x5D] = { "EOR", &CPU::EOR, &CPU::ABX, 4 };
        instrutionMap[0x5E] = { "LSR", &CPU::LSR, &CPU::ABX, 7 };
        instrutionMap[0x5F] = { "XXX", &CPU::XXX, &CPU::IMP, 7 };

        instrutionMap[0x60] = { "RTS", &CPU::RTS, &CPU::IMP, 6 };
        instrutionMap[0x61] = { "ADC", &CPU::ADC, &CPU::IZX, 6 };
        instrutionMap[0x62] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x63] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0x64] = { "NOP", &CPU::NOP, &CPU::ZP0, 3 };
        instrutionMap[0x65] = { "ADC", &CPU::ADC, &CPU::ZP0, 3 };
        instrutionMap[0x66] = { "ROR", &CPU::ROR, &CPU::ZP0, 5 };
        instrutionMap[0x67] = { "XXX", &CPU::XXX, &CPU::IMP, 5 };
        instrutionMap[0x68] = { "PLA", &CPU::PLA, &CPU::IMP, 4 };
        instrutionMap[0x69] = { "ADC", &CPU::ADC, &CPU::IMM, 2 };
        instrutionMap[0x6A] = { "ROR", &CPU::ROR, &CPU::ACC, 2 };
        instrutionMap[0x6B] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x6C] = { "JMP", &CPU::JMP, &CPU::IND, 5 };
        instrutionMap[0x6D] = { "ADC", &CPU::ADC, &CPU::ABS, 4 };
        instrutionMap[0x6E] = { "ROR", &CPU::ROR, &CPU::ABS, 6 };
        instrutionMap[0x6F] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };

        instrutionMap[0x70] = { "BVS", &CPU::BVS, &CPU::REL, 2 };
        instrutionMap[0x71] = { "ADC", &CPU::ADC, &CPU::IZY, 5 };
        instrutionMap[0x72] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x73] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0x74] = { "NOP", &CPU::NOP, &CPU::ZPX, 4 };
        instrutionMap[0x75] = { "ADC", &CPU::ADC, &CPU::ZPX, 4 };
        instrutionMap[0x76] = { "ROR", &CPU::ROR, &CPU::ZPX, 6 };
        instrutionMap[0x77] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };
        instrutionMap[0x78] = { "SEI", &CPU::SEI, &CPU::IMP, 2 };
        instrutionMap[0x79] = { "ADC", &CPU::ADC, &CPU::ABY, 4 };
        instrutionMap[0x7A] = { "NOP", &CPU::NOP, &CPU::IMP, 2 };
        instrutionMap[0x7B] = { "XXX", &CPU::XXX, &CPU::IMP, 7 };
        instrutionMap[0x7C] = { "NOP", &CPU::NOP, &CPU::ABX, 4 };
        instrutionMap[0x7D] = { "ADC", &CPU::ADC, &CPU::ABX, 4 };
        instrutionMap[0x7E] = { "ROR", &CPU::ROR, &CPU::ABX, 7 };
        instrutionMap[0x7F] = { "XXX", &CPU::XXX, &CPU::IMP, 7 };

        // 0x80–0xBF
        instrutionMap[0x80] = { "NOP", &CPU::NOP, &CPU::IMM, 2 };
        instrutionMap[0x81] = { "STA", &CPU::STA, &CPU::IZX, 6 };
        instrutionMap[0x82] = { "NOP", &CPU::NOP, &CPU::IMM, 2 };
        instrutionMap[0x83] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };
        instrutionMap[0x84] = { "STY", &CPU::STY, &CPU::ZP0, 3 };
        instrutionMap[0x85] = { "STA", &CPU::STA, &CPU::ZP0, 3 };
        instrutionMap[0x86] = { "STX", &CPU::STX, &CPU::ZP0, 3 };
        instrutionMap[0x87] = { "XXX", &CPU::XXX, &CPU::IMP, 3 };
        instrutionMap[0x88] = { "DEY", &CPU::DEY, &CPU::IMP, 2 };
        instrutionMap[0x89] = { "NOP", &CPU::NOP, &CPU::IMM, 2 };
        instrutionMap[0x8A] = { "TXA", &CPU::TXA, &CPU::IMP, 2 };
        instrutionMap[0x8B] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x8C] = { "STY", &CPU::STY, &CPU::ABS, 4 };
        instrutionMap[0x8D] = { "STA", &CPU::STA, &CPU::ABS, 4 };
        instrutionMap[0x8E] = { "STX", &CPU::STX, &CPU::ABS, 4 };
        instrutionMap[0x8F] = { "XXX", &CPU::XXX, &CPU::IMP, 4 };

        // 0x90–0xBF
        instrutionMap[0x90] = { "BCC", &CPU::BCC, &CPU::REL, 2 };
        instrutionMap[0x91] = { "STA", &CPU::STA, &CPU::IZY, 6 };
        instrutionMap[0x92] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0x93] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };
        instrutionMap[0x94] = { "STY", &CPU::STY, &CPU::ZPX, 4 };
        instrutionMap[0x95] = { "STA", &CPU::STA, &CPU::ZPX, 4 };
        instrutionMap[0x96] = { "STX", &CPU::STX, &CPU::ZPY, 4 };
        instrutionMap[0x97] = { "XXX", &CPU::XXX, &CPU::IMP, 4 };
        instrutionMap[0x98] = { "TYA", &CPU::TYA, &CPU::IMP, 2 };
        instrutionMap[0x99] = { "STA", &CPU::STA, &CPU::ABY, 5 };
        instrutionMap[0x9A] = { "TXS", &CPU::TXS, &CPU::IMP, 2 };
        instrutionMap[0x9B] = { "XXX", &CPU::XXX, &CPU::IMP, 5 };
        instrutionMap[0x9C] = { "XXX", &CPU::XXX, &CPU::IMP, 5 };
        instrutionMap[0x9D] = { "STA", &CPU::STA, &CPU::ABX, 5 };
        instrutionMap[0x9E] = { "XXX", &CPU::XXX, &CPU::IMP, 5 };
        instrutionMap[0x9F] = { "XXX", &CPU::XXX, &CPU::IMP, 5 };

        // 0xA0–0xBF
        instrutionMap[0xA0] = { "LDY", &CPU::LDY, &CPU::IMM, 2 };
        instrutionMap[0xA1] = { "LDA", &CPU::LDA, &CPU::IZX, 6 };
        instrutionMap[0xA2] = { "LDX", &CPU::LDX, &CPU::IMM, 2 };
        instrutionMap[0xA3] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };
        instrutionMap[0xA4] = { "LDY", &CPU::LDY, &CPU::ZP0, 3 };
        instrutionMap[0xA5] = { "LDA", &CPU::LDA, &CPU::ZP0, 3 };
        instrutionMap[0xA6] = { "LDX", &CPU::LDX, &CPU::ZP0, 3 };
        instrutionMap[0xA7] = { "XXX", &CPU::XXX, &CPU::IMP, 3 };
        instrutionMap[0xA8] = { "TAY", &CPU::TAY, &CPU::IMP, 2 };
        instrutionMap[0xA9] = { "LDA", &CPU::LDA, &CPU::IMM, 2 };
        instrutionMap[0xAA] = { "TAX", &CPU::TAX, &CPU::IMP, 2 };
        instrutionMap[0xAB] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0xAC] = { "LDY", &CPU::LDY, &CPU::ABS, 4 };
        instrutionMap[0xAD] = { "LDA", &CPU::LDA, &CPU::ABS, 4 };
        instrutionMap[0xAE] = { "LDX", &CPU::LDX, &CPU::ABS, 4 };
        instrutionMap[0xAF] = { "XXX", &CPU::XXX, &CPU::IMP, 4 };

        // 0xB0–0xBF
        instrutionMap[0xB0] = { "BCS", &CPU::BCS, &CPU::REL, 2 };
        instrutionMap[0xB1] = { "LDA", &CPU::LDA, &CPU::IZY, 5 };
        instrutionMap[0xB2] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0xB3] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0xB4] = { "LDY", &CPU::LDY, &CPU::ZPX, 4 };
        instrutionMap[0xB5] = { "LDA", &CPU::LDA, &CPU::ZPX, 4 };
        instrutionMap[0xB6] = { "LDX", &CPU::LDX, &CPU::ZPY, 4 };
        instrutionMap[0xB7] = { "XXX", &CPU::XXX, &CPU::IMP, 4 };
        instrutionMap[0xB8] = { "CLV", &CPU::CLV, &CPU::IMP, 2 };
        instrutionMap[0xB9] = { "LDA", &CPU::LDA, &CPU::ABY, 4 };
        instrutionMap[0xBA] = { "TSX", &CPU::TSX, &CPU::IMP, 2 };
        instrutionMap[0xBB] = { "XXX", &CPU::XXX, &CPU::IMP, 4 };
        instrutionMap[0xBC] = { "LDY", &CPU::LDY, &CPU::ABX, 4 };
        instrutionMap[0xBD] = { "LDA", &CPU::LDA, &CPU::ABX, 4 };
        instrutionMap[0xBE] = { "LDX", &CPU::LDX, &CPU::ABY, 4 };
        instrutionMap[0xBF] = { "XXX", &CPU::XXX, &CPU::IMP, 4 };

        // 0xC0–0xCF
        instrutionMap[0xC0] = { "CPY", &CPU::CPY, &CPU::IMM, 2 };
        instrutionMap[0xC1] = { "CMP", &CPU::CMP, &CPU::IZX, 6 };
        instrutionMap[0xC2] = { "NOP", &CPU::NOP, &CPU::IMM, 2 };
        instrutionMap[0xC3] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0xC4] = { "CPY", &CPU::CPY, &CPU::ZP0, 3 };
        instrutionMap[0xC5] = { "CMP", &CPU::CMP, &CPU::ZP0, 3 };
        instrutionMap[0xC6] = { "DEC", &CPU::DEC, &CPU::ZP0, 5 };
        instrutionMap[0xC7] = { "XXX", &CPU::XXX, &CPU::IMP, 5 };
        instrutionMap[0xC8] = { "INY", &CPU::INY, &CPU::IMP, 2 };
        instrutionMap[0xC9] = { "CMP", &CPU::CMP, &CPU::IMM, 2 };
        instrutionMap[0xCA] = { "DEX", &CPU::DEX, &CPU::IMP, 2 };
        instrutionMap[0xCB] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0xCC] = { "CPY", &CPU::CPY, &CPU::ABS, 4 };
        instrutionMap[0xCD] = { "CMP", &CPU::CMP, &CPU::ABS, 4 };
        instrutionMap[0xCE] = { "DEC", &CPU::DEC, &CPU::ABS, 6 };
        instrutionMap[0xCF] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };

        // 0xD0–0xDF
        instrutionMap[0xD0] = { "BNE", &CPU::BNE, &CPU::REL, 2 };
        instrutionMap[0xD1] = { "CMP", &CPU::CMP, &CPU::IZY, 5 };
        instrutionMap[0xD2] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0xD3] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0xD4] = { "NOP", &CPU::NOP, &CPU::ZPX, 4 };
        instrutionMap[0xD5] = { "CMP", &CPU::CMP, &CPU::ZPX, 4 };
        instrutionMap[0xD6] = { "DEC", &CPU::DEC, &CPU::ZPX, 6 };
        instrutionMap[0xD7] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };
        instrutionMap[0xD8] = { "CLD", &CPU::CLD, &CPU::IMP, 2 };
        instrutionMap[0xD9] = { "CMP", &CPU::CMP, &CPU::ABY, 4 };
        instrutionMap[0xDA] = { "NOP", &CPU::NOP, &CPU::IMP, 2 };
        instrutionMap[0xDB] = { "XXX", &CPU::XXX, &CPU::IMP, 7 };
        instrutionMap[0xDC] = { "NOP", &CPU::NOP, &CPU::ABX, 4 };
        instrutionMap[0xDD] = { "CMP", &CPU::CMP, &CPU::ABX, 4 };
        instrutionMap[0xDE] = { "DEC", &CPU::DEC, &CPU::ABX, 7 };
        instrutionMap[0xDF] = { "XXX", &CPU::XXX, &CPU::IMP, 7 };

        // 0xE0–0xEF
        instrutionMap[0xE0] = { "CPX", &CPU::CPX, &CPU::IMM, 2 };
        instrutionMap[0xE1] = { "SBC", &CPU::SBC, &CPU::IZX, 6 };
        instrutionMap[0xE2] = { "NOP", &CPU::NOP, &CPU::IMM, 2 };
        instrutionMap[0xE3] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0xE4] = { "CPX", &CPU::CPX, &CPU::ZP0, 3 };
        instrutionMap[0xE5] = { "SBC", &CPU::SBC, &CPU::ZP0, 3 };
        instrutionMap[0xE6] = { "INC", &CPU::INC, &CPU::ZP0, 5 };
        instrutionMap[0xE7] = { "XXX", &CPU::XXX, &CPU::IMP, 5 };
        instrutionMap[0xE8] = { "INX", &CPU::INX, &CPU::IMP, 2 };
        instrutionMap[0xE9] = { "SBC", &CPU::SBC, &CPU::IMM, 2 };
        instrutionMap[0xEA] = { "NOP", &CPU::NOP, &CPU::IMP, 2 };
        instrutionMap[0xEB] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0xEC] = { "CPX", &CPU::CPX, &CPU::ABS, 4 };
        instrutionMap[0xED] = { "SBC", &CPU::SBC, &CPU::ABS, 4 };
        instrutionMap[0xEE] = { "INC", &CPU::INC, &CPU::ABS, 6 };
        instrutionMap[0xEF] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };

        // 0xF0–0xFF
        instrutionMap[0xF0] = { "BEQ", &CPU::BEQ, &CPU::REL, 2 };
        instrutionMap[0xF1] = { "SBC", &CPU::SBC, &CPU::IZY, 5 };
        instrutionMap[0xF2] = { "XXX", &CPU::XXX, &CPU::IMP, 2 };
        instrutionMap[0xF3] = { "XXX", &CPU::XXX, &CPU::IMP, 8 };
        instrutionMap[0xF4] = { "NOP", &CPU::NOP, &CPU::ZPX, 4 };
        instrutionMap[0xF5] = { "SBC", &CPU::SBC, &CPU::ZPX, 4 };
        instrutionMap[0xF6] = { "INC", &CPU::INC, &CPU::ZPX, 6 };
        instrutionMap[0xF7] = { "XXX", &CPU::XXX, &CPU::IMP, 6 };
        instrutionMap[0xF8] = { "SED", &CPU::SED, &CPU::IMP, 2 };
        instrutionMap[0xF9] = { "SBC", &CPU::SBC, &CPU::ABY, 4 };
        instrutionMap[0xFA] = { "NOP", &CPU::NOP, &CPU::IMP, 2 };
        instrutionMap[0xFB] = { "XXX", &CPU::XXX, &CPU::IMP, 7 };
        instrutionMap[0xFC] = { "NOP", &CPU::NOP, &CPU::ABX, 4 };
        instrutionMap[0xFD] = { "SBC", &CPU::SBC, &CPU::ABX, 4 };
        instrutionMap[0xFE] = { "INC", &CPU::INC, &CPU::ABX, 7 };
        instrutionMap[0xFF] = { "XXX", &CPU::XXX, &CPU::IMP, 7 };
    }
};

std::vector<uint8_t> loadProgram(const std::string& filePath) {
    std::ifstream file(filePath, std::ios::binary);
    if (!file) {
        throw std::runtime_error("Failed to open file: " + filePath);
    }
    std::vector<uint8_t> program((std::istreambuf_iterator<char>(file)),
                                 std::istreambuf_iterator<char>());
    return program;
}

/*

FFFB:FFFA - NMI
FFFD:FFFC - reset vector
FFFF:FFFE - IRQ / BRK 

*/

int main(int argn, char* argv[]) {
    CPU cpu;
    cpu.PrintCharAddres    = 0xFFF8;
    cpu.PrintInvokeAddres  = 0xFFF9;
    cpu.InputCharAddres    = 0xFFF6;

    ///*
    std::vector<uint8_t> program;

    if (argn < 2) {
        std::cout << "Incorrect Usage, use it like this: 6502 <path_to_memory_image>\n";
        return 1;
    } else {
        program = readFileRaw(std::string(argv[1]));
    }
    //*/

    //std::vector<uint8_t> program = readFileRaw("E:\\vs code\\files\\6502cpp\\programs\\Input test\\memory.bin");
    //std::vector<uint8_t> program = readFileRaw("E:\\vs code\\files\\6502cpp\\programs\\Hello, world\\memory.bin");

    /*
    std::vector<uint8_t> program = {
        0x4C, 0x16, 0x00, 0xEA, 0xAD, 0xF6, 0xFF, 0x20,
        0x0D, 0x00, 0x4C, 0x16, 0x00, 0x8D, 0xF8, 0xFF,
        0xA9, 0x01, 0x8D, 0xF9, 0xFF, 0x60, 0x4C, 0x16,
        0x00
    };

    cpu.memory[0xFFFD] = 0x00;
    cpu.memory[0xFFFC] = 0x00;
    
    cpu.memory[0xFFFA] = 0x03;



    */

    std::copy(program.begin(), program.end(), cpu.memory);


    cpu.runFromReset();
}
