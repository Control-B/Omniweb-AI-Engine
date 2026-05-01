import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";

const PREFIX = "enc:v1:";

function key() {
  const secret = process.env.SESSION_SECRET || process.env.OMNIWEB_ENGINE_SHARED_SECRET || "";
  if (!secret) throw new Error("SESSION_SECRET is required for token encryption");
  return createHash("sha256").update(secret).digest();
}

export function encryptToken(value: string | null | undefined) {
  if (!value) return null;
  if (value.startsWith(PREFIX)) return value;

  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key(), iv);
  const encrypted = Buffer.concat([cipher.update(value, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return `${PREFIX}${iv.toString("base64")}:${tag.toString("base64")}:${encrypted.toString("base64")}`;
}

export function decryptToken(value: string | null | undefined) {
  if (!value) return null;
  if (!value.startsWith(PREFIX)) return value;

  const [, ivRaw, tagRaw, encryptedRaw] = value.slice(PREFIX.length).match(/^([^:]+):([^:]+):(.+)$/) || [];
  if (!ivRaw || !tagRaw || !encryptedRaw) throw new Error("Invalid encrypted token format");

  const decipher = createDecipheriv("aes-256-gcm", key(), Buffer.from(ivRaw, "base64"));
  decipher.setAuthTag(Buffer.from(tagRaw, "base64"));
  return Buffer.concat([
    decipher.update(Buffer.from(encryptedRaw, "base64")),
    decipher.final(),
  ]).toString("utf8");
}
