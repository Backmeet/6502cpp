.org $0000

.set XAML = $24
.set XAMH = $25
.set STL  = $26
.set STH  = $27
.set L    = $28
.set H    = $29
.set YSAV = $2A
.set MODE = $2B

.set IN = $0200

JMP RUN

RESET:
    SEI                 ; disable IRQs on start
    LDA #$1B            ; optional init value
    RTS

LEAVE_WOZMON:
    CLI                 ; enable IRQs when leaving WozMon
    RTS

NOTCR:
    CMP #$08
    BEQ BACKSPACE
    CMP #$1B
    BEQ ESCAPE
    INY
    BPL NEXTCHAR

ESCAPE:
    LDA #$5C
    JSR ECHO

GETLINE:
    LDA #$0D
    JSR ECHO
    LDY #$01

BACKSPACE:
    DEY
    BMI GETLINE

NEXTCHAR:
WAITCHAR:
    BIT $FFFF           ; check I flag
    BPL WAITCHAR        ; wait if interrupts disabled
    LDA $FFF6           ; read char from new I/O
    STA IN,Y
    JSR ECHO
    CMP #$0D
    BNE NOTCR
    LDY #$FF
    LDA #$00
    TAX

SETBLOCK:
    ASL

SETSTOR:
    ASL
    STA MODE

BLSKIP:
    INY

NEXTITEM:
    LDA IN,Y
    CMP #$0D
    BEQ GETLINE
    CMP #$2E
    BCC BLSKIP
    BEQ SETBLOCK
    CMP #$3A
    BEQ SETSTOR
    CMP #$52
    BEQ RUN
    STX L
    STX H
    STY YSAV

NEXTHEX:
    LDA IN,Y
    EOR #$30
    CMP #$0A
    BCC DIG
    ADC #$88
    CMP #$FA
    BCC NOTHEX

DIG:
    ASL
    ASL
    ASL
    ASL
    LDX #$04

HEXSHIFT:
    ASL
    ROL L
    ROL H
    DEX
    BNE HEXSHIFT
    INY
    BNE NEXTHEX

NOTHEX:
    CPY YSAV
    BEQ ESCAPE
    BIT MODE
    BVC NOTSTOR

    LDA L
    STA (STL,X)
    INC STL
    BNE NEXTITEM
    INC STH

TONEXTITEM:
    JMP NEXTITEM

RUN:
    JMP (XAML)

NOTSTOR:
    BMI XAMNEXT
    LDX #$02

SETADR:
    LDA L-1,X
    STA STL-1,X
    STA XAML-1,X
    DEX
    BNE SETADR

NXTPRNT:
    BNE PRDATA
    LDA #$0D
    JSR ECHO
    LDA XAMH
    JSR PRBYTE
    LDA XAML
    JSR PRBYTE
    LDA #$3A
    JSR ECHO

PRDATA:
    LDA #$20
    JSR ECHO
    LDA (XAML,X)
    JSR PRBYTE

XAMNEXT:
    STX MODE
    LDA XAML
    CMP L
    LDA XAMH
    SBC H
    BCS TONEXTITEM
    INC XAML
    BNE MOD8CHK
    INC XAMH

MOD8CHK:
    LDA XAML
    AND #$07
    BPL NXTPRNT

PRBYTE:
    PHA
    LSR
    LSR
    LSR
    LSR
    JSR PRHEX
    PLA
    RTS

PRHEX:
    AND #$0F
    ORA #$30
    CMP #$3A
    BCC ECHO
    ADC #$06

ECHO:
    PHA
    STA $FFF8
    LDA #$01
    STA $FFF9

.onNMI   RESET ; yea idgaf do what you want
.onStart RESET ; bruv
.onIRQ   RESET ; this will never run 
