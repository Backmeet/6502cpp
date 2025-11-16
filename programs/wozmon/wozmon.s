  .setcpu "65C02"

IN    = $0200                          ; Input buffer

MAIN:
  JSR GETLINE

  JMP MAIN

ESCAPE:
  LDA #$5C ; "\".
  JSR ECHO ; Output it.

GETLINE:
  ; Y registor is the index into the input buffer
  LDY #$00
LINEREADLOOP:
  JSR AWAITCHAR
  STA IN,Y
  CMP #$0A        ; Line feed?
  BEQ LINEDONE
  CMP #$08        ; Backspace?
  BEQ BACKSPACE
  JSR ECHO
  INY
  JMP LINEREADLOOP
LINEDONE:
  JSR NEWLINE
  RTS
BACKSPACE:
  JSR ECHO
  CPY #$00
  BEQ LINEREADLOOP ; If at start of line, ignore.
  DEY
  JMP LINEREADLOOP

AWAITCHAR:
  LDA $FFF6              ; Check for input char. 
  BEQ AWAITCHAR          ; while no char do nothing 
  LDA #0
  STA $FFF6              ; Clear input flag
  LDA $FFF7              ; get char
  RTS

NEWLINE:
  LDA #$0D
  JSR ECHO
  LDA #$0A
  JSR ECHO
  RTS

ECHO:
  PHA       ; Save A.
  STA $FFF8 ; Output character.
  LDA #1           
  STA $FFF9
  PLA
  RTS

.segment "VECTOR"
  .word MAIN ; NMI vector
  .word MAIN ; RESET vector
  .word MAIN ; IRQ vector