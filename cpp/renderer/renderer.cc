#include "renderer.h"
#include <cmath>

namespace fractal {

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

// Smooth iteration count to remove banding
static double smooth_iter(double cx, double cy, uint32_t max_iter) {
    double zx = 0.0, zy = 0.0;
    uint32_t i = 0;
    while (i < max_iter && zx * zx + zy * zy <= 256.0) {
        double tmp = zx * zx - zy * zy + cx;
        zy = 2.0 * zx * zy + cy;
        zx = tmp;
        ++i;
    }
    if (i == max_iter) return (double)max_iter;
    double log_zn = std::log(zx * zx + zy * zy) / 2.0;
    double nu     = std::log(log_zn / std::log(2.0)) / std::log(2.0);
    return (double)i + 1.0 - nu;
}

// ── Palettes ──────────────────────────────────────────────────────────────────

// 0: gold/orange — warm, high cache hit rate
static Pixel palette_gold(double t) {
    uint8_t r = (uint8_t)(255 * std::pow(t, 0.5));
    uint8_t g = (uint8_t)(255 * std::pow(t, 1.5));
    uint8_t b = (uint8_t)(100 * std::pow(t, 4.0));
    return {r, g, b};
}

// 1: deep blue — cool, moderate cache
static Pixel palette_blue(double t) {
    uint8_t r = (uint8_t)(9   * (1-t) * t * t * t * 255);
    uint8_t g = (uint8_t)(15  * (1-t) * (1-t) * t * t * 255);
    uint8_t b = (uint8_t)(200 * std::pow(t, 0.8));
    return {r, g, b};
}

// 2: green — fresh, healthy build
static Pixel palette_green(double t) {
    uint8_t r = (uint8_t)(30  * std::pow(t, 3.0));
    uint8_t g = (uint8_t)(255 * std::pow(t, 0.6));
    uint8_t b = (uint8_t)(80  * std::pow(t, 2.0));
    return {r, g, b};
}

// 3: red/white — failed build, harsh and bright
static Pixel palette_red(double t) {
    uint8_t r = (uint8_t)(255 * std::pow(t, 0.4));
    uint8_t g = (uint8_t)(40  * std::pow(t, 3.0));
    uint8_t b = (uint8_t)(40  * std::pow(t, 3.0));
    return {r, g, b};
}

// 4: plasma — psychedelic, late night commits
static Pixel palette_plasma(double t) {
    uint8_t r = (uint8_t)(255 * std::abs(std::sin(t * 3.14159 * 2.0)));
    uint8_t g = (uint8_t)(255 * std::abs(std::sin(t * 3.14159 * 2.0 + 2.094)));
    uint8_t b = (uint8_t)(255 * std::abs(std::sin(t * 3.14159 * 2.0 + 4.189)));
    return {r, g, b};
}

static Pixel apply_palette(double t, uint32_t palette) {
    t = std::max(0.0, std::min(t, 1.0));
    switch (palette % 5) {
        case 0: return palette_gold(t);
        case 1: return palette_blue(t);
        case 2: return palette_green(t);
        case 3: return palette_red(t);
        case 4: return palette_plasma(t);
        default: return palette_blue(t);
    }
}

// ── Main render ───────────────────────────────────────────────────────────────

std::vector<Pixel> render_mandelbrot(const RenderParams& p) {
    std::vector<Pixel> buf(p.width * p.height);

    for (uint32_t py = 0; py < p.height; ++py) {
        for (uint32_t px = 0; px < p.width; ++px) {
            double cx = p.center_x + (static_cast<double>(px) - p.width  / 2.0) / p.zoom;
            double cy = p.center_y + (static_cast<double>(py) - p.height / 2.0) / p.zoom;

            double s = smooth_iter(cx, cy, p.max_iter);

            if ((uint32_t)s == p.max_iter) {
                buf[py * p.width + px] = {0, 0, 0};
            } else {
                double t = s / (double)p.max_iter;
                // cycle the palette 3x for more color variation
                t = std::fmod(t * 3.0, 1.0);
                buf[py * p.width + px] = apply_palette(t, p.palette);
            }
        }
    }
    return buf;
}

} // namespace fractal