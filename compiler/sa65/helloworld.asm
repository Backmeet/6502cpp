
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

LDA #$0
STA $FF00

LDA #$0
STA $FDFF

push:

LDY $FF00
LDA $FDFF
STA $FEFF,Y

INC $FF00
RTS

pop:

DEC $FF00
LDY $FF00
LDA $FEFF,Y
STA $FDFF

RTS

printchar:

JSR pop

LDA $FDFF
STA $FFF8

LDA #$1
STA $FFF9

RTS

print:

JSR pop

LDA $FDFF
STA $FDFE

JSR pop

LDA $FDFF
STA $FDFD

JSR pop

LDA $FDFF
STA $FDFC

LDA #$0
STA $FDFB

LDA $FDFD
STA $FDFA
LDA $FDFC
STA $FDF9
whilestart_1:
LDA $FDFB
CMP $FDFE
BEQ skip_3
JMP while_2
skip_3:
JMP whileend_0
while_2:

LDA $FDFA
STA $FDFF

JSR push

JSR printchar

LDA $FDFA
STA $FDFF

INC $FDFF
LDA $FDFF
STA $FDFA

INC $FDFB
JMP whilestart_1
whileend_0:

RTS

main:

LDA #$48
STA $FDF7

LDA #$65
STA $FDF6

LDA #$6C
STA $FDF5

LDA #$6C
STA $FDF4

LDA #$6F
STA $FDF3

LDA #$2C
STA $FDF2

LDA #$20
STA $FDF1

LDA #$57
STA $FDF0

LDA #$6F
STA $FDEF

LDA #$72
STA $FDEE

LDA #$6C
STA $FDED

LDA #$64
STA $FDEC

LDA #$C
STA $FDFF

JSR push

LDA #$F
STA $FDFF

JSR push

LDA #$EA
STA $FDFF

JSR push

JSR print

RTS


.segment "VECTOR"
    .word NOPI
    .word startup
    .word NOPI
