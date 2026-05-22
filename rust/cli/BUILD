load("@rules_rust//rust:defs.bzl", "rust_binary")

package(default_visibility = ["//visibility:public"])

rust_binary(
    name = "fractal_cli",
    srcs = ["src/main.rs"],
    edition = "2021",
    deps = [
        "@crates//:clap",
        "@crates//:serde",
        "@crates//:serde_json",
    ],
    data = ["//cpp/renderer:render_cli"],
)