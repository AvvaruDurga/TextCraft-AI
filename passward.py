import os
import json
import base64
from PyQt6 import QtWidgets
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.exceptions import InvalidKey


# ====== Helper Functions ======
def generate_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt,
        iterations=390000, backend=default_backend()
    )
    return kdf.derive(password.encode())


def encrypt_data(data: bytes, key: bytes) -> tuple:
    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    return encrypted, iv


def decrypt_data(encrypted: bytes, key: bytes, iv: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    decrypted_padded = decryptor.update(encrypted) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(decrypted_padded) + unpadder.finalize()


def generate_recovery_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8')


# ====== Main App ======
class FileEncryptorApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secure File Encryptor")
        self.resize(400, 200)

        layout = QtWidgets.QVBoxLayout()

        self.encrypt_button = QtWidgets.QPushButton("Encrypt File")
        self.decrypt_button = QtWidgets.QPushButton("Decrypt File")

        layout.addWidget(self.encrypt_button)
        layout.addWidget(self.decrypt_button)

        self.encrypt_button.clicked.connect(self.encrypt_file)
        self.decrypt_button.clicked.connect(self.decrypt_file)

        self.setLayout(layout)

    def encrypt_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select File to Encrypt")
        if not file_path:
            return

        password, ok = QtWidgets.QInputDialog.getText(self, "Set Password", "Enter a password:", QtWidgets.QLineEdit.EchoMode.Password)
        if not ok or not password:
            return

        with open(file_path, 'rb') as f:
            data = f.read()

        salt = os.urandom(16)
        key = generate_key(password, salt)
        encrypted, iv = encrypt_data(data, key)

        recovery_key = generate_recovery_key()
        recovery_salt = os.urandom(16)
        recovery_key_bytes = generate_key(recovery_key, recovery_salt)
        # Encrypt original key using recovery key
        recovery_cipher = Cipher(algorithms.AES(recovery_key_bytes), modes.CBC(iv))
        encryptor = recovery_cipher.encryptor()
        padded_key = padding.PKCS7(128).padder().update(key) + padding.PKCS7(128).padder().finalize()
        encrypted_key = encryptor.update(padded_key) + encryptor.finalize()

        out_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Encrypted File", filter="Encrypted Files (*.enc)")
        if not out_path:
            return

        with open(out_path, 'wb') as f:
            file_content = {
                'salt': base64.b64encode(salt).decode(),
                'iv': base64.b64encode(iv).decode(),
                'encrypted_data': base64.b64encode(encrypted).decode(),
                'recovery': {
                    'salt': base64.b64encode(recovery_salt).decode(),
                    'encrypted_key': base64.b64encode(encrypted_key).decode()
                }
            }
            f.write(json.dumps(file_content).encode())

        QtWidgets.QMessageBox.information(self, "Success", f"File encrypted!\n\nRecovery Key:\n{recovery_key}\n\nSave it safely!")

    def decrypt_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Encrypted File", filter="Encrypted Files (*.enc)")
        if not file_path:
            return

        with open(file_path, 'rb') as f:
            content = json.loads(f.read().decode())

        salt = base64.b64decode(content['salt'])
        iv = base64.b64decode(content['iv'])
        encrypted_data = base64.b64decode(content['encrypted_data'])

        method, ok = QtWidgets.QInputDialog.getItem(self, "Decryption Method", "Use:", ["Password", "Recovery Key"], editable=False)
        if not ok:
            return

        if method == "Password":
            password, ok = QtWidgets.QInputDialog.getText(self, "Enter Password", "Password:", QtWidgets.QLineEdit.EchoMode.Password)
            if not ok:
                return
            try:
                key = generate_key(password, salt)
                decrypted = decrypt_data(encrypted_data, key, iv)
            except Exception:
                QtWidgets.QMessageBox.critical(self, "Error", "Wrong password or corrupted file.")
                return
        else:
            recovery_key, ok = QtWidgets.QInputDialog.getText(self, "Enter Recovery Key", "Recovery Key:", QtWidgets.QLineEdit.EchoMode.Normal)
            if not ok:
                return
            try:
                recovery_salt = base64.b64decode(content['recovery']['salt'])
                encrypted_key = base64.b64decode(content['recovery']['encrypted_key'])
                recovery_key_bytes = generate_key(recovery_key, recovery_salt)

                cipher = Cipher(algorithms.AES(recovery_key_bytes), modes.CBC(iv))
                decryptor = cipher.decryptor()
                padded_key = decryptor.update(encrypted_key) + decryptor.finalize()
                key = padding.PKCS7(128).unpadder().update(padded_key) + padding.PKCS7(128).unpadder().finalize()
                decrypted = decrypt_data(encrypted_data, key, iv)
            except Exception:
                QtWidgets.QMessageBox.critical(self, "Error", "Invalid recovery key or file corrupted.")
                return

        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Decrypted File")
        if save_path:
            with open(save_path, 'wb') as f:
                f.write(decrypted)
            QtWidgets.QMessageBox.information(self, "Success", "File decrypted successfully!")


# ====== Run the App ======
if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = FileEncryptorApp()
    window.show()
    sys.exit(app.exec())
