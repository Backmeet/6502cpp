.org $0200

START:
    LDA #$48; h
    JSR PRINT_CHAR

    LDA #$65; e
    JSR PRINT_CHAR

    LDA #$6C; l
    JSR PRINT_CHAR

    LDA #$6C; l
    JSR PRINT_CHAR

    LDA #$6F; o
    JSR PRINT_CHAR

    LDA #$2C; ,
    JSR PRINT_CHAR

    LDA #$20; 
    JSR PRINT_CHAR

    LDA #$77; w
    JSR PRINT_CHAR

    LDA #$6F; o
    JSR PRINT_CHAR

    LDA #$72; r
    JSR PRINT_CHAR

    LDA #$6C; l
    JSR PRINT_CHAR

    LDA #$64; d
    JSR PRINT_CHAR

    JMP END

; print the char in reg A
PRINT_CHAR:
    STA $FFF8
    LDA #$01
    STA $FFF9
    RTS

END:
JMP END

NMI:
IRQ:
JMP START

.onStart START
.onNMI NMI
.onIRQ IRQ