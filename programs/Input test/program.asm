JMP AWAIT

; attatched to NMI and emulators input mecanism
ON_CHAR:
    LDA $FFF6
    JSR PRINT_CHAR
    RTI

; print the char in reg A
PRINT_CHAR:
    STA $FFF8
    LDA #$01
    STA $FFF9
    RTS

AWAIT:
JMP AWAIT

.onStart AWAIT
.onNMI ON_CHAR
.onIRQ AWAIT