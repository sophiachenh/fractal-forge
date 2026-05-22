load("@rules_python//python:defs.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_test(
    name = "pipeline_test",
    srcs = ["test_render_pipeline.py"],
    python_version = "PY3",
    main = "test_render_pipeline.py",
    data = [
        "//cpp/renderer:render_cli",
        "//rust/cli:fractal_cli",
    ],
    env = {
        "RENDER_CLI_PATH":  "$(location //cpp/renderer:render_cli)",
        "FRACTAL_CLI_PATH": "$(location //rust/cli:fractal_cli)",
    },
)
