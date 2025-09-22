JMP AWAIT

; attatched to NMI and emulators input mecanism
START:
    NOP ; identifier for were to keep the NMI vector value
    LDA $FFF6
    JSR PRINT_CHAR
    JMP AWAIT

; print the char in reg A
PRINT_CHAR:
    STA $FFF8
    LDA #$01
    STA $FFF9
    RTS

AWAIT:
JMP AWAIT