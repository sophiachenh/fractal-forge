#pragma once

#include <cstdint>
#include <vector>

namespace fractal {

struct Pixel {
    uint8_t r, g, b;
};

struct RenderParams {
    uint32_t width;
    uint32_t height;
    double   center_x;
    double   center_y;
    double   zoom;
    uint32_t max_iter;
    uint32_t palette;   // 0=gold, 1=blue, 2=green, 3=red, 4=plasma
};

std::vector<Pixel> render_mandelbrot(const RenderParams& params);
uint32_t mandelbrot_iter(double cx, double cy, uint32_t max_iter);

} // namespace fractal