import secrets

# Generate a 32-byte (256-bit) random key
secret_key = secrets.token_urlsafe(32)
print(secret_key)