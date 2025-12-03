#include "simulator.h"
#include <cassert>

int cycle = 0;

ModInt::ModInt(int size, int initial_value) : size(size), val(0) {
    assert(size > 0);
    val = normalize(initial_value);
}

int ModInt::normalize(int v) const {
    v = v % size;
    if (v < 0) {
        v += size;
    }
    return v;
}

ModInt& ModInt::operator+=(int offset) {
    val = normalize(val + offset);
    return *this;
}

ModInt& ModInt::operator-=(int offset) {
    val = normalize(val - offset);
    return *this;
}

ModInt ModInt::operator+(int offset) const {
    ModInt result(size, val + offset);
    return result;
}

ModInt ModInt::operator-(int offset) const {
    ModInt result(size, val - offset);
    return result;
}

ModInt& ModInt::operator++() {
    return *this += 1;
}

ModInt ModInt::operator++(int) {
    ModInt temp = *this;
    ++(*this);
    return temp;
}

ModInt& ModInt::operator--() {
    return *this -= 1;
}

ModInt ModInt::operator--(int) {
    ModInt temp = *this;
    --(*this);
    return temp;
}
