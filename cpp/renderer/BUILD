load("@rules_cc//cc:defs.bzl", "cc_library", "cc_binary", "cc_test")

package(default_visibility = ["//visibility:public"])

cc_library(
    name = "renderer",
    srcs = ["renderer.cc"],
    hdrs = ["renderer.h"],
    copts = [
        "-O2",
        "-std=c++17",
        "-Wall",
        "-Wextra",
    ],
)

cc_binary(
    name = "render_cli",
    srcs = ["main.cc"],
    deps = [":renderer"],
    copts = ["-std=c++17"],
)

cc_test(
    name = "renderer_test",
    srcs = ["renderer_test.cc"],
    deps = [":renderer"],
    copts = ["-std=c++17"],
)
