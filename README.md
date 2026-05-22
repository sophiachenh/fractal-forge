# Fractal Forge

A polyglot Mandelbrot renderer built as a Bazel monorepo — the actual project is the **build system**, not the fractal.

```
fractal-forge/
├── cpp/renderer/     # C++ render engine  (cc_library + cc_binary)
├── rust/cli/         # Rust orchestrator  (rust_binary — wraps C++ via subprocess)
├── python/
│   ├── tools/        # Benchmark harness  (py_binary)
│   └── tests/        # Integration tests  (py_test)
└── .github/workflows/ci.yml
```

## Why three languages?

| Component | Language | Why |
|---|---|---|
| Pixel math core | C++ | 10M+ float ops per frame — genuinely needs native speed |
| CLI + benchmark harness | Rust | Safe concurrency, structured JSON output, great CLI ergonomics |
| Orchestration + tests | Python | Fast iteration, easy subprocess orchestration, rich test output |

## Quickstart

```bash
# Build everything
bazel build //...

# Render a frame (outputs PPM to stdout)
bazel run //cpp/renderer:render_cli > out.ppm

# Benchmark via Rust CLI
bazel run //rust/cli:fractal_cli -- bench --runs 5

# Run all tests
bazel test //...

# Python benchmark report
bazel run //python/tools:bench -- --runs 5 --out report.md
```

## Build architecture

```
//cpp/renderer:renderer      ← cc_library (the math)
        ↓ dep
//cpp/renderer:render_cli    ← cc_binary  (PPM writer)
        ↓ data dep
//rust/cli:fractal_cli       ← rust_binary (orchestrator + bench harness)
        ↓ data dep
//python/tools:bench         ← py_binary  (Markdown report generator)
//python/tests:pipeline_test ← py_test    (integration tests)
```

Every layer depends only on the layer below — Bazel enforces this with visibility rules.

## CI

GitHub Actions runs on every push:
1. Restores Bazel cache (incremental builds skip unchanged targets)
2. `bazel build //...`
3. `bazel test //...`
4. Runs benchmark and uploads `bench_report.md` as a CI artifact