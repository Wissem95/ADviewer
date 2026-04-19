// Shell Tauri — spawne FastAPI en subprocess puis ouvre la fenêtre.
// SIGTERM envoyé au backend à la fermeture.

use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use tauri::Manager;

fn wait_for_backend(url: &str, max_retries: u32, delay_ms: u64) -> bool {
    for _ in 0..max_retries {
        if let Ok(resp) = ureq::get(url).call() {
            if resp.status() == 200 {
                return true;
            }
        }
        thread::sleep(Duration::from_millis(delay_ms));
    }
    false
}

fn spawn_backend() -> Option<Child> {
    let venv_python = if cfg!(target_os = "windows") {
        "../venv/Scripts/python.exe"
    } else {
        "../venv/bin/python"
    };

    Command::new(venv_python)
        .args([
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ])
        .current_dir("..")
        .spawn()
        .ok()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let backend_clone = Arc::clone(&backend);

    {
        let mut guard = backend.lock().unwrap();
        *guard = spawn_backend();
    }

    let ready = wait_for_backend("http://127.0.0.1:8765/health", 10, 500);
    if !ready {
        eprintln!("[Tauri] FastAPI n'a pas démarré en 5s — vérifiez le backend.");
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_title("LocalCoder IDE v2");
            }
            Ok(())
        })
        .on_window_event(move |_window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let mut guard = backend_clone.lock().unwrap();
                if let Some(child) = guard.as_mut() {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
