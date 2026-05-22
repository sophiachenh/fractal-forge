#include <cstdlib>
#include <iostream>
#include "renderer.h"

// Usage: render_cli [width] [height] [cx] [cy] [zoom] [max_iter] [palette]
// palette: 0=gold  1=blue  2=green  3=red  4=plasma
int main(int argc, char** argv) {
    fractal::RenderParams p{
        .width    = 800,
        .height   = 600,
        .center_x = -0.5,
        .center_y = 0.0,
        .zoom     = 300.0,
        .max_iter = 256,
        .palette  = 1,
    };

    if (argc >= 3) { p.width  = std::atoi(argv[1]); p.height = std::atoi(argv[2]); }
    if (argc >= 5) { p.center_x = std::atof(argv[3]); p.center_y = std::atof(argv[4]); }
    if (argc >= 6) { p.zoom     = std::atof(argv[5]); }
    if (argc >= 7) { p.max_iter = std::atoi(argv[6]); }
    if (argc >= 8) { p.palette  = std::atoi(argv[7]); }

    auto pixels = fractal::render_mandelbrot(p);

    std::cout << "P6\n" << p.width << " " << p.height << "\n255\n";
    for (const auto& px : pixels) {
        std::cout.put(px.r);
        std::cout.put(px.g);
        std::cout.put(px.b);
    }
    return 0;
}
