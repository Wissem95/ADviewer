// Shell Tauri — spawne FastAPI en subprocess puis ouvre la fenêtre.
// Shutdown : SIGTERM (avec fallback SIGKILL si le process ne termine pas) + wait().

use std::env;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use tauri::Manager;

/// Nom de l'exécutable python dans le venv selon la plateforme.
fn python_exe_name() -> &'static str {
    if cfg!(target_os = "windows") {
        "Scripts/python.exe"
    } else {
        "bin/python"
    }
}

/// Cherche un interpréteur Python dans l'ordre :
/// 1. `$LOCALCODER_PYTHON` (override explicite)
/// 2. `./venv/bin/python` depuis cwd
/// 3. `../venv/bin/python` depuis cwd (cas `cargo tauri dev` lancé depuis `ui/`)
/// 4. `../../venv/bin/python` (bundle `.app` macOS dont le binaire est dans Contents/MacOS/)
/// Retourne (chemin_python, cwd_projet) ou None.
fn locate_python() -> Option<(PathBuf, PathBuf)> {
    if let Ok(custom) = env::var("LOCALCODER_PYTHON") {
        let p = PathBuf::from(&custom);
        if p.exists() {
            let project = p
                .ancestors()
                .nth(3)
                .map(Path::to_path_buf)
                .unwrap_or_else(|| PathBuf::from("."));
            return Some((p, project));
        }
        eprintln!("[Tauri] LOCALCODER_PYTHON={custom} introuvable, fallback sur la recherche.");
    }

    let cwd = env::current_dir().ok()?;
    let candidates = [
        cwd.join("venv").join(python_exe_name()),
        cwd.join("..").join("venv").join(python_exe_name()),
        cwd.join("..").join("..").join("venv").join(python_exe_name()),
    ];
    for candidate in &candidates {
        if candidate.exists() {
            let project = candidate
                .ancestors()
                .nth(3)
                .map(Path::to_path_buf)
                .unwrap_or(cwd.clone());
            return Some((candidate.clone(), project));
        }
    }
    None
}

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
    let (python, project_root) = match locate_python() {
        Some(p) => p,
        None => {
            eprintln!(
                "[Tauri] Backend introuvable. Définissez LOCALCODER_PYTHON=/chemin/vers/venv/bin/python \
                 ou lancez depuis un répertoire contenant venv/."
            );
            return None;
        }
    };

    match Command::new(&python)
        .args([
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ])
        .current_dir(&project_root)
        .spawn()
    {
        Ok(child) => {
            eprintln!(
                "[Tauri] Backend lancé : {} (cwd={})",
                python.display(),
                project_root.display()
            );
            Some(child)
        }
        Err(e) => {
            eprintln!(
                "[Tauri] Échec spawn backend ({}) : {e}. Vérifiez que venv/ contient uvicorn.",
                python.display()
            );
            None
        }
    }
}

/// Demande l'arrêt gracieux du process enfant.
/// Unix : SIGTERM, attend 2s, fallback SIGKILL si toujours vivant. Reap via wait().
/// Windows : Child::kill() (pas d'équivalent SIGTERM natif).
fn shutdown_child(child: &mut Child) {
    #[cfg(unix)]
    {
        let pid = child.id() as i32;
        unsafe {
            libc::kill(pid, libc::SIGTERM);
        }
        for _ in 0..20 {
            match child.try_wait() {
                Ok(Some(_)) => return,
                Ok(None) => thread::sleep(Duration::from_millis(100)),
                Err(_) => break,
            }
        }
    }
    // Soit on est sur Windows, soit SIGTERM n'a pas abouti → SIGKILL + reap.
    let _ = child.kill();
    let _ = child.wait();
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
                    shutdown_child(child);
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
