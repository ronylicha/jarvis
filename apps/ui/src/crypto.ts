/**
 * Jarvis Crypto — AES-GCM encryption for API keys stored in localStorage.
 *
 * Keys are encrypted before storage using Web Crypto API.
 * The encryption key is derived from a device-bound secret stored
 * separately in sessionStorage (cleared on browser close).
 *
 * First-run generates a random 256-bit device secret and stores it
 * in sessionStorage. On subsequent loads within the same session,
 * the secret is reused. Across sessions, keys must be re-entered.
 */

const ALGO = 'AES-GCM';
const KEY_BITS = 256;
const IV_LENGTH = 12; // 96 bits for AES-GCM
const SALT = 'jarvis-v1-keyring';

let cachedCryptoKey: CryptoKey | null = null;

async function getDeviceSecret(): Promise<string> {
 let secret = sessionStorage.getItem('jarvis_device_secret');
 if (!secret) {
 // Generate random 256-bit secret for this session
 const bytes = new Uint8Array(32);
 crypto.getRandomValues(bytes);
 secret = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
 sessionStorage.setItem('jarvis_device_secret', secret);
 }
 return secret;
}

async function deriveKey(secret: string): Promise<CryptoKey> {
 if (cachedCryptoKey) return cachedCryptoKey;

 const encoder = new TextEncoder();
 const keyMaterial = await crypto.subtle.importKey(
 'raw',
 encoder.encode(secret),
 'PBKDF2',
 false,
 ['deriveKey']
 );

 cachedCryptoKey = await crypto.subtle.deriveKey(
 {
 name: 'PBKDF2',
 salt: encoder.encode(SALT),
 iterations: 100000,
 hash: 'SHA-256',
 },
 keyMaterial,
 { name: ALGO, length: KEY_BITS },
 false,
 ['encrypt', 'decrypt']
 );

 return cachedCryptoKey;
}

function toBase64(buffer: ArrayBuffer): string {
 return btoa(String.fromCharCode(...new Uint8Array(buffer)));
}

function fromBase64(str: string): Uint8Array {
 return Uint8Array.from(atob(str), c => c.charCodeAt(0));
}

export async function encryptValue(plaintext: string): Promise<string> {
 if (!plaintext) return '';
 const secret = await getDeviceSecret();
 const key = await deriveKey(secret);
 const iv = crypto.getRandomValues(new Uint8Array(IV_LENGTH));
 const encoder = new TextEncoder();

 const encrypted = await crypto.subtle.encrypt(
 { name: ALGO, iv },
 key,
 encoder.encode(plaintext)
 );

 // Store as JSON: { iv: base64, data: base64 }
 return JSON.stringify({
 iv: toBase64(iv.buffer),
 data: toBase64(encrypted),
 });
}

export async function decryptValue(ciphertext: string): Promise<string> {
 if (!ciphertext) return '';

 // Support legacy unencrypted values (plain strings without JSON wrapper)
 if (!ciphertext.startsWith('{')) {
 return ciphertext;
 }

 try {
 const { iv, data } = JSON.parse(ciphertext);
 const secret = await getDeviceSecret();
 const key = await deriveKey(secret);

 const decrypted = await crypto.subtle.decrypt(
 { name: ALGO, iv: fromBase64(iv) },
 key,
 fromBase64(data)
 );

 return new TextDecoder().decode(decrypted);
 } catch {
 // Decryption failed (different session secret) — treat as empty
 return '';
 }
}

/**
 * Encrypt all key values in a record.
 * Empty strings are stored as-is (no encryption needed).
 */
export async function encryptKeys(keys: Record<string, string>): Promise<Record<string, string>> {
 const result: Record<string, string> = {};
 for (const [k, v] of Object.entries(keys)) {
 result[k] = v ? await encryptValue(v) : '';
 }
 return result;
}

/**
 * Decrypt all key values in a record.
 */
export async function decryptKeys(keys: Record<string, string>): Promise<Record<string, string>> {
 const result: Record<string, string> = {};
 for (const [k, v] of Object.entries(keys)) {
 result[k] = await decryptValue(v);
 }
 return result;
}