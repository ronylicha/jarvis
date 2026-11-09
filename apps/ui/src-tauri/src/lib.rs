use tauri::Manager;

#[tauri::command]
async fn get_service_status(service: String) -> Result<String, String> {
 let url = format!("http://localhost:{}/health", match service.as_str() {
 "stt" => "8001",
 "tts" => "8002",
 "core" => "8003",
 "memory" => "8004",
 _ => return Err(format!("Unknown service: {}", service)),
 });

 let client = reqwest::Client::new();
 match client.get(&url).send().await {
 Ok(resp) if resp.status().is_success() => {
 let body = resp.text().await.unwrap_or_default();
 Ok(body)
 }
 Ok(resp) => Ok(format!("{{\"status\":\"error\",\"code\":{}}}", resp.status().as_u16())),
 Err(e) => Ok(format!("{{\"status\":\"unreachable\",\"error\":\"{}\"}}", e)),
 }
}

#[tauri::command]
fn get_version() -> String {
 env!("CARGO_PKG_VERSION").to_string()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
 tauri::Builder::default()
 .plugin(tauri_plugin_shell::init())
 .plugin(tauri_plugin_global_shortcut::Builder::new().build())
 .invoke_handler(tauri::generate_handler![get_service_status, get_version])
 .setup(|app| {
 // Register global shortcut Ctrl+Space to toggle window visibility
 use tauri_plugin_global_shortcut::ShortcutState;
 app.handle()
 .plugin(
 tauri_plugin_global_shortcut::Builder::new()
 .with_shortcuts(["CommandOrControl+Space"])
 .unwrap()
 .with_handler(|app, _shortcut, event| {
 if event.state == ShortcutState::Pressed {
 if let Some(window) = app.get_webview_window("main") {
 let _ = window.set_focus();
 }
 }
 })
 .build(),
 )?;
 Ok(())
 })
 .run(tauri::generate_context!())
 .expect("error while running Jarvis");
}