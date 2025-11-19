  .setcpu "65C02"

.segment "BIOS"
AWAITCHAR:
  LDA $FFF6              ; Check for input char. 
  BEQ AWAITCHAR          ; while no char do nothing 
  LDA #0
  STA $FFF6              ; Clear input flag
  LDA $FFF7              ; get char
  RTS

CHAROUT:
  PHA       ; Save A.
  STA $FFF8 ; Output character.
  LDA #1           
  STA $FFF9
  PLA
  RTS

