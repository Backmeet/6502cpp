#include <stdint.h>

void printchar(char c) {
    // Write the character to memory address $FFF8
    *((volatile char*)0xFFF8) = c;
    // Set $FFF9 to 1
    *((volatile char*)0xFFF9) = 1;
}

void print(const char* str) {
    while (*str) {
        printchar(*str++);
    }
}

void main() {
    print("Hello, World!\n");
    while (1);
}
