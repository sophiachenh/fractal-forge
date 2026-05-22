#include <cassert>
#include <iostream>
#include "renderer.h"

// Minimal hand-rolled tests — no external framework needed for a starter
int main() {
    using namespace fractal;

    // Points clearly inside the set iterate to max
    assert(mandelbrot_iter(0.0, 0.0, 100) == 100);

    // Points clearly outside escape immediately
    assert(mandelbrot_iter(2.1, 0.0, 100) < 100);
    assert(mandelbrot_iter(0.0, 2.1, 100) < 100);

    // Render produces the right number of pixels
    RenderParams p{100, 80, -0.5, 0.0, 100.0, 64};
    auto buf = render_mandelbrot(p);
    assert(buf.size() == 100u * 80u);

    // Interior pixel should be black
    // Center of render ≈ (-0.5, 0) which is inside the set
    auto& center = buf[(80 / 2) * 100 + (100 / 2)];
    assert(center.r == 0 && center.g == 0 && center.b == 0);

    std::cout << "All renderer tests passed.\n";
    return 0;
}
