  .setcpu "65C02"
loop:
    LDA $FFF6              ; Check for input char. 
    BEQ loop               ; while no char do nothing 
    LDA $FFF7              ; get char
    STA $FFF8              ; Output character.
    LDA #1           
    STA $FFF9
BEQ loop:

.segment "VECTORS"
    .word   loop         ; NMI vector
    .word   loop         ; RESET vector
    .word   loop         ; IRQ vector