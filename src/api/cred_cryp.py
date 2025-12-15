from cryptography.fernet import Fernet
import os
import json

def encrypt_credentials(credentials: dict) -> str:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("Encryption key not found")
    fernet = Fernet(key)
    credentials_json = json.dumps(credentials)
    encrypted = fernet.encrypt(credentials_json.encode())
    return encrypted.decode()

def decrypt_credentials(encrypted: str) -> dict:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError("Encryption key not found")
    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted.encode())
    return json.loads(decrypted)

# Test the functions
if __name__ == "__main__":
    # Set the ENCRYPTION_KEY environment variable for testing
    os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()  # Generate a new key for testing
    sample_credentials = {
        "google": {
            "config": {"client_id": "test"},
            "token": {"access_token": "ya29.test", "refresh_token": "test.refresh"}
        }
    }
    print("Original credentials:", sample_credentials)
    encrypted = encrypt_credentials(sample_credentials)
    print("Encrypted:", encrypted)
    decrypted = decrypt_credentials(encrypted)
    print("Decrypted:", decrypted)