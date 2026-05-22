use clap::{Parser, Subcommand};
use serde::{Deserialize, Serialize};
use std::process::Command;
use std::time::{Duration, Instant};

#[derive(Parser)]
#[command(name = "fractal", about = "Fractal Forge — orchestrator & benchmark harness")]
struct Cli {
    #[command(subcommand)]
    command: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Render a single frame via the C++ engine, output as PPM
    Render {
        #[arg(long, default_value = "800")]   width:    u32,
        #[arg(long, default_value = "600")]   height:   u32,
        #[arg(long, default_value = "-0.5")]  cx:       f64,
        #[arg(long, default_value = "0.0")]   cy:       f64,
        #[arg(long, default_value = "300")]   zoom:     f64,
        #[arg(long, default_value = "256")]   max_iter: u32,
        #[arg(long, default_value = "out.ppm")] output: String,
    },
    /// Run N renders and emit benchmark results as JSON
    Bench {
        #[arg(long, default_value = "5")]   runs:   u32,
        #[arg(long, default_value = "800")] width:  u32,
        #[arg(long, default_value = "600")] height: u32,
    },
    /// Print path info — useful for debugging runfiles
    Info,
}

#[derive(Serialize, Deserialize)]
struct BenchResult {
    runs:          u32,
    width:         u32,
    height:        u32,
    timings_ms:    Vec<f64>,
    mean_ms:       f64,
    min_ms:        f64,
    max_ms:        f64,
    mpixels_per_s: f64,
}

/// Find the C++ render_cli binary.
/// When run via `bazel run`, the binary sits next to us in the runfiles tree.
/// We also accept an env override for flexibility.
fn render_cli_path() -> String {
    if let Ok(p) = std::env::var("RENDER_CLI_PATH") {
        return p;
    }
    // When run via `bazel run`, cwd is the runfiles _main directory
    let candidate = std::env::current_dir()
        .unwrap()
        .join("cpp/renderer/render_cli");
    if candidate.exists() {
        return candidate.to_string_lossy().into_owned();
    }
    // Fallback for direct invocation
    "bazel-bin/cpp/renderer/render_cli".to_string()
}

fn run_render(
    width: u32, height: u32,
    cx: f64, cy: f64, zoom: f64, max_iter: u32,
    output: &str,
) -> Duration {
    let start = Instant::now();
    let out_file = std::fs::File::create(output)
        .unwrap_or_else(|e| panic!("cannot create {output}: {e}"));

    let status = Command::new(render_cli_path())
        .args([
            &width.to_string(),    &height.to_string(),
            &cx.to_string(),       &cy.to_string(),
            &zoom.to_string(),     &max_iter.to_string(),
        ])
        .stdout(out_file)
        .status()
        .expect("failed to launch render_cli — run `bazel build //cpp/renderer:render_cli` first");

    assert!(status.success(), "render_cli exited non-zero");
    start.elapsed()
}

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Cmd::Render { width, height, cx, cy, zoom, max_iter, output } => {
            let t = run_render(width, height, cx, cy, zoom, max_iter, &output);
            eprintln!(
                "Rendered {}x{} → {} in {:.1}ms  ({:.1} Mpx/s)",
                width, height, output,
                t.as_secs_f64() * 1000.0,
                (width as f64 * height as f64 / 1e6) / t.as_secs_f64(),
            );
        }

        Cmd::Bench { runs, width, height } => {
            let mut timings: Vec<f64> = Vec::new();
            for i in 0..runs {
                let t = run_render(width, height, -0.5, 0.0, 300.0, 256,
                                   &format!("/tmp/bench_{i}.ppm"));
                let ms = t.as_secs_f64() * 1000.0;
                timings.push(ms);
                eprintln!("  run {}/{}: {:.1}ms", i + 1, runs, ms);
            }

            let mean = timings.iter().sum::<f64>() / timings.len() as f64;
            let min  = timings.iter().cloned().fold(f64::INFINITY,     f64::min);
            let max  = timings.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
            let mpix = (width as f64 * height as f64 / 1e6) / (mean / 1000.0);

            let result = BenchResult {
                runs, width, height, timings_ms: timings,
                mean_ms: mean, min_ms: min, max_ms: max,
                mpixels_per_s: mpix,
            };
            println!("{}", serde_json::to_string_pretty(&result).unwrap());
        }

        Cmd::Info => {
            println!("render_cli path: {}", render_cli_path());
            println!("cwd: {}", std::env::current_dir().unwrap().display());
            println!("fractal-cli version: {}", env!("CARGO_PKG_VERSION"));
        }
    }
}
