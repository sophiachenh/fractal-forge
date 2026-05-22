load("@rules_python//python:defs.bzl", "py_binary", "py_test")

package(default_visibility = ["//visibility:public"])

py_binary(
    name = "bench",
    srcs = ["bench.py"],
    main = "bench.py",
    python_version = "PY3",
    data = ["//rust/cli:fractal_cli"],
)
