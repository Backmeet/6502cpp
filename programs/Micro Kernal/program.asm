; ZP $0 - $E are args
; ZP $F is return
; $FFF8: char out, $FFF9: invoke print, $FFF6: last input char
; $10: flag set when new char is available
.org $0200

start:
    LDA #58 ; ":"
    JSR Await_char

    JSR Processe_Cmd

    JMP start ; loop back

; ----------------- Print char -----------------
print_char:
    LDA $0
    STA $FFF8
    LDA #1
    STA $FFF9
    RTS

; ----------------- Wait for a single char -----------------
Await_char:
    LDA #0
    STA $10
wait_for_char:
    LDA $11
    CMP #1
    BNE wait_for_char
    LDA $FFF6
    STA $10
    RTS

; ----------------- NMI handler -----------------
On_Char:
    LDA #1
    STA $11
    RTI

; ----------------- Command processor -----------------
Processe_Cmd:
    LDA $10
    CMP #$52  ; "R"
    BEQ Cmd_Read
    CMP #$57  ; "W"
    BEQ Cmd_Write
    CMP #$53  ; "S"
    BEQ Cmd_Section
    CMP #$43  ; "C"
    BEQ Cmd_Clear_jump_buffer
    CMP #$47  ; "G"
    BEQ Cmd_Goto_jump_buffer
    RTS

jmp Cmd_Clear_jump_buffer_end
Cmd_Clear_jump_buffer:
jmp Cmd_Clear
Cmd_Clear_jump_buffer_end:

jmp Cmd_Goto_jump_buffer_end
Cmd_Goto_jump_buffer:
jmp Cmd_Goto
Cmd_Goto_jump_buffer_end:

; ----------------- R: Read memory -----------------
Cmd_Read:
    JSR ReadHexAddress       ; $0 = high, $1 = low
    LDY $1
    LDA ($0),Y
    STA $0F
    JSR PrintHex
    RTS

; ----------------- W: Write memory -----------------
Cmd_Write:
    JSR ReadHexAddress       ; $0/$1 = address
    JSR Await_char
    JSR HexToNibble
    ASL A
    ASL A
    ASL A
    ASL A
    STA $2
    JSR Await_char
    JSR HexToNibble
    ORA $2
    STA $3                 ; $3 = value to write

    ; optional: print old value
    LDY $1
    LDA ($0),Y
    STA $0F
    JSR PrintHex

    ; write new value
    LDY $1
    LDA $3
    STA ($0),Y
    RTS

; ----------------- S: Print section -----------------
Cmd_Section:
    JSR ReadHexAddress       ; start address
    STA $5
    STX $6
    JSR ReadHexAddress       ; end address
    STA $7
    STX $8

Loop_Section:
    ; Print address
    LDA $5
    JSR PrintHex
    LDA $6
    JSR PrintHex
    LDA #58
    JSR print_char
    ; Print value
    LDY $6
    LDA ($5),Y
    STA $0F
    JSR PrintHex

    ; Increment address
    INC $6
    BNE SkipHighS
    INC $5
SkipHighS:

    ; Compare with end
    LDA $5
    CMP $7
    BNE Loop_Section
    LDA $6
    CMP $8
    BNE Loop_Section
    RTS

; ----------------- C: Clear section -----------------
Cmd_Clear:
    JSR ReadHexAddress       ; start
    STA $5
    STX $6
    JSR ReadHexAddress       ; end
    STA $7
    STX $8

Loop_Clear:
    LDY $6
    LDA #0
    STA ($5),Y

    INC $6
    BNE SkipHighC
    INC $5
SkipHighC:

    LDA $5
    CMP $7
    BNE Loop_Clear
    LDA $6
    CMP $8
    BNE Loop_Clear
    RTS

; ----------------- G: Goto -----------------
Cmd_Goto:
    JSR ReadHexAddress       ; target in $0/$1

    ; Print '\'
    LDA #92
    JSR print_char

    ; Jump via ZP indirect
    LDA $0
    STA $FA
    LDA $1
    STA $FB
    JMP ($FA)

; ----------------- Read interactive 16-bit hex -----------------
ReadHexAddress:
    JSR Await_char
    JSR HexToNibble
    ASL A
    ASL A
    ASL A
    ASL A
    STA $0
    JSR Await_char
    JSR HexToNibble
    ORA $0
    STA $0

    JSR Await_char
    JSR HexToNibble
    ASL A
    ASL A
    ASL A
    ASL A
    STA $1
    JSR Await_char
    JSR HexToNibble
    ORA $1
    STA $1
    RTS

; ----------------- Convert ASCII hex to 0-15 -----------------
HexToNibble:
    CMP #$30
    BCC HexErr
    CMP #$39
    BCC HexDigit
    CMP #$41
    BCC HexErr
    CMP #$46
    BCC HexAlpha
HexErr:
    LDA #0
    RTS
HexDigit:
    SEC
    SBC #$30
    RTS
HexAlpha:
    SEC
    SBC #$41
    CLC
    ADC #10
    RTS

; ----------------- Print byte in 2-digit hex -----------------
PrintHex:
    STA $4
    LDA $4
    LSR A
    LSR A
    LSR A
    LSR A
    JSR NibbleToASCII
    JSR print_char
    LDA $4
    AND #$0F
    JSR NibbleToASCII
    JSR print_char
    RTS

; ----------------- Convert 0-15 to ASCII -----------------
NibbleToASCII:
    CMP #10
    BCC NT_0_9
    ADC #$37
    RTS
NT_0_9:
    ADC #$30
    RTS

.onStart start
.onNMI On_Char
