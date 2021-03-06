#include "builtin.hpp"
#include "bit.hpp"

namespace __bit__ {


str *__name__;


/* See: http://gcc.gnu.org/onlinedocs/gcc/Other-Builtins.html */
__ss_int nextset(__ss_int vec, __ss_int pos) {
	// return next set bit starting from pos, -1 if there is none.
	// return ((vec >> pos) > 0) ? pos + __builtin_ffs(vec >> pos) - 1 : -1;
	return (vec >> pos) ? pos + __builtin_ctz((unsigned)vec >> pos) : -1;
}

__ss_int nextunset(__ss_int vec, __ss_int pos) {
	// return next unset bit starting from pos. there is always a next unset
	// bit, so no bounds checking 
	return pos + __builtin_ctz(~((unsigned)vec >> pos));
}

void __init() {
    __name__ = new str("bit");

}

} // module namespace


