#pragma once

#include <cstdint>
#include <vector>

namespace fractal {

// RGB pixel — 3 bytes, packed
struct Pixel {
    uint8_t r, g, b;
};

// Parameters for a single render
struct RenderParams {
    uint32_t width;
    uint32_t height;
    double   center_x;   // real part of center coordinate
    double   center_y;   // imaginary part of center coordinate
    double   zoom;       // pixels per unit in complex plane
    uint32_t max_iter;   // iteration depth cap
};

// Returns a flat row-major pixel buffer (width * height pixels)
std::vector<Pixel> render_mandelbrot(const RenderParams& params);

// Returns iteration count for a single point (exposed for testing)
uint32_t mandelbrot_iter(double cx, double cy, uint32_t max_iter);

} // namespace fractal
