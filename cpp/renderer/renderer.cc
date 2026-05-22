#include "renderer.h"

#include <algorithm>
#include <cmath>

namespace fractal {

// ── Iteration kernel ─────────────────────────────────────────────────────────
uint32_t mandelbrot_iter(double cx, double cy, uint32_t max_iter) {
    double zx = 0.0, zy = 0.0;
    uint32_t i = 0;
    while (i < max_iter && zx * zx + zy * zy <= 4.0) {
        double tmp = zx * zx - zy * zy + cx;
        zy = 2.0 * zx * zy + cy;
        zx = tmp;
        ++i;
    }
    return i;
}

// ── Smooth colouring (histogram not needed for starter) ──────────────────────
static Pixel iter_to_colour(uint32_t iter, uint32_t max_iter) {
    if (iter == max_iter) return {0, 0, 0};   // inside the set → black

    // Normalise to [0, 1) and map to a blue-gold palette
    double t = static_cast<double>(iter) / static_cast<double>(max_iter);
    uint8_t r = static_cast<uint8_t>(9  * (1 - t) * t * t * t * 255);
    uint8_t g = static_cast<uint8_t>(15 * (1 - t) * (1 - t) * t * t * 255);
    uint8_t b = static_cast<uint8_t>(8.5 * (1 - t) * (1 - t) * (1 - t) * t * 255);
    return {r, g, b};
}

// ── Main render ──────────────────────────────────────────────────────────────
std::vector<Pixel> render_mandelbrot(const RenderParams& p) {
    std::vector<Pixel> buf(p.width * p.height);

    for (uint32_t py = 0; py < p.height; ++py) {
        for (uint32_t px = 0; px < p.width; ++px) {
            // Map pixel → complex coordinate
            double cx = p.center_x + (static_cast<double>(px) - p.width  / 2.0) / p.zoom;
            double cy = p.center_y + (static_cast<double>(py) - p.height / 2.0) / p.zoom;

            uint32_t iter = mandelbrot_iter(cx, cy, p.max_iter);
            buf[py * p.width + px] = iter_to_colour(iter, p.max_iter);
        }
    }
    return buf;
}

} // namespace fractal
# updated
