#include <stdint.h>

void printchar(char c) {
    // Write the character to memory address $FFF8
    *((volatile uint8_t*)0xFFF8) = (uint8_t)c;

    // Set $FFF9 to 1
    *((volatile uint8_t*)0xFFF9) = 1;
}

void print(const char* str) {
    while (*str) {
        printchar(*str++);
    }
}

void _start() {
    print("Hello, World!\n");
    while (1);
}
